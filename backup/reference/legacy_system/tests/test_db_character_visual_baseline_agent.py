from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.agents.db_character_profile_agent import DatabaseCharacterProfileAgent
from saga.agents.db_character_visual_baseline_agent import DatabaseCharacterVisualBaselineAgent
from saga.services.retrieval_service import RetrievalService
from saga.storage.models import CharacterProfile, CharacterVisualBaseline, Entity
from saga.storage.persistence import SagaSQLiteStore
from tests.test_db_entity_agent import _sample_contract


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = str(text or "").lower()
        vectors.append(
            [
                float(lowered.count("harry")),
                float(lowered.count("hair")),
                float(lowered.count("hut")),
                float(lowered.count("wizard")),
            ]
        )
    return vectors


def test_db_character_visual_baseline_agent_fills_all_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "character_visual.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry Potter",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 6, "quote_count": 0}],
                }
            ],
            "alias_index": {
                "harry": "char_harry",
                "harry potter": "char_harry",
            },
            "reference_entities": [],
            "narrators": [],
            "diagnostics": {},
        },
        book_summaries=[
            {
                "book_index": 1,
                "book_slug": "hp1",
                "title": "Harry Potter 1.epub",
                "output_dir": str(tmp_path / "identity" / "book_01_hp1"),
                "pipeline_identity_path": str(tmp_path / "identity" / "book_01_hp1" / "booknlp_small_pipeline_identity.json"),
                "character_count": 1,
                "alias_count": 2,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )
    with store.session_factory() as session:
        session.add(
            Entity(
                book_id=persisted["book_id"],
                canonical_name="Harry Potter",
                entity_type="character",
                mention_count=4,
                first_seen_book_index=1,
                first_seen_chapter_index=1,
                first_seen_scene_index=1,
                entity_context="young wizard boy in the hut scene",
                metadata_json={"aliases": ["Harry"]},
            )
        )
        session.commit()

    class ProfileLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "character_name": "Harry Potter",
                "profile_summary": "A young wizard boy living with the Dursleys.",
                "personality_summary": "Curious and resilient.",
                "titles_or_roles": ["young wizard"],
                "affiliations": ["Hogwarts (future)"],
                "core_traits": ["curious"],
                "persistent_traits": {
                    "gender_presentation": "male",
                    "species_or_race": "human wizard",
                    "apparent_age_group": "boy",
                    "height_impression": "",
                    "build": "",
                    "skin_tone_or_complexion": "",
                    "hair_color": "",
                    "hair_length_or_style": "",
                    "eye_color": "",
                    "facial_features": "",
                    "distinguishing_marks": "",
                    "default_clothing_style": "",
                    "default_accessories": "",
                    "default_footwear": "",
                    "signature_items": "",
                    "fantasy_features": "",
                    "world_genre_cues": "",
                },
                "evidence_excerpt": "Harry Potter sat in the hut on the rock while Hagrid spoke.",
                "confidence": "high",
            }

    DatabaseCharacterProfileAgent(
        llm_client=ProfileLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    class VisualLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "character_name": "Harry Potter",
                "visual_baseline": {
                    "gender_presentation": "male",
                    "species_or_race": "human wizard",
                    "apparent_age_group": "boy",
                    "height_impression": "not_explicitly_stated_in_text",
                    "build": "slight build",
                    "skin_tone_or_complexion": "not_explicitly_stated_in_text",
                    "hair_color": "dark hair",
                    "hair_length_or_style": "untidy short hair",
                    "eye_color": "not_explicitly_stated_in_text",
                    "facial_features": "thin face",
                    "distinguishing_marks": "not_explicitly_stated_in_text",
                    "default_clothing_style": "not_explicitly_stated_in_text",
                    "default_accessories": "not_explicitly_stated_in_text",
                    "default_footwear": "not_explicitly_stated_in_text",
                    "signature_items": "letter from Hogwarts",
                    "fantasy_features": "not_explicitly_stated_in_text",
                    "world_genre_cues": "British boarding-school fantasy",
                },
                "evidence_excerpt": "Harry Potter sat in the hut on the rock while Hagrid spoke.",
                "confidence": "high",
            }

    result = DatabaseCharacterVisualBaselineAgent(
        llm_client=VisualLLM(),
        sqlite_store=store,
        retrieval_tool=RetrievalService(sqlite_store=store, embedder=_stub_embedder),
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    assert result["persisted_visual_baselines"] == 1
    with store.session_factory() as session:
        baseline = session.execute(
            select(CharacterVisualBaseline).where(CharacterVisualBaseline.book_id == persisted["book_id"])
        ).scalar_one()
        assert baseline.hair_color == "dark hair"
        assert baseline.height_impression == "not_explicitly_stated_in_text"
        profile = session.execute(
            select(CharacterProfile).where(CharacterProfile.book_id == persisted["book_id"])
        ).scalar_one()
        assert profile.payload_json["persistent_traits"]["hair_color"] == "dark hair"
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Harry Potter")
        ).scalar_one()
        assert entity.first_appearance_profile["persistent_traits"]["default_footwear"] == "not_explicitly_stated_in_text"


