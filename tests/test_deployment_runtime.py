from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from packages.deployment_runtime import (
    BackupRuntime,
    ArtifactBackupRuntime,
    CANARY_REQUIRED_GATES,
    MigrationRuntime,
    ReleaseRuntime,
    check_readiness,
    create_release_manifest,
    observability_tick,
    scheduler_tick,
)
from packages.deployment_runtime.heartbeat_probe import local_heartbeat_ready, process_heartbeat_ready
from packages.deployment_runtime.processes import _heartbeat, _worker_heartbeat_loop
from packages.execution_runtime import ExecutionRuntimeService, ExecutionRuntimeServiceConfig
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(name="deployment-test", mode="test_harness", database_url=f"sqlite:///{tmp_path / 'deployment.sqlite3'}", local_storage_root_dir=str(tmp_path / "storage"))
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _record_promotion_gates(runtime: ReleaseRuntime, release_id: str, *, observed_at_ms: int = 1_000) -> None:
    observed_at_ms = int(time.time() * 1000)
    release = runtime.store.get_release(release_id)
    manifest = dict(release["manifest"])
    for gate in CANARY_REQUIRED_GATES:
        details = _valid_gate_details(gate, release_id=release_id, manifest=manifest)
        expires_at_ms = observed_at_ms + 3_600_000 if gate in {
            "staging_readiness", "process_health", "slo",
        } else observed_at_ms + 86_400_000 if gate in {
            "production_qualification", "usage_cost",
        } else 0
        runtime.gates.record(
            release_id=release_id, gate=gate, status="passed", source="test-suite",
            observed_at_ms=observed_at_ms, expires_at_ms=expires_at_ms, details=details,
        )
    runtime.gates.record(
        release_id=release_id, gate="canary", status="passed", source="test-suite",
        observed_at_ms=observed_at_ms + 1, expires_at_ms=observed_at_ms + 3_600_000,
        details={
            "release_id": release_id, "sample_count": 1, "failure_count": 0,
            "slo_breach_count": 0, "rollback_trigger_tested": True,
        },
    )


def _valid_gate_details(gate: str, *, release_id: str, manifest: dict) -> dict:
    digest = "sha256:" + "9" * 64
    return {
        "ci": {
            "git_sha": manifest["git_sha"], "backend_tests_passed": True,
            "frontend_tests_passed": True, "containers_built": True,
            "architecture_boundaries_passed": True, "secret_scan_passed": True,
        },
        "database_recovery": {
            "backup_sha256": "a" * 64, "restored_schema_revision": manifest["schema_revision"],
            "table_counts_match": True,
        },
        "artifact_recovery": {"archive_sha256": "b" * 64, "checksums_verified": True, "object_count": 1},
        "migration": {
            "current_revision": manifest["schema_revision"], "head_revision": manifest["schema_revision"],
            "rollback_reupgrade_tested": True,
        },
        "staging_readiness": {"ready": True, "release_id": release_id},
        "process_health": {"ready_roles": ["worker", "scheduler", "observability"], "release_id": release_id},
        "production_qualification": {
            "accepted": True, "release_id": release_id, "run_id": "qualification-run",
            "source_sha256": "c" * 64,
        },
        "usage_cost": {"charge_count": 1, "unpriced_charge_count": 0, "reconciled": True},
        "slo": {"evaluation_count": 6, "breached_count": 0, "insufficient_data_count": 0},
        "rollback": {
            "rollback_release_id": "release-prior", "runtime_digest": digest,
            "dashboard_digest": digest, "restore_tested": True,
        },
    }[gate]


