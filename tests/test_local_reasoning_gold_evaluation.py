from benchmarks.reasoning.gold_evaluation import build_gold_evaluator, evaluate_gold_payload
from packages.reasoning_runtime import QualificationTask


def test_gold_entity_metrics_measure_precision_recall_and_f1():
    metrics = evaluate_gold_payload(
        family="canon_entities",
        payload={"entities": [{"name": "Silver Key"}, {"name": "Invented Tower"}]},
        annotation={"items": [
            {"aliases": ["silver key", "the silver key"]},
            {"aliases": ["gate"]},
        ]},
        source_text="Mara carried the silver key through the gate.",
    )
    assert metrics["gold_precision"] == 0.5
    assert metrics["gold_recall"] == 0.5
    assert metrics["gold_f1"] == 0.5


def test_gold_event_metrics_match_local_source_offsets_without_stored_quotes():
    source = "Mara entered the hall. Rowan locked the gate."
    normalized_start = source.casefold().index("rowan")
    metrics = evaluate_gold_payload(
        family="canon_events",
        payload={"events": [{"evidence_quote": "Rowan locked the gate."}]},
        annotation={"items": [{
            "normalized_evidence_spans": [[normalized_start, len(source)]],
        }]},
        source_text=source,
    )
    assert metrics["gold_precision"] == 1.0
    assert metrics["gold_recall"] == 1.0


def test_gold_evaluator_fails_closed_when_annotation_is_missing():
    evaluator = build_gold_evaluator({"annotations": []})
    task = QualificationTask(
        task_id="canon_entities:case", operation="json", prompt="extract",
        metadata={
            "family": "canon_entities", "case_id": "case", "result_key": "entities",
            "minimum_items": 1, "source_text": "A silver key.",
        },
    )
    result = evaluator(task, {"payload": {"entities": [{
        "name": "silver key", "evidence_quote": "A silver key.",
    }]}})
    assert result.accepted is False
    assert result.metrics["gold_available"] is False
