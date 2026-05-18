"""Shared schema helpers for local narrative evidence bundles."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List


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


def normalize_identity_label(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def is_forbidden_alias(value: str) -> bool:
    normalized = normalize_identity_label(value)
    return not normalized or normalized in FORBIDDEN_ALIAS_LABELS


def is_generic_alias(value: str) -> bool:
    normalized = normalize_identity_label(value)
    return normalized in GENERIC_ALIAS_LABELS
