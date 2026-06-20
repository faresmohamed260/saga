from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from saga.storage.models import AudiobookChapter, AudiobookRun, Book, Chapter, Entity, GeneratedImage, IdentityAlias, IdentityCharacter, IdentitySeries, Scene, VisualPrompt
from saga.storage.persistence import SagaSQLiteStore


def _sample_contract(tmp_path: Path) -> dict:
    return {
        "inputs": {
            "series": {"series_id": "acotar", "series_title": "ACOTAR"},
            "books": [
                {
                    "book_index": 1,
                    "title": "A Court of Thorns and Roses.epub",
                    "path": str(tmp_path / "acotar.epub"),
                    "type": "epub",
                    "source_hash_sha256": "abc123",
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
            "book_title": "A Court of Thorns and Roses.epub",
            "run_status": "success",
            "scene_analysis_quality": {"total_scenes": 1, "successful_scenes": 1, "failed_scenes": 0},
        },
        "outputs": {
            "chapters": [{"book_index": 1, "chapter_index": 1, "title": "Chapter 1", "text": "Feyre hunts in the woods."}],
            "resolved_scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "scene_summary": "Feyre hunts in the woods.",
                    "text": "Feyre hunts in the woods.",
                    "provider": "ollama",
                    "model": "gpt-oss:120b-cloud",
                    "entities_present": [{"name": "Feyre", "entity_type": "character"}],
                    "events": [{"event_id": "e1", "event_type": "action", "description": "Feyre hunts.", "entities_involved": ["Feyre"]}],
                }
            ],
            "entity_registry": [
                {
                    "name": "Feyre",
                    "entity_type": "character",
                    "mention_count": 1,
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "entity_context": "Young huntress.",
                    "initial_physical_description": {"status": "captured", "description": "slender young woman with long brown hair"},
                    "first_appearance_profile": {
                        "status": "captured",
                        "baseline_description": "slender young woman with long brown hair",
                        "persistent_traits": {
                            "apparent_age_group": "young woman",
                            "build": "slender",
                            "hair_color": "brown",
                            "default_clothing_style": "worn cloak",
                        },
                    },
                    "typed_attributes": {"appearance": ["slender"], "outfit": ["worn cloak"]},
                    "persistent_traits": {
                        "apparent_age_group": "young woman",
                        "build": "slender",
                        "hair_color": "brown",
                        "default_clothing_style": "worn cloak",
                    },
                    "scene_visual_states": [
                        {
                            "state": {"visible_condition": "cold", "scene_outfit": "worn cloak"},
                            "book_index": 1,
                            "chapter_index": 1,
                            "scene_index": 1,
                        }
                    ],
                    "descriptions": [{"description": "slender young woman with long brown hair", "description_type": "stable_trait", "book_index": 1, "chapter_index": 1, "scene_index": 1}],
                    "state_changes": [],
                    "event_links": [],
                    "visual_change_log": [],
                    "analysis_quality_flags": [],
                }
            ],
            "event_ledger": [
                {"event_id": "e1", "event_type": "action", "description": "Feyre hunts.", "chapter_index": 1, "scene_index": 1, "entities_involved": ["Feyre"]}
            ],
            "timeline": [{"event_id": "e1", "description": "Feyre hunts."}],
            "character_profiles": [{"character_name": "Feyre", "core_description": "A young huntress."}],
            "stable_character_states": [{"character_name": "Feyre", "state": {"location": "woods"}}],
            "visual_prompt_sets": {
                "initial_characters": [
                    {
                        "entity_name": "Feyre",
                        "entity_type": "character",
                        "prompt_type": "initial_character_description",
                        "positive_prompt": "portrait of Feyre",
                        "source_evidence": "slender young woman with long brown hair",
                        "confidence": "high",
                        "book_index": 1,
                        "chapter_index": 1,
                        "scene_index": 1,
                        "details": {"persistent_visual_profile": {"hair_description": "long brown hair"}},
                    }
                ]
            },
        },
    }


