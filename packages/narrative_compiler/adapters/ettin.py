"""Lazy Ettin cross-encoder challenger for identity candidate scoring.

The public Ettin reranker is trained for relevance, not literary coreference.
This adapter therefore exposes its raw score as experimental evidence only; it
does not turn a high score into a canonical merge.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..ir import Entity, Mention, ModelDescriptor
from ..source import NormalizedSource
from ..stages import IdentityCandidate, IdentityScore


class EttinRerankerIdentityScorer:
    def __init__(
        self,
        *,
        model_id: str = "cross-encoder/ettin-reranker-68m-v1",
        revision: str,
        context_chars: int = 360,
        model: Any | None = None,
    ) -> None:
        if not revision:
            raise ValueError("an exact model revision is required for qualification")
        if context_chars < 32:
            raise ValueError("context_chars must be >= 32")
        self.model_id = model_id
        self.revision = revision
        self.context_chars = context_chars
        self._model = model

    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id=self.model_id,
            revision=self.revision,
            adapter="sentence_transformers.CrossEncoder",
            license_id="apache-2.0",
        )

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover - heavyweight optional path
                raise RuntimeError(
                    "Ettin qualification is optional; install `sentence-transformers` in the qualification environment"
                ) from exc
            self._model = CrossEncoder(
                self.model_id,
                revision=self.revision,
                trust_remote_code=False,
            )
        return self._model

    def _entity(self, candidate: IdentityCandidate, entities: Sequence[Entity]) -> Entity:
        for entity in entities:
            if entity.entity_id == candidate.candidate_entity_id:
                return entity
        raise ValueError(f"candidate entity not found: {candidate.candidate_entity_id}")

    def _context(self, mention: Mention, source: NormalizedSource) -> str:
        span = mention.evidence.span
        start = max(0, span.start_offset - self.context_chars)
        end = min(len(source.normalized_text), span.end_offset + self.context_chars)
        return source.normalized_text[start:end]

    def score(
        self,
        *,
        mention: Mention,
        candidate: IdentityCandidate,
        existing_entities: Sequence[Entity],
        source: NormalizedSource,
    ) -> IdentityScore:
        entity = self._entity(candidate, existing_entities)
        aliases = ", ".join(entity.aliases)
        query = f"Mention: {mention.text}\nContext: {self._context(mention, source)}"
        passage = f"Candidate character: {entity.canonical_name or ''}\nAliases: {aliases}"
        raw = self._load_model().predict([(query, passage)])
        value = float(raw[0])
        return IdentityScore(
            mention_id=mention.mention_id,
            candidate_entity_id=entity.entity_id,
            score=value,
            scorer=self.descriptor,
        )
