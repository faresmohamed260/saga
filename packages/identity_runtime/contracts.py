"""Contracts for the reusable identity runtime."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IdentityCluster(BaseModel):
    cluster_id: int = 0
    display_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    mention_count: int = 0
    proper_mentions: list[str] = Field(default_factory=list)
    pronoun_mentions: list[str] = Field(default_factory=list)


class IdentityAliasEvidence(BaseModel):
    alias: str
    support_count: int = 0
    chapter_indices: list[int] = Field(default_factory=list)
    scene_ids: list[str] = Field(default_factory=list)
    matched_character_ids: list[str] = Field(default_factory=list)
    matched_display_names: list[str] = Field(default_factory=list)


class IdentityQualityDiagnostic(BaseModel):
    code: str
    severity: str = "warning"
    message: str = ""
    cluster_id: int = 0
    display_name: str = ""
    alias: str = ""
    related_character_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewedIdentityCluster(BaseModel):
    cluster: IdentityCluster
    keep_cluster: bool = True
    accepted_aliases: list[str] = Field(default_factory=list)
    rejected_aliases: list[str] = Field(default_factory=list)
    evidence: list[IdentityAliasEvidence] = Field(default_factory=list)
    diagnostics: list[IdentityQualityDiagnostic] = Field(default_factory=list)


class IdentityGroundingReviewResult(BaseModel):
    reviewed_clusters: list[ReviewedIdentityCluster] = Field(default_factory=list)
    diagnostics: list[IdentityQualityDiagnostic] = Field(default_factory=list)
    kept_cluster_count: int = 0
    dropped_cluster_count: int = 0
    accepted_alias_count: int = 0
    rejected_alias_count: int = 0


class IdentityRuntimeResult(BaseModel):
    provider_name: str = ""
    app_name: str = ""
    model_name: str = ""
    runtime_seconds: float = 0.0
    chunk_count: int = 0
    input_stats: dict[str, Any] = Field(default_factory=dict)
    clusters: list[IdentityCluster] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
