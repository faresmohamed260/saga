"""Headless pipeline helpers shared by dashboard-free workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from entities.character_profile_service import CharacterProfileService
from entities.entity_registry_service import EntityRegistryService
from rag.story_index_service import StoryIndexService
from state.canon_state_service import CanonStateService
from state.state_transition_service import StateTransitionService
from timeline.character_normalizer import CharacterNormalizer
from timeline.character_timeline_service import CharacterTimelineService
from timeline.event_ledger_service import EventLedgerService
from timeline.timeline_service import TimelineService


EXPORT_CONTRACT_VERSION = "1.0.0"
FORBIDDEN_IDENTITY_LABELS = {
    "i", "me", "my", "myself", "he", "she", "they", "them", "him", "her",
    "his", "hers", "their", "theirs", "it", "its", "narrator", "protagonist",
    "person", "character",
}
GENERIC_ALIAS_LABELS = {"man", "woman", "boy", "girl", "person", "figure", "voice"}


def normalize_identity_key(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def article_insensitive_key(name: str) -> str:
    normalized = normalize_identity_key(name)
    for prefix in ("the ", "a ", "an "):
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def is_forbidden_identity(name: str) -> bool:
    normalized = normalize_identity_key(name)
    return not normalized or len(normalized) <= 1 or normalized in FORBIDDEN_IDENTITY_LABELS


def looks_like_proper_name(name: str) -> bool:
    cleaned = (name or "").strip()
    if not cleaned:
        return False
    tokens = [token for token in cleaned.replace("-", " ").split() if token]
    if not tokens:
        return False
    alpha_tokens = []
    for token in tokens:
        letters = "".join(ch for ch in token if ch.isalpha() or ch in {"'", "-"})
        if not letters:
            return False
        alpha_tokens.append(letters)
    if len(alpha_tokens) >= 2:
        return all(token[:1].isupper() and token[1:].islower() for token in alpha_tokens if len(token) > 1)
    token = alpha_tokens[0]
    return len(token) >= 4 and token[:1].isupper() and token[1:].islower()


def canonical_lookup(alias_map: Dict[str, List[str]]) -> Dict[str, str]:
    lookup = {}
    for canonical_name, aliases in alias_map.items():
        lookup[canonical_name.lower()] = canonical_name
        for alias in aliases:
            lookup[alias.lower()] = canonical_name
    return lookup


def resolve_existing_canonical_name(name: str, alias_map: Dict[str, List[str]]) -> str:
    if not name:
        return ""
    normalized = normalize_identity_key(name)
    article_free = article_insensitive_key(name)
    candidates = []
    for canonical_name, aliases in alias_map.items():
        known_names = [canonical_name, *aliases]
        for known_name in known_names:
            if normalize_identity_key(known_name) == normalized:
                return canonical_name
            if article_insensitive_key(known_name) == article_free:
                return canonical_name
            candidates.append((canonical_name, known_name))
    if " " not in normalized and len(normalized) >= 4:
        matches = set()
        for canonical_name, known_name in candidates:
            known_token = normalize_identity_key(known_name)
            if " " in known_token:
                continue
            short, long_name = sorted([normalized, known_token], key=len)
            if len(long_name) - len(short) >= 2 and long_name.startswith(short):
                matches.add(canonical_name)
        if len(matches) == 1:
            return next(iter(matches))
    return ""


def sanitize_alias_map(alias_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    cleaned = {}
    for canonical_name, aliases in (alias_map or {}).items():
        canonical = (canonical_name or "").strip()
        if is_forbidden_identity(canonical):
            continue
        valid_aliases = {canonical}
        for alias in aliases or []:
            cleaned_alias = (alias or "").strip()
            if not cleaned_alias or is_forbidden_identity(cleaned_alias):
                continue
            valid_aliases.add(cleaned_alias)
        if valid_aliases:
            cleaned[canonical] = sorted(valid_aliases, key=str.lower)
    return cleaned


def canonicalize_name(name: str, alias_map: Dict[str, List[str]], rejected: List[str]) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return ""
    if cleaned.lower() in {item.lower() for item in rejected}:
        return ""
    lookup = canonical_lookup(alias_map)
    if cleaned.lower() in lookup:
        return lookup[cleaned.lower()]
    resolved = resolve_existing_canonical_name(cleaned, alias_map)
    return resolved or cleaned


def build_scene_context(
    scene_text: str,
    resolved_scene_analyses: List[Dict],
    state_result: Dict,
    identity_result: Dict,
    window: int = 6,
) -> str:
    parts = []
    alias_map = identity_result.get("alias_map") or {}
    if alias_map:
        parts.append("Known canonical characters: " + ", ".join(sorted(alias_map.keys(), key=str.lower)[:20]))
    recent_summaries = []
    for scene in resolved_scene_analyses[-window:]:
        summary = (scene.get("scene_summary") or "").strip()
        if summary:
            recent_summaries.append(
                f"- Book {scene.get('book_index')} Chapter {scene.get('chapter_index')} "
                f"Scene {scene.get('scene_index')}: {summary}"
            )
    if recent_summaries:
        parts.append("Recent scene summaries:")
        parts.extend(recent_summaries)
    latest_state = (state_result or {}).get("latest_state") or []
    scene_text_lower = (scene_text or "").lower()
    relevant_state = []
    for item in latest_state:
        entity_name = (item.get("entity_name") or "").strip()
        if not entity_name or entity_name.lower() not in scene_text_lower:
            continue
        attr_text = ", ".join(f"{key}={value}" for key, value in (item.get("attributes") or {}).items())
        if attr_text:
            relevant_state.append(f"- {entity_name}: {attr_text}")
    if relevant_state:
        parts.append("Relevant latest known state:")
        parts.extend(relevant_state[:8])
    return "\n".join(parts).strip()


def resolve_scene_analysis(scene_analysis: Dict, alias_map: Dict[str, List[str]], rejected: List[str]) -> Dict:
    resolved = dict(scene_analysis)
    lookup = canonical_lookup(alias_map)
    valid_character_names = set()
    for character in scene_analysis.get("canonical_characters", []):
        raw_name = (character.get("name") or "").strip()
        canonical = canonicalize_name(raw_name, alias_map, rejected)
        if canonical:
            valid_character_names.add(canonical)
        if raw_name:
            valid_character_names.add(raw_name)
    for mention in scene_analysis.get("character_mentions", []):
        canonical = canonicalize_name(mention.get("canonical_name", ""), alias_map, rejected)
        if canonical:
            valid_character_names.add(canonical)
    resolved_canonicals = []
    seen_canonicals = set()
    for character in scene_analysis.get("canonical_characters", []):
        canonical_name = canonicalize_name(character.get("name", ""), alias_map, rejected)
        if not canonical_name:
            continue
        lowered = canonical_name.lower()
        if lowered in seen_canonicals:
            continue
        seen_canonicals.add(lowered)
        names_used = []
        names_seen = set()
        for alias in character.get("names_used", []):
            cleaned = str(alias).strip()
            if not cleaned:
                continue
            lowered_alias = cleaned.lower()
            if lowered_alias in names_seen:
                continue
            names_seen.add(lowered_alias)
            names_used.append(cleaned)
        if lowered not in names_seen:
            names_used.insert(0, canonical_name)
        resolved_canonicals.append({**character, "name": canonical_name, "names_used": names_used})
    resolved["canonical_characters"] = resolved_canonicals
    resolved["character_mentions"] = [
        {**mention, "canonical_name": canonicalize_name(mention.get("canonical_name", ""), alias_map, rejected)}
        for mention in scene_analysis.get("character_mentions", [])
    ]
    resolved_events = []
    for event in scene_analysis.get("events", []):
        characters = []
        for character in event.get("characters", []):
            canonical = canonicalize_name(character, alias_map, rejected)
            lowered = (character or "").strip().lower()
            is_known_alias = lowered in lookup
            if canonical and (canonical in valid_character_names or is_known_alias) and canonical not in characters:
                characters.append(canonical)
        resolved_events.append({**event, "characters": characters})
    resolved["events"] = resolved_events
    resolved_entities = []
    seen_entities = set()
    entity_source = [{"name": item["name"], "entity_type": "character"} for item in resolved_canonicals] + list(
        scene_analysis.get("entities_present", [])
    )
    for entity in entity_source:
        name = (
            canonicalize_name(entity.get("name", ""), alias_map, rejected)
            if entity.get("entity_type") == "character"
            else (entity.get("name") or "").strip()
        )
        if not name:
            continue
        key = (name.lower(), entity.get("entity_type"))
        if key in seen_entities:
            continue
        seen_entities.add(key)
        resolved_entities.append({"name": name, "entity_type": entity.get("entity_type")})
    resolved["entities_present"] = resolved_entities
    resolved["entity_descriptions"] = [
        {**item, "entity_name": canonicalize_name(item.get("entity_name", ""), alias_map, rejected)
         if item.get("entity_type") == "character" else item.get("entity_name", "")}
        for item in scene_analysis.get("entity_descriptions", [])
        if (canonicalize_name(item.get("entity_name", ""), alias_map, rejected)
            if item.get("entity_type") == "character" else item.get("entity_name", ""))
    ]
    resolved["state_changes"] = [
        {**item, "entity_name": canonicalize_name(item.get("entity_name", ""), alias_map, rejected)
         if item.get("entity_type") == "character" else item.get("entity_name", "")}
        for item in scene_analysis.get("state_changes", [])
        if (canonicalize_name(item.get("entity_name", ""), alias_map, rejected)
            if item.get("entity_type") == "character" else item.get("entity_name", ""))
    ]
    relationship_changes = []
    for item in scene_analysis.get("relationship_changes", []):
        source_entity = canonicalize_name(item.get("source_entity", ""), alias_map, rejected)
        target_entity = canonicalize_name(item.get("target_entity", ""), alias_map, rejected)
        if source_entity and target_entity:
            relationship_changes.append({**item, "source_entity": source_entity, "target_entity": target_entity})
    resolved["relationship_changes"] = relationship_changes
    return resolved


def rebuild_resolved_scene_analyses(scene_analyses: List[Dict], identity_result: Dict) -> List[Dict]:
    alias_map = identity_result.get("alias_map", {})
    rejected = identity_result.get("rejected_non_characters", [])
    return [resolve_scene_analysis(scene_analysis, alias_map, rejected) for scene_analysis in scene_analyses]


def apply_identity_updates(scene_analysis: Dict, alias_result: Dict) -> None:
    alias_map = alias_result["alias_map"]
    rejected = alias_result["rejected_non_characters"]
    decisions = alias_result["decisions"]
    alias_history = alias_result["alias_history"]
    scene_ref = {
        "book_index": scene_analysis.get("book_index"),
        "chapter_index": scene_analysis.get("chapter_index"),
        "scene_index": scene_analysis.get("scene_index"),
    }
    rejected_lower = {item.lower() for item in rejected}
    for name in scene_analysis.get("rejected_identity_candidates", []):
        if not name or not name.strip():
            continue
        if looks_like_proper_name(name):
            alias_map.setdefault(name, [name])
            decisions.append({
                "decision_type": "inline_name_promoted",
                "character": name,
                "canonical_name": name,
                "same_character": True,
                "confidence": 1.0,
                "reasoning": "Promoted from rejection list because it matches a proper-name pattern.",
                "scene_ref": scene_ref,
            })
            alias_history.append({"canonical_name": name, "alias_name": name, "scene_ref": scene_ref})
            continue
        if name.lower() not in rejected_lower:
            rejected.append(name)
            rejected_lower.add(name.lower())
            decisions.append({
                "decision_type": "inline_rejection",
                "character": name,
                "same_character": False,
                "confidence": 1.0,
                "reasoning": "Rejected during scene analysis as clearly non-character or incidental.",
                "scene_ref": scene_ref,
            })
    for character in scene_analysis.get("canonical_characters", []):
        canonical_name = (character.get("name") or "").strip()
        if not canonical_name or is_forbidden_identity(canonical_name):
            continue
        alias_map.setdefault(canonical_name, [canonical_name])
        merged = {alias for alias in {canonical_name, *character.get("names_used", [])} if alias and not is_forbidden_identity(alias)}
        alias_map[canonical_name] = sorted(merged, key=str.lower)
    for mention in scene_analysis.get("character_mentions", []):
        alias = (mention.get("mention_text") or "").strip()
        canonical_name = (mention.get("canonical_name") or "").strip()
        if not alias or not canonical_name or not mention.get("is_consequential_character", False):
            continue
        if is_forbidden_identity(alias) or alias.lower() in rejected_lower:
            continue
        resolved_canonical = resolve_existing_canonical_name(canonical_name, alias_map) or canonical_name
        alias_map.setdefault(resolved_canonical, [resolved_canonical])
        alias_map[resolved_canonical] = sorted({resolved_canonical, alias, *alias_map[resolved_canonical]}, key=str.lower)
    for update in scene_analysis.get("alias_updates", []):
        alias = update["alias"].strip()
        canonical_name = update["canonical_name"].strip()
        action = update["action"]
        if not alias or not canonical_name:
            continue
        if is_forbidden_identity(alias) or is_forbidden_identity(canonical_name):
            if alias.lower() not in rejected_lower:
                rejected.append(alias)
                rejected_lower.add(alias.lower())
            continue
        if alias.lower() in rejected_lower:
            continue
        resolved_canonical = (
            resolve_existing_canonical_name(canonical_name, alias_map)
            or resolve_existing_canonical_name(alias, alias_map)
            or canonical_name
        )
        if action == "new_canonical" and resolved_canonical != canonical_name:
            action = "map_alias"
        alias_map.setdefault(resolved_canonical, [resolved_canonical])
        alias_map[resolved_canonical] = sorted({resolved_canonical, alias, *alias_map[resolved_canonical]}, key=str.lower)
        decisions.append({
            "decision_type": "inline_alias_update",
            "character": alias,
            "canonical_name": resolved_canonical,
            "same_character": True,
            "confidence": 1.0,
            "reasoning": update["reasoning"],
            "scene_ref": scene_ref,
        })
        alias_history.append({"canonical_name": resolved_canonical, "alias_name": alias, "scene_ref": scene_ref})
    alias_result["alias_map"] = sanitize_alias_map(alias_map)


def build_entity_registry(scene_analyses: List[Dict]) -> List[Dict]:
    return EntityRegistryService().build(scene_analyses)


def build_state_result(scene_analyses: List[Dict]) -> Dict:
    return StateTransitionService().build(scene_analyses)


def build_canon_snapshot(state_result: Dict, scene_ref: Tuple[int, int, int]) -> List[Dict]:
    return CanonStateService().snapshot_at(state_result.get("transitions", []), scene_ref=scene_ref)


def build_timeline(scene_analyses: List[Dict]) -> List[Dict]:
    return TimelineService().build_from_scene_analyses(scene_analyses)


def build_event_ledger(scene_analyses: List[Dict], timeline: List[Dict], causal_graph_result: Dict) -> List[Dict]:
    return EventLedgerService().build(scene_analyses, timeline, causal_graph_result)


def build_character_timelines(timeline: List[Dict]) -> List[Dict]:
    return CharacterTimelineService().build(timeline)


def build_formal_character_profiles(
    character_timelines: List[Dict],
    entity_registry: List[Dict],
    state_result: Dict,
    identity_result: Dict,
    scene_analyses: List[Dict],
) -> List[Dict]:
    return CharacterProfileService().build(
        character_timelines, entity_registry, state_result, identity_result, scene_analyses
    )


def normalize_character_timelines(character_timelines: List[Dict], identity_result: Dict) -> List[Dict]:
    normalized = CharacterNormalizer().normalize(character_timelines)
    existing_alias_map = identity_result.setdefault("alias_map", {})
    for canonical_name, aliases in normalized.get("alias_map", {}).items():
        merged = set(existing_alias_map.get(canonical_name, []))
        merged.update(aliases)
        merged.add(canonical_name)
        existing_alias_map[canonical_name] = sorted(merged, key=str.lower)
    identity_result["alias_map"] = sanitize_alias_map(existing_alias_map)
    return normalized.get("character_timelines", character_timelines)


def build_story_index_summary(
    scene_analyses: List[Dict],
    timeline: List[Dict],
    event_ledger: List[Dict],
    character_timelines: List[Dict],
    character_profiles: List[Dict],
    entity_registry: List[Dict],
    canon_snapshot: List[Dict],
    state_result: Dict,
    identity_result: Dict,
    causal_graph_result: Dict,
) -> Dict:
    service = StoryIndexService()
    result = service.build(
        scene_analyses=scene_analyses,
        timeline=timeline,
        event_ledger=event_ledger,
        character_timelines=character_timelines,
        character_profiles=character_profiles,
        entity_registry=entity_registry,
        canon_snapshot=canon_snapshot,
        state_result=state_result,
        identity_result=identity_result,
        causal_graph_result=causal_graph_result,
    )
    return {"document_count": result.get("document_count", 0)}


def build_export_contract_payload(
    *,
    app_name: str,
    pipeline_status: str,
    configuration: Dict,
    inputs: Dict,
    outputs: Dict,
    runtime: Dict,
) -> Dict:
    return {
        "contract_version": EXPORT_CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "app": {
            "name": app_name,
            "pipeline_status": pipeline_status,
        },
        "configuration": configuration,
        "inputs": inputs,
        "outputs": outputs,
        "runtime": runtime,
    }
