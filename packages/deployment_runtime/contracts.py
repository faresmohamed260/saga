"""Portable deployment, release, and process-health contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ProcessRole = Literal["api", "worker", "scheduler", "observability"]
ReleaseStatus = Literal["candidate", "staging", "canary", "production", "rolled_back", "failed"]
SourceState = Literal["clean", "dirty"]
ReleaseGateName = Literal[
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
    "canary",
]


class ReleaseManifest(BaseModel):
    release_id: str
    version: str
    git_sha: str
    image_digest: str = ""
    schema_revision: str
    status: ReleaseStatus = "candidate"
    built_at_ms: int
    configuration_fingerprint: str
    source_state: SourceState = "clean"
    components: dict[str, str] = Field(default_factory=dict)


class ReleaseGateEvidence(BaseModel):
    evidence_id: str
    release_id: str
    gate: ReleaseGateName
    status: Literal["passed", "failed"]
    observed_at_ms: int = Field(ge=1)
    expires_at_ms: int = Field(default=0, ge=0)
    source: str
    evidence_sha256: str
    details: dict[str, Any] = Field(default_factory=dict)
    artifact_reference: dict[str, Any] = Field(default_factory=dict)


class ReleaseGateCheck(BaseModel):
    gate: ReleaseGateName
    status: Literal["passed", "failed", "missing", "expired"]
    evidence_id: str = ""
    detail: str = ""


class ReleaseGateDecision(BaseModel):
    release_id: str
    target: Literal["canary", "production"]
    eligible: bool
    evaluated_at_ms: int
    checks: list[ReleaseGateCheck] = Field(default_factory=list)


class ReleaseCandidateBundle(BaseModel):
    format: Literal["saga-release-candidate-v1"] = "saga-release-candidate-v1"
    candidate_sha256: str
    created_at_ms: int
    manifest: ReleaseManifest
    canary_required_gates: list[ReleaseGateName]
    production_required_gates: list[ReleaseGateName]


class DependencyStatus(BaseModel):
    name: str
    status: Literal["ready", "degraded", "unavailable"]
    latency_ms: int = 0
    detail: str = ""


class ReadinessReport(BaseModel):
    ready: bool
    service: str
    release_id: str = ""
    schema_revision: str = ""
    dependencies: list[DependencyStatus] = Field(default_factory=list)


class ProcessTickResult(BaseModel):
    role: ProcessRole
    status: Literal["ok", "degraded", "failed"]
    release_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
