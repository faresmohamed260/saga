"""Deterministic divergence-workspace planning over the core artifact bundle."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.query.canon_query_service import CanonQueryService
from saga.domain.query.dependency_query_service import DependencyQueryService
from saga.domain.query.event_context_service import EventContextService


class DivergencePlanningService:
    """Produce a first-pass divergence workspace from the canonical artifact bundle."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}
        self.canon_query = CanonQueryService(self.bundle)
        self.dependency_query = DependencyQueryService(self.bundle)
        self.event_context = EventContextService(self.bundle)

    def plan_divergence(self, ledger_event_id: str, divergence_statement: str) -> Dict:
        event = self.canon_query.get_event(ledger_event_id)
        if not event:
            return {
                "divergence_event_id": ledger_event_id,
                "divergence_statement": divergence_statement,
                "locked_canon_before": [],
                "stable_downstream_facts": [],
                "unstable_downstream_facts": [],
                "invalidated_events": [],
                "required_continuity_constraints": [],
                "target_arcs": [],
            }

        downstream_depths = self._downstream_depths(ledger_event_id)
        invalidated_ids = {
            event_id
            for event_id, depth in downstream_depths.items()
            if depth == 1
        }
        locked_before = [
            item.get("ledger_event_id", "")
            for item in self.bundle.get("event_ledger") or []
            if item.get("time_index", 0) < event.get("time_index", 0)
        ]
        stable_after = [
            item.get("ledger_event_id", "")
            for item in self.bundle.get("event_ledger") or []
            if item.get("time_index", 0) > event.get("time_index", 0)
            and item.get("ledger_event_id") not in downstream_depths
        ]
        context = self.event_context.build_event_context(ledger_event_id)
        event_lookup = {
            item.get("ledger_event_id", ""): item
            for item in self.bundle.get("event_ledger") or []
            if item.get("ledger_event_id")
        }
        unstable_facts = self._unstable_facts(
            event=event,
            event_lookup=event_lookup,
            downstream_depths=downstream_depths,
        )
        constraints = self._continuity_constraints(context)
        target_arcs = self._target_arcs_for_event(event)
        return {
            "divergence_event_id": ledger_event_id,
            "divergence_statement": divergence_statement,
            "locked_canon_before": locked_before,
            "stable_downstream_facts": stable_after,
            "unstable_downstream_facts": unstable_facts,
            "invalidated_events": sorted(invalidated_ids),
            "required_continuity_constraints": constraints,
            "target_arcs": target_arcs,
        }

    def _continuity_constraints(self, context: Dict) -> List[str]:
        constraints: List[str] = []
        event = context.get("event") or {}
        if event.get("location"):
            constraints.append(f"Location at divergence: {event['location']}.")
        for precondition in event.get("preconditions") or []:
            constraints.append(f"Locked precondition: {precondition}")
        for stake in event.get("stakes") or []:
            constraints.append(f"Divergence stake: {stake}")
        for profile in context.get("participant_profiles") or []:
            name = profile.get("canonical_name", "")
            if not name:
                continue
            state = profile.get("state_at_event") or {}
            if state:
                parts = ", ".join(f"{key}={value}" for key, value in sorted(state.items()))
                constraints.append(f"{name} state at divergence: {parts}.")
            aliases = profile.get("aliases") or []
            if aliases:
                constraints.append(f"{name} known aliases before divergence: {', '.join(aliases)}.")
        for item in self.bundle.get("constraint_registry", {}).get("items", []) or []:
            rule = item.get("rule", "")
            if rule:
                constraints.append(rule)
        return constraints

    def _target_arcs_for_event(self, event: Dict) -> List[str]:
        participants = set(event.get("participants") or [])
        arc_ids = []
        for item in self.bundle.get("arc_registry", {}).get("items", []) or []:
            arc_characters = set(item.get("characters") or [])
            if participants.intersection(arc_characters):
                arc_ids.append(item.get("arc_id", ""))
        return [item for item in arc_ids if item]

    def _downstream_depths(self, ledger_event_id: str) -> Dict[str, int]:
        event_lookup = {
            item.get("ledger_event_id", ""): item
            for item in self.bundle.get("event_ledger") or []
            if item.get("ledger_event_id")
        }
        source_lookup = {
            item.get("source_event_id", ""): item.get("ledger_event_id", "")
            for item in self.bundle.get("event_ledger") or []
            if item.get("source_event_id") and item.get("ledger_event_id")
        }
        start = event_lookup.get(ledger_event_id)
        if not start:
            return {}
        queue = []
        for child in start.get("causal_children") or []:
            child_ledger_id = child if child in event_lookup else source_lookup.get(child, "")
            if child_ledger_id:
                queue.append((child_ledger_id, 1))
        depths: Dict[str, int] = {}
        while queue:
            current_id, depth = queue.pop(0)
            if current_id in depths and depths[current_id] <= depth:
                continue
            depths[current_id] = depth
            current = event_lookup.get(current_id) or {}
            for child in current.get("causal_children") or []:
                child_ledger_id = child if child in event_lookup else source_lookup.get(child, "")
                if child_ledger_id:
                    queue.append((child_ledger_id, depth + 1))
        return depths

    def _unstable_facts(self, *, event: Dict, event_lookup: Dict[str, Dict], downstream_depths: Dict[str, int]) -> List[Dict]:
        participants = set(event.get("participants") or [])
        results = []
        for event_id, depth in sorted(downstream_depths.items(), key=lambda item: (item[1], item[0])):
            item = event_lookup.get(event_id) or {}
            related_participants = participants.intersection(item.get("participants") or [])
            affected_preconditions = self._affected_preconditions(event, item)
            if depth == 1:
                reason = "directly caused by divergence event"
                status = "invalidated"
            elif affected_preconditions:
                reason = "downstream event depends on a precondition likely altered by divergence"
                status = "unstable"
            elif related_participants:
                reason = "downstream event still involves divergence participants"
                status = "unstable"
            else:
                reason = "causally downstream of divergence event"
                status = "unstable"
            results.append({
                "event_id": event_id,
                "summary": item.get("summary", ""),
                "status": status,
                "depth": depth,
                "reason": reason,
                "affected_preconditions": affected_preconditions,
                "stakes": item.get("stakes") or [],
            })
        return results

    def _affected_preconditions(self, event: Dict, downstream_event: Dict) -> List[str]:
        source_consequences = " ".join(event.get("direct_consequences") or []).lower()
        source_participants = {item.lower() for item in event.get("participants") or []}
        affected = []
        for precondition in downstream_event.get("preconditions") or []:
            lowered = precondition.lower()
            if any(participant in lowered for participant in source_participants):
                affected.append(precondition)
                continue
            if source_consequences and any(token in lowered for token in source_consequences.split()):
                affected.append(precondition)
        return affected
