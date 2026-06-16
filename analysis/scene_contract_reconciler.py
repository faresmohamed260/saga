"""Deterministic reconciliation for scene analysis payload coherence."""

from __future__ import annotations

from typing import Dict, List, Tuple


VALID_ENTITY_TYPES = {"character", "object", "location", "creature"}
ENTITY_TYPE_PRIORITY = {
    "character": 0,
    "creature": 1,
    "location": 2,
    "object": 3,
}
CREATURE_MARKERS = {
    "attor", "suriel", "kelpie", "naga", "bogge", "wyrm", "wolf", "beast", "monster", "creature",
    "animal", "faerie beast", "predatory", "talons", "fangs", "claws", "snout", "muzzle", "fur",
    "scaled", "scales", "hide", "skeletal", "carapace", "feathered wings", "leathery wings",
}
CREATURE_ANATOMY_MARKERS = {
    "talons", "fangs", "claws", "snout", "muzzle", "fur", "scaled", "scales", "hide",
    "skeletal", "forked tongue", "razor-sharp teeth", "taloned feet", "leathery skin",
    "skeletal wings", "feathered wings", "leathery wings",
}
HUMANOID_MARKERS = {
    "human", "humanoid", "man", "woman", "male", "female", "girl", "boy", "lady", "lord", "queen",
    "king", "priestess", "guard", "mercenary", "hunter", "servant", "soldier", "warrior", "attendant",
    "villager", "father", "mother", "sister", "brother", "person",
}
SENTIENT_ROLE_MARKERS = {
    "mercenary", "hunter", "guard", "soldier", "warrior", "queen", "king", "lord", "lady", "priestess",
    "servant", "attendant", "father", "mother", "sister", "brother", "friend", "enemy", "merchant",
    "captain", "general", "healer", "seer", "spy", "emissary", "maid",
}
LOCATION_MARKERS = {
    "court", "house", "forest", "woods", "mountain", "river", "hall", "room", "chamber", "city",
    "village", "cottage", "manor", "palace", "garden", "street", "road", "camp", "prison", "library",
}


