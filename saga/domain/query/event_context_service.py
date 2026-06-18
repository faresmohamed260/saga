"""Event-centered context retrieval over the core artifact bundle."""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List

from saga.domain.query.canon_query_service import CanonQueryService


class EventContextService:
    """Build a grounded context packet around a canonical event."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}
        self.canon_query = CanonQueryService(self.bundle)

    def build_event_context(self, ledger_event_id: str) -> Dict:
        event = self.canon_query.get_event(ledger_event_id)
        if not event:
            return {}

        participants = event.get("participants") or []
        participant_profiles = [
            self.canon_query.get_character_profile_at(name, ledger_event_id)
            for name in participants
        ]
        participant_profiles = [item for item in participant_profiles if item]

        relationship_states = []
        for source, target in combinations(participants, 2):
            relationship_states.append(
                self.canon_query.get_relationship_state_at(source, target, ledger_event_id)
            )

        related_entities = self._related_entity_profiles(event, participants)
        return {
            "event": event,
            "snapshot_before": self.canon_query.snapshot_before(ledger_event_id),
            "snapshot_after": self.canon_query.snapshot_after(ledger_event_id),
            "participant_profiles": participant_profiles,
            "relationship_states": relationship_states,
            "related_entity_profiles": related_entities,
        }

    def _related_entity_profiles(self, event: Dict, participants: List[str]) -> List[Dict]:
        location = (event.get("location") or "").strip().lower()
        participant_set = {item.strip().lower() for item in participants if item}
        related = []
        for item in self.bundle.get("entity_profiles") or []:
            entity_name = (item.get("name") or "").strip().lower()
            connected = {value.strip().lower() for value in item.get("connected_characters", []) if value}
            if location and entity_name == location:
                related.append(item)
                continue
            if participant_set and connected.intersection(participant_set):
                related.append(item)
        seen = set()
        output = []
        for item in related:
            entity_id = item.get("entity_id")
            if entity_id and entity_id not in seen:
                seen.add(entity_id)
                output.append(item)
        return output
