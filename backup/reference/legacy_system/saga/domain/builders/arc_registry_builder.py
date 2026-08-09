"""Builds a lightweight arc registry from character and relationship artifacts."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.normalization.helpers import stable_slug


class ArcRegistryBuilder:
    """Create deterministic first-pass narrative arcs from durable artifacts."""

    def build(
        self,
        *,
        character_profiles: List[Dict],
        relationship_profiles: List[Dict],
    ) -> Dict:
        items: List[Dict] = []

        for profile in character_profiles:
            name = profile.get("canonical_name", "")
            if not name:
                continue
            history = profile.get("important_history") or []
            items.append({
                "arc_id": stable_slug("arc", name),
                "title": f"{name} narrative arc",
                "characters": [name],
                "starting_event": (profile.get("first_seen") or {}).get("event_id", ""),
                "development_beats": history[:8],
                "resolution_or_status": history[-1] if history else profile.get("state_at_latest", {}),
                "dependencies": [],
            })

        for profile in relationship_profiles:
            source = profile.get("source_character", "")
            target = profile.get("target_character", "")
            if not source or not target:
                continue
            items.append({
                "arc_id": stable_slug("arc_rel", f"{source}:{target}"),
                "title": f"{source} / {target} relationship arc",
                "characters": [source, target],
                "starting_event": "",
                "development_beats": profile.get("change_log", [])[:8],
                "resolution_or_status": profile.get("change_log", [])[-1] if profile.get("change_log") else {},
                "dependencies": [],
            })

        return {"items": items}