def reconcile_scene_contract(scene_analysis: Dict) -> Dict:
    scene = dict(scene_analysis)
    scene.setdefault("events", [])
    scene.setdefault("entities_present", [])
    scene.setdefault("entity_descriptions", [])
    scene.setdefault("state_changes", [])
    scene.setdefault("relationship_changes", [])
    scene.setdefault("canonical_characters", [])
    scene.setdefault("entity_world_state", {"entities": [], "diagnostics": {}})

    entity_map: Dict[Tuple[str, str], Dict] = {}
    entity_name_map: Dict[str, Tuple[str, str]] = {}

    def entity_key(name: str, entity_type: str) -> Tuple[str, str]:
        return (_name_key(name), str(entity_type or "").strip().lower())

    def add_entity(name: str, entity_type: str) -> None:
        cleaned_name = " ".join(str(name or "").strip().split())
        cleaned_type = _normalize_entity_type(cleaned_name, str(entity_type or "").strip().lower(), scene)
        if not cleaned_name or cleaned_type not in VALID_ENTITY_TYPES:
            return
        key = entity_key(cleaned_name, cleaned_type)
        name_only_key = _name_key(cleaned_name)
        existing_key = entity_name_map.get(name_only_key)
        if existing_key is not None:
            existing_type = existing_key[1]
            if existing_type == cleaned_type:
                if key not in entity_map:
                    entity_map[key] = {"name": cleaned_name, "entity_type": cleaned_type}
                return
            existing_priority = ENTITY_TYPE_PRIORITY.get(existing_type, 99)
            incoming_priority = ENTITY_TYPE_PRIORITY.get(cleaned_type, 99)
            if incoming_priority < existing_priority:
                entity_map.pop(existing_key, None)
                entity_map[key] = {"name": cleaned_name, "entity_type": cleaned_type}
                entity_name_map[name_only_key] = key
            return
        entity_map[key] = {"name": cleaned_name, "entity_type": cleaned_type}
        entity_name_map[name_only_key] = key

    for item in scene.get("canonical_characters") or []:
        add_entity(item.get("name"), "character")
    for item in scene.get("entities_present") or []:
        if isinstance(item, dict):
            add_entity(item.get("name"), item.get("entity_type"))
    location = scene.get("location") or {}
    if isinstance(location, dict):
        add_entity(location.get("name"), location.get("entity_type"))
    for item in (scene.get("entity_world_state") or {}).get("entities") or []:
        if isinstance(item, dict):
            add_entity(item.get("entity_name"), item.get("entity_type"))

    for change in scene.get("state_changes") or []:
        if isinstance(change, dict):
            add_entity(change.get("entity_name"), change.get("entity_type"))
    for row in scene.get("entity_descriptions") or []:
        if isinstance(row, dict):
            add_entity(row.get("entity_name"), row.get("entity_type"))
    for row in scene.get("relationship_changes") or []:
        if isinstance(row, dict):
            add_entity(row.get("source_entity"), "character")
            add_entity(row.get("target_entity"), "character")

    existing_description_keys = {
        (
            " ".join(str(item.get("entity_name") or "").strip().lower().split()),
            str(item.get("entity_type") or "").strip().lower(),
            " ".join(str(item.get("description") or "").strip().lower().split()),
            str(item.get("description_type") or "").strip().lower(),
        )
        for item in scene.get("entity_descriptions") or []
        if isinstance(item, dict)
    }
    existing_state_keys = {
        (
            " ".join(str(item.get("entity_name") or "").strip().lower().split()),
            str(item.get("entity_type") or "").strip().lower(),
            " ".join(str(item.get("attribute") or "").strip().lower().split()),
            " ".join(str(item.get("new_state") or "").strip().lower().split()),
        )
        for item in scene.get("state_changes") or []
        if isinstance(item, dict)
    }

    for entity in (scene.get("entity_world_state") or {}).get("entities") or []:
        if not isinstance(entity, dict):
            continue
        name = " ".join(str(entity.get("entity_name") or "").strip().split())
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        if not name or entity_type not in VALID_ENTITY_TYPES:
            continue
        add_entity(name, entity_type)
        baseline = " ".join(str(entity.get("baseline_description") or "").strip().split())
        if baseline:
            description_type = "stable_trait" if entity_type == "character" else "appearance_note"
            key = (name.lower(), entity_type, baseline.lower(), description_type)
            if key not in existing_description_keys:
                existing_description_keys.add(key)
                scene["entity_descriptions"].append(
                    {
                        "entity_name": name,
                        "entity_type": entity_type,
                        "description": baseline,
                        "description_type": description_type,
                        "evidence": " | ".join(entity.get("source_evidence") or []),
                        "world_state_source": "entity_world_state_analyzer",
                    }
                )
        for attribute_name, values in (entity.get("typed_attributes") or {}).items():
            if not isinstance(values, list):
                continue
            for value in values:
                cleaned_value = " ".join(str(value or "").strip().split())
                if not cleaned_value:
                    continue
                description_type = _description_type_for_attribute(attribute_name)
                d_key = (name.lower(), entity_type, cleaned_value.lower(), description_type)
                if d_key not in existing_description_keys:
                    existing_description_keys.add(d_key)
                    scene["entity_descriptions"].append(
                        {
                            "entity_name": name,
                            "entity_type": entity_type,
                            "description": cleaned_value,
                            "description_type": description_type,
                            "evidence": " | ".join(entity.get("source_evidence") or []),
                            "world_state_source": "entity_world_state_analyzer",
                        }
                    )
        for change in entity.get("state_changes") or []:
            if not isinstance(change, dict):
                continue
            attribute = " ".join(str(change.get("attribute") or "").strip().split())
            new_state = " ".join(str(change.get("new_state") or "").strip().split())
            if not attribute or not new_state:
                continue
            s_key = (name.lower(), entity_type, attribute.lower(), new_state.lower())
            if s_key in existing_state_keys:
                continue
            existing_state_keys.add(s_key)
            scene["state_changes"].append(
                {
                    "entity_name": name,
                    "entity_type": entity_type,
                    "attribute": attribute,
                    "previous_state": " ".join(str(change.get("previous_state") or "").strip().split()),
                    "new_state": new_state,
                    "change_type": " ".join(str(change.get("change_type") or "").strip().split()) or "state_update",
                    "evidence": " ".join(str(change.get("evidence") or "").strip().split()),
                    "world_state_source": "entity_world_state_analyzer",
                }
            )

    for event in scene.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "").strip().lower()
        if not event_type:
            event_type = _classify_event_type(event)
        event["type"] = event_type or "action"
        characters = []
        character_seen = set()
        for name in event.get("characters") or []:
            cleaned_name = " ".join(str(name or "").strip().split())
            if not cleaned_name or cleaned_name.lower() in character_seen:
                continue
            character_seen.add(cleaned_name.lower())
            characters.append(cleaned_name)
            add_entity(cleaned_name, "character")
        event["characters"] = characters

        entities_involved = []
        entity_seen = set()
        for name in event.get("entities_involved") or []:
            cleaned_name = " ".join(str(name or "").strip().split())
            if not cleaned_name or cleaned_name.lower() in entity_seen:
                continue
            entity_seen.add(cleaned_name.lower())
            entities_involved.append(cleaned_name)
            inferred_type = _infer_entity_type(cleaned_name, scene, event)
            add_entity(cleaned_name, inferred_type)
        event["entities_involved"] = entities_involved

    scene["entities_present"] = sorted(entity_map.values(), key=lambda item: (item["entity_type"], item["name"].lower()))
    return scene


