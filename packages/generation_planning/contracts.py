"""Portable contracts for canon-grounded generation planning."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class StoryIntentArtifact(BaseModel):
    intent_id: str
    series_id: str
    premise: str
    target_audience: str = ""
    tone: str = ""
    continuation_mode: str = "canon_continuation"
    desired_chapter_count: int = 3
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("desired_chapter_count", mode="before")
    @classmethod
    def _coerce_chapter_count(cls, value: Any) -> int:
        try:
            return max(1, min(24, int(value)))
        except Exception:
            return 3


class CanonGroundingArtifact(BaseModel):
    grounding_id: str
    series_id: str
    canon_event_ids: list[str] = Field(default_factory=list)
    timeline_ids: list[str] = Field(default_factory=list)
    required_character_ids: list[str] = Field(default_factory=list)
    required_entity_ids: list[str] = Field(default_factory=list)
    timeline_constraints: list[str] = Field(default_factory=list)
    character_constraints: list[str] = Field(default_factory=list)
    world_constraints: list[str] = Field(default_factory=list)
    relationship_constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterOutlineItem(BaseModel):
    chapter_index: int
    title: str = ""
    goal: str = ""
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)


class ScenePlanItem(BaseModel):
    scene_id: str
    chapter_index: int
    scene_index: int
    summary: str = ""
    purpose: str = ""
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    visual_requirements: list[str] = Field(default_factory=list)
    audio_requirements: list[str] = Field(default_factory=list)


class GenerationBlueprintArtifact(BaseModel):
    blueprint_id: str
    series_id: str
    intent_id: str
    grounding_id: str
    title: str = ""
    premise: str = ""
    continuation_plan: str = ""
    divergence_plan: str = ""
    chapter_outline: list[ChapterOutlineItem] = Field(default_factory=list)
    scene_plan: list[ScenePlanItem] = Field(default_factory=list)
    visual_requirements: list[str] = Field(default_factory=list)
    audio_requirements: list[str] = Field(default_factory=list)
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationPlanningResult(BaseModel):
    series_id: str
    intent: StoryIntentArtifact
    grounding: CanonGroundingArtifact
    blueprint: GenerationBlueprintArtifact
    run_metadata: dict[str, Any] = Field(default_factory=dict)
