"""Prepare generation-facing rewrite context packets from the core artifact bundle."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.query.divergence_planning_service import DivergencePlanningService
from saga.domain.query.event_context_service import EventContextService


class RewriteContextService:
    """Collect the grounded context needed for a rewrite beat or chapter."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}
        self.event_context_service = EventContextService(self.bundle)
        self.divergence_planning_service = DivergencePlanningService(self.bundle)

    def build_rewrite_context(
        self,
        *,
        divergence_event_id: str,
        divergence_statement: str,
        anchor_event_id: str,
        involved_characters: List[str] | None = None,
    ) -> Dict:
        workspace = self.divergence_planning_service.plan_divergence(
            divergence_event_id,
            divergence_statement,
        )
        event_context = self.event_context_service.build_event_context(anchor_event_id)
        involved = set(involved_characters or [])
        if not involved:
            involved = {item.get("canonical_name", "") for item in event_context.get("participant_profiles", [])}
            involved.discard("")

        return {
            "divergence_workspace": workspace,
            "anchor_event_context": event_context,
            "relevant_arcs": self._relevant_arcs(involved),
            "relevant_knowledge": self._relevant_knowledge(involved, anchor_event_id),
            "continuity_constraints": self._continuity_constraints(workspace, involved),
        }

    def _relevant_arcs(self, involved_characters: set[str]) -> List[Dict]:
        rows = []
        for item in self.bundle.get("arc_registry", {}).get("items", []) or []:
            if involved_characters.intersection(item.get("characters", []) or []):
                rows.append(item)
        return rows

    def _relevant_knowledge(self, involved_characters: set[str], anchor_event_id: str) -> List[Dict]:
        rows = []
        anchor_time = 0
        for item in self.bundle.get("event_ledger") or []:
            if item.get("ledger_event_id") == anchor_event_id:
                anchor_time = item.get("time_index", 0)
                break
        for item in self.bundle.get("knowledge_registry", {}).get("items", []) or []:
            if item.get("subject") not in involved_characters:
                continue
            source_event = item.get("source_event", "")
            source_time = 0
            for event in self.bundle.get("event_ledger") or []:
                if event.get("ledger_event_id") == source_event:
                    source_time = event.get("time_index", 0)
                    break
            if source_time <= anchor_time:
                rows.append(item)
        return rows

    def _continuity_constraints(self, workspace: Dict, involved_characters: set[str]) -> List[str]:
        constraints = list(workspace.get("required_continuity_constraints") or [])
        for item in self.bundle.get("constraint_registry", {}).get("items", []) or []:
            rule = item.get("rule", "")
            if not rule:
                continue
            if item.get("scope") == "identity":
                if any(character in rule for character in involved_characters):
                    constraints.append(rule)
            else:
                constraints.append(rule)
        seen = set()
        output = []
        for rule in constraints:
            if rule not in seen:
                seen.add(rule)
                output.append(rule)
        return output