def test_release_identity_transitions_and_single_production_release(tmp_path: Path):
    persistence = _persistence(tmp_path)
    runtime = ReleaseRuntime(store=persistence.deployments)
    components_one = {"runtime": "sha256:" + "1" * 64, "dashboard": "sha256:" + "2" * 64}
    one = create_release_manifest(version="1.2.3", git_sha="a" * 40, image_digest="sha256:" + "1" * 64, components=components_one, configuration={"queue": "main", "api_token": "first"}, built_at_ms=1)
    same_identity = create_release_manifest(version="1.2.3", git_sha="a" * 40, image_digest="sha256:" + "1" * 64, components=components_one, configuration={"queue": "main", "api_token": "different"}, built_at_ms=1)
    assert one.configuration_fingerprint == same_identity.configuration_fingerprint
    assert "first" not in one.model_dump_json()
    runtime.register(one)
    runtime.transition(one.release_id, "staging")
    _record_promotion_gates(runtime, one.release_id)
    assert runtime.transition(one.release_id, "canary")["status"] == "canary"
    assert runtime.transition(one.release_id, "production")["status"] == "production"

    two = create_release_manifest(version="1.2.4", git_sha="b" * 40, image_digest="sha256:" + "3" * 64, components={"runtime": "sha256:" + "3" * 64, "dashboard": "sha256:" + "4" * 64}, built_at_ms=2)
    runtime.register(two)
    runtime.transition(two.release_id, "staging")
    _record_promotion_gates(runtime, two.release_id)
    runtime.transition(two.release_id, "canary")
    runtime.transition(two.release_id, "production")
    assert persistence.deployments.get_release(one.release_id)["status"] == "rolled_back"
    assert len(persistence.deployments.list_releases(status="production")) == 1
    with pytest.raises(ValueError, match="Invalid release transition"):
        runtime.transition(one.release_id, "production")


def test_release_promotion_rejects_dirty_or_mutable_provenance(tmp_path: Path):
    persistence = _persistence(tmp_path)
    runtime = ReleaseRuntime(store=persistence.deployments)
    dirty = create_release_manifest(version="1.2.3-rc.1", git_sha="c" * 40, image_digest="sha256:" + "3" * 64, source_state="dirty", components={"runtime": "sha256:" + "3" * 64, "dashboard": "sha256:" + "4" * 64})
    runtime.register(dirty)
    runtime.transition(dirty.release_id, "staging")
    with pytest.raises(ValueError, match="clean committed"):
        runtime.transition(dirty.release_id, "canary")

    with pytest.raises(ValueError, match="semantic versioning"):
        create_release_manifest(version="release-1", git_sha="d" * 40, image_digest="sha256:" + "4" * 64)
    with pytest.raises(ValueError, match="40-character"):
        create_release_manifest(version="1.2.3", git_sha="abcdef1", image_digest="sha256:" + "4" * 64)
    with pytest.raises(ValueError, match="immutable sha256"):
        create_release_manifest(version="1.2.3", git_sha="d" * 40, image_digest="latest")
    incomplete = create_release_manifest(
        version="1.2.4-rc.1", git_sha="f" * 40, image_digest="sha256:" + "7" * 64,
    )
    runtime.register(incomplete)
    runtime.transition(incomplete.release_id, "staging")
    with pytest.raises(ValueError, match="runtime and dashboard"):
        runtime.transition(incomplete.release_id, "canary")


