"""Immutable, expiry-aware release evidence and promotion decisions."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Literal

from packages.deployment_runtime.contracts import (
    ReleaseGateCheck,
    ReleaseGateDecision,
    ReleaseGateEvidence,
    ReleaseGateName,
)

CANARY_REQUIRED_GATES: tuple[ReleaseGateName, ...] = (
    "ci",
    "database_recovery",
    "artifact_recovery",
    "migration",
    "staging_readiness",
    "process_health",
    "production_qualification",
    "usage_cost",
    "slo",
    "rollback",
)
PRODUCTION_REQUIRED_GATES: tuple[ReleaseGateName, ...] = (*CANARY_REQUIRED_GATES, "canary")
_SECRET_FRAGMENTS = ("token", "secret", "password", "credential", "api_key", "apikey", "authorization")
_MAX_EVIDENCE_BYTES = 256 * 1024


class ReleaseGateRuntime:
    def __init__(self, *, store) -> None:
        self.store = store

    def record(
        self,
        *,
        release_id: str,
        gate: ReleaseGateName,
        status: Literal["passed", "failed"],
        source: str,
        details: dict[str, Any] | None = None,
        artifact_reference: dict[str, Any] | None = None,
        observed_at_ms: int | None = None,
        expires_at_ms: int = 0,
    ) -> ReleaseGateEvidence:
        release = self.store.get_release(release_id)
        if release is None:
            raise ValueError(f"Unknown release '{release_id}'.")
        observed = int(observed_at_ms or _now_ms())
        if expires_at_ms and int(expires_at_ms) <= observed:
            raise ValueError("Release gate evidence must expire after it was observed.")
        payload = {
            "release_id": str(release_id),
            "gate": gate,
            "status": status,
            "observed_at_ms": observed,
            "expires_at_ms": max(0, int(expires_at_ms)),
            "source": str(source or "").strip(),
            "details": _sanitize(details or {}),
            "artifact_reference": _sanitize(artifact_reference or {}),
        }
        if not payload["source"]:
            raise ValueError("Release gate evidence source is required.")
        _validate_gate_details(gate, status=status, details=payload["details"], release=release)
        _validate_expiry(gate, observed_at_ms=observed, expires_at_ms=payload["expires_at_ms"])
        encoded = _canonical(payload)
        if len(encoded) > _MAX_EVIDENCE_BYTES:
            raise ValueError("Release gate evidence exceeds the 256 KiB limit.")
        digest = hashlib.sha256(encoded).hexdigest()
        evidence = ReleaseGateEvidence(
            evidence_id=f"release-gate-{digest[:32]}", evidence_sha256=digest, **payload
        )
        return ReleaseGateEvidence.model_validate(
            self.store.record_release_gate_evidence(evidence.model_dump())
        )

    def evaluate(
        self,
        *,
        release_id: str,
        target: Literal["canary", "production"],
        now_ms: int | None = None,
    ) -> ReleaseGateDecision:
        evaluated_at = int(now_ms or _now_ms())
        required = CANARY_REQUIRED_GATES if target == "canary" else PRODUCTION_REQUIRED_GATES
        evidence = self.store.list_release_gate_evidence(release_id=release_id, limit=10_000)
        latest: dict[str, dict[str, Any]] = {}
        for row in evidence:
            gate = str(row.get("gate") or "")
            if gate not in latest:
                latest[gate] = row
        checks: list[ReleaseGateCheck] = []
        for gate in required:
            row = latest.get(gate)
            if row is None:
                checks.append(ReleaseGateCheck(gate=gate, status="missing", detail="No evidence recorded."))
                continue
            expires_at = int(row.get("expires_at_ms") or 0)
            if expires_at and expires_at < evaluated_at:
                checks.append(ReleaseGateCheck(
                    gate=gate, status="expired", evidence_id=str(row.get("evidence_id") or ""),
                    detail=f"Evidence expired at {expires_at}.",
                ))
                continue
            status = "passed" if row.get("status") == "passed" else "failed"
            checks.append(ReleaseGateCheck(
                gate=gate, status=status, evidence_id=str(row.get("evidence_id") or ""),
                detail="Latest immutable evidence accepted." if status == "passed" else "Latest evidence failed.",
            ))
        return ReleaseGateDecision(
            release_id=release_id,
            target=target,
            eligible=all(check.status == "passed" for check in checks),
            evaluated_at_ms=evaluated_at,
            checks=checks,
        )

    def assert_eligible(self, *, release_id: str, target: Literal["canary", "production"]) -> ReleaseGateDecision:
        decision = self.evaluate(release_id=release_id, target=target)
        if not decision.eligible:
            failures = ", ".join(f"{check.gate}={check.status}" for check in decision.checks if check.status != "passed")
            raise ValueError(f"Release '{release_id}' is not eligible for {target}: {failures}.")
        return decision


def _sanitize(value: Any, *, key: str = "") -> Any:
    if (
        any(fragment in key.casefold() for fragment in _SECRET_FRAGMENTS)
        and not isinstance(value, (bool, int, float))
    ):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(item_key): _sanitize(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _validate_gate_details(
    gate: ReleaseGateName,
    *,
    status: Literal["passed", "failed"],
    details: dict[str, Any],
    release: dict[str, Any],
) -> None:
    if status == "failed":
        if not str(details.get("reason") or "").strip():
            raise ValueError(f"Failed release gate '{gate}' evidence requires a reason.")
        return
    manifest = dict(release.get("manifest") or {})
    release_id = str(release.get("release_id") or "")
    checks: dict[str, bool] = {
        "ci": (
            details.get("git_sha") == manifest.get("git_sha")
            and all(details.get(key) is True for key in (
                "backend_tests_passed", "frontend_tests_passed", "containers_built",
                "architecture_boundaries_passed", "secret_scan_passed",
            ))
        ),
        "database_recovery": (
            _sha256(details.get("backup_sha256"))
            and details.get("restored_schema_revision") == manifest.get("schema_revision")
            and details.get("table_counts_match") is True
        ),
        "artifact_recovery": (
            _sha256(details.get("archive_sha256"))
            and details.get("checksums_verified") is True
            and _nonnegative_int(details.get("object_count"))
        ),
        "migration": (
            details.get("current_revision") == manifest.get("schema_revision")
            and details.get("head_revision") == manifest.get("schema_revision")
            and details.get("rollback_reupgrade_tested") is True
        ),
        "staging_readiness": details.get("ready") is True and details.get("release_id") == release_id,
        "process_health": (
            {"worker", "scheduler", "observability"}.issubset(set(details.get("ready_roles") or []))
            and details.get("release_id") == release_id
        ),
        "production_qualification": (
            details.get("accepted") is True
            and details.get("release_id") == release_id
            and bool(str(details.get("run_id") or "").strip())
            and _sha256(details.get("source_sha256"))
        ),
        "usage_cost": (
            _positive_int(details.get("charge_count"))
            and _zero_int(details.get("unpriced_charge_count"))
            and details.get("reconciled") is True
        ),
        "slo": (
            _positive_int(details.get("evaluation_count"))
            and _zero_int(details.get("breached_count"))
            and _zero_int(details.get("insufficient_data_count"))
        ),
        "rollback": (
            bool(str(details.get("rollback_release_id") or "").strip())
            and _digest(details.get("runtime_digest"))
            and _digest(details.get("dashboard_digest"))
            and details.get("restore_tested") is True
        ),
        "canary": (
            details.get("release_id") == release_id
            and _positive_int(details.get("sample_count"))
            and _zero_int(details.get("failure_count"))
            and _zero_int(details.get("slo_breach_count"))
            and details.get("rollback_trigger_tested") is True
        ),
    }
    if not checks[gate]:
        raise ValueError(f"Release gate '{gate}' evidence is incomplete or does not match the release.")


def _validate_expiry(gate: ReleaseGateName, *, observed_at_ms: int, expires_at_ms: int) -> None:
    ttl_limits = {
        "staging_readiness": 3_600_000,
        "process_health": 3_600_000,
        "production_qualification": 86_400_000,
        "usage_cost": 86_400_000,
        "slo": 3_600_000,
        "canary": 3_600_000,
    }
    max_ttl = ttl_limits.get(gate)
    if max_ttl is None:
        return
    ttl = int(expires_at_ms) - int(observed_at_ms)
    if ttl <= 0 or ttl > max_ttl:
        raise ValueError(f"Release gate '{gate}' requires fresh evidence with TTL at most {max_ttl // 1000} seconds.")


def _sha256(value: Any) -> bool:
    text = str(value or "").casefold()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _digest(value: Any) -> bool:
    text = str(value or "").casefold()
    return text.startswith("sha256:") and _sha256(text.removeprefix("sha256:"))


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _zero_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _now_ms() -> int:
    return int(time.time() * 1000)
