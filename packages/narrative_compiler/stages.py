"""Model-independent compiler-stage contracts for V3.0."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence, runtime_checkable

from .ir import Entity, Mention, ModelDescriptor, StageRunDescriptor
from .source import NormalizedSource


@dataclass(frozen=True, slots=True)
class LexerResult:
    run: StageRunDescriptor
    mentions: tuple[Mention, ...]


@runtime_checkable
class SemanticLexer(Protocol):
    @property
    def descriptor(self) -> ModelDescriptor | None: ...

    def analyze(self, source: NormalizedSource) -> LexerResult: ...


@dataclass(frozen=True, slots=True)
class IdentityScoringContext:
    """Immutable source + prior-mention context shared by identity retrieval/scoring.

    Candidate generation and learned scoring need more than names: discourse
    recency and representative prior contexts matter for pronouns, nominals and
    aliases. Keeping the evidence packet explicit prevents adapters from reaching
    into mutable/global state.
    """

    source: NormalizedSource
    mentions: tuple[Mention, ...]
    _mention_by_id: Mapping[str, Mention] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        mapping: dict[str, Mention] = {}
        for mention in self.mentions:
            if mention.mention_id in mapping:
                raise ValueError(f"duplicate context mention ID: {mention.mention_id}")
            if mention.evidence.source_fingerprint != self.source.source_fingerprint:
                raise ValueError("identity context mention belongs to a different source")
            mapping[mention.mention_id] = mention
        object.__setattr__(self, "_mention_by_id", MappingProxyType(mapping))

    @property
    def mention_by_id(self) -> Mapping[str, Mention]:
        return self._mention_by_id


@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    mention_id: str
    candidate_entity_id: str
    features: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.mention_id or not self.candidate_entity_id:
            raise ValueError("identity candidate IDs are required")
        normalized = {key: float(value) for key, value in self.features.items()}
        if any(not math.isfinite(value) for value in normalized.values()):
            raise ValueError("identity candidate features must be finite")
        object.__setattr__(self, "features", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class IdentityScore:
    mention_id: str
    candidate_entity_id: str
    score: float
    scorer: ModelDescriptor | None = None

    def __post_init__(self) -> None:
        if not self.mention_id or not self.candidate_entity_id:
            raise ValueError("identity score IDs are required")
        if not math.isfinite(self.score):
            raise ValueError("identity score must be finite")


@runtime_checkable
class IdentityCandidateGenerator(Protocol):
    def generate(
        self,
        *,
        mention: Mention,
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> Sequence[IdentityCandidate]: ...


@runtime_checkable
class IdentityScorer(Protocol):
    @property
    def descriptor(self) -> ModelDescriptor | None: ...

    def score(
        self,
        *,
        mention: Mention,
        candidate: IdentityCandidate,
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> IdentityScore: ...


@runtime_checkable
class BatchIdentityScorer(Protocol):
    """Optional efficient scorer boundary for one mention's candidate set."""

    @property
    def descriptor(self) -> ModelDescriptor | None: ...

    def score_many(
        self,
        *,
        mention: Mention,
        candidates: Sequence[IdentityCandidate],
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> Sequence[IdentityScore]: ...


@dataclass(frozen=True, slots=True)
class LinkerResult:
    run: StageRunDescriptor
    entities: tuple[Entity, ...]
    unresolved_mention_ids: tuple[str, ...]


@runtime_checkable
class GlobalCharacterLinker(Protocol):
    def link(
        self,
        *,
        source: NormalizedSource,
        mentions: Sequence[Mention],
        upstream_fingerprints: Sequence[str] = (),
    ) -> LinkerResult: ...
