from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.agents.db_noncharacter_visual_dossier_agent import DatabaseNonCharacterVisualDossierAgent
from saga.services.retrieval_service import RetrievalService
from saga.storage.models import Entity
from saga.storage.persistence import SagaSQLiteStore
from tests.test_db_event_agent import _sample_contract


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = str(text or "").lower()
        vectors.append(
            [
                float(lowered.count("letter")),
                float(lowered.count("parchment")),
                float(lowered.count("green")),
                float(lowered.count("ink")),
            ]
        )
    return vectors


def test_db_noncharacter_visual_dossier_agent_enriches_entity_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "noncharacter_visual_dossier.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))

    with store.session_factory() as session:
        session.add(
            Entity(
                book_id=persisted["book_id"],
                canonical_name="Letter",
                entity_type="object",
                mention_count=2,
                first_seen_book_index=1,
                first_seen_chapter_index=1,
                first_seen_scene_index=1,
                entity_context="A parchment Hogwarts letter.",
                typed_attributes={"appearance": ["cream envelope"]},
                metadata_json={"aliases": ["letters"]},
            )
        )
        session.commit()

    class DossierLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "entity_name": "Letter",
                "entity_type": "object",
                "baseline_description": "A cream parchment Hogwarts letter with green ink and a formal hand-addressed finish.",
                "prompt_ready_description": "Cream parchment letter, hand-addressed in green ink, neat formal wizarding correspondence.",
                "typed_attributes": {
                    "appearance": ["cream parchment letter", "green ink address"],
                    "materials": ["parchment", "ink"],
                    "abilities": ["not_explicitly_stated_in_text"],
                    "owner_or_holder": ["not_explicitly_stated_in_text"],
                    "current_state": ["sealed and intact"],
                    "symbolic_role": ["invitation to Hogwarts"],
                },
                "persistent_traits": {
                    "object_class": "letter",
                    "function": "delivers a written message",
                    "size_scale": "handheld",
                    "shape_form": "flat folded rectangle",
                    "primary_material": "parchment",
                    "secondary_materials": "ink",
                    "color_finish": "cream with green lettering",
                    "surface_texture": "papery",
                    "condition_default": "sealed and intact",
                    "symbolic_markings": "addressed in green ink",
                    "magical_properties": "not_explicitly_stated_in_text",
                    "world_genre_cues": "wizarding correspondence",
                },
                "evidence_excerpt": "A letter addressed in green ink arrived.",
                "confidence": "high",
            }

    result = DatabaseNonCharacterVisualDossierAgent(
        llm_client=DossierLLM(),
        sqlite_store=store,
        retrieval_tool=RetrievalService(sqlite_store=store, embedder=_stub_embedder),
        max_attempts=1,
        retry_delay_seconds=0.0,
        max_entity_workers=1,
    ).analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    assert result["persisted_dossiers"] == 1
    with store.session_factory() as session:
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Letter")
        ).scalar_one()
        assert entity.initial_physical_description["description"].startswith("A cream parchment Hogwarts letter")
        assert entity.initial_physical_description["prompt_ready_description"].startswith("Cream parchment letter")
        assert entity.first_appearance_profile["typed_attributes"]["materials"] == ["parchment", "ink"]
        assert entity.typed_attributes["appearance"][0] == "cream envelope"
        assert "green ink address" in entity.typed_attributes["appearance"]
        assert entity.metadata_json["visual_dossier"]["source"] == DatabaseNonCharacterVisualDossierAgent.VERSION
