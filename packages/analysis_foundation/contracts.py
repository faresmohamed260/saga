"""Portable contracts for analysis-foundation canon artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceDocumentArtifact(BaseModel):
    source_id: str
    series_id: str
    book_id: str
    filename: str
    source_type: str
    title: str = ""
    object_path: str = ""
    bucket_name: str = ""
    text_hash: str = ""
    text_length: int = 0
    word_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookArtifact(BaseModel):
    book_id: str
    series_id: str
    title: str
    book_index: int
    source_uri: str = ""
    source_type: str = ""
    chapter_count: int = 0
    word_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterArtifact(BaseModel):
    chapter_id: str
    series_id: str
    book_id: str
    chapter_index: int
    title: str = ""
    content: str
    source_id: str
    source_type: str = ""
    word_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneArtifact(BaseModel):
    scene_id: str
    book_id: str
    chapter_index: int
    scene_index: int
    summary: str = ""
    text: str
    word_count: int = 0
    source_chapter_indices: list[int] = Field(default_factory=list)
    end_chapter_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrativeEvidenceSpan(BaseModel):
    kind: str = ""
    text: str = ""
    start_char: int = 0
    end_char: int = 0
    character_id: str = ""
    character_name: str = ""


class SceneNarrativeGrounding(BaseModel):
    scene_id: str
    perspective: str = ""
    narrator_character_id: str = ""
    narrator_name: str = ""
    narrator_confidence: float = 0.0
    addressee_character_ids: list[str] = Field(default_factory=list)
    addressee_names: list[str] = Field(default_factory=list)
    first_person_count: int = 0
    second_person_count: int = 0
    dialogue_first_person_count: int = 0
    dialogue_second_person_count: int = 0
    raw_first_person_count: int = 0
    raw_second_person_count: int = 0
    evidence_spans: list[NarrativeEvidenceSpan] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class CanonicalCharacter(BaseModel):
    character_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    mention_count: int = 0
    proper_mentions: list[str] = Field(default_factory=list)
    pronoun_mentions: list[str] = Field(default_factory=list)
    chapter_indices: list[int] = Field(default_factory=list)
    scene_ids: list[str] = Field(default_factory=list)


class NarratorReferenceData(BaseModel):
    perspective: str = ""
    first_person_pronoun_count: int = 0
    third_person_pronoun_count: int = 0
    named_reference_candidates: list[str] = Field(default_factory=list)


class CanonicalIdentityBundle(BaseModel):
    series_id: str
    provider_name: str
    book_ids: list[str] = Field(default_factory=list)
    characters: list[CanonicalCharacter] = Field(default_factory=list)
    alias_map: dict[str, str] = Field(default_factory=dict)
    narrator: NarratorReferenceData = Field(default_factory=NarratorReferenceData)
    source_stats: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisFoundationResult(BaseModel):
    series_id: str
    books: list[BookArtifact] = Field(default_factory=list)
    chapters: list[ChapterArtifact] = Field(default_factory=list)
    scenes: list[SceneArtifact] = Field(default_factory=list)
    identity_bundle: CanonicalIdentityBundle | None = None
    run_metadata: dict[str, Any] = Field(default_factory=dict)
