"""Lazy Ettin cross-encoder challenger for identity candidate scoring.

The public Ettin reranker is trained for relevance, not literary coreference.
This adapter therefore exposes its raw score as experimental evidence only; it
does not turn a high score into a canonical merge.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..ir import Entity, Mention, ModelDescriptor
from ..model_manifest import ETTIN_RERANKER_68M_V1
from ..stages import IdentityCandidate, IdentityScore, IdentityScoringContext


class EttinRerankerIdentityScorer:
    def __init__(
        self,
        *,
        model_id: str = ETTIN_RERANKER_68M_V1.model_id,
        revision: str = ETTIN_RERANKER_68M_V1.revision,
        context_chars: int = 360,
        entity_contexts: int = 3,
        model_path: str | None = None,
        device: str | None = None,
        model: Any | None = None,
    ) -> None:
        if not revision:
            raise ValueError("an exact model revision is required for qualification")
        if context_chars < 32:
            raise ValueError("context_chars must be >= 32")
        if entity_contexts < 1:
            raise ValueError("entity_contexts must be >= 1")
        self.model_id = model_id
        self.revision = revision
        self.context_chars = context_chars
        self.entity_contexts = entity_contexts
        self.model_path = model_path
        self.device = device
        self._model = model

    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id=self.model_id,
            revision=self.revision,
            adapter="sentence_transformers.CrossEncoder",
            license_id=ETTIN_RERANKER_68M_V1.license_id if self.model_id == ETTIN_RERANKER_68M_V1.model_id else None,
        )

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover - heavyweight optional path
                raise RuntimeError(
                    "Ettin qualification dependency is intentionally outside normal CI; install the dedicated V3 Ettin qualification environment"
                ) from exc
            model_source = self.model_path or self.model_id
            kwargs: dict[str, Any] = {"trust_remote_code": False}
            if self.model_path is None:
                kwargs["revision"] = self.revision
            if self.device is not None:
                kwargs["device"] = self.device
            self._model = CrossEncoder(model_source, **kwargs)
        return self._model

    def _entity(self, candidate: IdentityCandidate, entities: Sequence[Entity]) -> Entity:
        for entity in entities:
            if entity.entity_id == candidate.candidate_entity_id:
                return entity
        raise ValueError(f"candidate entity not found: {candidate.candidate_entity_id}")

    def _mention_context(self, mention: Mention, context: IdentityScoringContext) -> str:
        span = mention.evidence.span
        start = max(0, span.start_offset - self.context_chars)
        end = min(len(context.source.normalized_text), span.end_offset + self.context_chars)
        return context.source.normalized_text[start:end]

    def _representative_mentions(self, entity: Entity, context: IdentityScoringContext) -> tuple[Mention, ...]:
        rows = sorted(
            (
                context.mention_by_id[mention_id]
                for mention_id in entity.mention_ids
                if mention_id in context.mention_by_id
            ),
            key=lambda item: (item.evidence.span.start_offset, item.mention_id),
        )
        if len(rows) <= self.entity_contexts:
            return tuple(rows)
        if self.entity_contexts == 1:
            return (rows[-1],)
        indices = {
            round(index * (len(rows) - 1) / (self.entity_contexts - 1))
            for index in range(self.entity_contexts)
        }
        return tuple(rows[index] for index in sorted(indices))

    def score(
        self,
        *,
        mention: Mention,
        candidate: IdentityCandidate,
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> IdentityScore:
        entity = self._entity(candidate, existing_entities)
        aliases = ", ".join(entity.aliases)
        query = f"Mention: {mention.text}\nContext: {self._mention_context(mention, context)}"
        representative = self._representative_mentions(entity, context)
        known_contexts = "\n".join(
            f"{index}. {self._mention_context(item, context)}"
            for index, item in enumerate(representative, start=1)
        )
        passage = (
            f"Candidate character: {entity.canonical_name or ''}\n"
            f"Aliases: {aliases}\n"
            f"Known contexts:\n{known_contexts}"
        )
        raw = self._load_model().predict([(query, passage)])
        value = float(raw[0])
        return IdentityScore(
            mention_id=mention.mention_id,
            candidate_entity_id=entity.entity_id,
            score=value,
            scorer=self.descriptor,
        )
