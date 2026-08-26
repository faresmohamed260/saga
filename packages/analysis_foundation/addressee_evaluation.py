"""Portable evaluation metrics for scene addressee resolution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from packages.analysis_foundation.contracts import SceneNarrativeGrounding


class AddresseeGoldCase(BaseModel):
    case_id: str
    scene_id: str
    category: Literal["explicit", "inferable", "unknown", "absent"]
    expected_character_ids: list[str] = Field(default_factory=list)
    evidence_note: str = ""


class AddresseeEvaluation(BaseModel):
    case_count: int = 0
    matched_case_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    coverage: float = 0.0
    unsupported_attribution_rate: float = 0.0
    contamination_rate: float = 0.0
    details: list[dict[str, object]] = Field(default_factory=list)


def evaluate_addressees(
    *,
    groundings: list[SceneNarrativeGrounding],
    gold_cases: list[AddresseeGoldCase],
    valid_character_ids: set[str],
) -> AddresseeEvaluation:
    by_scene = {item.scene_id: item for item in groundings}
    true_positive = false_positive = false_negative = 0
    predicted_refs = unsupported_refs = predicted_cases = contaminated_cases = 0
    details: list[dict[str, object]] = []
    for gold in gold_cases:
        grounding = by_scene.get(gold.scene_id)
        actual = set(grounding.addressee_character_ids if grounding else [])
        expected = set(gold.expected_character_ids)
        extras = actual - expected
        missing = expected - actual
        true_positive += len(actual & expected)
        false_positive += len(extras)
        false_negative += len(missing)
        predicted_refs += len(actual)
        unsupported_refs += len(actual - valid_character_ids)
        predicted_cases += int(bool(actual))
        contaminated_cases += int(bool(extras))
        details.append(
            {
                "case_id": gold.case_id,
                "scene_id": gold.scene_id,
                "category": gold.category,
                "evidence_note": gold.evidence_note,
                "matched": grounding is not None,
                "expected": sorted(expected),
                "actual": sorted(actual),
                "missing": sorted(missing),
                "extra": sorted(extras),
            }
        )
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    case_count = len(gold_cases)
    return AddresseeEvaluation(
        case_count=case_count,
        matched_case_count=sum(1 for item in details if item["matched"]),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        coverage=round(predicted_cases / max(case_count, 1), 4),
        unsupported_attribution_rate=round(unsupported_refs / max(predicted_refs, 1), 4),
        contamination_rate=round(contaminated_cases / max(case_count, 1), 4),
        details=details,
    )
