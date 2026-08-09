"""Portable contracts for canon-grounded narrative generation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SceneProseArtifact(BaseModel):
    scene_prose_id: str
    series_id: str
    story_id: str
    blueprint_id: str
    source_scene_id: str
    chapter_index: int
    scene_index: int
    title: str = ""
    prose: str = ""
    purpose: str = ""
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterDraftArtifact(BaseModel):
    chapter_draft_id: str
    series_id: str
    story_id: str
    blueprint_id: str
    chapter_index: int
    title: str = ""
    goal: str = ""
    prose: str = ""
    scene_prose_ids: list[str] = Field(default_factory=list)
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContinuityCheckArtifact(BaseModel):
    continuity_check_id: str
    series_id: str
    story_id: str
    blueprint_id: str
    chapter_index: int = 0
    passed: bool = True
    issues: list[str] = Field(default_factory=list)
    canon_ref_coverage_rate: float = 1.0
    character_ref_coverage_rate: float = 1.0
    entity_ref_coverage_rate: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionRecordArtifact(BaseModel):
    revision_id: str
    series_id: str
    story_id: str
    blueprint_id: str
    chapter_index: int = 0
    source_artifact_id: str = ""
    reason: str = ""
    before_excerpt: str = ""
    after_excerpt: str = ""
    issues_addressed: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratedStoryArtifact(BaseModel):
    story_id: str
    series_id: str
    blueprint_id: str
    title: str = ""
    premise: str = ""
    chapters: list[ChapterDraftArtifact] = Field(default_factory=list)
    continuity_checks: list[ContinuityCheckArtifact] = Field(default_factory=list)
    revisions: list[RevisionRecordArtifact] = Field(default_factory=list)
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrativeGenerationResult(BaseModel):
    series_id: str
    story: GeneratedStoryArtifact
    scene_prose: list[SceneProseArtifact] = Field(default_factory=list)
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class SupportEvidenceArtifact(BaseModel):
    evidence_id: str
    document_id: str
    source_type: str = ""
    excerpt: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimSupportArtifact(BaseModel):
    claim_id: str
    claim: str
    claim_type: Literal["canon_fact", "story_local"] = "canon_fact"
    classification: Literal["supported", "creative_expansion", "unsupported", "contradiction"]
    severity: Literal["low", "medium", "high"] = "medium"
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_scope: Literal["prior_canon", "generated_present"] = "prior_canon"
    plan_alignment: Literal["aligned", "not_aligned", "not_applicable"] = "not_applicable"


class SceneSupportAuditArtifact(BaseModel):
    audit_id: str
    series_id: str
    story_id: str
    source_scene_id: str
    scene_prose_id: str
    evaluation_round: int = 1
    claims: list[ClaimSupportArtifact] = Field(default_factory=list)
    evidence: list[SupportEvidenceArtifact] = Field(default_factory=list)
    factual_support_rate: float = 0.0
    unsupported_invention_rate: float = 0.0
    contradiction_rate: float = 0.0
    status: Literal["accepted", "revision_required", "rejected"] = "rejected"
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrativeSupportDecisionArtifact(BaseModel):
    decision_id: str
    series_id: str
    story_id: str
    accepted: bool = False
    status: Literal["accepted", "rejected"] = "rejected"
    scene_count: int = 0
    accepted_scene_count: int = 0
    factual_support_rate: float = 0.0
    unsupported_invention_rate: float = 0.0
    contradiction_rate: float = 0.0
    provider_success_rate: float = 0.0
    revised_scene_ids: list[str] = Field(default_factory=list)
    rejected_scene_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrativeSupportResult(BaseModel):
    series_id: str
    story: GeneratedStoryArtifact
    scene_prose: list[SceneProseArtifact] = Field(default_factory=list)
    audits: list[SceneSupportAuditArtifact] = Field(default_factory=list)
    revisions: list[RevisionRecordArtifact] = Field(default_factory=list)
    decision: NarrativeSupportDecisionArtifact
    run_metadata: dict[str, Any] = Field(default_factory=dict)