def _description_type_for_attribute(attribute_name: str) -> str:
    lowered = str(attribute_name or "").strip().lower()
    if lowered in {"appearance", "materials", "species_or_kind", "titles_or_roles", "abilities", "symbolic_role"}:
        return "stable_trait"
    if lowered in {"condition", "damage_or_change", "current_state"}:
        return "temporary_condition"
    if lowered in {"possessions", "owner_or_holder", "occupants"}:
        return "possession"
    return "appearance_note"


def _name_key(name: str) -> str:
    lowered = " ".join(str(name or "").strip().lower().split())
    for prefix in ("the ", "a ", "an "):
        if lowered.startswith(prefix):
            return lowered[len(prefix):]
    return lowered


def _infer_entity_type(name: str, scene: Dict, event: Dict) -> str:
    lowered = _name_key(name)
    for character in event.get("characters") or []:
        if lowered == _name_key(character):
            return "character"
    location = scene.get("location") or {}
    if lowered and lowered == _name_key(location.get("name", "")):
        return "location"
    for entity in scene.get("entities_present") or []:
        if lowered == _name_key(entity.get("name", "")):
            entity_type = str(entity.get("entity_type") or "").strip().lower()
            if entity_type in VALID_ENTITY_TYPES:
                return _normalize_entity_type(name, entity_type, scene)
    return _normalize_entity_type(name, "object", scene)


def _normalize_entity_type(name: str, proposed_type: str, scene: Dict) -> str:
    cleaned_name = " ".join(str(name or "").strip().split())
    cleaned_type = str(proposed_type or "").strip().lower()
    if cleaned_type not in VALID_ENTITY_TYPES:
        cleaned_type = "object"
    if _looks_like_location(cleaned_name, scene):
        return "location"
    if _looks_like_creature(cleaned_name, scene):
        return "creature"
    if _looks_like_character(cleaned_name, scene):
        return "character"
    return cleaned_type