def test_release_gates_fail_closed_for_missing_expired_and_latest_failed_evidence(tmp_path: Path):
    persistence = _persistence(tmp_path)
    runtime = ReleaseRuntime(store=persistence.deployments)
    manifest = create_release_manifest(
        version="2.0.0-rc.1", git_sha="e" * 40, image_digest="sha256:" + "5" * 64,
        components={"runtime": "sha256:" + "5" * 64, "dashboard": "sha256:" + "6" * 64}, built_at_ms=1,
    )
    runtime.register(manifest)
    runtime.transition(manifest.release_id, "staging")
    missing = runtime.gates.evaluate(release_id=manifest.release_id, target="canary", now_ms=2_000)
    assert missing.eligible is False
    assert all(check.status == "missing" for check in missing.checks)

    release = persistence.deployments.get_release(manifest.release_id)
    for gate in CANARY_REQUIRED_GATES:
        runtime.gates.record(
            release_id=manifest.release_id, gate=gate, status="passed", source="test-suite",
            observed_at_ms=1_000, expires_at_ms=1_500,
            details=_valid_gate_details(gate, release_id=manifest.release_id, manifest=release["manifest"]),
        )
    expired = runtime.gates.evaluate(release_id=manifest.release_id, target="canary", now_ms=2_000)
    assert expired.eligible is False
    assert all(check.status == "expired" for check in expired.checks)

    runtime.gates.record(
        release_id=manifest.release_id, gate="ci", status="failed", source="test-suite",
        observed_at_ms=3_000, details={"api_token": "must-not-persist", "reason": "regression"},
    )
    rows = persistence.deployments.list_release_gate_evidence(release_id=manifest.release_id, gate="ci")
    assert rows[0]["details"]["api_token"] == "[redacted]"
    decision = runtime.gates.evaluate(release_id=manifest.release_id, target="canary", now_ms=3_100)
    assert next(check for check in decision.checks if check.gate == "ci").status == "failed"
    with pytest.raises(ValueError, match="not eligible"):
        runtime.transition(manifest.release_id, "canary")


def test_scheduler_and_observability_roles_persist_metrics_and_heartbeats(tmp_path: Path):
    service = ExecutionRuntimeService(config=ExecutionRuntimeServiceConfig(
        persistence_mode="test_harness", database_url=f"sqlite:///{tmp_path / 'roles.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"), global_limit=1, per_series_limit=1,
    ))
    scheduler = scheduler_tick(service, process_id="scheduler-1", release_id="release-test", now_ms=100_000)
    assert scheduler.status == "ok" and scheduler.details["queue_depth"] == 0
    assert service.persistence.observability.list(name="queue.depth")[0]["value"] == 0
    observer = observability_tick(service, process_id="observer-1", release_id="release-test", now_ms=200_000_000)
    assert observer.status == "ok"
    roles = {row["role"] for row in service.persistence.deployments.list_heartbeats()}
    assert roles == {"scheduler", "observability"}


def test_lightweight_heartbeat_probe_uses_bounded_direct_postgres_query() -> None:
    calls: dict[str, object] = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, parameters):
            calls["query"] = query
            calls["parameters"] = parameters

        def fetchone(self):
            return (True,)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return Cursor()

    def connect(**kwargs):
        calls["connect"] = kwargs
        return Connection()

    ready = process_heartbeat_ready(
        role="worker",
        release_id="release-test",
        database_url="postgresql+psycopg://saga:secret@db.example:5432/saga?sslmode=require",
        max_age_seconds=120,
        now_ms=500_000,
        connector=connect,
    )

    assert ready is True
    assert calls["connect"]["connect_timeout"] == 3
    assert calls["connect"]["prepare_threshold"] is None
    assert calls["parameters"] == ("worker", 380_000, "release-test", "release-test")


def test_local_heartbeat_probe_reads_marker_written_after_durable_heartbeat(tmp_path: Path, monkeypatch) -> None:
    writes: list[dict[str, object]] = []

    class Deployments:
        def heartbeat(self, payload):
            writes.append(payload)

    monkeypatch.setenv("SAGA_LOCAL_HEARTBEAT_DIR", str(tmp_path))
    persistence = type("Persistence", (), {"deployments": Deployments()})()
    _heartbeat(persistence, "worker-1", "worker", "release-test", "ready", 500_000, {"state": "running"})

    assert writes
    assert local_heartbeat_ready(
        role="worker",
        release_id="release-test",
        max_age_seconds=120,
        heartbeat_dir=str(tmp_path),
        now_ms=550_000,
    )
    assert not local_heartbeat_ready(
        role="worker",
        release_id="another-release",
        max_age_seconds=120,
        heartbeat_dir=str(tmp_path),
        now_ms=550_000,
    )


