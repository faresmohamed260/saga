"""Portable contracts for audiobook planning, synthesis, assembly, and QA."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class AudiobookPlanArtifact(BaseModel):
    run_id: str
    series_id: str
    story_id: str
    title: str
    narrator_voice: str
    language: str = "en"
    lang_code: str = "a"
    sample_rate: int = 24000
    audio_format: Literal["wav"] = "wav"
    max_segment_chars: int = 1800
    sentence_pause_ms: int = 120
    chapter_pause_ms: int = 800
    selected_chapter_indices: list[int] = Field(default_factory=list)
    provider_name: str = "kokoro_tts"
    provider_model: str = "kokoro"
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrationSegmentArtifact(BaseModel):
    segment_id: str
    run_id: str
    series_id: str
    story_id: str
    chapter_index: int
    segment_index: int
    source_scene_ids: list[str] = Field(default_factory=list)
    speaker_role: Literal["narrator"] = "narrator"
    voice: str
    text: str
    word_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudioSynthesisArtifact(BaseModel):
    synthesis_id: str
    run_id: str
    series_id: str
    story_id: str
    segment_id: str
    chapter_index: int
    segment_index: int
    attempt: int = 1
    status: Literal["synthesized", "technical_rejection", "provider_error"]
    voice: str
    sample_rate: int = 24000
    audio_format: Literal["wav"] = "wav"
    duration_seconds: float = 0.0
    byte_length: int = 0
    audio_sha256: str = ""
    bucket_name: str = ""
    object_path: str = ""
    provider_name: str = "kokoro_tts"
    provider_account: str = ""
    elapsed_seconds: float = 0.0
    technical_metrics: dict[str, Any] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudioQualityDecisionArtifact(BaseModel):
    audit_id: str
    run_id: str
    series_id: str
    story_id: str
    segment_id: str
    synthesis_id: str
    attempt: int = 1
    accepted: bool = False
    status: Literal["accepted", "retry_required", "rejected"] = "rejected"
    technical_passed: bool = False
    transcription_text: str = ""
    word_error_rate: float = 1.0
    word_match_rate: float = 0.0
    speaking_rate_wpm: float = 0.0
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudiobookChapterArtifact(BaseModel):
    chapter_audio_id: str
    run_id: str
    series_id: str
    story_id: str
    chapter_index: int
    title: str = ""
    accepted_segment_ids: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    byte_length: int = 0
    bucket_name: str = ""
    object_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudiobookManifestArtifact(BaseModel):
    manifest_id: str
    run_id: str
    series_id: str
    story_id: str
    title: str
    chapter_audio_ids: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    byte_length: int = 0
    bucket_name: str = ""
    object_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudiobookDecisionArtifact(BaseModel):
    decision_id: str
    run_id: str
    series_id: str
    story_id: str
    accepted: bool = False
    status: Literal["accepted", "rejected"] = "rejected"
    requested_segment_count: int = 0
    accepted_segment_count: int = 0
    rejected_segment_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudiobookGenerationResult(BaseModel):
    series_id: str
    story_id: str
    plan: AudiobookPlanArtifact
    segments: list[NarrationSegmentArtifact] = Field(default_factory=list)
    syntheses: list[AudioSynthesisArtifact] = Field(default_factory=list)
    audits: list[AudioQualityDecisionArtifact] = Field(default_factory=list)
    chapters: list[AudiobookChapterArtifact] = Field(default_factory=list)
    manifest: AudiobookManifestArtifact | None = None
    decision: AudiobookDecisionArtifact
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class SpeechSynthesisProvider(Protocol):
    def synthesize(self, **kwargs: Any) -> dict[str, Any]: ...


class SpeechTranscriptionProvider(Protocol):
    def transcribe_audio(self, **kwargs: Any) -> dict[str, Any]: ...
