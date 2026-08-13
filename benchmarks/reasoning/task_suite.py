"""SAGA task definitions and deterministic evaluators for local model qualification."""

from __future__ import annotations

import re
from typing import Any

from packages.reasoning_runtime import QualificationEvaluation, QualificationTask


TASK_FAMILIES = (
    "canon_events",
    "canon_entities",
    "canon_relationships",
    "character_world_modeling",
    "generation_planning",
    "narrative_generation",
    "continuity_grounding",
    "structured_json",
    "tool_use",
)


def build_tasks(corpus: dict[str, Any], *, scope: str = "full") -> list[QualificationTask]:
    cases = list(corpus.get("cases") or [])
    if len(cases) < len(TASK_FAMILIES):
        raise ValueError(f"Corpus requires at least {len(TASK_FAMILIES)} cases.")
    builders = {
        "canon_events": _canon_events,
        "canon_entities": _canon_entities,
        "canon_relationships": _canon_relationships,
        "character_world_modeling": _character_world,
        "generation_planning": _generation_planning,
        "narrative_generation": _narrative_generation,
        "continuity_grounding": _continuity_grounding,
        "structured_json": _structured_json,
        "tool_use": _tool_use,
    }
    if scope == "screening":
        return [builders[family](cases[index]) for index, family in enumerate(TASK_FAMILIES)]
    if scope != "full":
        raise ValueError("Task suite scope must be 'screening' or 'full'.")

    cases_by_source: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        cases_by_source.setdefault(str(case["source_id"]), []).append(case)
    if len(cases_by_source) < 3:
        raise ValueError("Full qualification requires cases from at least three books.")

    tasks: list[QualificationTask] = []
    for family_index, family in enumerate(TASK_FAMILIES):
        for source_cases in cases_by_source.values():
            case = source_cases[family_index % len(source_cases)]
            tasks.append(builders[family](case))
    return tasks


def evaluate_task(task: QualificationTask, output: dict[str, Any]) -> QualificationEvaluation:
    payload = output.get("payload")
    if not isinstance(payload, dict) or payload.get("error"):
        return QualificationEvaluation(accepted=False, metrics={"schema_valid": False}, reasons=["invalid_payload"])
    family = str(task.metadata.get("family") or "")
    if family == "structured_json":
        expected = dict(task.metadata["expected"])
        exact = all(payload.get(key) == value for key, value in expected.items())
        return QualificationEvaluation(accepted=exact, metrics={"schema_valid": True, "exact_match": exact}, reasons=[] if exact else ["metadata_mismatch"])
    if family == "tool_use":
        calls = list(payload.get("tool_calls") or [])
        expected = dict(task.metadata["expected_arguments"])
        exact = bool(calls) and calls[0].get("tool") == "fetch_passage" and calls[0].get("arguments") == expected
        return QualificationEvaluation(accepted=exact, metrics={"tool_call_valid": exact}, reasons=[] if exact else ["tool_call_mismatch"])
    if family == "continuity_grounding":
        rows = list(payload.get("classifications") or [])
        observed = {str(item.get("claim_id")): str(item.get("label")) for item in rows if isinstance(item, dict)}
        expected = {"supported": "supported", "fabricated": "unsupported"}
        correct = sum(observed.get(key) == value for key, value in expected.items())
        accuracy = correct / len(expected)
        precision = _evidence_precision(rows, str(task.metadata["source_text"]))
        return QualificationEvaluation(
            accepted=accuracy == 1.0 and precision == 1.0,
            metrics={"classification_accuracy": accuracy, "evidence_precision": precision, "hallucination_rate": 1.0 - precision},
            reasons=[] if accuracy == 1.0 and precision == 1.0 else ["grounding_failure"],
        )
    if family == "narrative_generation":
        prose = str(payload.get("prose") or "")
        rows = [{"evidence_quote": item} for item in list(payload.get("grounding_quotes") or [])]
        precision = _evidence_precision(rows, str(task.metadata["source_text"]))
        words = len(prose.split())
        accepted = words >= 120 and precision == 1.0 and bool(rows)
        return QualificationEvaluation(
            accepted=accepted,
            metrics={"word_count": words, "evidence_precision": precision, "hallucination_rate": 1.0 - precision},
            reasons=[] if accepted else ["narrative_contract_failed"],
        )
    key = str(task.metadata["result_key"])
    rows = list(payload.get(key) or [])
    precision = _evidence_precision(rows, str(task.metadata["source_text"]))
    minimum = int(task.metadata.get("minimum_items") or 1)
    coverage = min(1.0, len(rows) / minimum)
    accepted = len(rows) >= minimum and precision == 1.0
    return QualificationEvaluation(
        accepted=accepted,
        metrics={
            "schema_valid": True, "item_count": len(rows), "evidence_precision": precision,
            "minimum_item_coverage": coverage, "hallucination_rate": 1.0 - precision,
        },
        reasons=[] if accepted else ["evidence_or_completeness_failure"],
    )


