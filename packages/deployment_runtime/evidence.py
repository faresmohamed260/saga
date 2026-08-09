"""Derive staging release evidence from normalized runtime contracts."""

from __future__ import annotations

import time
from typing import Any

from packages.deployment_runtime.contracts import ReadinessReport
from packages.deployment_runtime.gates import ReleaseGateRuntime
from packages.qualification_runtime import ProductionQualificationReport


def record_staging_runtime_evidence(
    *,
    store,
    release_id: str,
    qualification: ProductionQualificationReport,
    readiness: ReadinessReport,
    usage_summary: dict[str, Any],
    slo_evaluations: list[dict[str, Any]],
    now_ms: int | None = None,
    heartbeat_max_age_seconds: int = 180,
) -> list[dict[str, Any]]:
    observed = int(now_ms or time.time() * 1000)
    runtime = ReleaseGateRuntime(store=store)
    rows: list[dict[str, Any]] = []

    rows.append(_record(
        runtime, release_id=release_id, gate="staging_readiness", observed=observed,
        ttl_ms=3_600_000,
        passed=readiness.ready and readiness.release_id == release_id,
        details={"ready": readiness.ready, "release_id": readiness.release_id},
        reason="Staging dependency readiness did not match the release.",
    ))

    since_ms = observed - max(1, int(heartbeat_max_age_seconds)) * 1000
    heartbeats = store.list_heartbeats(since_ms=since_ms, limit=1000)
    ready_roles = sorted({
        str(row.get("role") or "") for row in heartbeats
        if row.get("status") == "ready" and row.get("release_id") == release_id
    })
    rows.append(_record(
        runtime, release_id=release_id, gate="process_health", observed=observed,
        ttl_ms=3_600_000,
        passed={"worker", "scheduler", "observability"}.issubset(set(ready_roles)),
        details={"ready_roles": ready_roles, "release_id": release_id},
        reason="Required release-scoped process heartbeats were missing.",
    ))

    rows.append(_record(
        runtime, release_id=release_id, gate="production_qualification", observed=observed,
        ttl_ms=86_400_000,
        passed=qualification.accepted and qualification.release_id == release_id,
        details={
            "accepted": qualification.accepted, "release_id": qualification.release_id,
            "run_id": qualification.run_id, "source_sha256": qualification.source_sha256,
        },
        artifact_reference=qualification.artifact_reference,
        reason="Real-book production qualification was not accepted for this release.",
    ))

    usage_passed = (
        int(usage_summary.get("charge_count") or 0) > 0
        and int(usage_summary.get("unpriced_charge_count") or 0) == 0
        and bool(usage_summary.get("reconciled", True))
    )
    rows.append(_record(
        runtime, release_id=release_id, gate="usage_cost", observed=observed,
        ttl_ms=86_400_000,
        passed=usage_passed,
        details={
            "charge_count": int(usage_summary.get("charge_count") or 0),
            "unpriced_charge_count": int(usage_summary.get("unpriced_charge_count") or 0),
            "reconciled": bool(usage_summary.get("reconciled", True)),
        },
        reason="Provider usage was absent, unpriced, or unreconciled.",
    ))

    statuses = [str(item.get("status") or "") for item in slo_evaluations]
    rows.append(_record(
        runtime, release_id=release_id, gate="slo", observed=observed,
        ttl_ms=3_600_000,
        passed=bool(statuses) and all(status == "healthy" for status in statuses),
        details={
            "evaluation_count": len(statuses),
            "breached_count": statuses.count("breached"),
            "insufficient_data_count": statuses.count("insufficient_data"),
        },
        reason="Staging SLO evaluation was breached or lacked samples.",
    ))
    return rows


def _record(
    runtime: ReleaseGateRuntime,
    *,
    release_id: str,
    gate: str,
    observed: int,
    ttl_ms: int,
    passed: bool,
    details: dict[str, Any],
    reason: str,
    artifact_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = details if passed else {"reason": reason, "observed": details}
    return runtime.record(
        release_id=release_id,
        gate=gate,
        status="passed" if passed else "failed",
        source="staging-runtime-collector",
        observed_at_ms=observed,
        expires_at_ms=observed + ttl_ms,
        details=payload,
        artifact_reference=artifact_reference,
    ).model_dump()
