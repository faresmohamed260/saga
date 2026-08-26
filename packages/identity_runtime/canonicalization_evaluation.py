"""Portable pairwise evaluation for identity canonicalization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .review import review_identity_clusters


class IdentityPairEvaluation(BaseModel):
    left_cluster_id: int
    right_cluster_id: int
    expected_same: bool
    predicted_same: bool


class IdentityCanonicalizationMetrics(BaseModel):
    labeled_pair_count: int = 0
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    over_merge_rate: float = 0.0
    fragmentation_rate: float = 0.0
    contamination_rate: float = 0.0
    details: list[IdentityPairEvaluation] = Field(default_factory=list)


def evaluate_identity_canonicalization(dataset: dict[str, Any]) -> IdentityCanonicalizationMetrics:
    review = review_identity_clusters(
        raw_clusters=list(dataset.get("clusters") or []),
        chapters=list(dataset.get("chapters") or []),
        scenes=list(dataset.get("scenes") or []),
    )
    canonical_by_source: dict[int, int] = {}
    for canonical_index, item in enumerate(review.reviewed_clusters):
        if not item.keep_cluster:
            continue
        for source_id in item.source_cluster_ids:
            canonical_by_source[int(source_id)] = canonical_index

    details: list[IdentityPairEvaluation] = []
    for expected_same, key in ((True, "same_identity_pairs"), (False, "different_identity_pairs")):
        for raw_pair in list(dataset.get(key) or []):
            left, right = int(raw_pair[0]), int(raw_pair[1])
            predicted_same = (
                left in canonical_by_source
                and right in canonical_by_source
                and canonical_by_source[left] == canonical_by_source[right]
            )
            details.append(
                IdentityPairEvaluation(
                    left_cluster_id=left,
                    right_cluster_id=right,
                    expected_same=expected_same,
                    predicted_same=predicted_same,
                )
            )

    true_positive = sum(item.expected_same and item.predicted_same for item in details)
    false_positive = sum(not item.expected_same and item.predicted_same for item in details)
    false_negative = sum(item.expected_same and not item.predicted_same for item in details)
    true_negative = sum(not item.expected_same and not item.predicted_same for item in details)
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return IdentityCanonicalizationMetrics(
        labeled_pair_count=len(details),
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        precision=precision,
        recall=recall,
        f1=_ratio(2 * precision * recall, precision + recall),
        over_merge_rate=_ratio(false_positive, true_positive + false_positive),
        fragmentation_rate=_ratio(false_negative, true_positive + false_negative),
        contamination_rate=_ratio(false_positive, false_positive + true_negative),
        details=details,
    )


def _ratio(numerator: float, denominator: float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0