def _canon_events(case: dict[str, Any]) -> QualificationTask:
    return _evidence_task(case, family="canon_events", result_key="events", minimum=2, item_properties={
        "title": {"type": "string"}, "summary": {"type": "string"}, "event_type": {"type": "string"},
    }, instruction="Extract distinct consequential events in chronological order.")


def _canon_entities(case: dict[str, Any]) -> QualificationTask:
    return _evidence_task(case, family="canon_entities", result_key="entities", minimum=3, item_properties={
        "name": {"type": "string"}, "entity_type": {"type": "string", "enum": ["location", "object", "creature", "organization", "artifact", "concept"]},
        "description": {"type": "string"},
    }, instruction="Extract grounded non-character entities only.")


def _canon_relationships(case: dict[str, Any]) -> QualificationTask:
    return _evidence_task(case, family="canon_relationships", result_key="relationships", minimum=2, item_properties={
        "source": {"type": "string"}, "target": {"type": "string"}, "relationship_type": {"type": "string"},
        "description": {"type": "string"},
    }, instruction="Extract explicit or strongly evidenced relationships between named participants or entities.")


def _character_world(case: dict[str, Any]) -> QualificationTask:
    return _evidence_task(case, family="character_world_modeling", result_key="observations", minimum=3, item_properties={
        "subject": {"type": "string"}, "observation_type": {"type": "string", "enum": ["character_trait", "character_state", "world_rule", "world_state"]},
        "description": {"type": "string"},
    }, instruction="Extract stable character traits/states and world rules/states. Do not infer beyond the passage.")


def _generation_planning(case: dict[str, Any]) -> QualificationTask:
    return _evidence_task(case, family="generation_planning", result_key="beats", minimum=3, item_properties={
        "beat_index": {"type": "integer"}, "objective": {"type": "string"}, "constraint": {"type": "string"},
    }, instruction="Plan three continuation beats that preserve passage facts. Every beat must cite a constraint from the passage.")


def _narrative_generation(case: dict[str, Any]) -> QualificationTask:
    schema = _schema("narrative_generation", {
        "prose": {"type": "string"},
        "grounding_quotes": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    }, ["prose", "grounding_quotes"])
    return QualificationTask(
        task_id=f"narrative_generation:{case['case_id']}", operation="json",
        prompt=f"Write a 120-220 word continuation consistent with the passage. Do not introduce unsupported named facts. Return prose and exact grounding_quotes copied from the passage.\n\nPASSAGE:\n{case['text']}",
        max_tokens=700, response_format=schema, expected_keys=["prose", "grounding_quotes"],
        metadata={"family": "narrative_generation", "source_text": case["text"], "case_id": case["case_id"]},
    )


