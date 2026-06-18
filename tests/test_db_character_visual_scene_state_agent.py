from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.agents.db_character_visual_scene_state_agent import DatabaseCharacterVisualSceneStateAgent
from saga.storage.models import CharacterVisualSceneState, Entity
from saga.storage.persistence import SagaSQLiteStore
from tests.test_db_entity_agent import _sample_contract


def test_db_character_visual_scene_state_agent_persists_scene_state(tmp_path: Path) -> None:
    db_path = tmp_path / "character_visual_scene.sqlite3"
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

    class SceneStateLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "scene_states": [
                    {
                        "character_name": "Harry Potter",
                        "scene_state": {
                            "scene_outfit": "oversized worn clothes",
                            "scene_accessories": "broken glasses",
                            "scene_footwear": "not_explicitly_stated_in_text",
                            "visible_condition": "cold and tense",
                            "injuries": "not_explicitly_stated_in_text",
                            "dirt_blood_markings": "not_explicitly_stated_in_text",
                            "body_language": "hunched and wary",
                            "expression": "startled",
                            "carried_items": "birthday cake box",
                            "temporary_effects": "not_explicitly_stated_in_text",
                        },
                        "evidence_excerpt": "Harry stood in the hut wearing oversized clothes and broken glasses while Hagrid spoke.",
                        "confidence": "high",
                    }
                ]
            }

    result = DatabaseCharacterVisualSceneStateAgent(
        llm_client=SceneStateLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    ).analyze_book(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_indices=[1],
        character_names=["Harry Potter"],
    )

    assert result["persisted_scene_states"] == 1
    with store.session_factory() as session:
        row = session.execute(
            select(CharacterVisualSceneState).where(CharacterVisualSceneState.book_id == persisted["book_id"])
        ).scalar_one()
        assert row.scene_outfit == "oversized worn clothes"
        assert row.visible_condition == "cold and tense"
        entity = session.execute(
            select(Entity).where(Entity.book_id == persisted["book_id"], Entity.canonical_name == "Harry Potter")
        ).scalar_one()
        assert isinstance(entity.visual_change_log, list)
        assert entity.visual_change_log[0]["expression"] == "startled"
