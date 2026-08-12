"""Portable contracts for production orchestration and deliverable packaging."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator


StageName = Literal[
    "analysis_foundation",
    "canon_extraction",
    "character_world_modeling",
    "generation_planning",
    "narrative_generation",
    "narrative_support",
    "visual_generation",
    "audiobook_generation",
    "artifact_packaging",
]


class OrchestrationExecutionLimits(BaseModel):
    """Portable work bounds forwarded to the owning stage runtimes."""

    target_words_per_scene: int = Field(default=180, ge=80, le=1200)
    visual_include_types: list[str] = Field(default_factory=list)
    max_visual_renders_per_type: int = Field(default=0, ge=0, le=100)
    max_visual_attempts: int = Field(default=0, ge=0, le=6)
    audiobook_max_chapters: int = Field(default=0, ge=0, le=1000)
    audiobook_max_segment_chars: int = Field(default=1800, ge=200, le=10000)


class ArtifactReference(BaseModel):
    artifact_id: str
    role: str
    media_type: str = "application/octet-stream"
    bucket_name: str = ""
    object_path: str = ""
    byte_length: int = 0
    sha256: str = ""
    source_stage: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationRequest(BaseModel):
    run_id: str
    series_id: str
    project_id: str = ""
    story_id: str = ""
    blueprint_id: str = ""
    audiobook_run_id: str = ""
    source_paths: list[str] = Field(default_factory=list)
    premise: str = ""
    target_audience: str = ""
    tone: str = ""
    desired_chapter_count: int = 3
    selected_stages: list[StageName] = Field(default_factory=lambda: ["artifact_packaging"])
    include_visuals: bool = True
    include_audiobook: bool = True
    max_attempts: int = 2
    execution_limits: OrchestrationExecutionLimits = Field(default_factory=OrchestrationExecutionLimits)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run_id", "series_id")
    @classmethod
    def _require_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("identifier is required")
        return normalized


class StageOutcomeArtifact(BaseModel):
    stage: StageName
    status: Literal["accepted", "rejected", "failed", "cancelled", "skipped"]
    accepted: bool = False
    attempt: int = 1
    reused: bool = False
    started_at: int = 0
    completed_at: int = 0
    elapsed_seconds: float = 0.0
    artifact_refs: list[ArtifactReference] = Field(default_factory=list)
    output_context: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    error_type: str = ""
    error_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliverableManifestArtifact(BaseModel):
    manifest_id: str
    version: int = 1
    run_id: str
    series_id: str
    story_id: str
    title: str
    status: Literal["accepted", "rejected"] = "accepted"
    created_at: int
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    stage_lineage: list[StageOutcomeArtifact] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationDecisionArtifact(BaseModel):
    decision_id: str
    run_id: str
    series_id: str
    accepted: bool = False
    status: Literal["accepted", "rejected", "failed", "cancelled"] = "failed"
    completed_stages: list[StageName] = Field(default_factory=list)
    failed_stage: StageName | None = None
    reasons: list[str] = Field(default_factory=list)


class OrchestrationResult(BaseModel):
    request: OrchestrationRequest
    planned_stages: list[StageName]
    outcomes: list[StageOutcomeArtifact] = Field(default_factory=list)
    manifest: DeliverableManifestArtifact | None = None
    decision: OrchestrationDecisionArtifact
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationStage(Protocol):
    def inspect(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None: ...

    def execute(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact: ...


class DeliverablePackager(Protocol):
    def package(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> DeliverableManifestArtifact: ...
