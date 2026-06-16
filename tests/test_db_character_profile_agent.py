from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from analysis.db_character_profile_agent import DatabaseCharacterProfileAgent
from sql_store.models import CharacterProfile, CharacterVisualBaseline, Entity
from sql_store.persistence import SagaSQLiteStore
from tests.test_db_entity_agent import _sample_contract


def test_db_character_profile_agent_persists_profile_and_visual_baseline(tmp_path: Path) -> None:
    db_path = tmp_path / "character_profile.sqlite3"
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

    class StubLLM:
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, prompt: str, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"error": "parse_failed"}
            return {
                "character_name": "Harry Potter",
                "profile_summary": "A slight young wizard boy with dark hair and a watchful presence.",
                "personality_summary": "Curious, attentive, and quietly resilient.",
                "titles_or_roles": ["young wizard"],
                "affiliations": ["Hogwarts"],
                "core_traits": ["curious", "resilient"],
                "persistent_traits": {
                    "gender_presentation": "boy",
                    "species_or_race": "human wizard",
                    "apparent_age_group": "child",
                    "height_impression": "small for his age",
                    "build": "slight build",
                    "skin_tone_or_complexion": "",
                    "hair_color": "dark hair",
                    "hair_length_or_style": "short untidy hair",
                    "eye_color": "",
                    "facial_features": "thin face",
                    "distinguishing_marks": "",
                    "default_clothing_style": "",
                    "default_accessories": "",
                    "default_footwear": "",
                    "signature_items": "letter from Hogwarts",
                    "fantasy_features": "",
                    "world_genre_cues": "British boarding-school fantasy",
                },
                "evidence_excerpt": "Harry Potter sat in the hut on the rock while Hagrid spoke.",
                "confidence": "high",
            }

    agent = DatabaseCharacterProfileAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=2,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book(book_ref=f"db://book/{persisted['book_id']}")

    assert result["persisted_profiles"] == 1
    with store.session_factory() as session:
        profile = session.execute(select(CharacterProfile).where(CharacterProfile.book_id == persisted["book_id"])).scalar_one()
        assert profile.character_name == "Harry Potter"
        assert profile.payload_json["personality_summary"] == "Curious, attentive, and quietly resilient."
        baseline = session.execute(
            select(CharacterVisualBaseline).where(CharacterVisualBaseline.book_id == persisted["book_id"])
        ).scalar_one()
        assert baseline.height_impression == "small for his age"
        assert baseline.hair_color == "dark hair"
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Harry Potter")
        ).scalar_one()
        assert entity.first_appearance_profile["persistent_traits"]["build"] == "slight build"