def _continuity_grounding(case: dict[str, Any]) -> QualificationTask:
    quote = _representative_sentence(str(case["text"]))
    fabricated = "The passage explicitly states that every named character is a spacecraft pilot."
    schema = _schema("continuity_grounding", {
        "classifications": {"type": "array", "items": {"type": "object", "properties": {
            "claim_id": {"type": "string"}, "label": {"type": "string", "enum": ["supported", "unsupported"]},
            "evidence_quote": {"type": "string"},
        }, "required": ["claim_id", "label", "evidence_quote"], "additionalProperties": False}},
    }, ["classifications"])
    return QualificationTask(
        task_id=f"continuity_grounding:{case['case_id']}", operation="json",
        prompt=f"Classify each claim against the passage. For unsupported claims, evidence_quote must be an empty string.\nClaims:\n- supported: {quote}\n- fabricated: {fabricated}\n\nPASSAGE:\n{case['text']}",
        max_tokens=300, response_format=schema, expected_keys=["classifications"],
        metadata={"family": "continuity_grounding", "source_text": case["text"], "case_id": case["case_id"]},
    )


def _structured_json(case: dict[str, Any]) -> QualificationTask:
    expected = {"source_id": case["source_id"], "chapter_index": case["chapter_index"], "segment": case["segment"]}
    schema = _schema("structured_json", {
        "source_id": {"type": "string"}, "chapter_index": {"type": "integer"}, "segment": {"type": "string"},
    }, list(expected))
    return QualificationTask(
        task_id=f"structured_json:{case['case_id']}", operation="json",
        prompt=f"Return this metadata exactly: {expected}", max_tokens=100,
        response_format=schema, expected_keys=list(expected),
        metadata={"family": "structured_json", "expected": expected, "case_id": case["case_id"]},
    )


def _tool_use(case: dict[str, Any]) -> QualificationTask:
    expected = {"source_id": case["source_id"], "chapter_index": case["chapter_index"]}
    tools = [{"type": "function", "function": {
        "name": "fetch_passage", "description": "Fetch one chapter passage.",
        "parameters": {"type": "object", "properties": {
            "source_id": {"type": "string"}, "chapter_index": {"type": "integer"},
        }, "required": ["source_id", "chapter_index"], "additionalProperties": False},
    }}]
    return QualificationTask(
        task_id=f"tool_use:{case['case_id']}", operation="json",
        prompt=f"Use fetch_passage for source_id={case['source_id']} and chapter_index={case['chapter_index']}.",
        max_tokens=100, tools=tools,
        metadata={"family": "tool_use", "expected_arguments": expected, "case_id": case["case_id"]},
    )


def _evidence_task(
    case: dict[str, Any], *, family: str, result_key: str, minimum: int,
    item_properties: dict[str, Any], instruction: str,
) -> QualificationTask:
    properties = {**item_properties, "evidence_quote": {"type": "string"}}
    required = [*item_properties, "evidence_quote"]
    schema = _schema(family, {
        result_key: {"type": "array", "items": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}},
    }, [result_key])
    return QualificationTask(
        task_id=f"{family}:{case['case_id']}", operation="json",
        prompt=f"{instruction} Every item must include a short verbatim evidence_quote copied from the passage.\n\nPASSAGE:\n{case['text']}",
        max_tokens=900, response_format=schema, expected_keys=[result_key],
        metadata={"family": family, "result_key": result_key, "minimum_items": minimum, "source_text": case["text"], "case_id": case["case_id"]},
    )


def _schema(name: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": name, "schema": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False,
    }}}


def _evidence_precision(rows: list[Any], source_text: str) -> float:
    quotes = [str(item.get("evidence_quote") or "").strip() for item in rows if isinstance(item, dict)]
    nonempty = [quote for quote in quotes if quote]
    if not nonempty:
        return 0.0
    normalized_source = _normalize(source_text)
    supported = sum(_normalize(quote) in normalized_source for quote in nonempty)
    return supported / len(nonempty)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _representative_sentence(value: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", _normalize_whitespace(value)):
        if 40 <= len(sentence) <= 240:
            return sentence
    return _normalize_whitespace(value)[:160]


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
