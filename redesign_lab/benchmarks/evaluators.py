"""Audit scorers for redesign benchmark outputs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def narrative_extraction_score(output: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, float]:
    if not output:
        return {"validity_score": 0.0, "semantic_score": 0.0, "structural_failures": 1.0}
    validity = 1.0
    if output.get("error") or output.get("last_error"):
        validity = 0.0
    anchors = _flatten_names(output.get("canonical_characters", []))
    expected_names = case.get("expected_character_anchors") or []
    expected_hits = sum(1 for name in expected_names if any(name.lower() == anchor.lower() for anchor in anchors))
    events_blob = " ".join(str(item.get("description") or "") for item in output.get("events", []))
    event_hits = _keyword_hits(events_blob, case.get("expected_event_keywords") or [])
    location_blob = str((output.get("location") or {}).get("description") or "") + " " + str((output.get("location") or {}).get("name") or "")
    location_hits = _keyword_hits(location_blob, case.get("expected_location_keywords") or [])
    semantic = round(
        (expected_hits + event_hits + location_hits)
        / max(
            len(expected_names)
            + len(case.get("expected_event_keywords") or [])
            + len(case.get("expected_location_keywords") or []),
            1,
        ),
        3,
    )
    return {"validity_score": validity, "semantic_score": semantic, "structural_failures": 0.0 if validity else 1.0}


def identity_inventory_score(output: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, float]:
    canonicals = [str(name or "") for name in (output.get("canonical_characters") or [])]
    expected = case.get("expected_canonicals") or []
    hits = sum(1 for item in expected if item in canonicals)
    semantic = round(hits / max(len(expected), 1), 3)
    return {"validity_score": 1.0 if output else 0.0, "semantic_score": semantic, "structural_failures": 0.0 if output else 1.0}


def stable_state_score(output: List[Dict[str, Any]], case: Dict[str, Any]) -> Dict[str, float]:
    names = {str(item.get("canonical_name") or "").strip() for item in output if str(item.get("canonical_name") or "").strip()}
    expected = set(case.get("expected_character_names") or [])
    hits = len(names & expected)
    semantic = round(hits / max(len(expected), 1), 3)
    empty_facts = sum(1 for item in output if not (item.get("facts") or {}))
    return {
        "validity_score": 1.0 if output else 0.0,
        "semantic_score": semantic,
        "structural_failures": float(empty_facts),
    }


def retrieval_packet_score(output: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, float]:
    characters = output.get("character_states") or []
    names = [str(item.get("name") or "") for item in characters]
    expected_names = case.get("expected_character_anchors") or []
    name_hits = sum(1 for item in expected_names if item in names)
    docs_blob = " ".join(
        str(doc.get("text") or doc.get("summary") or doc.get("description") or "")
        for doc in (output.get("retrieval_documents") or [])
    )
    thread_hits = _keyword_hits(docs_blob, case.get("expected_thread_keywords") or [])
    semantic = round((name_hits + thread_hits) / max(len(expected_names) + len(case.get("expected_thread_keywords") or []), 1), 3)
    validity = 1.0 if output and output.get("story_ending") else 0.0
    return {"validity_score": validity, "semantic_score": semantic, "structural_failures": 0.0 if validity else 1.0}


def blueprint_score(output: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, float]:
    if not output:
        return {"validity_score": 0.0, "semantic_score": 0.0, "structural_failures": 1.0}
    blob = _json_blob(output)
    name_hits = _keyword_hits(blob, case.get("expected_character_anchors") or [])
    thread_hits = _keyword_hits(blob, case.get("expected_thread_keywords") or [])
    semantic = round((name_hits + thread_hits) / max(len(case.get("expected_character_anchors") or []) + len(case.get("expected_thread_keywords") or []), 1), 3)
    validity = 1.0 if output.get("title") and output.get("acts") and output.get("relationship_targets") is not None else 0.0
    missing_act_ranges = sum(1 for act in (output.get("acts") or []) if not act.get("chapter_range"))
    return {"validity_score": validity, "semantic_score": semantic, "structural_failures": float(missing_act_ranges)}


def outline_score(output: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, float]:
    if not output:
        return {"validity_score": 0.0, "semantic_score": 0.0, "structural_failures": 1.0}
    blob = _json_blob(output)
    keyword_hits = _keyword_hits(blob, case.get("expected_keywords") or [])
    pov_ok = 1 if str(output.get("pov_character") or "").strip() == str(case.get("expected_pov") or "").strip() else 0
    semantic = round((keyword_hits + pov_ok) / max(len(case.get("expected_keywords") or []) + 1, 1), 3)
    validity = 1.0 if output.get("scenes") and output.get("chapter_title") else 0.0
    structural_failures = 0.0
    if not output.get("scenes"):
        structural_failures += 1.0
    return {"validity_score": validity, "semantic_score": semantic, "structural_failures": structural_failures}


def prose_score(text: str, case: Dict[str, Any]) -> Dict[str, float]:
    if not text:
        return {"validity_score": 0.0, "semantic_score": 0.0, "structural_failures": 1.0}
    keyword_hits = _keyword_hits(text, case.get("expected_keywords") or [])
    forbidden_hits = _keyword_hits(text, case.get("forbidden_keywords") or [])
    validity = 1.0 if len(text.split()) >= 120 else 0.0
    semantic = round(max(0.0, (keyword_hits - forbidden_hits) / max(len(case.get("expected_keywords") or []), 1)), 3)
    return {"validity_score": validity, "semantic_score": semantic, "structural_failures": float(forbidden_hits)}


def chapter_batching_score(output: List[Dict[str, Any]]) -> Dict[str, float]:
    if not output:
        return {"validity_score": 0.0, "semantic_score": 0.0, "structural_failures": 1.0}
    boundary_preserved = all(item.get("chapter_indices") for item in output)
    grouped = any(len(item.get("chapter_indices") or []) > 1 for item in output)
    semantic = 1.0 if boundary_preserved else 0.0
    if grouped:
        semantic += 0.25
    return {"validity_score": 1.0, "semantic_score": round(min(semantic, 1.0), 3), "structural_failures": 0.0}


def compare_text_quality(text: str, expected_keywords: Iterable[str]) -> float:
    keywords = list(expected_keywords)
    return round(_keyword_hits(text, keywords) / max(len(keywords), 1), 3)


def _flatten_names(items: List[Dict[str, Any]]) -> List[str]:
    return [str(item.get("name") or "").strip() for item in items if str(item.get("name") or "").strip()]


def _keyword_hits(text: str, keywords: Iterable[str]) -> int:
    lowered = str(text or "").lower()
    return sum(1 for keyword in keywords if str(keyword).lower() in lowered)


def _json_blob(payload: Any) -> str:
    return str(payload) if isinstance(payload, str) else __import__("json").dumps(payload, ensure_ascii=False)
