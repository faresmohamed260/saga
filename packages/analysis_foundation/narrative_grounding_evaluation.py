"""Portable quality evaluation for scene perspective and narrator grounding."""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.analysis_foundation.contracts import SceneNarrativeGrounding


class NarrativeGroundingGoldCase(BaseModel):
    case_id: str
    scene_id: str
    expected_perspective: str
    expected_narrator_character_id: str = ""


class NarrativeGroundingEvaluation(BaseModel):
    case_count: int = 0
    matched_case_count: int = 0
    perspective_precision: float = 0.0
    perspective_recall: float = 0.0
    perspective_f1: float = 0.0
    narrator_precision: float | None = None
    narrator_recall: float | None = None
    narrator_f1: float | None = None
    narrator_applicable_case_count: int = 0
    narrator_coverage: float = 0.0
    contradiction_rate: float = 0.0
    details: list[dict[str, object]] = Field(default_factory=list)


def evaluate_narrative_grounding(
    *,
    groundings: list[SceneNarrativeGrounding],
    gold_cases: list[NarrativeGroundingGoldCase],
) -> NarrativeGroundingEvaluation:
    by_scene = {item.scene_id: item for item in groundings}
    perspective_correct = 0
    narrator_tp = 0
    narrator_fp = 0
    narrator_fn = 0
    narrator_predictions = 0
    narrator_applicable = 0
    contradictions = 0
    details: list[dict[str, object]] = []
    for gold in gold_cases:
        actual = by_scene.get(gold.scene_id)
        perspective_match = bool(actual and actual.perspective == gold.expected_perspective)
        perspective_correct += int(perspective_match)
        expected_narrator = gold.expected_narrator_character_id
        narrator_applicable += int(bool(expected_narrator))
        actual_narrator = actual.narrator_character_id if actual else ""
        narrator_predictions += int(bool(actual_narrator))
        narrator_tp += int(bool(expected_narrator) and actual_narrator == expected_narrator)
        narrator_fp += int(bool(actual_narrator) and actual_narrator != expected_narrator)
        narrator_fn += int(bool(expected_narrator) and actual_narrator != expected_narrator)
        contradicted = not perspective_match or actual_narrator != expected_narrator
        contradictions += int(contradicted)
        details.append(
            {
                "case_id": gold.case_id,
                "scene_id": gold.scene_id,
                "matched": actual is not None,
                "expected_perspective": gold.expected_perspective,
                "actual_perspective": actual.perspective if actual else "",
                "expected_narrator_character_id": expected_narrator,
                "actual_narrator_character_id": actual_narrator,
                "contradicted": contradicted,
            }
        )
    count = len(gold_cases)
    perspective_score = perspective_correct / max(count, 1)
    narrator_precision = (
        narrator_tp / (narrator_tp + narrator_fp)
        if narrator_tp + narrator_fp
        else None
    )
    narrator_recall = (
        narrator_tp / (narrator_tp + narrator_fn)
        if narrator_tp + narrator_fn
        else None
    )
    narrator_f1 = (
        2 * narrator_precision * narrator_recall / max(narrator_precision + narrator_recall, 1e-9)
        if narrator_precision is not None and narrator_recall is not None
        else None
    )
    return NarrativeGroundingEvaluation(
        case_count=count,
        matched_case_count=sum(1 for item in details if item["matched"]),
        perspective_precision=round(perspective_score, 4),
        perspective_recall=round(perspective_score, 4),
        perspective_f1=round(perspective_score, 4),
        narrator_precision=round(narrator_precision, 4) if narrator_precision is not None else None,
        narrator_recall=round(narrator_recall, 4) if narrator_recall is not None else None,
        narrator_f1=round(narrator_f1, 4) if narrator_f1 is not None else None,
        narrator_applicable_case_count=narrator_applicable,
        narrator_coverage=round(narrator_predictions / max(count, 1), 4),
        contradiction_rate=round(contradictions / max(count, 1), 4),
        details=details,
    )
