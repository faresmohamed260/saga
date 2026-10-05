"""Model-light candidate generation for the V3 global identity linker."""

from __future__ import annotations

import re
from typing import Sequence

from .ir import Entity, Mention
from .linker import normalized_surface
from .stages import IdentityCandidate


_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(value) if token}


class LexicalIdentityCandidateGenerator:
    """Retrieve plausible entity candidates without making a merge decision.

    This stage intentionally optimizes candidate recall. Final acceptance remains
    the responsibility of a scorer plus S.A.G.A.-owned constraints/policy.
    """

    def __init__(self, *, top_k: int = 8, minimum_overlap: float = 0.0) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not 0.0 <= minimum_overlap <= 1.0:
            raise ValueError("minimum_overlap must be between 0 and 1")
        self.top_k = top_k
        self.minimum_overlap = minimum_overlap

    def generate(self, *, mention: Mention, existing_entities: Sequence[Entity]) -> Sequence[IdentityCandidate]:
        mention_surface = normalized_surface(mention.text)
        mention_tokens = _tokens(mention.text)
        ranked: list[tuple[float, IdentityCandidate]] = []

        for entity in existing_entities:
            if entity.entity_type is not mention.entity_type:
                continue
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
            if lexical < self.minimum_overlap and exact == 0.0:
                continue
            candidate = IdentityCandidate(
                mention_id=mention.mention_id,
                candidate_entity_id=entity.entity_id,
                features={
                    "exact_surface": exact,
                    "token_jaccard": token_jaccard,
                    "surface_containment": containment,
                    "lexical_score": lexical,
                },
            )
            ranked.append((lexical, candidate))

        ranked.sort(key=lambda item: (-item[0], item[1].candidate_entity_id))
        return tuple(candidate for _, candidate in ranked[: self.top_k])
