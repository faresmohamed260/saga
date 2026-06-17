"""Dependency queries over the event ledger and causal graph."""

from __future__ import annotations

from typing import Dict, List


class DependencyQueryService:
    """Small query helper for causal downstream dependency inspection."""

    def __init__(self, artifact_bundle: Dict):
        self.bundle = artifact_bundle or {}

    def get_downstream_dependencies(self, ledger_event_id: str) -> List[Dict]:
        ledger_rows = self.bundle.get("event_ledger") or []
        ledger = {item.get("ledger_event_id"): item for item in ledger_rows}
        source_lookup = {
            item.get("source_event_id"): item
            for item in ledger_rows
            if item.get("source_event_id")
        }
        start = ledger.get(ledger_event_id)
        if not start:
            return []
        queue = list(start.get("causal_children") or [])
        seen = set(queue)
        results = []
        while queue:
            child_id = queue.pop(0)
            child = ledger.get(child_id) or source_lookup.get(child_id)
            if not child:
                continue
            results.append(child)
            for grandchild in child.get("causal_children") or []:
                if grandchild not in seen:
                    seen.add(grandchild)
                    queue.append(grandchild)
        return results
