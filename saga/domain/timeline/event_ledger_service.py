"""Legacy adapter for event-ledger construction.

The long-term source of truth now lives in :mod:`saga.domain.builders.event_ledger_builder`.
This service remains as a compatibility wrapper for the stable pipeline while the
new core artifact layer is adopted incrementally.
"""

from __future__ import annotations

from typing import Dict, List

from saga.domain.builders.event_ledger_builder import EventLedgerBuilder


class EventLedgerService:
    """Compatibility wrapper that delegates to the core event-ledger builder."""

    def __init__(self) -> None:
        self.builder = EventLedgerBuilder()

    def build(
        self,
        scene_analyses: List[Dict],
        timeline: List[Dict],
        causal_graph_result: Dict | None = None,
    ) -> List[Dict]:
        return self.builder.build(
            scene_analyses=scene_analyses,
            timeline=timeline,
            causal_graph_result=causal_graph_result,
        )
