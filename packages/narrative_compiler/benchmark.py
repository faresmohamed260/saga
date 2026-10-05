"""Model-independent identity benchmark contract for V2/V3 comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .ir import Entity


@dataclass(frozen=True, slots=True)
class IdentityMetrics:
    evaluated_mentions: int
    predicted_linked_mentions: int
    mention_attachment_precision: float
    mention_attachment_recall: float
    incorrect_merge_rate: float
    fragmentation_rate: float
    unresolved_rate: float


def _pairs(cluster: Sequence[str]) -> set[tuple[str, str]]:
    ordered = sorted(set(cluster))
    return {(ordered[i], ordered[j]) for i in range(len(ordered)) for j in range(i + 1, len(ordered))}


def score_identity_clusters(
    *,
    gold_entity_by_mention: Mapping[str, str],
    predicted_entities: Sequence[Entity],
    unresolved_mention_ids: Sequence[str] = (),
) -> IdentityMetrics:
    """Score predicted clusters without rewarding unsupported singleton creation.

    Pairwise attachment measures links. Incorrect-merge rate is the fraction of
    predicted links crossing gold identities. Fragmentation is the fraction of
    gold-linked pairs that remain separated.
    """

    gold_mentions = set(gold_entity_by_mention)
    predicted_pairs: set[tuple[str, str]] = set()
    predicted_mentions: set[str] = set()
    for entity in predicted_entities:
        in_scope = [mention_id for mention_id in entity.mention_ids if mention_id in gold_mentions]
        predicted_mentions.update(in_scope)
        predicted_pairs.update(_pairs(in_scope))

    gold_clusters: dict[str, list[str]] = {}
    for mention_id, gold_id in gold_entity_by_mention.items():
        gold_clusters.setdefault(gold_id, []).append(mention_id)
    gold_pairs = set().union(*(_pairs(cluster) for cluster in gold_clusters.values())) if gold_clusters else set()

    correct_pairs = predicted_pairs & gold_pairs
    wrong_pairs = predicted_pairs - gold_pairs
    missed_pairs = gold_pairs - predicted_pairs

    precision = len(correct_pairs) / len(predicted_pairs) if predicted_pairs else 1.0
    recall = len(correct_pairs) / len(gold_pairs) if gold_pairs else 1.0
    incorrect_merge = len(wrong_pairs) / len(predicted_pairs) if predicted_pairs else 0.0
    fragmentation = len(missed_pairs) / len(gold_pairs) if gold_pairs else 0.0
    unresolved = len(set(unresolved_mention_ids) & gold_mentions) / len(gold_mentions) if gold_mentions else 0.0

    return IdentityMetrics(
        evaluated_mentions=len(gold_mentions),
        predicted_linked_mentions=len(predicted_mentions),
        mention_attachment_precision=precision,
        mention_attachment_recall=recall,
        incorrect_merge_rate=incorrect_merge,
        fragmentation_rate=fragmentation,
        unresolved_rate=unresolved,
    )
