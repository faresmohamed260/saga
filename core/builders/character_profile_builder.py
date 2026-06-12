"""Builds formal character profiles from existing narrative outputs."""

from __future__ import annotations

from typing import Dict, List

from core.normalization.helpers import dedupe_strings, stable_slug


class CharacterProfileBuilder:
    """Synthesize durable character profiles from timeline/state/identity outputs."""

    def build(
        self,
        *,
        character_timelines: List[Dict],
        entity_registry: List[Dict],
        state_result: Dict,
        identity_result: Dict,
        scene_analyses: List[Dict],
    ) -> List[Dict]:
        registry_by_name = {
            (item.get("name") or "").strip().lower(): item
            for item in entity_registry
            if item.get("entity_type") == "character"
        }
        latest_state_by_name = {
            (item.get("entity_name") or "").strip().lower(): item
            for item in (state_result.get("latest_state") or [])
            if item.get("entity_type") == "character"
        }
        alias_map = identity_result.get("alias_map") or {}
        relationships_by_name = self._relationship_refs(scene_analyses)

        output = []
        for item in character_timelines:
            canonical_name = (item.get("character") or "").strip()
            if not canonical_name:
                continue
            normalized = canonical_name.lower()
            registry_entry = registry_by_name.get(normalized) or {}
            descriptions = registry_entry.get("descriptions") or []
            stable_traits = [row.get("description") for row in descriptions if row.get("description_type") == "stable_trait" and row.get("description")]
            appearance_notes = [row.get("description") for row in descriptions if row.get("description_type") == "appearance_note" and row.get("description")]
            typed_attributes = registry_entry.get("typed_attributes") or {}
            history = item.get("events") or []
            first_appearance_profile = registry_entry.get("first_appearance_profile") or {}
            baseline_description = str(first_appearance_profile.get("baseline_description") or "").strip()
            output.append({
                "character_id": stable_slug("char", canonical_name),
                "canonical_name": canonical_name,
                "aliases": dedupe_strings(alias_map.get(canonical_name, [canonical_name])),
                "core_description": baseline_description or (stable_traits[0] if stable_traits else (appearance_notes[0] if appearance_notes else "")),
                "traits": dedupe_strings(stable_traits[:8]),
                "personality": [],
                "speech_style": [],
                "goals": [],
                "fears": [],
                "loyalties": dedupe_strings((typed_attributes.get("affiliations") or [])[:8]),
                "abilities": dedupe_strings((typed_attributes.get("abilities") or [])[:8]),
                "constraints": dedupe_strings((typed_attributes.get("condition") or [])[:8]),
                "visual_profile": {
                    "first_appearance": first_appearance_profile,
                    "appearance": typed_attributes.get("appearance") or [],
                    "outfit": typed_attributes.get("outfit") or [],
                    "condition": typed_attributes.get("condition") or [],
                    "body_language": typed_attributes.get("body_language") or [],
                },
                "world_state_profile": {
                    "possessions": typed_attributes.get("possessions") or [],
                    "abilities": typed_attributes.get("abilities") or [],
                    "titles_or_roles": typed_attributes.get("titles_or_roles") or [],
                    "affiliations": typed_attributes.get("affiliations") or [],
                    "latest_world_state": registry_entry.get("latest_world_state") or {},
                },
                "important_history": history[:12],
                "relationship_refs": relationships_by_name.get(normalized, []),
                "state_history": registry_entry.get("state_changes") or [],
                "state_at_latest": (latest_state_by_name.get(normalized) or {}).get("attributes", {}),
                "first_seen": registry_entry.get("first_seen") or (history[0] if history else {}),
                "event_count": len(history),
                "mention_count": int(registry_entry.get("mention_count", 0)),
            })
        return sorted(output, key=lambda item: (-item.get("event_count", 0), item.get("canonical_name", "").lower()))

    def _relationship_refs(self, scene_analyses: List[Dict]) -> Dict[str, List[Dict]]:
        refs: Dict[str, List[Dict]] = {}
        for scene in scene_analyses:
            scene_ref = {
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
            }
            for item in scene.get("relationship_changes") or []:
                source = (item.get("source_entity") or "").strip()
                target = (item.get("target_entity") or "").strip()
                if not source or not target:
                    continue
                record = {
                    "source_entity": source,
                    "target_entity": target,
                    "relationship": item.get("relationship", ""),
                    "change": item.get("change", ""),
                    "evidence": item.get("evidence", ""),
                    **scene_ref,
                }
                refs.setdefault(source.lower(), []).append(record)
                refs.setdefault(target.lower(), []).append(record)
        return refs
