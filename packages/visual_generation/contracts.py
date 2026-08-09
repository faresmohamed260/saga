"""Portable contracts for visual planning, rendering, and quality decisions."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


VisualTargetType = Literal["character", "location", "creature", "object", "scene"]


class CharacterVisualBaselineArtifact(BaseModel):
    baseline_id: str
    series_id: str
    story_id: str
    character_id: str
    canonical_name: str
    appearance: str = ""
    body: str = ""
    face: str = ""
    hair: str = ""
    clothing: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)
    immutable_traits: list[str] = Field(default_factory=list)
    consistency_key: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterSceneStateArtifact(BaseModel):
    state_id: str
    series_id: str
    story_id: str
    source_scene_id: str
    character_id: str
    expression: str = ""
    pose: str = ""
    clothing_state: str = ""
    physical_condition: str = ""
    action: str = ""
    baseline_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityVisualDossierArtifact(BaseModel):
    dossier_id: str
    series_id: str
    story_id: str
    entity_id: str
    canonical_name: str
    entity_type: Literal["location", "creature", "object"]
    visual_description: str = ""
    materials: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    scale: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)
    consistency_key: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneVisualPlanArtifact(BaseModel):
    plan_id: str
    series_id: str
    story_id: str
    source_scene_id: str
    title: str = ""
    composition: str = ""
    environment: str = ""
    lighting: str = ""
    mood: str = ""
    camera: str = ""
    action: str = ""
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualPromptArtifact(BaseModel):
    prompt_id: str
    series_id: str
    story_id: str
    target_type: VisualTargetType
    target_ref: str
    source_scene_id: str = ""
    workflow_mode: Literal["character_sheet", "entity_generation"]
    positive_prompt: str
    negative_prompt: str
    width: int = 512
    height: int = 512
    steps: int = 4
    cfg: float = 1.2
    workflow_version: str = ""
    consistency_keys: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualRenderArtifact(BaseModel):
    render_id: str
    series_id: str
    story_id: str
    prompt_id: str
    target_type: VisualTargetType
    target_ref: str
    attempt: int = 1
    seed: int
    status: Literal["rendered", "technical_rejection", "provider_error"]
    bucket_name: str = ""
    object_path: str = ""
    content_type: str = "image/png"
    byte_length: int = 0
    image_sha256: str = ""
    provider_name: str = ""
    provider_account: str = ""
    elapsed_seconds: float = 0.0
    technical_metrics: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualQualityDecisionArtifact(BaseModel):
    audit_id: str
    series_id: str
    story_id: str
    prompt_id: str
    render_id: str
    target_type: VisualTargetType
    target_ref: str
    accepted: bool = False
    status: Literal["accepted", "retry_required", "rejected"] = "rejected"
    prompt_alignment_score: float = 0.0
    subject_consistency_score: float = 0.0
    composition_score: float = 0.0
    photorealism_score: float = 0.0
    defect_score: float = 1.0
    technical_passed: bool = False
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualGenerationDecisionArtifact(BaseModel):
    decision_id: str
    series_id: str
    story_id: str
    accepted: bool = False
    status: Literal["accepted", "rejected"] = "rejected"
    requested_count: int = 0
    accepted_count: int = 0
    rejected_prompt_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualGenerationResult(BaseModel):
    series_id: str
    story_id: str
    character_baselines: list[CharacterVisualBaselineArtifact] = Field(default_factory=list)
    character_scene_states: list[CharacterSceneStateArtifact] = Field(default_factory=list)
    entity_dossiers: list[EntityVisualDossierArtifact] = Field(default_factory=list)
    scene_plans: list[SceneVisualPlanArtifact] = Field(default_factory=list)
    prompts: list[VisualPromptArtifact] = Field(default_factory=list)
    renders: list[VisualRenderArtifact] = Field(default_factory=list)
    audits: list[VisualQualityDecisionArtifact] = Field(default_factory=list)
    decision: VisualGenerationDecisionArtifact
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class ImageRenderProvider(Protocol):
    def render(self, **kwargs: Any) -> dict[str, Any]: ...


class VisualSemanticEvaluator(Protocol):
    def evaluate(self, *, image_bytes: bytes, prompt: VisualPromptArtifact) -> dict[str, Any]: ...
