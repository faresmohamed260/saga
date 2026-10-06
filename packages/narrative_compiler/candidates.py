"""Model-light candidate generation for the V3 global identity linker."""

from __future__ import annotations

import re
from typing import Sequence

from .ir import Entity, Mention
from .linker import normalized_surface
from .stages import IdentityCandidate, IdentityScoringContext


_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(value) if token}


def _lexical_features(mention: Mention, entity: Entity) -> dict[str, float]:
    mention_surface = normalized_surface(mention.text)
    mention_tokens = _tokens(mention.text)
    surfaces = [entity.canonical_name or "", *entity.aliases]
    normalized = {normalized_surface(surface) for surface in surfaces if surface}
    exact = 1.0 if mention_surface and mention_surface in normalized else 0.0
    candidate_tokens = set().union(*(_tokens(surface) for surface in surfaces)) if surfaces else set()
    union = mention_tokens | candidate_tokens
    token_jaccard = len(mention_tokens & candidate_tokens) / len(union) if union else 0.0
    containment = 1.0 if mention_surface and any(
        mention_surface in surface or surface in mention_surface for surface in normalized if surface
    ) else 0.0
    lexical = max(exact, token_jaccard, 0.85 * containment)
    return {
        "exact_surface": exact,
        "token_jaccard": token_jaccard,
        "surface_containment": containment,
        "lexical_score": lexical,
    }


class LexicalIdentityCandidateGenerator:
    """Retrieve plausible entity candidates without making a merge decision.

    Zero-overlap entities are excluded by default. The original foundation
    implementation accidentally allowed them when ``minimum_overlap == 0``;
    that made lexical retrieval behave like an arbitrary entity sampler.
    """

    def __init__(self, *, top_k: int = 8, minimum_overlap: float = 0.0) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not 0.0 <= minimum_overlap <= 1.0:
            raise ValueError("minimum_overlap must be between 0 and 1")
        self.top_k = top_k
        self.minimum_overlap = minimum_overlap

    def generate(
        self,
        *,
        mention: Mention,
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> Sequence[IdentityCandidate]:
        del context  # lexical retrieval is intentionally context-free
        ranked: list[tuple[float, IdentityCandidate]] = []

        for entity in existing_entities:
            if entity.entity_type is not mention.entity_type:
                continue
            features = _lexical_features(mention, entity)
            lexical = features["lexical_score"]
            if features["exact_surface"] == 0.0 and lexical <= self.minimum_overlap:
                continue
            candidate = IdentityCandidate(
                mention_id=mention.mention_id,
                candidate_entity_id=entity.entity_id,
                features=features,
            )
            ranked.append((lexical, candidate))

        ranked.sort(key=lambda item: (-item[0], item[1].candidate_entity_id))
        return tuple(candidate for _, candidate in ranked[: self.top_k])


class HybridIdentityCandidateGenerator:
    """Union lexical and recent-discourse candidates for high-recall ranking.

    The generator deliberately does not decide identity. It reserves part of the
    candidate budget for lexical matches and part for recently mentioned
    characters so pronouns/nominals can reach a semantic scorer even when their
    surface form has no lexical overlap with a character name.
    """

    def __init__(
        self,
        *,
        top_k: int = 8,
        lexical_k: int = 4,
        recent_k: int = 4,
        minimum_overlap: float = 0.0,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if lexical_k < 0 or recent_k < 0:
            raise ValueError("candidate quotas must be >= 0")
        if lexical_k + recent_k > top_k:
            raise ValueError("lexical_k + recent_k must be <= top_k")
        if lexical_k + recent_k == 0:
            raise ValueError("at least one candidate quota must be positive")
        self.top_k = top_k
        self.lexical_k = lexical_k
        self.recent_k = recent_k
        self.minimum_overlap = minimum_overlap

    def generate(
        self,
        *,
        mention: Mention,
        existing_entities: Sequence[Entity],
        context: IdentityScoringContext,
    ) -> Sequence[IdentityCandidate]:
        selected: dict[str, dict[str, float]] = {}

        if self.lexical_k:
            lexical = LexicalIdentityCandidateGenerator(
                top_k=self.lexical_k,
                minimum_overlap=self.minimum_overlap,
            ).generate(
                mention=mention,
                existing_entities=existing_entities,
                context=context,
            )
            for candidate in lexical:
                selected[candidate.candidate_entity_id] = dict(candidate.features)

        recent_rows: list[tuple[int, str, Entity, int]] = []
        for entity in existing_entities:
            if entity.entity_type is not mention.entity_type:
                continue
            prior_mentions = [
                context.mention_by_id[mention_id]
                for mention_id in entity.mention_ids
                if mention_id in context.mention_by_id
            ]
            if not prior_mentions:
                continue
            last_offset = max(item.evidence.span.end_offset for item in prior_mentions)
            char_distance = max(0, mention.evidence.span.start_offset - last_offset)
            recent_rows.append((-last_offset, entity.entity_id, entity, char_distance))

        recent_rows.sort(key=lambda item: (item[0], item[1]))
        for rank, (_, entity_id, entity, char_distance) in enumerate(recent_rows[: self.recent_k], start=1):
            features = selected.get(entity_id, _lexical_features(mention, entity))
            features = dict(features)
            features.update(
                {
                    "recent_rank": float(rank),
                    "char_distance": float(char_distance),
                    "prior_mention_count": float(len(entity.mention_ids)),
                }
            )
            selected[entity_id] = features

        entity_ids = {entity.entity_id for entity in existing_entities}
        candidates = [
            IdentityCandidate(
                mention_id=mention.mention_id,
                candidate_entity_id=entity_id,
                features=features,
            )
            for entity_id, features in selected.items()
            if entity_id in entity_ids
        ]
        candidates.sort(
            key=lambda item: (
                -item.features.get("exact_surface", 0.0),
                -item.features.get("lexical_score", 0.0),
                item.features.get("recent_rank", float("inf")),
                item.candidate_entity_id,
            )
        )
        return tuple(candidates[: self.top_k])
