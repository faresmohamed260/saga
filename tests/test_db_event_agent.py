from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.agents.db_event_agent import DatabaseEventAnalysisAgent
from saga.storage.models import Event
from saga.storage.persistence import SagaSQLiteStore


def _sample_contract(tmp_path: Path) -> dict:
    return {
        "inputs": {
            "series": {"series_id": "hp1-db-events", "series_title": "HP1"},
            "books": [
                {
                    "book_index": 1,
                    "title": "Harry Potter 1.epub",
                    "path": str(tmp_path / "hp1.epub"),
                    "type": "epub",
                    "source_hash_sha256": "hp1",
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
            "scene_analysis_quality": {"total_scenes": 1, "successful_scenes": 1, "failed_scenes": 0},
        },
        "outputs": {
            "chapters": [{"book_index": 1, "chapter_index": 1, "title": "Chapter 1", "text": "Harry meets Hagrid."}],
            "resolved_scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "scene_summary": "Harry meets Hagrid.",
                    "text": "Harry meets Hagrid in the hut on the rock.",
                    "provider": "ollama",
                    "model": "gpt-oss:120b-cloud",
                    "entities_present": [
                        {"name": "Harry", "entity_type": "character"},
                        {"name": "Hagrid", "entity_type": "character"},
                    ],
                    "events": [],
                }
            ],
            "entity_registry": [
                {
                    "name": "Harry",
                    "entity_type": "character",
                    "mention_count": 1,
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "entity_context": "Young wizard.",
                },
                {
                    "name": "Hagrid",
                    "entity_type": "character",
                    "mention_count": 1,
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "entity_context": "Groundskeeper.",
                },
            ],
        },
    }


def test_db_event_agent_retries_and_persists_events(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    store.persist_identity_bundle(
        series_id="hp1-db-events",
        source_path="db://identity-series/hp1-db-events",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
                    "llm_review": {"recommended_bucket": "stable"},
                },
                {
                    "id": "char_hagrid",
                    "display_name": "Hagrid",
                    "aliases": ["Hagrid", "Rubeus Hagrid"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
                },
            ],
            "alias_index": {"harry": "char_harry", "harry potter": "char_harry", "hagrid": "char_hagrid"},
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
                "character_count": 2,
                "alias_count": 3,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )

    class StubLLM:
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, prompt: str, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"error": "parse_failed"}
            return {
                "events": [
                    {
                        "description": "Harry meets Hagrid.",
                        "event_location": "",
                        "characters": ["Harry", "Hagrid"],
                        "creatures_involved": ["Owl"],
                        "objects_involved": ["Letter"],
                        "locations_involved": ["Hut on the Rock"],
                        "organizations_involved": ["Hogwarts"],
                        "entities_involved": ["Harry", "Hagrid"],
                        "reason": "",
                        "outcome": "",
                        "type": "discovery",
                    }
                ]
            }

    agent = DatabaseEventAnalysisAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=2,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    assert result["inserted_event_count"] == 1
    with store.session_factory() as session:
        rows = session.execute(select(Event)).scalars().all()
        assert len(rows) == 1
        payload = rows[0].payload_json or {}
        assert payload["agent_metadata"]["source"] == agent.VERSION
        assert payload["event_location"] == "unspecified_location"
        assert payload["creatures_involved"] == ["Owl"]
        assert payload["objects_involved"] == ["Letter"]
        assert payload["locations_involved"] == ["Hut On The Rock"]
        assert payload["organizations_involved"] == ["Hogwarts"]
        assert payload["reason"] == agent.UNSPECIFIED_REASON
        assert payload["outcome"] == agent.UNSPECIFIED_OUTCOME


