"""Builds entity and location profiles from existing entity/state outputs."""

from __future__ import annotations

from typing import Dict, List

from core.normalization.helpers import dedupe_strings, stable_slug


class EntityProfileBuilder:
    """Synthesize durable entity/location profiles."""

    def build(
        self,
        *,
        entity_registry: List[Dict],
        scene_analyses: List[Dict],
        state_result: Dict | None = None,
    ) -> List[Dict]:
        character_links = self._connected_characters(scene_analyses)
        state_by_entity = self._status_history_by_entity(state_result or {})
        output = []
        for item in entity_registry:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            description = ""
            descriptions = item.get("descriptions") or []
            if descriptions:
                description = (descriptions[0].get("description") or "").strip()
            output.append({
                "entity_id": stable_slug("ent", f"{item.get('entity_type', '')}:{name}"),
                "name": name,
                "entity_type": item.get("entity_type", ""),
                "description": description,
                "rules_or_constraints": [],
                "connected_characters": character_links.get(name.lower(), []),
                "status_history": state_by_entity.get(name.lower()) or item.get("state_changes") or [],
            })
        return sorted(output, key=lambda item: (item["entity_type"], item["name"].lower()))

    def _connected_characters(self, scene_analyses: List[Dict]) -> Dict[str, List[str]]:
        links: Dict[str, List[str]] = {}
        for scene in scene_analyses:
            characters = [item.get("name") for item in scene.get("canonical_characters") or [] if item.get("name")]
            for entity in scene.get("entities_present") or []:
                name = (entity.get("name") or "").strip()
                entity_type = (entity.get("entity_type") or "").strip()
                if not name or entity_type == "character":
                    continue
                links.setdefault(name.lower(), []).extend(characters)
            location = scene.get("location") or {}
            location_name = (location.get("name") or "").strip()
            if location_name:
                links.setdefault(location_name.lower(), []).extend(characters)
        return {key: dedupe_strings(values) for key, values in links.items()}

    def _status_history_by_entity(self, state_result: Dict) -> Dict[str, List[Dict]]:
        rows: Dict[str, List[Dict]] = {}
        for item in state_result.get("transitions") or []:
            name = (item.get("entity_name") or "").strip()
            if not name:
                continue
            rows.setdefault(name.lower(), []).append(item)
        return rows
