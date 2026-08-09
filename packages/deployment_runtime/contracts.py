"""Portable deployment, release, and process-health contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProcessRole = Literal["api", "worker", "scheduler", "observability"]
ReleaseStatus = Literal["candidate", "staging", "production", "rolled_back", "failed"]


class ReleaseManifest(BaseModel):
    release_id: str
    version: str
    git_sha: str
    image_digest: str = ""
    schema_revision: str
    status: ReleaseStatus = "candidate"
    built_at_ms: int
    configuration_fingerprint: str
    components: dict[str, str] = Field(default_factory=dict)


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