def test_db_character_visual_baseline_agent_uses_web_reference_as_gap_fill(tmp_path: Path) -> None:
    db_path = tmp_path / "character_visual_web.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    with store.session_factory() as session:
        session.add(
            Entity(
                book_id=persisted["book_id"],
                canonical_name="Harry Potter",
                entity_type="character",
                mention_count=4,
                first_seen_book_index=1,
                first_seen_chapter_index=1,
                first_seen_scene_index=1,
                entity_context="young wizard boy in the hut scene",
                metadata_json={"aliases": ["Harry"]},
            )
        )
        session.commit()

    captured = {"prompt": ""}

    class StubWikiService:
        def research_character(self, name: str, **kwargs) -> dict:
            return {
                "display_name": name,
                "page_title": "Harry_Potter",
                "page_url": "https://harrypotter.fandom.com/wiki/Harry_Potter",
                "resolved_via": "exact_search_match",
                "confidence": "high",
                "structured_traits": {
                    "hair_description": "jet-black untidy hair",
                    "eye_description": "bright green eyes",
                    "distinguishing_marks": "lightning-shaped scar",
                },
                "canon_notes": ["boy wizard", "round glasses", "lightning scar"],
                "agent_web_search_used": True,
            }

    class VisualLLM:
        def generate_json(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            return {
                "character_name": "Harry Potter",
                "visual_baseline": {
                    "gender_presentation": "male",
                    "species_or_race": "human wizard",
                    "apparent_age_group": "boy",
                    "height_impression": "not_explicitly_stated_in_text",
                    "build": "slight build",
                    "skin_tone_or_complexion": "not_explicitly_stated_in_text",
                    "hair_color": "black",
                    "hair_length_or_style": "untidy hair",
                    "eye_color": "green",
                    "facial_features": "not_explicitly_stated_in_text",
                    "distinguishing_marks": "lightning-shaped scar",
                    "default_clothing_style": "not_explicitly_stated_in_text",
                    "default_accessories": "round glasses",
                    "default_footwear": "not_explicitly_stated_in_text",
                    "signature_items": "wand",
                    "fantasy_features": "lightning-shaped scar",
                    "world_genre_cues": "British wizarding school fantasy",
                },
                "evidence_excerpt": "Harry Potter sat in the hut on the rock while Hagrid spoke.",
                "confidence": "high",
            }

    DatabaseCharacterVisualBaselineAgent(
        llm_client=VisualLLM(),
        sqlite_store=store,
        retrieval_tool=RetrievalService(sqlite_store=store, embedder=_stub_embedder),
        web_reference_service=StubWikiService(),
        web_reference_policy="always",
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    assert "External web reference" in captured["prompt"]
    assert "Harry_Potter" in captured["prompt"]
    with store.session_factory() as session:
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Harry Potter")
        ).scalar_one()
        metadata = entity.metadata_json or {}
        assert metadata["character_visual_baseline_agent"]["web_reference_used"] is True
        assert metadata["character_visual_baseline_agent"]["web_reference"]["page_title"] == "Harry_Potter"


def test_db_character_visual_baseline_agent_backfills_missing_slots_from_web_only(tmp_path: Path) -> None:
    db_path = tmp_path / "character_visual_web_only.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    with store.session_factory() as session:
        session.add(
            Entity(
                book_id=persisted["book_id"],
                canonical_name="Harry Potter",
                entity_type="character",
                mention_count=4,
                first_seen_book_index=1,
                first_seen_chapter_index=1,
                first_seen_scene_index=1,
                entity_context="young wizard boy in the hut scene",
                initial_physical_description={
                    "baseline_visual_fields": {
                        "gender_presentation": "male",
                        "species_or_race": "human wizard",
                        "apparent_age_group": "boy",
                        "height_impression": "not_explicitly_stated_in_text",
                        "build": "not_explicitly_stated_in_text",
                        "skin_tone_or_complexion": "not_explicitly_stated_in_text",
                        "hair_color": "not_explicitly_stated_in_text",
                        "hair_length_or_style": "not_explicitly_stated_in_text",
                        "eye_color": "not_explicitly_stated_in_text",
                        "facial_features": "not_explicitly_stated_in_text",
                        "distinguishing_marks": "not_explicitly_stated_in_text",
                        "default_clothing_style": "not_explicitly_stated_in_text",
                        "default_accessories": "not_explicitly_stated_in_text",
                        "default_footwear": "not_explicitly_stated_in_text",
                        "signature_items": "not_explicitly_stated_in_text",
                        "fantasy_features": "not_explicitly_stated_in_text",
                        "world_genre_cues": "not_explicitly_stated_in_text",
                    }
                },
                first_appearance_profile={"persistent_traits": {}},
                metadata_json={"aliases": ["Harry"]},
            )
        )
        session.commit()

    class StubWikiService:
        def research_character(self, name: str, **kwargs) -> dict:
            return {
                "display_name": name,
                "page_title": "Harry_Potter",
                "page_url": "https://harrypotter.fandom.com/wiki/Harry_Potter",
                "resolved_via": "direct_title_match",
                "confidence": "high",
                "structured_traits": {
                    "hair_description": "jet-black untidy hair",
                    "eye_description": "bright green eyes",
                    "skin_description": "pale skin",
                    "body_type": "slight build",
                    "facial_structure": "thin face",
                    "clothing_description": "black Hogwarts robes",
                    "footwear_description": "black school shoes",
                    "world_aesthetic_cues": "British wizarding boarding-school fantasy",
                    "distinguishing_marks": "lightning-shaped scar",
                    "fantasy_features": "wizard with a wand",
                },
                "canon_notes": ["round glasses", "lightning scar", "school robes"],
                "agent_web_search_used": True,
            }

    result = DatabaseCharacterVisualBaselineAgent(
        sqlite_store=store,
        retrieval_tool=RetrievalService(sqlite_store=store, embedder=_stub_embedder),
        web_reference_service=StubWikiService(),
        web_reference_policy="always",
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).backfill_web_reference_gaps(book_ref=f"db://book/{persisted['book_id']}")

    assert result["updated_characters"] == 1
    with store.session_factory() as session:
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Harry Potter")
        ).scalar_one()
        traits = entity.initial_physical_description["baseline_visual_fields"]
        assert traits["hair_color"] == "jet-black untidy hair"
        assert traits["eye_color"] == "bright green eyes"
        assert traits["default_clothing_style"] == "black Hogwarts robes"
        assert entity.metadata_json["character_web_gap_fill"]["page_title"] == "Harry_Potter"
