"""Builds canon snapshots anchored to ledger events."""

from __future__ import annotations

from typing import Dict, List


class CanonSnapshotBuilder:
    """Compute point-in-time snapshots from transitions and artifact families."""

    def build(
        self,
        *,
        event_ledger: List[Dict],
        state_result: Dict,
        relationship_profiles: List[Dict],
    ) -> List[Dict]:
        transitions = sorted(state_result.get("transitions") or [], key=lambda item: item.get("state_index", 0))
        snapshots = []
        for ledger_event in event_ledger:
            scene_ref = (
                ledger_event.get("book_index", 0),
                ledger_event.get("chapter_index", 0),
                ledger_event.get("scene_index", 0),
            )
            entity_states = self._entity_states_at(transitions, scene_ref)
            relationship_states = self._relationship_states_at(relationship_profiles, scene_ref)
            snapshots.append({
                "snapshot_id": f"snap_{ledger_event.get('ledger_event_id')}",
                "anchor_event_id": ledger_event.get("ledger_event_id", ""),
                "scene_ref": {
                    "book_index": ledger_event.get("book_index", 0),
                    "chapter_index": ledger_event.get("chapter_index", 0),
                    "scene_index": ledger_event.get("scene_index", 0),
                },
                "character_states": [item for item in entity_states if item.get("entity_type") == "character"],
                "relationship_states": relationship_states,
                "entity_states": [item for item in entity_states if item.get("entity_type") != "character"],
                "active_goals": [],
                "active_threats": [],
                "known_information": [],
                "unresolved_threads": [],
            })
        return snapshots

    def _entity_states_at(self, transitions: List[Dict], scene_ref: tuple[int, int, int]) -> List[Dict]:
        state_by_entity: Dict[tuple[str, str], Dict] = {}
        for transition in transitions:
            ref = (
                transition.get("book_index", 0),
                transition.get("chapter_index", 0),
                transition.get("scene_index", 0),
            )
            if ref > scene_ref:
                break
            key = ((transition.get("entity_name") or "").strip().lower(), transition.get("entity_type") or "")
            entry = state_by_entity.setdefault(
                key,
                {
                    "entity_name": transition.get("entity_name", ""),
                    "entity_type": transition.get("entity_type", ""),
                    "attributes": {},
                },
            )
            entry["attributes"][transition.get("attribute", "")] = transition.get("new_state", "")
        return [value for _, value in sorted(state_by_entity.items(), key=lambda item: (item[1]["entity_type"], item[1]["entity_name"].lower()))]

    def _relationship_states_at(self, relationship_profiles: List[Dict], scene_ref: tuple[int, int, int]) -> List[Dict]:
        rows = []
        for profile in relationship_profiles:
            changes = []
            for item in profile.get("change_log") or []:
                ref = (
                    item.get("book_index", 0),
                    item.get("chapter_index", 0),
                    item.get("scene_index", 0),
                )
                if ref <= scene_ref:
                    changes.append(item)
            rows.append({
                "relationship_id": profile.get("relationship_id", ""),
                "source_character": profile.get("source_character", ""),
                "target_character": profile.get("target_character", ""),
                "relationship_type": profile.get("relationship_type", ""),
                "change_log": changes,
                "partial": True,
            })
        return rows
