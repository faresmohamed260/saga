"""Portable contracts for character and world modeling artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CharacterProfileArtifact(BaseModel):
    profile_id: str
    series_id: str
    character_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    book_ids: list[str] = Field(default_factory=list)
    chapter_indices: list[int] = Field(default_factory=list)
    scene_ids: list[str] = Field(default_factory=list)
    overview: str = ""
    role_or_archetype: str = ""
    traits: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)
    loyalties: list[str] = Field(default_factory=list)
    tensions: list[str] = Field(default_factory=list)
    notable_relationships: list[str] = Field(default_factory=list)
    visual_cues: list[str] = Field(default_factory=list)
    first_seen_summary: str = ""
    latest_state_summary: str = ""
    important_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StableCharacterStateArtifact(BaseModel):
    stable_state_id: str
    series_id: str
    character_id: str
    canonical_name: str
    stable_attributes: dict[str, str] = Field(default_factory=dict)
    summary: str = ""
    supporting_event_ids: list[str] = Field(default_factory=list)
    supporting_scene_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldStateArtifact(BaseModel):
    world_state_id: str
    series_id: str
    entity_id: str
    canonical_name: str
    entity_type: str = ""
    description: str = ""
    book_ids: list[str] = Field(default_factory=list)
    scene_ids: list[str] = Field(default_factory=list)
    stable_facts: dict[str, str] = Field(default_factory=dict)
    active_conditions: list[str] = Field(default_factory=list)
    current_state_summary: str = ""
    story_relevance: str = ""
    supporting_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterWorldModelingResult(BaseModel):
    series_id: str
    character_profiles: list[CharacterProfileArtifact] = Field(default_factory=list)
    stable_character_states: list[StableCharacterStateArtifact] = Field(default_factory=list)
    world_states: list[WorldStateArtifact] = Field(default_factory=list)
    run_metadata: dict[str, Any] = Field(default_factory=dict)