def test_worker_heartbeat_loop_updates_while_job_is_running() -> None:
    stop = threading.Event()
    writes: list[dict[str, object]] = []

    class Deployments:
        def heartbeat(self, payload):
            writes.append(payload)
            stop.set()

    persistence = type("Persistence", (), {"deployments": Deployments()})()
    _worker_heartbeat_loop(persistence, "worker-1", "release-test", stop, 0.01)

    assert len(writes) == 1
    assert writes[0]["metadata"] == {"state": "running"}


def test_readiness_fails_closed_for_degraded_dependency(tmp_path: Path):
    persistence = _persistence(tmp_path)
    ready = check_readiness(persistence=persistence, service="test")
    assert ready.ready is True and ready.schema_revision == "test_harness"
    degraded = check_readiness(persistence=persistence, service="test", extra_probes={"modal": lambda: (_ for _ in ()).throw(TimeoutError("slow"))})
    assert degraded.ready is False
    assert degraded.dependencies[-1].status == "degraded"
    assert "TimeoutError" in degraded.dependencies[-1].detail


def test_backup_commands_keep_password_out_of_arguments_and_require_confirmation(tmp_path: Path):
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        output = next((item.split("=", 1)[1] for item in command if item.startswith("--file=")), "")
        if output:
            Path(output).write_bytes(b"backup")
    runtime = BackupRuntime(runner=runner)
    url = "postgresql+psycopg://saga:very-secret@db.example:5432/saga_test"
    manifest = runtime.create(database_url=url, output_path=tmp_path / "backup.dump", release_id="release-test")
    assert manifest["size_bytes"] == 6
    assert "very-secret" not in " ".join(calls[0][0])
    assert "--schema=public" in calls[0][0]
    assert calls[0][1]["env"]["PGPASSWORD"] == "very-secret"
    with pytest.raises(ValueError, match="exactly match"):
        runtime.restore(database_url=url, backup_path=tmp_path / "backup.dump", confirm_target="wrong")
    assert runtime.restore(database_url=url, backup_path=tmp_path / "backup.dump", confirm_target="saga_test")["restored"] is True
    assert calls[-2][0][0] == "psql"
    assert "--command=CREATE EXTENSION IF NOT EXISTS vector;" in calls[-2][0]
    assert "--schema=public" in calls[-1][0]


def test_artifact_backup_round_trip_uses_storage_contract(tmp_path: Path):
    source = _persistence(tmp_path / "source")
    source.objects.ensure_bucket("renders")
    source.objects.upload_bytes("renders", "books/one/image.bin", b"render-bytes", content_type="image/png")
    archive = tmp_path / "artifacts.zip"
    created = ArtifactBackupRuntime(object_store=source.objects).create(bucket_names=["renders"], output_path=archive)
    assert created["object_count"] == 1

    target = _persistence(tmp_path / "target")
    with pytest.raises(ValueError, match="exactly match"):
        ArtifactBackupRuntime(object_store=target.objects).restore(backup_path=archive, confirm_target="wrong")
    restored = ArtifactBackupRuntime(object_store=target.objects).restore(backup_path=archive, confirm_target="artifact-storage")
    assert restored["object_count"] == 1
    assert target.objects.download_bytes("renders", "books/one/image.bin") == b"render-bytes"


def test_migration_runtime_has_one_expected_head():
    runtime = MigrationRuntime()
    assert runtime.head() == "202608120100"


def test_migration_adoption_rejects_incomplete_unversioned_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'incomplete.sqlite3'}")
    with pytest.raises(RuntimeError, match="incomplete baseline"):
        MigrationRuntime().adopt_existing(engine)


def test_production_provider_rejects_unmigrated_database(tmp_path: Path):
    profile = PersistenceProfile(name="production-fail-closed", mode="supabase_postgres", database_url=f"sqlite:///{tmp_path / 'unmigrated.sqlite3'}")
    with pytest.raises(ValueError, match="requires a PostgreSQL"):
        create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
