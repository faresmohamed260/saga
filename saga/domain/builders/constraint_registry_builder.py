"""Builds a lightweight continuity constraint registry from canonical artifacts."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.normalization.helpers import stable_slug


class ConstraintRegistryBuilder:
    """Extract deterministic continuity constraints from profiles and events."""

    def build(
        self,
        *,
        character_profiles: List[Dict],
        entity_profiles: List[Dict],
        event_ledger: List[Dict],
    ) -> Dict:
        items: List[Dict] = []

        for profile in character_profiles:
            name = profile.get("canonical_name", "")
            aliases = profile.get("aliases") or []
            if not name:
                continue
            if aliases:
                items.append({
                    "constraint_id": stable_slug("constraint", f"aliases:{name}"),
                    "scope": "identity",
                    "rule": f"{name} may also be referred to as: {', '.join(aliases)}.",
                    "source": profile.get("character_id", ""),
                    "locked_before_event": self._first_event_id(profile),
                })

        for profile in entity_profiles:
            name = profile.get("name", "")
            entity_type = profile.get("entity_type", "")
            if not name or not entity_type:
                continue
            items.append({
                "constraint_id": stable_slug("constraint", f"entity:{entity_type}:{name}"),
                "scope": entity_type,
                "rule": f"{name} exists in canon as a {entity_type}.",
                "source": profile.get("entity_id", ""),
                "locked_before_event": "",
            })

        if event_ledger:
            first_event_id = event_ledger[0].get("ledger_event_id", "")
            items.append({
                "constraint_id": stable_slug("constraint", "timeline_anchor"),
                "scope": "timeline",
                "rule": "Canonical event ordering before divergence must remain locked.",
                "source": "event_ledger",
                "locked_before_event": first_event_id,
            })

        return {"items": items}

    def _first_event_id(self, profile: Dict) -> str:
        first_seen = profile.get("first_seen") or {}
        if first_seen.get("event_id"):
            return first_seen["event_id"]
        return ""
