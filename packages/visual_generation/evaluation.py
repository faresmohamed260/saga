"""Reusable labeled evaluation for visual quality decisions."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from packages.visual_generation.policy import decide_visual_quality


class VisualQualityEvaluationMetrics(BaseModel):
    case_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_accept_rate: float = 0.0
    false_reject_rate: float = 0.0
    exact_outcome_accuracy: float = 0.0
    per_defect_recall: dict[str, float] = Field(default_factory=dict)
    details: list[dict[str, Any]] = Field(default_factory=list)


def evaluate_visual_quality_policy(dataset: dict[str, Any], *, use_existing_decisions: bool = False) -> VisualQualityEvaluationMetrics:
    details: list[dict[str, Any]] = []
    expected_defects: dict[str, int] = defaultdict(int)
    detected_defects: dict[str, int] = defaultdict(int)
    for case in list(dataset.get("cases") or []):
        expected = str(case.get("expected_outcome") or "rejected")
        if use_existing_decisions:
            predicted = "accepted" if case.get("existing_accepted") is True else "rejected"
            predicted_categories = set()
        else:
            decision = decide_visual_quality(
                technical_passed=case.get("technical_passed") is True,
                scores=dict(case.get("scores") or {}),
                issues=list(case.get("issues") or []),
                hard_violations=list(case.get("hard_violations") or []),
                defect_observations=list(case.get("defect_observations") or []),
                evaluator_error=case.get("evaluator_error") is True,
            )
            predicted = decision.outcome
            predicted_categories = {item.category for item in decision.defects}
        for category in set(case.get("expected_defects") or []):
            expected_defects[category] += 1
            if category in predicted_categories:
                detected_defects[category] += 1
        details.append({
            "case_id": str(case.get("case_id") or ""), "target_type": str(case.get("target_type") or ""),
            "expected": expected, "predicted": predicted,
        })

    expected_unsafe = [item for item in details if item["expected"] != "accepted"]
    expected_safe = [item for item in details if item["expected"] == "accepted"]
    predicted_unsafe = [item for item in details if item["predicted"] != "accepted"]
    true_positive = sum(item["expected"] != "accepted" and item["predicted"] != "accepted" for item in details)
    false_positive = sum(item["expected"] == "accepted" and item["predicted"] != "accepted" for item in details)
    false_negative = sum(item["expected"] != "accepted" and item["predicted"] == "accepted" for item in details)
    precision = _ratio(true_positive, len(predicted_unsafe))
    recall = _ratio(true_positive, len(expected_unsafe))
    return VisualQualityEvaluationMetrics(
        case_count=len(details), precision=precision, recall=recall,
        f1=_ratio(2 * precision * recall, precision + recall),
        false_accept_rate=_ratio(false_negative, len(expected_unsafe)),
        false_reject_rate=_ratio(false_positive, len(expected_safe)),
        exact_outcome_accuracy=_ratio(sum(item["expected"] == item["predicted"] for item in details), len(details)),
        per_defect_recall={key: _ratio(detected_defects[key], count) for key, count in sorted(expected_defects.items())},
        details=details,
    )


def _ratio(numerator: float, denominator: float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0
