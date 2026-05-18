"""Point-in-time query service over the artifact bundle."""

from __future__ import annotations

from typing import Dict, List


class CanonQueryService:
    """Provide stable event/profile/snapshot lookups over the artifact bundle."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}

    def get_event(self, ledger_event_id: str) -> Dict:
        return self._find_by_id(self.bundle.get("event_ledger") or [], "ledger_event_id", ledger_event_id)

    def snapshot_before(self, ledger_event_id: str) -> Dict:
        snapshots = self.bundle.get("canon_snapshots") or []
        target = self.get_event(ledger_event_id)
        if not target:
            return {}
        target_time = target.get("time_index", 0)
        candidate = {}
        for item in snapshots:
            event = self.get_event(item.get("anchor_event_id", ""))
            if not event:
                continue
            if event.get("time_index", 0) < target_time:
                candidate = item
        return candidate

    def snapshot_after(self, ledger_event_id: str) -> Dict:
        return self._find_by_id(self.bundle.get("canon_snapshots") or [], "anchor_event_id", ledger_event_id)

    def get_character_profile(self, canonical_name_or_id: str) -> Dict:
        for item in self.bundle.get("character_profiles") or []:
            if (
                item.get("character_id") == canonical_name_or_id
                or item.get("canonical_name") == canonical_name_or_id
                or canonical_name_or_id in (item.get("aliases") or [])
            ):
                return item
        return {}

    def get_character_profile_at(self, character_id: str, ledger_event_id: str) -> Dict:
        profile = self.get_character_profile(character_id)
        if not profile:
            return {}
        event = self.get_event(ledger_event_id)
        if not event:
            return {}
        scene_ref = (
            event.get("book_index", 0),
            event.get("chapter_index", 0),
            event.get("scene_index", 0),
        )
        state_at_event = {}
        for row in profile.get("state_history") or []:
            ref = (
                row.get("book_index", 0),
                row.get("chapter_index", 0),
                row.get("scene_index", 0),
            )
            if ref <= scene_ref:
                state_at_event[row.get("attribute", "")] = row.get("new_state", "")
        enriched = dict(profile)
        enriched["state_at_event"] = state_at_event
        enriched["anchor_event_id"] = ledger_event_id
        return enriched

    def get_relationship_state_at(self, source_id: str, target_id: str, ledger_event_id: str) -> Dict:
        event = self.get_event(ledger_event_id)
        if not event:
            return {}
        scene_ref = (
            event.get("book_index", 0),
            event.get("chapter_index", 0),
            event.get("scene_index", 0),
        )
        for item in self.bundle.get("relationship_profiles") or []:
            pair = {item.get("source_character"), item.get("target_character")}
            if {source_id, target_id} != pair:
                continue
            changes = []
            for row in item.get("change_log") or []:
                ref = (
                    row.get("book_index", 0),
                    row.get("chapter_index", 0),
                    row.get("scene_index", 0),
                )
                if ref <= scene_ref:
                    changes.append(row)
            result = dict(item)
            result["change_log"] = changes
            result["partial"] = True
            result["anchor_event_id"] = ledger_event_id
            return result
        return {
            "relationship_id": "",
            "source_character": source_id,
            "target_character": target_id,
            "relationship_type": "",
            "baseline_dynamic": "",
            "trust_level": "unknown",
            "conflict_level": "unknown",
            "romantic_signal": "unknown",
            "shared_history": [],
            "change_log": [],
            "partial": True,
            "anchor_event_id": ledger_event_id,
        }

    def _find_by_id(self, items: List[Dict], key: str, value: str) -> Dict:
        for item in items:
            if item.get(key) == value:
                return item
        return {}
