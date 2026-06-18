"""Deterministic filtering and scoring for local evidence bundles."""

from __future__ import annotations

import re
from typing import Dict, List

from saga.agents.evidence_schema import (
    is_forbidden_alias,
    is_generic_alias,
    normalize_evidence_bundle,
    normalize_identity_label,
)


PROPER_NAME_PATTERN = re.compile(r"^[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)+$")


def score_and_filter_evidence(bundle: Dict | None) -> Dict:
    bundle = normalize_evidence_bundle(bundle)
    ambiguities = list(bundle.get("metadata", {}).get("ambiguities") or [])
    ambiguous_names = set()
    for item in ambiguities:
        if item.get("type") == "descriptor_candidate" and item.get("candidate"):
            ambiguous_names.add(normalize_identity_label(item["candidate"]))
        for candidate in item.get("candidates") or []:
            ambiguous_names.add(normalize_identity_label(candidate))

    filtered_characters = []
    for item in bundle.get("candidate_characters") or []:
        name = (item.get("name") or "").strip()
        if not name or is_forbidden_alias(name):
            continue
        score = _character_score(name, item.get("evidence_mentions") or [], item.get("source") or "")
        if normalize_identity_label(name) in ambiguous_names:
            score -= 0.1
        if score < 0.45:
            continue
        filtered_characters.append({
            **item,
            "evidence_mentions": _dedupe_strings(item.get("evidence_mentions") or []),
            "score": round(score, 2),
        })

    filtered_entities = []
    for item in bundle.get("candidate_entities") or []:
        name = (item.get("name") or "").strip()
        if not name or is_forbidden_alias(name):
            continue
        score = _entity_score(name, item.get("entity_type") or "", item.get("evidence_mentions") or [])
        if score < 0.35:
            continue
        filtered_entities.append({
            **item,
            "evidence_mentions": _dedupe_strings(item.get("evidence_mentions") or []),
            "score": round(score, 2),
        })

    kept_character_names = {normalize_identity_label(item["name"]) for item in filtered_characters}
    filtered_aliases = []
    for item in bundle.get("candidate_aliases") or []:
        canonical_name = (item.get("canonical_name") or "").strip()
        alias = (item.get("alias") or "").strip()
        if not canonical_name or not alias:
            continue
        if is_forbidden_alias(alias) or is_generic_alias(alias):
            continue
        if normalize_identity_label(canonical_name) == normalize_identity_label(alias):
            continue
        if normalize_identity_label(canonical_name) not in kept_character_names:
            continue
        filtered_aliases.append({"canonical_name": canonical_name, "alias": alias, "score": round(_alias_score(alias), 2)})

    kept_mentions = []
    for mention in bundle.get("mentions") or []:
        if not isinstance(mention, dict):
            continue
        text = (mention.get("text") or "").strip()
        if not text:
            continue
        if mention.get("is_pronoun"):
            kept_mentions.append(mention)
            continue
        normalized = normalize_identity_label(text)
        if normalized in kept_character_names:
            kept_mentions.append(mention)
            continue
        if any(normalize_identity_label(item.get("name") or "") == normalized for item in filtered_entities):
            kept_mentions.append(mention)
            continue
        if looks_like_proper_name(text):
            kept_mentions.append(mention)

    bundle["candidate_characters"] = filtered_characters
    bundle["candidate_entities"] = filtered_entities
    bundle["candidate_aliases"] = filtered_aliases
    bundle["mentions"] = kept_mentions
    bundle["metadata"]["filtering"] = {
        "characters_kept": len(filtered_characters),
        "entities_kept": len(filtered_entities),
        "aliases_kept": len(filtered_aliases),
        "ambiguities_detected": len(ambiguities),
    }
    return bundle


def looks_like_proper_name(name: str) -> bool:
    cleaned = (name or "").strip()
    if not cleaned:
        return False
    return bool(PROPER_NAME_PATTERN.match(cleaned))


def _character_score(name: str, evidence_mentions: List[str], source: str) -> float:
    score = 0.0
    normalized = normalize_identity_label(name)
    mention_count = len(_dedupe_strings(evidence_mentions))
    if looks_like_proper_name(name):
        score += 0.65
    elif len(name.split()) >= 2:
        score += 0.35
    if mention_count > 1:
        score += 0.15
    if "role" in source:
        score += 0.1
    if normalized.startswith("the "):
        score -= 0.05
    if is_generic_alias(name):
        score -= 0.4
    return max(0.0, min(1.0, score))


def _entity_score(name: str, entity_type: str, evidence_mentions: List[str]) -> float:
    score = 0.25
    if entity_type in {"location", "artifact"}:
        score += 0.15
    if len(_dedupe_strings(evidence_mentions)) > 1:
        score += 0.1
    if len(name.split()) > 1:
        score += 0.05
    return max(0.0, min(1.0, score))


def _alias_score(alias: str) -> float:
    score = 0.5
    if len(alias.split()) > 1:
        score += 0.15
    if alias.lower().startswith("the "):
        score += 0.05
    return max(0.0, min(1.0, score))


def _dedupe_strings(values: List[str]) -> List[str]:
    output = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output
