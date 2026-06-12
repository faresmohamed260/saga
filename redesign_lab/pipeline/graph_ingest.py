"""Redesign-local Neo4j ingest stage."""

from __future__ import annotations

from typing import Any, Dict, List

from infrastructure.neo4j_ingestion_service import Neo4jIngestionService
from redesign_lab.pipeline.adapters import build_redesign_contract, now_utc


class GraphIngestStage:
    """Persist redesign artifacts into a redesign-only Neo4j namespace."""

    def __init__(self, *, series_suffix: str = "-redesign") -> None:
        self.series_suffix = series_suffix

    def redesign_series_id(self, base_series_id: str) -> str:
        return f"{base_series_id}{self.series_suffix}"

    def ingest(
        self,
        *,
        base_series_id: str,
        series_title: str,
        prepared_books: List[Dict[str, Any]],
        configuration: Dict[str, Any],
        scene_analyses: List[Dict[str, Any]],
        identity_result: Dict[str, Any],
        stable_character_states: List[Dict[str, Any]],
        causal_graph_result: Dict[str, Any],
        runtime: Dict[str, Any],
    ) -> Dict[str, Any]:
        redesign_series_id = self.redesign_series_id(base_series_id)
        service = Neo4jIngestionService()
        service.purge_series_residue(redesign_series_id)
        service.register_series(redesign_series_id, f"{series_title} (Redesign)")
        books = []
        for book in prepared_books:
            copied = dict(book)
            copied["series_id"] = redesign_series_id
            books.append(copied)
        contract = build_redesign_contract(
            series_id=redesign_series_id,
            series_title=f"{series_title} (Redesign)",
            prepared_books=books,
            configuration={
                **configuration,
                "series_id_suffix": self.series_suffix,
                "redesign_generated_at_utc": now_utc(),
            },
            scene_analyses=scene_analyses,
            identity_result=identity_result,
            stable_character_states=stable_character_states,
            causal_graph_result=causal_graph_result,
            runtime=runtime,
        )
        result = service.ingest_contract(contract, replace_existing=True)
        service.close()
        return {
            "series_id": redesign_series_id,
            "contract": contract,
            "ingest_result": result,
        }