def test_sql_store_persists_contract_and_render_manifest(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    contract = _sample_contract(tmp_path)
    contract_path = tmp_path / "contract.json"
    result = store.persist_contract(contract, contract_path=contract_path)
    assert result["scene_count"] == 1

    image_path = tmp_path / "feyre.png"
    image_path.write_bytes(b"fakepng")
    manifest = {
        "contract_path": str(contract_path),
        "workflow_mode": "character_sheet",
        "renders": [
            {
                "entity_name": "Feyre",
                "entity_type": "character",
                "prompt_type": "initial_character_description",
                "visual_bucket": "initial_characters",
                "positive_prompt": "portrait of Feyre",
                "negative_prompt": "bad anatomy",
                "source_evidence": "slender young woman with long brown hair",
                "confidence": "high",
                "output_path": str(image_path),
                "status": "rendered",
            }
        ],
    }
    render_result = store.persist_render_manifest(manifest)
    assert render_result["stored_images"] == 1

    with store.session_factory() as session:
        assert session.execute(select(Book)).scalars().all()
        assert session.execute(select(Scene)).scalars().all()
        assert session.execute(select(Entity)).scalars().all()
        prompts = session.execute(select(VisualPrompt)).scalars().all()
        images = session.execute(select(GeneratedImage)).scalars().all()
        assert len(prompts) >= 1
        assert len(images) == 1
        assert images[0].image_bytes == b"fakepng"


def test_sql_store_persists_render_manifest_for_db_book_ref(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    result = store.persist_contract(_sample_contract(tmp_path), contract_path=None)
    book_ref = f"db://book/{result['book_id']}"

    image_path = tmp_path / "feyre-db.png"
    image_path.write_bytes(b"fakepngdb")
    render_result = store.persist_render_manifest(
        {
            "contract_path": book_ref,
            "workflow_mode": "character_sheet",
            "renders": [
                {
                    "entity_name": "Feyre",
                    "entity_type": "character",
                    "prompt_type": "initial_character_description",
                    "visual_bucket": "initial_characters",
                    "positive_prompt": "portrait of Feyre",
                    "negative_prompt": "bad anatomy",
                    "source_evidence": "slender young woman with long brown hair",
                    "confidence": "high",
                    "output_path": str(image_path),
                    "status": "rendered",
                }
            ],
        }
    )
    assert render_result["stored_images"] == 1


def test_sql_store_persists_identity_bundle(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    series_payload = {
        "series_id": "acotar",
        "provider": "booknlp_clean",
        "characters": [
            {
                "id": "char_feyre",
                "display_name": "Feyre Archeron",
                "aliases": ["Feyre"],
                "book_sources": [{"book_index": 1, "book_slug": "acotar", "mention_count": 10, "quote_count": 2}],
                "risk_flags": [],
                "llm_review": {
                    "recommended_bucket": "stable",
                    "confidence": "high",
                    "notes": ["Verified by review layer."],
                },
            }
        ],
        "alias_index": {"feyre": "char_feyre"},
        "reference_entities": [{"id": "ref_spring_court", "display_name": "Spring Court", "category": "location"}],
        "narrators": [{"book_index": 1, "book_slug": "acotar", "name": "Feyre"}],
        "diagnostics": {"book_count": 1},
    }
    book_summaries = [
        {
            "book_index": 1,
            "book_slug": "acotar",
            "title": "A Court of Thorns and Roses.epub",
            "output_dir": str(tmp_path / "identity" / "book_01_acotar"),
            "pipeline_identity_path": str(tmp_path / "identity" / "book_01_acotar" / "booknlp_small_pipeline_identity.json"),
            "character_count": 1,
            "alias_count": 1,
            "reference_entity_count": 1,
            "suppressed_cluster_count": 0,
            "narrator": {"name": "Feyre"},
        }
    ]

    result = store.persist_identity_bundle(
        series_id="acotar",
        source_path=tmp_path / "identity" / "acotar_series_pipeline_identity.json",
        series_payload=series_payload,
        book_summaries=book_summaries,
    )
    assert result["character_count"] == 1

    with store.session_factory() as session:
        assert session.execute(select(IdentitySeries)).scalars().all()
        characters = session.execute(select(IdentityCharacter)).scalars().all()
        assert characters
        aliases = session.execute(select(IdentityAlias)).scalars().all()
        assert len(aliases) == 1
        payload = characters[0].payload_json or {}
        assert payload["llm_review"]["recommended_bucket"] == "stable"


def test_sql_store_resplits_book_scenes_and_clears_dependents(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    contract = _sample_contract(tmp_path)
    paragraphs = []
    for idx in range(1, 9):
        paragraphs.append(
            f"Harry and Hagrid discuss Hogwarts letter number {idx} in detail while the storm lashes the hut, "
            f"covering Harry's questions, Hagrid's answers, family history, and the strange world opening before him."
        )
    contract["outputs"]["chapters"][0]["text"] = "\n\n".join(paragraphs)
    contract["outputs"]["resolved_scene_analyses"][0]["text"] = contract["outputs"]["chapters"][0]["text"]
    result = store.persist_contract(contract, contract_path=None)
    book_ref = f"db://book/{result['book_id']}"

    resplit = store.resplit_book_scenes(
        book_ref=book_ref,
        target_words=70,
        allow_cross_chapter=False,
        clear_dependent_rows=True,
    )

    assert resplit["scene_count"] >= 2
    with store.session_factory() as session:
        scenes = session.execute(select(Scene).where(Scene.book_id == result["book_id"]).order_by(Scene.chapter_index, Scene.scene_index)).scalars().all()
        entities = session.execute(select(Entity).where(Entity.book_id == result["book_id"])).scalars().all()
        assert len(scenes) >= 2
        assert not entities
        assert all((row.payload_json or {}).get("final_status") == "pending_analysis" for row in scenes)


def test_sql_store_persists_audiobook_run_and_chapter_outputs(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    contract_result = store.persist_contract(_sample_contract(tmp_path), contract_path=None)

    run = store.create_audiobook_run(
        {
            "series_id": "acotar",
            "book_id": contract_result["book_id"],
            "scope_type": "book",
            "title": "ACOTAR Book 1 Audiobook",
            "status": "queued",
            "tts_provider": "tts_modal",
            "tts_app_name": "graduation-kokoro-tts",
            "provider_account_alias": "member-01",
            "voice": "af_bella",
            "lang_code": "a",
            "sample_rate": 24000,
            "audio_format": "wav",
            "normalize_audio": True,
            "trim_silence": False,
            "sentence_pause_ms": 80,
            "transcript_storage_mode": "database",
            "audio_storage_mode": "path",
            "total_books": 1,
        }
    )

    with store.session_factory() as session:
        chapter = session.execute(select(Chapter).where(Chapter.book_id == contract_result["book_id"])).scalars().first()
        assert chapter is not None
        chapter_id = chapter.id

    chapter_payload = store.upsert_audiobook_chapter(
        {
            "run_id": run["id"],
            "series_id": "acotar",
            "book_id": contract_result["book_id"],
            "chapter_id": chapter_id,
            "book_index": 1,
            "chapter_index": 1,
            "chapter_title": "Chapter 1",
            "transcript_status": "completed",
            "audio_status": "completed",
            "transcript_text": "Feyre moved through the woods with practiced silence.",
            "audio_path": str(tmp_path / "audio" / "chapter_01.wav"),
            "audio_mime_type": "audio/wav",
            "audio_byte_size": 123456,
            "duration_seconds": 12.5,
            "tts_provider": "tts_modal",
            "tts_app_name": "graduation-kokoro-tts",
            "provider_account_alias": "member-01",
            "voice": "af_bella",
            "lang_code": "a",
            "sample_rate": 24000,
            "audio_format": "wav",
        }
    )

    assert chapter_payload["transcript_text"].startswith("Feyre moved")
    assert chapter_payload["audio_path"].endswith("chapter_01.wav")

    stored_run = store.get_audiobook_run(run["id"])
    assert stored_run is not None
    assert stored_run["status"] == "completed"
    assert len(stored_run["chapters"]) == 1
    assert stored_run["chapters"][0]["transcript_word_count"] == 8

    with store.session_factory() as session:
        assert session.execute(select(AudiobookRun)).scalars().all()
        assert session.execute(select(AudiobookChapter)).scalars().all()


def test_sql_store_persists_series_level_audiobook_run(tmp_path: Path) -> None:
    db_path = tmp_path / "saga.sqlite3"
    store = SagaSQLiteStore(db_path)
    contract_result = store.persist_contract(_sample_contract(tmp_path), contract_path=None)

    run = store.create_audiobook_run(
        {
            "series_id": "acotar",
            "scope_type": "series",
            "title": "ACOTAR Full Series Audiobook",
            "status": "running",
            "tts_provider": "tts_modal",
            "tts_app_name": "graduation-kokoro-tts",
            "provider_account_alias": "member-02",
            "voice": "af_bella",
            "lang_code": "a",
            "sample_rate": 32000,
            "audio_format": "flac",
            "normalize_audio": False,
            "trim_silence": True,
            "sentence_pause_ms": 200,
            "transcript_storage_mode": "database",
            "audio_storage_mode": "path",
            "total_books": 5,
            "total_chapters": 42,
            "completed_chapters": 10,
            "failed_chapters": 1,
        }
    )

    assert run["scope_type"] == "series"
    assert run["book_id"] == ""
    assert run["audio_format"] == "flac"
    assert run["trim_silence"] is True

    runs = store.get_audiobook_runs(series_id="acotar")
    assert any(item["id"] == run["id"] for item in runs)
