"""Gold-backed extraction metrics without storing copyrighted source passages."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from packages.reasoning_runtime import QualificationEvaluation, QualificationTask

from .task_suite import evaluate_task


EXTRACTION_FAMILIES = {"canon_events", "canon_entities", "canon_relationships"}


def build_gold_evaluator(
    gold: dict[str, Any], *, minimum_precision: float = 0.9,
    minimum_recall: float = 0.8,
):
    annotations = {
        (str(item["family"]), str(item["case_id"])): item
        for item in list(gold.get("annotations") or [])
    }

    def evaluator(task: QualificationTask, output: dict[str, Any]) -> QualificationEvaluation:
        base = evaluate_task(task, output)
        family = str(task.metadata.get("family") or "")
        if family not in EXTRACTION_FAMILIES:
            return base
        key = (family, str(task.metadata.get("case_id") or ""))
        annotation = annotations.get(key)
        if annotation is None:
            return QualificationEvaluation(
                accepted=False, metrics={**base.metrics, "gold_available": False},
                reasons=[*base.reasons, "gold_annotation_missing"],
            )
        if str(annotation.get("review_status") or "") != "reviewed":
            return QualificationEvaluation(
                accepted=False,
                metrics={**base.metrics, "gold_available": True, "gold_reviewed": False},
                reasons=[*base.reasons, "gold_annotation_not_reviewed"],
            )
        if not list(annotation.get("items") or []):
            return QualificationEvaluation(
                accepted=False,
                metrics={**base.metrics, "gold_available": True, "gold_reviewed": True},
                reasons=[*base.reasons, "gold_annotation_empty"],
            )
        payload = output.get("payload") if isinstance(output, dict) else None
        metrics = evaluate_gold_payload(
            family=family, payload=payload if isinstance(payload, dict) else {},
            annotation=annotation, source_text=str(task.metadata.get("source_text") or ""),
        )
        accepted = (
            base.accepted
            and float(metrics["gold_precision"]) >= minimum_precision
            and float(metrics["gold_recall"]) >= minimum_recall
        )
        return QualificationEvaluation(
            accepted=accepted,
            metrics={**base.metrics, **metrics, "gold_available": True, "gold_reviewed": True},
            reasons=base.reasons if accepted else [*base.reasons, "gold_quality_gate_failed"],
        )

    return evaluator


def evaluate_gold_payload(
    *, family: str, payload: dict[str, Any], annotation: dict[str, Any],
    source_text: str,
) -> dict[str, float | int]:
    result_key = {
        "canon_events": "events",
        "canon_entities": "entities",
        "canon_relationships": "relationships",
    }[family]
    predictions = [item for item in list(payload.get(result_key) or []) if isinstance(item, dict)]
    gold_items = [item for item in list(annotation.get("items") or []) if isinstance(item, dict)]
    matched_predictions, matched_gold = _match_predictions(
        family, predictions, gold_items, source_text,
    )
    precision = len(matched_predictions) / max(1, len(predictions))
    recall = len(matched_gold) / max(1, len(gold_items))
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "gold_item_count": len(gold_items),
        "gold_matched_items": len(matched_gold),
        "gold_precision": precision,
        "gold_recall": recall,
        "gold_f1": f1,
    }


def _match_predictions(
    family: str, predictions: list[dict[str, Any]], gold_items: list[dict[str, Any]],
    source_text: str,
) -> tuple[set[int], set[int]]:
    matched_predictions: set[int] = set()
    matched_gold: set[int] = set()
    normalized_source = _normalize(source_text)
    for prediction_index, prediction in enumerate(predictions):
        for gold_index, gold_item in enumerate(gold_items):
            if gold_index in matched_gold:
                continue
            if _matches(family, prediction, gold_item, normalized_source):
                matched_predictions.add(prediction_index)
                matched_gold.add(gold_index)
                break
    return matched_predictions, matched_gold


def _matches(
    family: str, prediction: dict[str, Any], gold_item: dict[str, Any],
    normalized_source: str,
) -> bool:
    if family == "canon_entities":
        return _normalize(str(prediction.get("name") or "")) in _aliases(gold_item)
    if family == "canon_relationships":
        return (
            _normalize(str(prediction.get("source") or "")) in _aliases(gold_item, "source_aliases")
            and _normalize(str(prediction.get("target") or "")) in _aliases(gold_item, "target_aliases")
            and _normalize(str(prediction.get("relationship_type") or "")) in _aliases(gold_item, "type_aliases")
        )
    quote = _normalize(str(prediction.get("evidence_quote") or ""))
    start = normalized_source.find(quote) if quote else -1
    if start < 0:
        return False
    predicted_span = (start, start + len(quote))
    for span in list(gold_item.get("normalized_evidence_spans") or []):
        if len(span) == 2 and _span_overlap(predicted_span, (int(span[0]), int(span[1]))) >= 0.6:
            return True
    return False


def _aliases(item: dict[str, Any], key: str = "aliases") -> set[str]:
    return {_normalize(str(value)) for value in list(item.get(key) or []) if str(value).strip()}


def _span_overlap(left: tuple[int, int], right: tuple[int, int]) -> float:
    overlap = max(0, min(left[1], right[1]) - max(left[0], right[0]))
    return overlap / max(1, min(left[1] - left[0], right[1] - right[0]))


def _normalize(value: str) -> str:
    punctuation = str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u00a0": " ",
    })
    canonical = unicodedata.normalize("NFKC", str(value or "")).translate(punctuation)
    return re.sub(r"\s+", " ", canonical).strip().casefold()