def _scene_entity_evidence_text(name: str, scene: Dict) -> str:
    lowered = _name_key(name)
    parts: List[str] = [str(name or "")]
    for row in scene.get("entity_descriptions") or []:
        if lowered == _name_key(row.get("entity_name", "")):
            parts.extend([
                str(row.get("description") or ""),
                str(row.get("description_type") or ""),
                str(row.get("evidence") or ""),
            ])
    for row in scene.get("state_changes") or []:
        if lowered == _name_key(row.get("entity_name", "")):
            parts.extend([
                str(row.get("attribute") or ""),
                str(row.get("new_state") or ""),
                str(row.get("evidence") or ""),
            ])
    for row in (scene.get("entity_world_state") or {}).get("entities") or []:
        if lowered == _name_key(row.get("entity_name", "")):
            parts.extend([
                str(row.get("baseline_description") or ""),
                str(row.get("narrative_role") or ""),
            ])
            typed = row.get("typed_attributes") or {}
            if isinstance(typed, dict):
                for values in typed.values():
                    if isinstance(values, list):
                        parts.extend(str(value or "") for value in values)
            parts.extend(str(value or "") for value in (row.get("source_evidence") or []))
    for row in scene.get("relationship_changes") or []:
        if lowered in {
            _name_key(row.get("source_entity", "")),
            _name_key(row.get("target_entity", "")),
        }:
            parts.extend([
                str(row.get("relationship") or ""),
                str(row.get("change") or ""),
                str(row.get("evidence") or ""),
            ])
    for event in scene.get("events") or []:
        names = [
            _name_key(item)
            for item in list(event.get("entities_involved") or []) + list(event.get("characters") or [])
        ]
        if lowered in names:
            parts.extend([
                str(event.get("description") or ""),
                str(event.get("reason") or ""),
                str(event.get("outcome") or ""),
                str(event.get("type") or ""),
            ])
    return " ".join(part for part in parts if part).lower()


def _looks_like_creature(name: str, scene: Dict) -> bool:
    haystack = _scene_entity_evidence_text(name, scene)
    if any(marker in haystack for marker in CREATURE_ANATOMY_MARKERS):
        return True
    has_creature = any(marker in haystack for marker in CREATURE_MARKERS)
    has_humanoid = any(marker in haystack for marker in HUMANOID_MARKERS)
    if has_creature and not has_humanoid:
        return True
    return False


def _looks_like_character(name: str, scene: Dict) -> bool:
    lowered = _name_key(name)
    if any(lowered == _name_key(item.get("name", "")) for item in scene.get("canonical_characters") or []):
        return True
    if any(
        lowered in {
            _name_key(row.get("source_entity", "")),
            _name_key(row.get("target_entity", "")),
        }
        for row in scene.get("relationship_changes") or []
    ):
        return True
    haystack = _scene_entity_evidence_text(name, scene)
    if any(marker in haystack for marker in SENTIENT_ROLE_MARKERS):
        return True
    tokens = set(lowered.split())
    if tokens & SENTIENT_ROLE_MARKERS:
        return True
    return False


def _looks_like_location(name: str, scene: Dict) -> bool:
    lowered = _name_key(name)
    location = scene.get("location") or {}
    if lowered and lowered == _name_key(location.get("name", "")):
        return True
    return any(marker in lowered for marker in LOCATION_MARKERS)


def _classify_event_type(event: Dict) -> str:
    text = " ".join(
        str(part or "").strip().lower()
        for part in [
            event.get("description"),
            event.get("reason"),
            event.get("outcome"),
        ]
    )
    movement_markers = {"walk", "walks", "travel", "travels", "ride", "rides", "return", "returns", "leave", "leaves", "enter", "enters", "go", "goes", "carry", "carries"}
    discovery_markers = {"notice", "notices", "learn", "learns", "realize", "realizes", "discover", "discovers", "find", "finds", "see", "sees", "reveal", "reveals"}
    interaction_markers = {"say", "says", "tell", "tells", "ask", "asks", "speak", "speaks", "argue", "argues", "promise", "promises", "warn", "warns", "confide", "confides"}
    if any(marker in text for marker in interaction_markers):
        return "interaction"
    if any(marker in text for marker in discovery_markers):
        return "discovery"
    if any(marker in text for marker in movement_markers):
        return "movement"
    return "action"
