"""Model-independent compiler-stage contracts for V3.0."""

from __future__ import annotations

from dataclasses import dataclass
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
class IdentityCandidate:
    mention_id: str
    candidate_entity_id: str
    features: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class IdentityScore:
    mention_id: str
    candidate_entity_id: str
    score: float
    scorer: ModelDescriptor | None = None


@runtime_checkable
class IdentityCandidateGenerator(Protocol):
    def generate(
        self,
        *,
        mention: Mention,
        existing_entities: Sequence[Entity],
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
        source: NormalizedSource,
    ) -> IdentityScore: ...


@dataclass(frozen=True, slots=True)
class LinkerResult:
    run: StageRunDescriptor
    entities: tuple[Entity, ...]
    unresolved_mention_ids: tuple[str, ...]


@runtime_checkable
class GlobalCharacterLinker(Protocol):
    def link(self, *, source: NormalizedSource, mentions: Sequence[Mention]) -> LinkerResult: ...
