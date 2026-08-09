"""Shared schema helpers for local narrative evidence bundles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


GENERIC_ALIAS_LABELS = {
    "man",
    "woman",
    "boy",
    "girl",
    "person",
    "figure",
    "voice",
}

FORBIDDEN_ALIAS_LABELS = {
    "i",
    "me",
    "my",
    "myself",
    "he",
    "she",
    "they",
    "them",
    "him",
    "her",
    "his",
    "hers",
    "their",
    "theirs",
    "it",
    "its",
    "narrator",
    "protagonist",
    "person",
    "character",
}


def empty_evidence_bundle() -> Dict:
    return {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [],
        "candidate_entities": [],
        "candidate_aliases": [],
        "metadata": {
            "provider": "none",
            "coreference_available": False,
            "span_resolution_available": False,
            "transformer_available": False,
            "ambiguities": [],
            "filtering": {},
        },
    }


def normalize_evidence_bundle(bundle: Dict | None) -> Dict:
    if not isinstance(bundle, dict):
        return empty_evidence_bundle()

    normalized = empty_evidence_bundle()
    normalized["metadata"].update(bundle.get("metadata") or {})

    for key in ("mentions", "clusters", "candidate_characters", "candidate_entities", "candidate_aliases"):
        value = bundle.get(key) or []
        if isinstance(value, list):
            normalized[key] = deepcopy(value)

    return normalized


def compact_evidence_bundle(
    bundle: Dict | None,
    *,
    max_mentions: int = 8,
    max_clusters: int = 4,
    max_candidate_characters: int = 6,
    max_candidate_entities: int = 8,
    max_candidate_aliases: int = 8,
    max_text_length: int = 140,
) -> Dict:
    normalized = normalize_evidence_bundle(bundle)
    compacted = empty_evidence_bundle()
    compacted["metadata"].update(normalized.get("metadata") or {})

    def _truncate_value(value: Any):
        if isinstance(value, str):
            return " ".join(value.strip().split())[:max_text_length]
        if isinstance(value, list):
            return [_truncate_value(item) for item in value[:6]]
        if isinstance(value, dict):
            trimmed: Dict[str, Any] = {}
            for key, item in list(value.items())[:10]:
                trimmed[key] = _truncate_value(item)
            return trimmed
        return value

    def _trim_rows(rows: List[Any], limit: int) -> List[Any]:
        trimmed_rows: List[Any] = []
        for row in rows[:limit]:
            trimmed_rows.append(_truncate_value(row))
        return trimmed_rows

    compacted["mentions"] = _trim_rows(normalized.get("mentions") or [], max_mentions)
    compacted["clusters"] = _trim_rows(normalized.get("clusters") or [], max_clusters)
    compacted["candidate_characters"] = _trim_rows(normalized.get("candidate_characters") or [], max_candidate_characters)
    compacted["candidate_entities"] = _trim_rows(normalized.get("candidate_entities") or [], max_candidate_entities)
    compacted["candidate_aliases"] = _trim_rows(normalized.get("candidate_aliases") or [], max_candidate_aliases)
    return compacted


def normalize_identity_label(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def is_forbidden_alias(value: str) -> bool:
    normalized = normalize_identity_label(value)
    return not normalized or normalized in FORBIDDEN_ALIAS_LABELS


def is_generic_alias(value: str) -> bool:
    normalized = normalize_identity_label(value)
    return normalized in GENERIC_ALIAS_LABELS
