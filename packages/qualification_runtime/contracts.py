"""Contracts for release-level production qualification."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QualificationThresholds(BaseModel):
    max_run_seconds: float = 2400.0
    min_identity_characters: int = 3
    min_identity_evidence_rate: float = 0.75
    min_factual_support_rate: float = 0.90
    max_contradiction_rate: float = 0.05
    min_visual_score: float = 0.60
    max_visual_defect_score: float = 0.40
    max_audio_word_error_rate: float = 0.25
    min_audio_word_match_rate: float = 0.75
    min_image_dimension: int = 256
    min_image_luma_mean: float = 5.0
    min_image_luma_stddev: float = 3.0
    min_audio_duration_seconds: float = 5.0
    min_audio_rms: float = 0.002
    min_story_words: int = 100


class QualificationCheck(BaseModel):
    check_id: str
    category: str
    status: Literal["passed", "failed", "warning"]
    critical: bool = True
    observed: Any = None
    expected: Any = None
    detail: str = ""


class ProductionQualificationReport(BaseModel):
    report_id: str
    run_id: str
    series_id: str
    source_path: str
    source_sha256: str
    release_id: str = ""
    accepted: bool = False
    checks: list[QualificationCheck] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_reference: dict[str, Any] = Field(default_factory=dict)
