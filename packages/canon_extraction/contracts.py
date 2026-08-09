"""Portable contracts for canon extraction artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventArtifact(BaseModel):
    event_id: str
    series_id: str
    book_id: str
    scene_id: str
    chapter_index: int
    scene_index: int
    event_index: int
    title: str
    summary: str = ""
    event_type: str = ""
    participant_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityArtifact(BaseModel):
    entity_id: str
    series_id: str
    canonical_name: str
    entity_type: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    mention_scene_ids: list[str] = Field(default_factory=list)
    book_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipArtifact(BaseModel):
    relationship_id: str
    series_id: str
    source_ref: str
    target_ref: str
    relationship_type: str = ""
    description: str = ""
    scene_ids: list[str] = Field(default_factory=list)
    book_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineArtifact(BaseModel):
    timeline_id: str
    series_id: str
    book_id: str
    scene_id: str
    event_id: str
    sequence_index: int
    chapter_index: int
    scene_index: int
    title: str
    summary: str = ""
    event_type: str = ""
    participant_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonExtractionResult(BaseModel):
    series_id: str
    events: list[EventArtifact] = Field(default_factory=list)
    entities: list[EntityArtifact] = Field(default_factory=list)
    relationships: list[RelationshipArtifact] = Field(default_factory=list)
    timeline: list[TimelineArtifact] = Field(default_factory=list)
    run_metadata: dict[str, Any] = Field(default_factory=dict)
