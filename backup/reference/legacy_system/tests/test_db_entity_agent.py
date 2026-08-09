from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.agents.db_entity_agent import DatabaseEntityDiscoveryAgent
from saga.storage.models import Entity
from saga.storage.persistence import SagaSQLiteStore


def _sample_contract(tmp_path: Path) -> dict:
    chapter_text = (
        "Harry Potter sat in the hut on the rock while Hagrid spoke. "
        "An owl tapped at the window. The sea crashed below the hut. "
        "Hagrid handed Harry a letter from Hogwarts."
    )
    return {
        "inputs": {
            "series": {"series_id": "hp1-db-entities", "series_title": "HP1"},
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
            "scene_analysis_quality": {"total_scenes": 2, "successful_scenes": 2, "failed_scenes": 0},
        },
        "outputs": {
            "chapters": [{"book_index": 1, "chapter_index": 1, "title": "Chapter 1", "text": chapter_text}],
            "resolved_scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "scene_summary": "Harry listens to Hagrid in the hut.",
                    "text": chapter_text,
                    "provider": "ollama",
                    "model": "gpt-oss:120b-cloud",
                    "entities_present": [],
                    "events": [],
                }
            ],
            "entity_registry": [],
            "event_ledger": [
                {
                    "event_id": "e1",
                    "event_type": "interaction",
                    "description": "Harry listens to Hagrid in the hut.",
                    "characters": ["Harry", "Hagrid"],
                    "entities_involved": ["Harry", "Hagrid", "Hogwarts"],
                    "reason": "",
                    "outcome": "Harry receives important information.",
                    "chapter_index": 1,
                    "scene_index": 1,
                }
            ],
        },
    }


def test_db_entity_agent_retries_and_persists_entities(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
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
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, prompt: str, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"error": "parse_failed"}
            return {
                "should_create": True,
                "canonical_name": "Hogwarts",
                "entity_type": "location",
                "aliases": [],
                "entity_context": "wizarding school named in the letter",
                "evidence": "a letter from Hogwarts",
            }

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=StubLLM(),
        sqlite_store=store,
        max_attempts=2,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    assert result["inserted_count"] == 3
    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc())).scalars().all()
        assert len(rows) == 3
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Harry Potter", "character") in names
        assert ("Rubeus Hagrid", "character") in names
        assert ("Hogwarts", "location") in names


def test_db_entity_agent_prefers_full_seed_name_and_forces_location(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    contract = _sample_contract(tmp_path)
    contract["outputs"]["event_ledger"] = [
        {
            "event_id": "e1",
            "event_type": "observation",
            "description": "Harry looks out toward Privet Drive.",
            "characters": ["Harry"],
            "entities_involved": ["Harry", "Privet Drive"],
            "reason": "",
            "outcome": "He notices the street outside.",
            "chapter_index": 1,
            "scene_index": 1,
        }
    ]
    persisted = store.persist_contract(contract)
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
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

    class QuietLLM:
        def generate_json(self, prompt: str, **kwargs):
            return {
                "should_create": False,
            }

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=QuietLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    assert result["inserted_count"] == 2
    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc())).scalars().all()
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Harry Potter", "character") in names
        assert ("Privet Drive", "location") in names
        assert ("Harry", "character") not in names


def test_db_entity_agent_uses_typed_event_fields_deterministically(tmp_path: Path) -> None:
    db_path = tmp_path / "typed.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    contract = _sample_contract(tmp_path)
    contract["outputs"]["event_ledger"] = [
        {
            "event_id": "e1",
            "event_type": "action",
            "description": "Harry opens the letter in the hut.",
            "event_location": "Hut on the Rock",
            "characters": ["Harry"],
            "objects_involved": ["Letter"],
            "locations_involved": ["Hut on the Rock"],
            "entities_involved": ["Harry", "Letter", "Hut on the Rock"],
            "reason": "not_explicitly_stated",
            "outcome": "Harry reads the message.",
            "chapter_index": 1,
            "scene_index": 1,
        }
    ]
    persisted = store.persist_contract(contract)
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
        series_payload={
            "provider": "booknlp_clean_series",
            "characters": [
                {
                    "id": "char_harry",
                    "display_name": "Harry",
                    "aliases": ["Harry", "Harry Potter"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 1, "quote_count": 0}],
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

    class QuietLLM:
        def generate_json(self, prompt: str, **kwargs):
            raise AssertionError("typed deterministic resolution should not need LLM here")

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=QuietLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc())).scalars().all()
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Harry Potter", "character") in names
        assert ("Letter", "object") in names
        assert ("Hut On The Rock", "location") in names
    assert result["unresolved_entities"] == []


