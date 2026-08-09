from __future__ import annotations

import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from packages.deployment_runtime import (
    BackupRuntime,
    ArtifactBackupRuntime,
    MigrationRuntime,
    ReleaseRuntime,
    check_readiness,
    create_release_manifest,
    observability_tick,
    scheduler_tick,
)
from packages.deployment_runtime.heartbeat_probe import process_heartbeat_ready
from packages.deployment_runtime.processes import _worker_heartbeat_loop
from packages.execution_runtime import ExecutionRuntimeService, ExecutionRuntimeServiceConfig
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, SchemaNotReadyError, create_persistence_client


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(name="deployment-test", mode="test_harness", database_url=f"sqlite:///{tmp_path / 'deployment.sqlite3'}", local_storage_root_dir=str(tmp_path / "storage"))
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def test_release_identity_transitions_and_single_production_release(tmp_path: Path):
    persistence = _persistence(tmp_path)
    runtime = ReleaseRuntime(store=persistence.deployments)
    one = create_release_manifest(version="1.2.3", git_sha="a" * 40, image_digest="sha256:" + "1" * 64, configuration={"queue": "main", "api_token": "first"}, built_at_ms=1)
    same_identity = create_release_manifest(version="1.2.3", git_sha="a" * 40, image_digest="sha256:" + "1" * 64, configuration={"queue": "main", "api_token": "different"}, built_at_ms=1)
    assert one.configuration_fingerprint == same_identity.configuration_fingerprint
    assert "first" not in one.model_dump_json()
    runtime.register(one)
    runtime.transition(one.release_id, "staging")
    assert runtime.transition(one.release_id, "production")["status"] == "production"

    two = create_release_manifest(version="1.2.4", git_sha="b" * 40, image_digest="sha256:" + "2" * 64, built_at_ms=2)
    runtime.register(two)
    runtime.transition(two.release_id, "staging")
    runtime.transition(two.release_id, "production")
    assert persistence.deployments.get_release(one.release_id)["status"] == "rolled_back"
    assert len(persistence.deployments.list_releases(status="production")) == 1
    with pytest.raises(ValueError, match="Invalid release transition"):
        runtime.transition(one.release_id, "production")


def test_release_promotion_rejects_dirty_or_mutable_provenance(tmp_path: Path):
    persistence = _persistence(tmp_path)
    runtime = ReleaseRuntime(store=persistence.deployments)
    dirty = create_release_manifest(version="1.2.3-rc.1", git_sha="c" * 40, image_digest="sha256:" + "3" * 64, source_state="dirty")
    runtime.register(dirty)
    runtime.transition(dirty.release_id, "staging")
    with pytest.raises(ValueError, match="clean committed"):
        runtime.transition(dirty.release_id, "production")

    with pytest.raises(ValueError, match="semantic versioning"):
        create_release_manifest(version="release-1", git_sha="d" * 40, image_digest="sha256:" + "4" * 64)
    with pytest.raises(ValueError, match="40-character"):
        create_release_manifest(version="1.2.3", git_sha="abcdef1", image_digest="sha256:" + "4" * 64)
    with pytest.raises(ValueError, match="immutable sha256"):
        create_release_manifest(version="1.2.3", git_sha="d" * 40, image_digest="latest")


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
    assert runtime.head() == "202608090200"


def test_migration_adoption_rejects_incomplete_unversioned_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'incomplete.sqlite3'}")
    with pytest.raises(RuntimeError, match="incomplete baseline"):
        MigrationRuntime().adopt_existing(engine)


def test_production_provider_rejects_unmigrated_database(tmp_path: Path):
    profile = PersistenceProfile(name="production-fail-closed", mode="supabase_postgres", database_url=f"sqlite:///{tmp_path / 'unmigrated.sqlite3'}")
    with pytest.raises(ValueError, match="requires a PostgreSQL"):
        create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
