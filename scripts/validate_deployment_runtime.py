"""Bounded PostgreSQL validation for release integrity and deployment readiness."""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from packages.deployment_runtime import (
    CANARY_REQUIRED_GATES,
    ReleaseRuntime,
    check_readiness,
    create_deployment_persistence_client,
    create_release_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default=f"validation-{int(time.time())}")
    args = parser.parse_args()
    persistence = create_deployment_persistence_client()
    runtime = ReleaseRuntime(store=persistence.deployments)
    releases = []
    for index in range(2):
        manifest = create_release_manifest(
            version=f"0.0.0-validation.{int(time.time())}.{index}",
            git_sha=f"{index + 1:040x}",
            image_digest=f"sha256:{index + 1:064x}",
            components={
                "runtime": f"sha256:{index + 1:064x}",
                "dashboard": f"sha256:{index + 11:064x}",
            },
        )
        runtime.register(manifest)
        runtime.transition(manifest.release_id, "staging")
        observed_at_ms = int(time.time() * 1000)
        for gate in CANARY_REQUIRED_GATES:
            expires_at_ms = observed_at_ms + 3_600_000 if gate in {
                "staging_readiness", "process_health", "slo",
            } else observed_at_ms + 86_400_000 if gate in {
                "production_qualification", "usage_cost",
            } else 0
            runtime.gates.record(
                release_id=manifest.release_id, gate=gate, status="passed", source="deployment-validation",
                observed_at_ms=observed_at_ms, expires_at_ms=expires_at_ms,
                details=_gate_details(gate, release_id=manifest.release_id, manifest=manifest.model_dump()),
            )
        runtime.transition(manifest.release_id, "canary")
        runtime.gates.record(
            release_id=manifest.release_id, gate="canary", status="passed", source="deployment-validation",
            observed_at_ms=observed_at_ms + 1, expires_at_ms=observed_at_ms + 3_600_000,
            details={
                "release_id": manifest.release_id, "sample_count": 1, "failure_count": 0,
                "slo_breach_count": 0, "rollback_trigger_tested": True,
            },
        )
        releases.append(manifest.release_id)

    barrier = threading.Barrier(2)

    def promote(release_id: str) -> str:
        barrier.wait(timeout=10)
        return str(runtime.transition(release_id, "production")["status"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(promote, releases))
    production = persistence.deployments.list_releases(status="production", limit=100)
    selected = [item for item in production if item["release_id"] in releases]
    readiness = check_readiness(persistence=persistence, service="deployment-validation")
    result = {
        "ready": readiness.ready and statuses == ["production", "production"] and len(selected) == 1,
        "schema_revision": readiness.schema_revision,
        "promotion_results": statuses,
        "validation_production_count": len(selected),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 2


def _gate_details(gate: str, *, release_id: str, manifest: dict) -> dict:
    digest = "sha256:" + "f" * 64
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
            "accepted": True, "release_id": release_id, "run_id": "deployment-validation",
            "source_sha256": "c" * 64,
        },
        "usage_cost": {"charge_count": 1, "unpriced_charge_count": 0, "reconciled": True},
        "slo": {"evaluation_count": 1, "breached_count": 0, "insufficient_data_count": 0},
        "rollback": {
            "rollback_release_id": "release-validation-prior", "runtime_digest": digest,
            "dashboard_digest": digest, "restore_tested": True,
        },
    }[gate]


if __name__ == "__main__":
    raise SystemExit(main())
