"""Typed V3.0 subset of the S.A.G.A. Narrative Intermediate Representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .fingerprint import stable_id


class AcceptanceState(str, Enum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    OBJECT = "object"
    ORGANIZATION = "organization"
    FACTION = "faction"
    CREATURE = "creature"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if self.start_offset < 0:
            raise ValueError("start_offset must be >= 0")
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")

    @property
    def length(self) -> int:
        return self.end_offset - self.start_offset


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    source_fingerprint: str
    source_unit_key: str
    span: SourceSpan

    def __post_init__(self) -> None:
        if not self.source_fingerprint:
            raise ValueError("source_fingerprint is required")
        if not self.source_unit_key:
            raise ValueError("source_unit_key is required")


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    model_id: str
    revision: str
    adapter: str
    license_id: str | None = None

    def __post_init__(self) -> None:
        if not self.model_id or not self.revision or not self.adapter:
            raise ValueError("model_id, revision and adapter are required")


@dataclass(frozen=True, slots=True)
class StageRunDescriptor:
    stage_name: str
    stage_version: str
    config_fingerprint: str
    artifact_fingerprint: str
    model: ModelDescriptor | None = None

    def __post_init__(self) -> None:
        if not all((self.stage_name, self.stage_version, self.config_fingerprint, self.artifact_fingerprint)):
            raise ValueError("stage run descriptor fields must be non-empty")


@dataclass(frozen=True, slots=True)
class Mention:
    mention_id: str
    entity_type: EntityType
    text: str
    evidence: EvidenceRef
    confidence: float | None = None
    acceptance: AcceptanceState = AcceptanceState.CANDIDATE
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.mention_id or not self.text:
            raise ValueError("mention_id and text are required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @classmethod
    def create(
        cls,
        *,
        source_fingerprint: str,
        source_unit_key: str,
        span: SourceSpan,
        entity_type: EntityType,
        text: str,
        confidence: float | None = None,
        acceptance: AcceptanceState = AcceptanceState.CANDIDATE,
        attributes: Mapping[str, str] | None = None,
    ) -> "Mention":
        mention_id = stable_id(
            "mention-v3",
            source_fingerprint,
            source_unit_key,
            span.start_offset,
            span.end_offset,
            entity_type.value,
            prefix="men",
        )
        return cls(
            mention_id=mention_id,
            entity_type=entity_type,
            text=text,
            evidence=EvidenceRef(
                source_fingerprint=source_fingerprint,
                source_unit_key=source_unit_key,
                span=span,
            ),
            confidence=confidence,
            acceptance=acceptance,
            attributes=dict(attributes or {}),
        )


@dataclass(frozen=True, slots=True)
class Entity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str | None
    mention_ids: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    confidence: float | None = None
    acceptance: AcceptanceState = AcceptanceState.UNRESOLVED

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("entity_id is required")
        if not self.mention_ids:
            raise ValueError("an entity must contain at least one mention")
        if len(set(self.mention_ids)) != len(self.mention_ids):
            raise ValueError("mention_ids must be unique")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @classmethod
    def unresolved_singleton(cls, mention: Mention) -> "Entity":
        return cls(
            entity_id=stable_id("entity-v3-unresolved", mention.mention_id, prefix="ent"),
            entity_type=mention.entity_type,
            canonical_name=None,
            mention_ids=(mention.mention_id,),
            aliases=(mention.text,),
            acceptance=AcceptanceState.UNRESOLVED,
        )
