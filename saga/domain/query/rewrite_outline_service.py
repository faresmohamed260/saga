"""Deterministic rewrite-outline generation from divergence planning artifacts."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.query.rewrite_context_service import RewriteContextService


class RewriteOutlineService:
    """Build a grounded rewrite outline from divergence and canon context."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}
        self.context_service = RewriteContextService(self.bundle)

    def build_outline(
        self,
        *,
        divergence_event_id: str,
        divergence_statement: str,
        anchor_event_id: str | None = None,
        involved_characters: List[str] | None = None,
        max_beats: int = 5,
    ) -> Dict:
        anchor_event_id = anchor_event_id or divergence_event_id
        context = self.context_service.build_rewrite_context(
            divergence_event_id=divergence_event_id,
            divergence_statement=divergence_statement,
            anchor_event_id=anchor_event_id,
            involved_characters=involved_characters,
        )
        if not context:
            return {"beats": []}

        workspace = context.get("divergence_workspace") or {}
        event = (context.get("anchor_event_context") or {}).get("event") or {}
        participant_profiles = (context.get("anchor_event_context") or {}).get("participant_profiles") or []
        involved = involved_characters or [item.get("canonical_name", "") for item in participant_profiles if item.get("canonical_name")]
        invalidated = workspace.get("unstable_downstream_facts") or []
        constraints = context.get("continuity_constraints") or []
        beats: List[Dict] = []

        beats.append({
            "beat_id": "beat_1",
            "summary": self._opening_summary(divergence_statement, event),
            "characters_involved": involved,
            "based_on_locked_facts": [event.get("ledger_event_id", "")],
            "required_states": self._required_states(participant_profiles),
            "relationship_movement": self._relationship_movement(divergence_statement),
            "causal_purpose": "establish the divergence immediately after the locked canon event",
            "continuity_notes": constraints[:5],
        })

        beat_index = 2
        for item in invalidated[: max(0, max_beats - 2)]:
            beats.append({
                "beat_id": f"beat_{beat_index}",
                "summary": self._replacement_summary(item),
                "characters_involved": involved,
                "based_on_locked_facts": [divergence_event_id, item.get("event_id", "")],
                "required_states": self._required_states(participant_profiles),
                "relationship_movement": self._relationship_movement(divergence_statement),
                "causal_purpose": f"replace or reroute canon event {item.get('event_id', '')} while preserving continuity",
                "continuity_notes": (item.get("affected_preconditions") or []) + (item.get("stakes") or []),
            })
            beat_index += 1

        beats.append({
            "beat_id": f"beat_{beat_index}",
            "summary": self._stabilization_summary(divergence_statement, involved),
            "characters_involved": involved,
            "based_on_locked_facts": workspace.get("locked_canon_before", [])[-3:],
            "required_states": self._required_states(participant_profiles),
            "relationship_movement": self._relationship_movement(divergence_statement),
            "causal_purpose": "stabilize the new canon direction and create a path for subsequent chapters",
            "continuity_notes": constraints[:8],
        })

        return {"beats": beats[:max_beats]}

    def _opening_summary(self, divergence_statement: str, event: Dict) -> str:
        title = event.get("title", "the divergence event")
        return f"Immediately after {title}, the story diverges: {divergence_statement}"

    def _replacement_summary(self, invalidated_event: Dict) -> str:
        summary = invalidated_event.get("summary", "").strip()
        if summary:
            return f"Replace the canon fallout around: {summary}"
        return "Replace the invalidated downstream canon with a grounded alternative beat."

    def _stabilization_summary(self, divergence_statement: str, involved_characters: List[str]) -> str:
        character_text = ", ".join(item for item in involved_characters if item) or "the central cast"
        return f"Stabilize the post-divergence trajectory for {character_text} so the new direction from '{divergence_statement}' becomes sustainable."

    def _required_states(self, participant_profiles: List[Dict]) -> List[str]:
        rows = []
        for profile in participant_profiles:
            name = profile.get("canonical_name", "")
            state = profile.get("state_at_event") or {}
            if not name or not state:
                continue
            rows.append(f"{name}: " + ", ".join(f"{key}={value}" for key, value in sorted(state.items())))
        return rows

    def _relationship_movement(self, divergence_statement: str) -> str:
        lowered = (divergence_statement or "").lower()
        if any(marker in lowered for marker in {"romance", "romantic", "closer", "love", "relationship", "together"}):
            return "relationship deepening"
        if any(marker in lowered for marker in {"betray", "conflict", "fall out", "rift"}):
            return "relationship deterioration"
        return "relationship and character dynamics adapt to the divergence"
