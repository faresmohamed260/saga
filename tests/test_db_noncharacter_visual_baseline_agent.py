from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from analysis.db_noncharacter_visual_baseline_agent import DatabaseNonCharacterVisualBaselineAgent
from sql_store.models import CreatureVisualBaseline, Entity, LocationVisualBaseline, ObjectVisualBaseline
from sql_store.persistence import SagaSQLiteStore
from sql_store.semantic_retrieval import SQLiteSemanticRetrievalService
from tests.test_db_event_agent import _sample_contract


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = str(text or "").lower()
        vectors.append(
            [
                float(lowered.count("owl") + lowered.count("bird")),
                float(lowered.count("letter") + lowered.count("parchment")),
                float(lowered.count("hut") + lowered.count("rock")),
                float(lowered.count("storm") + lowered.count("sea")),
            ]
        )
    return vectors


def test_db_noncharacter_visual_baseline_agent_persists_type_specific_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "noncharacter_visual.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))

    with store.session_factory() as session:
        session.add_all(
            [
                Entity(
                    book_id=persisted["book_id"],
                    canonical_name="Owl",
                    entity_type="creature",
                    mention_count=2,
                    first_seen_book_index=1,
                    first_seen_chapter_index=1,
                    first_seen_scene_index=1,
                    entity_context="A large owl delivering post.",
                    metadata_json={"aliases": ["the owl"]},
                ),
                Entity(
                    book_id=persisted["book_id"],
                    canonical_name="Letter",
                    entity_type="object",
                    mention_count=2,
                    first_seen_book_index=1,
                    first_seen_chapter_index=1,
                    first_seen_scene_index=1,
                    entity_context="A parchment Hogwarts letter.",
                    metadata_json={"aliases": ["letters"]},
                ),
                Entity(
                    book_id=persisted["book_id"],
                    canonical_name="Hut on the Rock",
                    entity_type="location",
                    mention_count=1,
                    first_seen_book_index=1,
                    first_seen_chapter_index=1,
                    first_seen_scene_index=1,
                    entity_context="A storm-battered hut isolated at sea.",
                    metadata_json={"aliases": ["the hut"]},
                ),
            ]
        )
        session.commit()

    class NonCharacterLLM:
        def generate_json(self, prompt: str, **kwargs):
            if '"entity_type": "creature"' in prompt:
                return {
                    "entity_name": "Owl",
                    "entity_type": "creature",
                    "visual_baseline": {
                        "species_kind": "owl",
                        "size_class": "medium bird",
                        "body_plan": "compact bird body",
                        "surface_covering": "feathers",
                        "coloration": "mottled brown",
                        "head_features": "round head",
                        "eyes": "large round eyes",
                        "limbs_appendages": "two wings and clawed feet",
                        "natural_weapons": "talons",
                        "wings": "broad feathered wings",
                        "tail": "short tail feathers",
                        "magical_features": "not_explicitly_stated_in_text",
                        "world_genre_cues": "British wizarding world messenger bird",
                    },
                    "evidence_excerpt": "An owl dropped a letter.",
                    "confidence": "high",
                }
            if '"entity_type": "object"' in prompt:
                return {
                    "entity_name": "Letter",
                    "entity_type": "object",
                    "visual_baseline": {
                        "object_class": "letter",
                        "function": "delivers written messages",
                        "size_scale": "handheld",
                        "shape_form": "flat folded rectangle",
                        "primary_material": "parchment",
                        "secondary_materials": "ink",
                        "color_finish": "cream",
                        "surface_texture": "papery",
                        "condition_default": "sealed and intact",
                        "symbolic_markings": "addressed in green ink",
                        "magical_properties": "not_explicitly_stated_in_text",
                        "world_genre_cues": "wizarding correspondence",
                    },
                    "evidence_excerpt": "A letter addressed in green ink arrived.",
                    "confidence": "high",
                }
            return {
                "entity_name": "Hut on the Rock",
                "entity_type": "location",
                "visual_baseline": {
                    "location_class": "hut",
                    "indoor_outdoor": "indoor shelter on exposed rock",
                    "environment_type": "coastal rock outcrop",
                    "region_or_domain": "sea coast",
                    "architecture_or_terrain_style": "small weather-beaten shack",
                    "dominant_materials": "wood",
                    "lighting_default": "dim interior light",
                    "weather_exposure": "high wind and sea spray exposure",
                    "ambient_mood": "bleak and isolated",
                    "notable_features": "perched on a rock in the sea",
                    "magic_or_tech_presence": "not_explicitly_stated_in_text",
                    "world_genre_cues": "grim coastal refuge",
                },
                "evidence_excerpt": "The hut stood on a rock out at sea.",
                "confidence": "medium",
            }

    result = DatabaseNonCharacterVisualBaselineAgent(
        llm_client=NonCharacterLLM(),
        sqlite_store=store,
        semantic_retrieval=SQLiteSemanticRetrievalService(sqlite_store=store, embedder=_stub_embedder),
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    assert result["persisted_visual_baselines"] == 3
    with store.session_factory() as session:
        creature = session.execute(select(CreatureVisualBaseline)).scalar_one()
        obj = session.execute(select(ObjectVisualBaseline)).scalar_one()
        location = session.execute(select(LocationVisualBaseline)).scalar_one()
        assert creature.surface_covering == "feathers"
        assert obj.primary_material == "parchment"
        assert location.ambient_mood == "bleak and isolated"

        rows = session.execute(select(Entity).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())).scalars().all()
        by_name = {row.canonical_name: row for row in rows}
        assert by_name["Owl"].first_appearance_profile["persistent_traits"]["magical_features"] == "not_explicitly_stated_in_text"
        assert by_name["Letter"].initial_physical_description["baseline_visual_fields"]["shape_form"] == "flat folded rectangle"
        assert by_name["Hut on the Rock"].metadata_json["noncharacter_visual_baseline_agent"]["source"] == DatabaseNonCharacterVisualBaselineAgent.VERSION
