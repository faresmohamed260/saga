"""Evaluation metrics for narrative attribution quality."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field


class AttributionGoldCase(BaseModel):
    case_id: str
    scene_id: str = ""
    title_contains: str = ""
    title_any_contains: list[str] = Field(default_factory=list)
    expected_participant_refs: list[str] = Field(default_factory=list)
    forbidden_participant_refs: list[str] = Field(default_factory=list)
    narrator_character_id: str = ""


class AttributionEvaluationResult(BaseModel):
    case_count: int = 0
    matched_case_count: int = 0
    participant_precision: float = 0.0
    participant_recall: float = 0.0
    attribution_f1: float = 0.0
    narrator_attribution_accuracy: float = 0.0
    unsupported_ref_rate: float = 0.0
    contamination_rate: float = 0.0
    details: list[dict[str, Any]] = Field(default_factory=list)


def evaluate_attribution(
    *,
    events: list[dict[str, Any]],
    gold_cases: list[AttributionGoldCase],
    valid_character_refs: set[str],
) -> AttributionEvaluationResult:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    unsupported_refs = 0
    total_refs = 0
    contamination_cases = 0
    narrator_correct = 0
    narrator_total = 0
    matched_cases = 0
    details: list[dict[str, Any]] = []
    for gold in gold_cases:
        event = _match_event(events, gold)
        actual = set(str(ref) for ref in list((event or {}).get("participant_refs") or []) if str(ref or "").strip())
        expected = set(gold.expected_participant_refs)
        forbidden = set(gold.forbidden_participant_refs)
        matched = event is not None
        if matched:
            matched_cases += 1
        true_positive += len(actual.intersection(expected))
        false_positive += len(actual - expected)
        false_negative += len(expected - actual)
        total_refs += len(actual)
        unsupported_refs += len([ref for ref in actual if ref not in valid_character_refs])
        contaminated = bool(actual.intersection(forbidden))
        if contaminated:
            contamination_cases += 1
        if gold.narrator_character_id:
            narrator_total += 1
            if gold.narrator_character_id in actual:
                narrator_correct += 1
        details.append(
            {
                "case_id": gold.case_id,
                "matched": matched,
                "event_id": str((event or {}).get("event_id") or ""),
                "title": str((event or {}).get("title") or ""),
                "expected": sorted(expected),
                "actual": sorted(actual),
                "missing": sorted(expected - actual),
                "extra": sorted(actual - expected),
                "forbidden_present": sorted(actual.intersection(forbidden)),
            }
        )
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return AttributionEvaluationResult(
        case_count=len(gold_cases),
        matched_case_count=matched_cases,
        participant_precision=round(precision, 4),
        participant_recall=round(recall, 4),
        attribution_f1=round(f1, 4),
        narrator_attribution_accuracy=round(narrator_correct / max(narrator_total, 1), 4),
        unsupported_ref_rate=round(unsupported_refs / max(total_refs, 1), 4),
        contamination_rate=round(contamination_cases / max(len(gold_cases), 1), 4),
        details=details,
    )


def _match_event(events: list[dict[str, Any]], gold: AttributionGoldCase) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for event in events:
        if gold.scene_id and str(event.get("scene_id") or "") != gold.scene_id:
            continue
        searchable_text = f"{event.get('title') or ''}\n{event.get('summary') or ''}".casefold()
        if gold.title_contains and gold.title_contains.casefold() not in searchable_text:
            continue
        title_needles = [item.casefold() for item in list(gold.title_any_contains or []) if str(item or "").strip()]
        if title_needles and not any(_needle_matches_text(needle, searchable_text) for needle in title_needles):
            continue
        candidates.append(event)
    if not candidates:
        return None
    expected = set(gold.expected_participant_refs)
    forbidden = set(gold.forbidden_participant_refs)
    return max(candidates, key=lambda event: _event_match_score(event, expected=expected, forbidden=forbidden))


def _event_match_score(event: dict[str, Any], *, expected: set[str], forbidden: set[str]) -> tuple[int, int, int]:
    actual = set(str(ref) for ref in list(event.get("participant_refs") or []) if str(ref or "").strip())
    expected_hits = len(actual.intersection(expected))
    forbidden_hits = len(actual.intersection(forbidden))
    extras = len(actual - expected)
    return (expected_hits, -forbidden_hits, -extras)


def _needle_matches_text(needle: str, text: str) -> bool:
    if needle in text:
        return True
    needle_tokens = [_token_stem(token) for token in needle.replace("-", " ").split() if len(token) > 2]
    needle_tokens = [token for token in needle_tokens if token not in {"the", "and", "for", "with", "under"}]
    if len(needle_tokens) < 2:
        return False
    text_tokens = {_token_stem(token) for token in text.replace("-", " ").split() if len(token) > 2}
    unique_needles = set(needle_tokens)
    required_matches = max(2, math.ceil(len(unique_needles) * 0.6))
    return len(unique_needles.intersection(text_tokens)) >= required_matches


def _token_stem(token: str) -> str:
    cleaned = "".join(ch for ch in token.casefold() if ch.isalnum())
    if cleaned in {"marry", "marries", "married", "marriage"}:
        return "marry"
    if cleaned.endswith("ing") and len(cleaned) > 5:
        return cleaned[:-3]
    if cleaned.endswith("ed") and len(cleaned) > 4:
        return cleaned[:-2]
    if cleaned.endswith("s") and len(cleaned) > 4:
        return cleaned[:-1]
    return cleaned
