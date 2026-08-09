from __future__ import annotations

from pathlib import Path

from saga.storage.hybrid_retrieval import SQLiteHybridRetrievalService
from saga.storage.models import SemanticDocumentEmbedding
from saga.storage.persistence import SagaSQLiteStore


def _sample_contract(tmp_path: Path) -> dict:
    return {
        "inputs": {
            "series": {"series_id": "hp1-rag", "series_title": "HP1"},
            "books": [
                {
                    "book_index": 1,
                    "title": "Harry Potter 1.epub",
                    "path": str(tmp_path / "hp1.epub"),
                    "type": "epub",
                    "source_hash_sha256": "hp1-rag",
                }
            ],
        },
        "configuration": {
            "analysis_model": "gpt_oss",
            "analysis_provider_mode": "same_provider_rotating",
            "identity_provider": "booknlp_clean",
            "scene_failure_policy": "fail_fast",
        },
        "metadata": {
            "book_title": "Harry Potter 1.epub",
            "run_status": "success",
            "scene_analysis_quality": {"total_scenes": 2, "successful_scenes": 2, "failed_scenes": 0},
        },
        "outputs": {
            "chapters": [
                {"book_index": 1, "chapter_index": 1, "title": "Chapter 1", "text": "Harry with the letter."},
                {"book_index": 1, "chapter_index": 2, "title": "Chapter 2", "text": "An owl arrives at the hut."},
            ],
            "resolved_scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "scene_summary": "Harry receives a Hogwarts letter.",
                    "text": "Harry stares at the parchment letter addressed in green ink.",
                    "entities_present": [{"name": "Harry Potter", "entity_type": "character"}, {"name": "Letter", "entity_type": "object"}],
                    "events": [],
                },
                {
                    "book_index": 1,
                    "chapter_index": 2,
                    "scene_index": 1,
                    "scene_summary": "An owl lands near the hut on the rock.",
                    "text": "A mottled brown owl beats its wings and lands by the storm-battered hut on the rock.",
                    "entities_present": [{"name": "Owl", "entity_type": "creature"}, {"name": "Hut on the Rock", "entity_type": "location"}],
                    "events": [],
                },
            ],
            "event_ledger": [
                {
                    "event_id": "e1",
                    "event_type": "delivery",
                    "description": "Harry receives a Hogwarts letter.",
                    "reason": "The school contacts him.",
                    "outcome": "Harry reads the message.",
                    "chapter_index": 1,
                    "scene_index": 1,
                    "entities_involved": ["Harry Potter", "Letter"],
                    "objects_involved": ["Letter"],
                },
                {
                    "event_id": "e2",
                    "event_type": "arrival",
                    "description": "An owl arrives at the hut.",
                    "reason": "It carries post.",
                    "outcome": "The owl lands safely.",
                    "chapter_index": 2,
                    "scene_index": 1,
                    "entities_involved": ["Owl", "Hut on the Rock"],
                    "creatures_involved": ["Owl"],
                    "locations_involved": ["Hut on the Rock"],
                },
            ],
            "entity_registry": [],
        },
    }


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = str(text or "").lower()
        vectors.append(
            [
                float(lowered.count("harry") + lowered.count("letter") + lowered.count("parchment")),
                float(lowered.count("owl") + lowered.count("wings") + lowered.count("brown")),
                float(lowered.count("hut") + lowered.count("rock") + lowered.count("storm")),
            ]
        )
    return vectors


def test_sqlite_hybrid_retrieval_indexes_and_queries_db_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "hybrid.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path), contract_path=None)
    service = SQLiteHybridRetrievalService(sqlite_store=store, embedder=_stub_embedder)

    index_summary = service.ensure_book_index(book_id=persisted["book_id"])

    assert index_summary["document_count"] == 4
    with store.session_factory() as session:
        rows = session.query(SemanticDocumentEmbedding).all()
        assert len(rows) == 4

    hits = service.query_book(
        book_id=persisted["book_id"],
        query_text="Which scene describes an owl with brown feathers near the hut?",
        top_k=2,
        entity_bias=["Owl", "Hut on the Rock"],
    )

    assert hits
    assert hits[0]["source_type"] in {"scene", "event"}
    assert any("owl" in hit["excerpt"].lower() for hit in hits)
    assert hits[0]["chapter_index"] == 2
