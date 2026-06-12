"""Redesign-local retrieval build stage."""

from __future__ import annotations

from typing import Any, Dict

from query.neo4j_narrative_context_service import Neo4jNarrativeContextService
from redesign_lab.pipeline.contracts import validate_contract


class RetrievalBuildStage:
    """Build decoder-ready retrieval context from the redesign graph."""

    def build(self, *, series_id: str) -> Dict[str, Any]:
        context = Neo4jNarrativeContextService().build_from_graph(series_id=series_id)
        packet = {
            "series_id": series_id,
            "meta": context.get("meta", {}),
            "story_ending": context.get("story_ending", {}),
            "character_states": context.get("character_states", []),
            "relationship_summary": context.get("relationship_summary", []),
            "unresolved_threads": context.get("unresolved_threads", []),
            "retrieval_documents": context.get("retrieval_documents", []),
            "_raw_context": context,
        }
        return validate_contract("retrieval_packet", packet)