def test_db_event_agent_does_not_backfill_seeded_characters_before_entity_pass(tmp_path: Path) -> None:
    db_path = tmp_path / "typed_chars.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    store.persist_identity_bundle(
        series_id="hp1-db-events",
        source_path="db://identity-series/hp1-db-events",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
                },
                {
                    "id": "char_hagrid",
                    "display_name": "Hagrid",
                    "aliases": ["Hagrid", "Rubeus Hagrid"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
                },
            ],
            "alias_index": {
                "harry": "char_harry",
                "harry potter": "char_harry",
                "hagrid": "char_hagrid",
                "rubeus hagrid": "char_hagrid",
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
                "character_count": 2,
                "alias_count": 4,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )

    class StubLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "events": [
                    {
                        "description": "Dumbledore places a bundle of blankets containing a baby Harry on the step of number four.",
                        "event_location": "Number Four",
                        "characters": ["Dumbledore"],
                        "creatures_involved": ["Harry"],
                        "objects_involved": ["Blankets"],
                        "locations_involved": ["Number Four"],
                        "organizations_involved": [],
                        "entities_involved": ["Dumbledore", "Harry", "Blankets", "Number Four"],
                        "reason": "To leave Harry with his relatives.",
                        "outcome": "Harry remains on the doorstep.",
                        "type": "action",
                    }
                ]
            }

    agent = DatabaseEventAnalysisAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    event = result["events"][0]
    assert event["characters"] == ["Dumbledore"]
    assert "Harry" not in event["creatures_involved"]


def test_db_event_agent_keeps_seed_noise_out_before_character_backfill_phase(tmp_path: Path) -> None:
    db_path = tmp_path / "seed_cleanup.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    store.persist_identity_bundle(
        series_id="hp1-db-events",
        source_path="db://identity-series/hp1-db-events",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 40, "quote_count": 0}],
                },
                {
                    "id": "char_privet_drive",
                    "display_name": "Privet Drive",
                    "aliases": ["Privet Drive"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 14, "quote_count": 0}],
                },
                {
                    "id": "char_merged",
                    "display_name": "Professor Dumbledore Professor McGonagall",
                    "aliases": ["Professor Dumbledore Professor McGonagall"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 4, "quote_count": 0}],
                },
            ],
            "alias_index": {
                "harry": "char_harry",
                "harry potter": "char_harry",
                "privet drive": "char_privet_drive",
                "professor dumbledore professor mcgonagall": "char_merged",
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
                "character_count": 3,
                "alias_count": 4,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )

    class StubLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "events": [
                    {
                        "description": "Harry is left on Privet Drive.",
                        "event_location": "Privet Drive",
                        "characters": [],
                        "creatures_involved": [],
                        "objects_involved": [],
                        "locations_involved": ["Privet Drive"],
                        "organizations_involved": [],
                        "entities_involved": ["Harry", "Privet Drive"],
                        "reason": "Dumbledore leaves him there.",
                        "outcome": "Harry remains at number four.",
                        "type": "action",
                    }
                ]
            }

    agent = DatabaseEventAnalysisAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    event = result["events"][0]
    assert event["characters"] == []
    assert "Privet Drive" not in event["characters"]


def test_db_event_agent_non_character_fields_outrank_character_seed(tmp_path: Path) -> None:
    db_path = tmp_path / "non_character_precedence.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    persisted = store.persist_contract(_sample_contract(tmp_path))
    store.persist_identity_bundle(
        series_id="hp1-db-events",
        source_path="db://identity-series/hp1-db-events",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_hogwarts",
                    "display_name": "Hogwarts",
                    "aliases": ["Hogwarts"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 42, "quote_count": 0}],
                }
            ],
            "alias_index": {"hogwarts": "char_hogwarts"},
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
                "alias_count": 1,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )

    class StubLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "events": [
                    {
                        "description": "Harry reads a letter from Hogwarts.",
                        "event_location": "Hut on the Rock",
                        "characters": ["Hogwarts"],
                        "creatures_involved": [],
                        "objects_involved": ["Letter"],
                        "locations_involved": ["Hut on the Rock"],
                        "organizations_involved": ["Hogwarts"],
                        "entities_involved": ["Hogwarts", "Letter"],
                        "reason": "not_explicitly_stated",
                        "outcome": "Harry learns about the school.",
                        "type": "discovery",
                    }
                ]
            }

    agent = DatabaseEventAnalysisAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    event = result["events"][0]
    assert event["characters"] == []
    assert event["organizations_involved"] == ["Hogwarts"]
