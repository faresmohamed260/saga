from __future__ import annotations

from pathlib import Path

import pytest

from packages.deployment_runtime import (
    ReadinessReport,
    ReleaseRuntime,
    create_release_candidate,
    verify_release_candidate,
)
from packages.deployment_runtime.evidence import record_staging_runtime_evidence
from packages.deployment_runtime.source_integrity import scan_source_files
from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    create_persistence_client,
)
from packages.qualification_runtime import ProductionQualificationReport


def test_release_candidate_is_deterministic_and_secret_safe() -> None:
    kwargs = {
        "version": "2.0.0-rc.1",
        "git_sha": "a" * 40,
        "runtime_digest": "sha256:" + "1" * 64,
        "dashboard_digest": "sha256:" + "2" * 64,
        "configuration": {"queue": "staging", "api_token": "must-not-appear"},
        "created_at_ms": 1_000,
    }
    first = create_release_candidate(**kwargs)
    second = create_release_candidate(**kwargs)

    assert first == second
    assert first.manifest.release_id == "release-2.0.0-rc.1-aaaaaaaaaaaa"
    assert first.manifest.components == {
        "runtime": "sha256:" + "1" * 64,
        "dashboard": "sha256:" + "2" * 64,
    }
    assert "must-not-appear" not in first.model_dump_json()
    assert first.production_required_gates[-1] == "canary"
    assert verify_release_candidate(first) == first

    tampered = first.model_dump()
    tampered["manifest"]["version"] = "9.9.9"
    with pytest.raises(ValueError, match="integrity"):
        verify_release_candidate(tampered)


def test_release_candidate_rejects_dirty_source() -> None:
    with pytest.raises(ValueError, match="clean committed"):
        create_release_candidate(
            version="2.0.0-rc.1", git_sha="a" * 40,
            runtime_digest="sha256:" + "1" * 64,
            dashboard_digest="sha256:" + "2" * 64,
            source_state="dirty",
        )


def test_source_secret_scan_reports_location_without_value(tmp_path: Path) -> None:
    safe = tmp_path / "safe.py"
    unsafe = tmp_path / "unsafe.env"
    safe.write_text("TOKEN = 'inject-at-deploy-time'\n", encoding="utf-8")
    synthetic_token = "hf_" + ("a" * 32)
    unsafe.write_text(f"HF_TOKEN={synthetic_token}\n", encoding="utf-8")

    findings = scan_source_files(tmp_path, ["safe.py", "unsafe.env"])

    assert findings == [{"path": "unsafe.env", "line": 1, "kind": "hugging_face_token"}]
    assert synthetic_token not in str(findings)


def test_staging_collector_records_release_bound_runtime_evidence(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="release-evidence-test", mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'release.sqlite3'}",
    )
    persistence = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    persistence.initialize()
    candidate = create_release_candidate(
        version="2.0.0-rc.2", git_sha="d" * 40,
        runtime_digest="sha256:" + "3" * 64, dashboard_digest="sha256:" + "4" * 64,
        created_at_ms=1_000,
    )
    ReleaseRuntime(store=persistence.deployments).register(candidate.manifest)
    now_ms = 1_000_000
    for role in ("worker", "scheduler", "observability"):
        persistence.deployments.heartbeat({
            "process_id": f"{role}-1", "role": role, "release_id": candidate.manifest.release_id,
            "status": "ready", "last_seen_ms": now_ms,
        })
    report = ProductionQualificationReport(
        report_id="qualification-1", run_id="run-1", series_id="series-1", source_path="book.epub",
        source_sha256="a" * 64, release_id=candidate.manifest.release_id, accepted=True,
        artifact_reference={"bucket": "runtime-reports", "path": "qualification-1.json"},
    )

    evidence = record_staging_runtime_evidence(
        store=persistence.deployments,
        release_id=candidate.manifest.release_id,
        qualification=report,
        readiness=ReadinessReport(
            ready=True, service="staging", release_id=candidate.manifest.release_id,
            schema_revision="test_harness",
        ),
        usage_summary={"charge_count": 3, "unpriced_charge_count": 0, "reconciled": True},
        slo_evaluations=[{"status": "healthy"}, {"status": "healthy"}],
        now_ms=now_ms,
    )

    assert len(evidence) == 5
    assert all(row["status"] == "passed" for row in evidence)
    assert {row["gate"] for row in evidence} == {
        "staging_readiness", "process_health", "production_qualification", "usage_cost", "slo",
    }
