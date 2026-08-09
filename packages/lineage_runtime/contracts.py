"""Portable contracts for immutable artifact lineage."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class LineageVersions(BaseModel):
    runtime: str = "1"
    schema_version: str = "1"
    quality_policy: str = "1"
    prompt: str = ""
    workflow: str = ""
    model: str = ""
    provider_config: str = ""
    extra: dict[str, str] = Field(default_factory=dict)


class StageLineageSpec(BaseModel):
    stage: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    versions: LineageVersions = Field(default_factory=LineageVersions)


class StageLineageRecord(BaseModel):
    execution_id: str
    run_id: str
    series_id: str
    stage: str
    attempt: int = 1
    status: str
    execution_mode: Literal["executed", "reused", "adopted"] = "executed"
    input_fingerprint: str
    output_fingerprint: str = ""
    lineage_fingerprint: str
    parent_fingerprints: dict[str, str] = Field(default_factory=dict)
    versions: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class LineageRecordStore(Protocol):
    def append(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, execution_id: str) -> dict[str, Any] | None: ...

    def find_latest_accepted(self, *, series_id: str, stage: str, input_fingerprint: str, output_fingerprint: str = "") -> dict[str, Any] | None: ...

    def list(self, *, run_id: str = "", series_id: str = "", stage: str = "", limit: int = 1000) -> list[dict[str, Any]]: ...


class ArtifactVersionStore(Protocol):
    def put(
        self, *, execution_id: str, run_id: str, series_id: str, stage: str,
        output_fingerprint: str, output_payload: Any,
    ) -> dict[str, Any]: ...