def test_db_entity_agent_prefers_seeded_character_even_if_event_field_is_wrong(tmp_path: Path) -> None:
    db_path = tmp_path / "typed_character.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    contract = _sample_contract(tmp_path)
    contract["outputs"]["event_ledger"] = [
        {
            "event_id": "e1",
            "event_type": "action",
            "description": "Hagrid carries Harry into the hut.",
            "event_location": "Hut on the Rock",
            "characters": ["Hagrid"],
            "creatures_involved": ["Harry"],
            "objects_involved": [],
            "locations_involved": ["Hut on the Rock"],
            "organizations_involved": [],
            "entities_involved": ["Hagrid", "Harry", "Hut on the Rock"],
            "reason": "not_explicitly_stated",
            "outcome": "Harry is safe inside.",
            "chapter_index": 1,
            "scene_index": 1,
        }
    ]
    persisted = store.persist_contract(contract)
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
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

    class QuietLLM:
        def generate_json(self, prompt: str, **kwargs):
            raise AssertionError("seeded character recovery should not need LLM here")

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=QuietLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc(), Entity.entity_type.asc())).scalars().all()
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Harry Potter", "character") in names
        assert ("Harry", "creature") not in names
    assert result["unresolved_entities"] == []


def test_db_entity_agent_sanitizes_split_and_noisy_seed_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "seed_cleanup.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    contract = _sample_contract(tmp_path)
    contract["outputs"]["event_ledger"] = [
        {
            "event_id": "e1",
            "event_type": "interaction",
            "description": "Dursley reads the letter at Privet Drive while Harry watches.",
            "event_location": "Privet Drive",
            "characters": ["Dursley", "Harry"],
            "objects_involved": ["Letter"],
            "locations_involved": ["Privet Drive"],
            "organizations_involved": [],
            "entities_involved": ["Dursley", "Harry", "Letter", "Privet Drive"],
            "reason": "not_explicitly_stated",
            "outcome": "The family reacts to the message.",
            "chapter_index": 1,
            "scene_index": 1,
        }
    ]
    persisted = store.persist_contract(contract)
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
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
                    "id": "char_dursley",
                    "display_name": "Dursley",
                    "aliases": ["Dursley", "Vernon Dursley"],
                    "risk_flags": ["possible_split_cluster"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 3, "quote_count": 0}],
                },
                {
                    "id": "char_noise",
                    "display_name": "ANYTHING Harry",
                    "aliases": ["ANYTHING Harry"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 5, "quote_count": 0}],
                },
                {
                    "id": "char_place",
                    "display_name": "Privet Drive",
                    "aliases": ["Privet Drive"],
                    "book_sources": [{"book_index": 1, "book_slug": "hp1", "mention_count": 14, "quote_count": 0}],
                },
            ],
            "alias_index": {
                "harry": "char_harry",
                "harry potter": "char_harry",
                "dursley": "char_dursley",
                "vernon dursley": "char_dursley",
                "anything harry": "char_noise",
                "privet drive": "char_place",
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
                "character_count": 4,
                "alias_count": 6,
                "reference_entity_count": 0,
                "suppressed_cluster_count": 0,
                "narrator": {},
            }
        ],
    )

    class QuietLLM:
        def generate_json(self, prompt: str, **kwargs):
            raise AssertionError("deterministic typed/entity resolution should not need LLM here")

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=QuietLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc(), Entity.entity_type.asc())).scalars().all()
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Harry Potter", "character") in names
        assert ("Vernon Dursley", "character") in names
        assert ("Privet Drive", "location") in names
        assert ("Privet Drive", "character") not in names
        assert ("ANYTHING Harry", "character") not in names
    assert result["unresolved_entities"] == []


def test_db_entity_agent_non_character_mentions_outrank_character_seed(tmp_path: Path) -> None:
    db_path = tmp_path / "cross_type.sqlite3"
    store = SagaSQLiteStore(database_path=db_path)
    contract = _sample_contract(tmp_path)
    contract["outputs"]["event_ledger"] = [
        {
            "event_id": "e1",
            "event_type": "discovery",
            "description": "Harry receives a Hogwarts letter in the hut.",
            "event_location": "Hut on the Rock",
            "characters": ["Hogwarts"],
            "objects_involved": ["Letter"],
            "locations_involved": ["Hut on the Rock"],
            "organizations_involved": ["Hogwarts"],
            "entities_involved": ["Hogwarts", "Letter", "Hut on the Rock"],
            "reason": "not_explicitly_stated",
            "outcome": "Harry learns about the school.",
            "chapter_index": 1,
            "scene_index": 1,
        }
    ]
    persisted = store.persist_contract(contract)
    store.persist_identity_bundle(
        series_id="hp1-db-entities",
        source_path="db://identity-series/hp1-db-entities",
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

    class QuietLLM:
        def generate_json(self, prompt: str, **kwargs):
            raise AssertionError("typed deterministic resolution should not need LLM here")

    agent = DatabaseEntityDiscoveryAgent(
        llm_client=QuietLLM(),
        sqlite_store=store,
        max_attempts=1,
        retry_delay_seconds=0.0,
    )
    result = agent.analyze_book_chapter(
        book_ref=f"db://book/{persisted['book_id']}",
        chapter_index=1,
    )

    with store.session_factory() as session:
        rows = session.execute(select(Entity).where(Entity.book_id == persisted["book_id"]).order_by(Entity.canonical_name.asc(), Entity.entity_type.asc())).scalars().all()
        names = {(row.canonical_name, row.entity_type) for row in rows}
        assert ("Hogwarts", "organization") in names
        assert ("Hogwarts", "character") not in names
        assert ("Letter", "object") in names
    assert result["unresolved_entities"] == []
