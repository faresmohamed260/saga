"""Reusable quality metrics for character and world modeling outputs."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from packages.character_world_modeling.contracts import CharacterProfileArtifact, CharacterWorldModelingResult, WorldStateArtifact


class CharacterWorldQualityMetrics(BaseModel):
    profile_grounding_rate: float = 0.0
    unsupported_profile_claim_rate: float = 0.0
    stable_attribute_precision: float = 0.0
    relationship_support_rate: float = 0.0
    entity_deduplication_rate: float = 0.0
    useful_entity_rate: float = 0.0
    unsupported_world_fact_rate: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


def evaluate_character_world_quality(result: CharacterWorldModelingResult) -> CharacterWorldQualityMetrics:
    profiles = list(result.character_profiles or [])
    states = list(result.stable_character_states or [])
    world_states = list(result.world_states or [])

    profile_claims = _profile_claims(profiles)
    unsupported_profile_claims = [claim for claim in profile_claims if _is_unsupported_profile_claim(claim)]
    grounded_profiles = [profile for profile in profiles if _is_grounded_profile(profile)]

    stable_attribute_count = sum(len(state.stable_attributes or {}) for state in states)
    unsupported_stable_attributes = [
        {"character_id": state.character_id, "key": key, "value": value}
        for state in states
        for key, value in dict(state.stable_attributes or {}).items()
        if not _state_has_support(state.canonical_name, value, state.supporting_event_ids, state.supporting_scene_ids)
    ]

    relationship_claims = _relationship_claims(profiles)
    supported_relationship_claims = [claim for claim in relationship_claims if _is_supported_relationship_claim(claim)]

    normalized_entity_names = [_normalize_entity_key(item.canonical_name) for item in world_states if str(item.canonical_name or "").strip()]
    unique_entity_names = set(normalized_entity_names)
    useful_entities = [item for item in world_states if _is_useful_world_entity(item)]

    world_fact_count = sum(len(item.stable_facts or {}) + len(item.active_conditions or []) for item in world_states)
    unsupported_world_facts = [
        {"entity_id": item.entity_id, "claim": claim}
        for item in world_states
        for claim in _world_fact_claims(item)
        if not _world_fact_has_support(item, claim)
    ]

    return CharacterWorldQualityMetrics(
        profile_grounding_rate=_ratio(len(grounded_profiles), len(profiles)),
        unsupported_profile_claim_rate=_ratio(len(unsupported_profile_claims), len(profile_claims)),
        stable_attribute_precision=1.0 - _ratio(len(unsupported_stable_attributes), stable_attribute_count),
        relationship_support_rate=_ratio(len(supported_relationship_claims), len(relationship_claims)),
        entity_deduplication_rate=_ratio(len(unique_entity_names), len(normalized_entity_names)),
        useful_entity_rate=_ratio(len(useful_entities), len(world_states)),
        unsupported_world_fact_rate=_unsupported_rate(len(unsupported_world_facts), world_fact_count),
        details={
            "unsupported_profile_claims": unsupported_profile_claims[:50],
            "unsupported_stable_attributes": unsupported_stable_attributes[:50],
            "unsupported_world_facts": unsupported_world_facts[:50],
            "duplicate_entity_names": _duplicate_entity_names(normalized_entity_names),
            "low_usefulness_entity_ids": [item.entity_id for item in world_states if not _is_useful_world_entity(item)][:50],
        },
    )


def _profile_claims(profiles: list[CharacterProfileArtifact]) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for profile in profiles:
        scalar_fields = ["overview", "role_or_archetype", "first_seen_summary", "latest_state_summary"]
        for field in scalar_fields:
            value = str(getattr(profile, field, "") or "").strip()
            if value:
                claims.append({"character_id": profile.character_id, "canonical_name": profile.canonical_name, "field": field, "value": value})
        for field in ["traits", "motivations", "loyalties", "tensions", "notable_relationships", "visual_cues"]:
            for value in list(getattr(profile, field, []) or []):
                cleaned = str(value or "").strip()
                if cleaned:
                    claims.append({"character_id": profile.character_id, "canonical_name": profile.canonical_name, "field": field, "value": cleaned})
    return claims


def _relationship_claims(profiles: list[CharacterProfileArtifact]) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for profile in profiles:
        for value in list(profile.notable_relationships or []):
            cleaned = str(value or "").strip()
            if cleaned:
                claims.append({"character_id": profile.character_id, "canonical_name": profile.canonical_name, "value": cleaned})
    return claims


def _world_fact_claims(world_state: WorldStateArtifact) -> list[str]:
    claims: list[str] = []
    claims.extend(str(value or "").strip() for value in dict(world_state.stable_facts or {}).values())
    claims.extend(str(value or "").strip() for value in list(world_state.active_conditions or []))
    return [claim for claim in claims if claim]


def _is_grounded_profile(profile: CharacterProfileArtifact) -> bool:
    if _is_conservative_text(profile.overview):
        return True
    if profile.important_event_ids:
        return bool(profile.overview or profile.notable_relationships or profile.latest_state_summary)
    if profile.scene_ids and profile.overview and _mentions_name_or_ref(profile.overview, profile.canonical_name):
        return True
    return not _has_substantive_profile_claim(profile)


def _is_unsupported_profile_claim(claim: dict[str, str]) -> bool:
    value = claim["value"]
    field = claim["field"]
    canonical_name = claim["canonical_name"]
    if _is_conservative_text(value):
        return False
    if field in {"first_seen_summary", "latest_state_summary"}:
        return not _mentions_name_or_ref(value, canonical_name)
    if field == "notable_relationships":
        return not _is_supported_relationship_claim(claim)
    return False


def _is_supported_relationship_claim(claim: dict[str, str]) -> bool:
    value = claim["value"]
    canonical_name = claim["canonical_name"]
    if _mentions_name_or_ref(value, canonical_name):
        return True
    if re.search(r"\bchar-[a-z0-9-]+\b", value, flags=re.IGNORECASE):
        return True
    return bool(
        re.search(
            r"\b(?:sibling|sister|brother|family|ally|friend|friendship|romantic|marriage|spouse|protective|antagonistic|companion|manipulation|conflict)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def _state_has_support(canonical_name: str, value: str, supporting_event_ids: list[str], supporting_scene_ids: list[str]) -> bool:
    if supporting_event_ids or supporting_scene_ids:
        return True
    if not str(value or "").strip():
        return True
    if _claim_overlaps_text(value, canonical_name):
        return True
    if _title_supports_stable_attribute(canonical_name, value):
        return True
    return bool(re.search(r"\b(?:mother|father|sister|brother|sibling|human|mortal|faerie|court|family|companion|ally|friend|romantic|marriage)\b", value, flags=re.IGNORECASE))


def _title_supports_stable_attribute(canonical_name: str, value: str) -> bool:
    name = str(canonical_name or "").casefold()
    claim = str(value or "").casefold()
    if not re.search(r"\b(?:prince|princess|king|queen)\b", name):
        return False
    return bool(re.search(r"\b(?:royal|royalty|prince|princess|king|queen)\b", claim))


def _world_fact_has_support(world_state: WorldStateArtifact, claim: str) -> bool:
    if world_state.supporting_event_ids or world_state.scene_ids:
        return True
    if not str(claim or "").strip():
        return True
    return _claim_overlaps_text(
        claim,
        f"{world_state.canonical_name} {world_state.entity_type} {world_state.description} {world_state.current_state_summary} {world_state.story_relevance}",
    )


def _is_useful_world_entity(item: WorldStateArtifact) -> bool:
    name = str(item.canonical_name or "").strip()
    if not name or _is_generic_entity_name(name):
        return False
    if len(name.split()) > 8:
        return False
    return bool(item.description or item.current_state_summary or item.stable_facts or item.active_conditions or item.supporting_event_ids)


def _has_substantive_profile_claim(profile: CharacterProfileArtifact) -> bool:
    return bool(
        profile.role_or_archetype
        or profile.traits
        or profile.motivations
        or profile.loyalties
        or profile.tensions
        or profile.notable_relationships
        or profile.visual_cues
        or profile.first_seen_summary
        or profile.latest_state_summary
    )


def _is_conservative_text(value: str) -> bool:
    lowered = str(value or "").casefold()
    return "no primary grounded actions" in lowered or "no durable character-state facts" in lowered or "no durable facts are grounded" in lowered


def _mentions_name_or_ref(value: str, name: str) -> bool:
    cleaned_name = str(name or "").strip()
    for variant in _name_variants(cleaned_name):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(variant)}(?![A-Za-z0-9])", value or "", flags=re.IGNORECASE):
            return True
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned_name.casefold()).strip("-")
    return bool(slug and re.search(rf"\bchar-{re.escape(slug)}\b", value or "", flags=re.IGNORECASE))


def _name_variants(name: str) -> list[str]:
    cleaned = " ".join(str(name or "").split()).strip()
    if not cleaned:
        return []
    variants = [cleaned]
    without_title = re.sub(r"^(?:prince|princess|king|queen|lord|lady|sir|madam)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    if without_title and without_title.casefold() != cleaned.casefold():
        variants.append(without_title)
    return variants


def _claim_overlaps_text(claim: str, text: str) -> bool:
    claim_tokens = _content_tokens(claim)
    text_tokens = _content_tokens(text)
    if not claim_tokens:
        return True
    return len(claim_tokens.intersection(text_tokens)) >= min(2, len(claim_tokens))


def _content_tokens(value: str) -> set[str]:
    stopwords = {"the", "and", "for", "with", "from", "that", "this", "into", "onto", "are", "was", "were", "has", "have"}
    return {
        _stem_token(token)
        for token in re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold()).split()
        if len(token) > 2 and token not in stopwords
    }


def _stem_token(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _normalize_entity_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())
    cleaned = re.sub(r"\b(?:the|a|an)\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _duplicate_entity_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _is_generic_entity_name(value: str) -> bool:
    normalized = _normalize_entity_key(value)
    return normalized in {"thing", "things", "someone", "something", "anything", "everything", "there", "here", "people", "person"}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def _unsupported_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _ratio(numerator, denominator)
