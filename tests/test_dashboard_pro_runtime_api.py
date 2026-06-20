import time
from pathlib import Path

from fastapi.testclient import TestClient

import apps.dashboard_api.app as dashboard_api
from saga.storage.models import (
    Book,
    Chapter,
    CharacterProfile,
    CharacterVisualBaseline,
    Entity,
    Event,
    GeneratedImage,
    GeneratedStory,
    Scene,
    StableCharacterState,
    TimelineRow,
    VisualPrompt,
)
from saga.storage.persistence import SagaSQLiteStore


def _temp_runtime(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(dashboard_api, "SQLITE_STORE", store)
    monkeypatch.setattr(dashboard_api, "OUTPUTS_DIR", tmp_path / "analysis_outputs")
    monkeypatch.setattr(dashboard_api, "DASHBOARD_DIR", tmp_path / "analysis_outputs" / "dashboard")
    monkeypatch.setattr(dashboard_api, "UPLOADS_DIR", tmp_path / "analysis_outputs" / "dashboard" / "uploads")
    monkeypatch.setattr(dashboard_api, "STORY_EXPORTS_DIR", tmp_path / "analysis_outputs" / "dashboard" / "story_exports")
    dashboard_api.ensure_dirs()
    return store, TestClient(dashboard_api.app)


def test_import_plan_start_writes_book_chapter_and_scene_rows(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    source_path = tmp_path / "book.txt"
    source_path.write_text(
        "Chapter One\n\n"
        "Mr. Example walked through a quiet street and found a strange silver key. "
        "The key hummed softly in his hand while rain tapped the windows.\n\n"
        "Chapter Two\n\n"
        "At dawn, he returned to the old house and opened the locked blue door. "
        "A hidden room waited beyond it with maps on every wall.",
        encoding="utf-8",
    )
    source = store.register_uploaded_source(
        original_name="book.txt",
        stored_path=str(source_path),
        size_bytes=source_path.stat().st_size,
        mime_type="text/plain",
        sha256="test-hash",
        source_kind="book",
        metadata={},
    )
    plan = client.post(
        "/runtime/import-plans",
        json={
            "series_id": "test-series",
            "series_title": "Test Series",
            "books": [{"source_id": source["id"], "title": "Test Book", "book_index": 1, "selected": True}],
            "shared_config": {"scene_target_words": 80, "analysis_model": "gpt_oss", "run_agents": False},
        },
    ).json()
    validated = client.post(f"/runtime/import-plans/{plan['id']}/validate")
    assert validated.status_code == 200

    started = client.post(f"/runtime/import-plans/{plan['id']}/start")
    assert started.status_code == 200
    job_id = started.json()["id"]
    for _ in range(50):
        payload = client.get(f"/runtime/jobs/{job_id}").json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert payload["status"] == "completed", payload

    with store.session_factory() as session:
        books = session.query(Book).all()
        chapters = session.query(Chapter).all()
        scenes = session.query(Scene).all()
    assert len(books) == 1
    assert books[0].contract_path is None
    assert len(chapters) == 2
    assert len(scenes) >= 1


def test_single_entity_render_endpoint_passes_exact_entity_id(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    with store.session_factory() as session:
        book = Book(series_id="series", book_index=1, title="Book")
        session.add(book)
        session.flush()
        from saga.storage.models import Entity

        entity = Entity(book_id=book.id, canonical_name="Selected Entity", entity_type="object")
        session.add(entity)
        session.flush()
        entity_id = entity.id
        book_id = book.id
        session.commit()

    captured = {}

    def fake_start_character_render(request):
        captured["request"] = request
        return {"id": "render-test", "status": "queued", "request": request.model_dump()}

    monkeypatch.setattr(dashboard_api, "start_character_render", fake_start_character_render)

    response = client.post(f"/runtime/assets/entities/{entity_id}/render", json={"overwrite": True, "prompt_id": "prompt-123"})

    assert response.status_code == 200
    assert captured["request"].contract_path == f"db://book/{book_id}"
    assert captured["request"].entity_ids == [entity_id]
    assert captured["request"].prompt_ids == ["prompt-123"]
    assert captured["request"].limit == 0


def test_render_batch_endpoint_passes_exact_entity_ids(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(dashboard_api, "run_selected_entity_render_job", lambda *args, **kwargs: None)

    with store.session_factory() as session:
        book = Book(series_id="series", book_index=2, title="Book")
        session.add(book)
        session.flush()
        session.add(Entity(id="entity-a", book_id=book.id, canonical_name="Entity A", entity_type="character"))
        session.add(Entity(id="entity-b", book_id=book.id, canonical_name="Entity B", entity_type="object"))
        session.commit()

    response = client.post(
        "/runtime/assets/render-batch",
        json={
            "entity_ids": ["entity-a", "entity-b"],
            "entity_types": ["character", "object"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "render-selected-assets"
    assert payload["request"]["entity_ids"] == ["entity-a", "entity-b"]
    assert payload["request"]["entity_groups"][0]["entity_ids"] == ["entity-a", "entity-b"]
    assert payload["request"]["entity_groups"][0]["book_ref"] == f"db://book/{book.id}"
    assert payload["request"]["entity_groups"][0]["entity_types"] == ["character", "object"]


def test_delete_asset_entity_removes_entity_related_visual_rows_and_files(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    image_path = dashboard_api.OUTPUTS_DIR / "renders" / "entity.png"
    thumb_path = dashboard_api.OUTPUTS_DIR / "renders" / "entity.thumb.png"
    preview_dir = dashboard_api.DASHBOARD_DIR / "asset_previews" / "entity-cleanup"
    preview_file = preview_dir / "preview.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"image-bytes")
    thumb_path.write_bytes(b"thumb-bytes")
    preview_file.write_bytes(b"preview-bytes")

    with store.session_factory() as session:
        book = Book(series_id="series", book_index=1, title="Book")
        session.add(book)
        session.flush()
        entity = Entity(
            id="entity-cleanup",
            book_id=book.id,
            canonical_name="Noise Entity",
            entity_type="character",
            generated_image_path=str(image_path),
            generated_thumbnail_path=str(thumb_path),
        )
        session.add(entity)
        session.flush()
        session.add(CharacterProfile(book_id=book.id, entity_id=entity.id, character_name=entity.canonical_name, payload_json={"test": True}))
        session.add(CharacterVisualBaseline(book_id=book.id, entity_id=entity.id, evidence_excerpt="excerpt"))
        prompt = VisualPrompt(book_id=book.id, entity_id=entity.id, entity_name=entity.canonical_name, entity_type=entity.entity_type, positive_prompt="prompt")
        session.add(prompt)
        session.flush()
        session.add(
            GeneratedImage(
                book_id=book.id,
                entity_id=entity.id,
                prompt_id=prompt.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
                output_path=str(image_path),
                thumbnail_path=str(thumb_path),
                image_bytes=b"image-bytes",
            )
        )
        session.commit()

    response = client.delete("/runtime/assets/entities/entity-cleanup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["entity_id"] == "entity-cleanup"
    assert payload["deleted_counts"]["generated_images"] == 1
    assert payload["deleted_counts"]["visual_prompts"] == 1
    assert payload["deleted_counts"]["character_profiles"] == 1
    assert payload["deleted_counts"]["character_visual_baselines"] == 1

    with store.session_factory() as session:
        assert session.get(Entity, "entity-cleanup") is None
        assert session.query(VisualPrompt).count() == 0
        assert session.query(GeneratedImage).count() == 0
        assert session.query(CharacterProfile).count() == 0
        assert session.query(CharacterVisualBaseline).count() == 0

    assert not image_path.exists()
    assert not thumb_path.exists()
    assert not preview_dir.exists()


def test_rename_asset_entity_updates_linked_system_rows(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    with store.session_factory() as session:
        book = Book(series_id="series", book_index=1, title="Book")
        session.add(book)
        session.flush()
        entity = Entity(
            id="entity-rename",
            book_id=book.id,
            canonical_name="Old Name",
            entity_type="character",
            entity_context="Old Name enters the hall.",
            baseline_visual_prompt="Portrait of Old Name in formal clothing.",
            latest_world_state={"entity_name": "Old Name", "status": "ready"},
        )
        session.add(entity)
        session.flush()
        session.add(CharacterProfile(book_id=book.id, entity_id=entity.id, character_name="Old Name", payload_json={"character_name": "Old Name"}))
        session.add(StableCharacterState(book_id=book.id, entity_id=entity.id, character_name="Old Name", payload_json={"character_name": "Old Name"}))
        prompt = VisualPrompt(
            book_id=book.id,
            entity_id=entity.id,
            entity_name="Old Name",
            entity_type="character",
            positive_prompt="Create a reference image of Old Name.",
            negative_prompt="avoid Old Name duplicates",
            details_json={"canonical_entity_name": "Old Name"},
        )
        session.add(prompt)
        session.flush()
        session.add(
            GeneratedImage(
                book_id=book.id,
                entity_id=entity.id,
                prompt_id=prompt.id,
                entity_name="Old Name",
                entity_type="character",
                output_path=str(tmp_path / "image.png"),
                manifest_json={"entity_name": "Old Name", "details": {"canonical_entity_name": "Old Name"}},
            )
        )
        session.add(Event(book_id=book.id, entities_involved=["Old Name"], payload_json={"entity_name": "Old Name"}))
        session.add(Scene(book_id=book.id, chapter_index=1, scene_index=1, payload_json={"entity_name": "Old Name"}))
        session.add(TimelineRow(book_id=book.id, row_index=1, payload_json={"entity_name": "Old Name"}))
        session.add(
            GeneratedStory(
                book_id=book.id,
                primary_pov_character="Old Name",
                output_text="Old Name looked back.",
                blueprint_json={"participants": ["Old Name"]},
            )
        )
        session.commit()

    response = client.patch("/runtime/assets/entities/entity-rename", json={"name": "New Name"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["renamed"] is True
    assert payload["old_name"] == "Old Name"
    assert payload["new_name"] == "New Name"
    assert payload["asset"]["entity"]["name"] == "New Name"

    with store.session_factory() as session:
        entity = session.get(Entity, "entity-rename")
        assert entity is not None
        assert entity.canonical_name == "New Name"
        assert entity.entity_context == "New Name enters the hall."
        assert entity.baseline_visual_prompt == "Portrait of New Name in formal clothing."
        assert entity.latest_world_state["entity_name"] == "New Name"
        profile = session.query(CharacterProfile).one()
        assert profile.character_name == "New Name"
        assert profile.payload_json["character_name"] == "New Name"
        stable_state = session.query(StableCharacterState).one()
        assert stable_state.character_name == "New Name"
        assert stable_state.payload_json["character_name"] == "New Name"
        prompt = session.query(VisualPrompt).one()
        assert prompt.entity_name == "New Name"
        assert prompt.positive_prompt == "Create a reference image of New Name."
        assert prompt.negative_prompt == "avoid New Name duplicates"
        assert prompt.details_json["canonical_entity_name"] == "New Name"
        image = session.query(GeneratedImage).one()
        assert image.entity_name == "New Name"
        assert image.manifest_json["entity_name"] == "New Name"
        assert image.manifest_json["details"]["canonical_entity_name"] == "New Name"
        assert session.query(Event).one().entities_involved == ["New Name"]
        assert session.query(Scene).one().payload_json["entity_name"] == "New Name"
        assert session.query(TimelineRow).one().payload_json["entity_name"] == "New Name"
        story = session.query(GeneratedStory).one()
        assert story.primary_pov_character == "New Name"
        assert story.output_text == "New Name looked back."
        assert story.blueprint_json["participants"] == ["New Name"]


def test_prompt_editor_keeps_entity_name_line_editable_for_creatures():
    payload = dashboard_api._build_prompt_editor_payload(
        (
            "Create a photorealistic creature reference image of Griphook.\n"
            "Single-subject creature reference plate focused entirely on the creature.\n"
            "Neutral worldbuilding reference for a canon creature, presented as design documentation rather than narrative action.\n"
            "Depict Griphook as goblin.\n"
            "Persistent visual description: goblin.\n"
            "Use a clear full-subject composition with readable silhouette, believable anatomy, grounded material detail, and stable proportions.\n"
            "Observational documentary framing suitable for a production design reference library.\n"
            "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects."
        ),
        "",
        "creature",
    )

    assert "Griphook" not in payload["positive"]["locked_prefix"]
    assert payload["positive"]["editable_body"].startswith("Create a photorealistic creature reference image of Griphook.")


def test_runtime_asset_entity_collapses_duplicate_prompt_rows(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    with store.session_factory() as session:
        book = Book(series_id="series", book_index=1, title="Book")
        session.add(book)
        session.flush()
        entity = Entity(book_id=book.id, canonical_name="Griphook", entity_type="creature")
        session.add(entity)
        session.flush()
        session.add(
            VisualPrompt(
                book_id=book.id,
                entity_id=entity.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
                prompt_type="creature_baseline",
                positive_prompt="older",
            )
        )
        session.add(
            VisualPrompt(
                book_id=book.id,
                entity_id=entity.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
                prompt_type="initial_creature_description",
                positive_prompt="newer",
            )
        )
        session.commit()

    response = client.get(f"/runtime/assets/entities/{entity.id}")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["prompts"]) == 1
    assert payload["prompts"][0]["positive_prompt"] == "newer"


def test_save_tts_modal_provider_persists_config(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)

    response = client.post(
        "/runtime/providers/tts-modal",
        json={
            "app_name": "custom-kokoro-app",
            "api_url": "https://example.modal.run",
            "default_voice": "af_bella",
            "default_lang_code": "a",
            "default_sample_rate": 32000,
            "default_audio_format": "wav",
            "default_normalize_audio": True,
            "default_trim_silence": True,
            "default_sentence_pause_ms": 180,
            "timeout_seconds": 420,
        },
    )

    assert response.status_code == 200
    payload = response.json()["tts_modal"]
    assert payload["app_name"] == "custom-kokoro-app"
    assert payload["api_url"] == "https://example.modal.run"
    assert payload["default_sample_rate"] == 32000
    assert payload["default_trim_silence"] is True
    assert payload["default_sentence_pause_ms"] == 180

    stored = store.get_provider_config("tts_modal")
    assert stored is not None
    assert stored["app_name"] == "custom-kokoro-app"
    assert stored["transport"] == "modal_api"


def test_provider_statuses_include_tts_modal(monkeypatch, tmp_path):
    _, client = _temp_runtime(monkeypatch, tmp_path)
    client.post(
        "/runtime/providers/tts-modal",
        json={
            "app_name": "custom-kokoro-app",
            "api_url": "https://example.modal.run",
        },
    )

    monkeypatch.setattr(
        dashboard_api,
        "_safe_probe_tts_modal_provider",
        lambda config: {
            "provider_name": "tts_modal",
            "label": config["app_name"],
            "probe_status": "ready",
            "transport": "modal_api",
            "resolved_model": "af_bella/a",
            "quota_source": "modal_token_pool",
            "credits_remaining": "unknown",
            "detail": "Resolved Modal TTS API URL from test stub.",
            "last_checked_at_utc": dashboard_api.utc_now(),
            "payload": {"api_url": config["api_url"]},
        },
    )

    response = client.get("/runtime/providers/status?refresh=1")
    assert response.status_code == 200
    payload = response.json()["providers"]["tts_modal"]
    assert payload["config"]["app_name"] == "custom-kokoro-app"
    assert payload["statuses"][0]["provider_name"] == "tts_modal"
    assert payload["statuses"][0]["probe_status"] == "ready"


def test_audiobook_stage_endpoint_persists_run_and_chapter_rows(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    with store.session_factory() as session:
        from saga.storage.models import Series

        series = Series(series_id="series-1", title="Series One")
        session.add(series)
        session.flush()
        book = Book(series_id="series-1", book_index=1, title="Book One")
        session.add(book)
        session.flush()
        session.add(Chapter(book_id=book.id, chapter_index=1, title="Chapter 1", text="Opening line.", word_count=2))
        session.add(Chapter(book_id=book.id, chapter_index=2, title="Chapter 2", text="Second chapter text.", word_count=3))
        session.commit()
        book_id = book.id

    response = client.post(
        "/runtime/audiobook/runs/stage",
        json={
            "scope": "book",
            "series_id": "series-1",
            "book_ref": f"db://book/{book_id}",
            "tone": "dramatic",
            "rewrite_provider": "codex",
            "rewrite_fallback_mode": "strict_rewrite",
            "voice": "af_bella",
            "audio_format": "wav",
            "store_transcript": True,
            "store_audio": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["run"]
    assert payload["status"] == "staged"
    assert payload["series_id"] == "series-1"
    assert payload["book_id"] == book_id
    assert payload["total_chapters"] == 2
    assert len(payload["chapters"]) == 2
    assert payload["chapters"][0]["transcript_text"] == "Opening line."
    assert payload["chapters"][0]["audio_path"].endswith(".wav")
    assert payload["metadata"]["rewrite_provider"] == "codex"
    assert payload["metadata"]["rewrite_fallback_mode"] == "strict_rewrite"

    runs = client.get("/runtime/audiobook/runs", params={"series_id": "series-1"})
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) == 1


def test_audiobook_start_endpoint_creates_dashboard_job(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(dashboard_api, "run_audiobook_job", lambda *args, **kwargs: None)
    with store.session_factory() as session:
        from saga.storage.models import Series

        series = Series(series_id="series-1", title="Series One")
        session.add(series)
        session.flush()
        book = Book(series_id="series-1", book_index=1, title="Book One")
        session.add(book)
        session.flush()
        session.add(Chapter(book_id=book.id, chapter_index=1, title="Chapter 1", text="Opening line.", word_count=2))
        session.commit()
        book_id = book.id

    staged = client.post(
        "/runtime/audiobook/runs/stage",
        json={
            "scope": "book",
            "series_id": "series-1",
            "book_ref": f"db://book/{book_id}",
            "tone": "classic",
            "voice": "af_bella",
            "audio_format": "wav",
            "store_transcript": True,
            "store_audio": True,
        },
    ).json()["run"]

    response = client.post(f"/runtime/audiobook/runs/{staged['id']}/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["type"] == "audiobook-pipeline"
    assert payload["job"]["artifacts"]["audiobook_run_id"] == staged["id"]


def test_run_audiobook_job_generates_outputs_and_logs(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)

    class FakePool:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def ensure_live(self):
            return {
                "token_name": "member-01",
                "api_url": "https://fake.modal.run",
                "health_url": "https://fake.modal.run/health",
                "live_payload": {"ready": True},
            }

    class FakeAudiobookService:
        def __init__(self, *args, **kwargs):
            self.tts_pool = kwargs.get("tts_pool") or FakePool()

        def rewrite_chapter_text(self, *, chapter_title, chapter_text, tone, fallback_mode="strict_rewrite"):
            return {
                "transcript_text": f"Narrated {chapter_title}: {chapter_text}",
                "source_provider": "ollama",
                "source_model": "fake-gpt-oss",
                "metadata": {"rewrite_mode": "llm_rewrite", "tone": tone, "fallback_mode": fallback_mode},
            }

        def synthesize_audio(self, **kwargs):
            return {
                "audio_bytes": b"FAKE_WAV_BYTES",
                "media_type": "audio/wav",
                "voice": kwargs["voice"],
                "lang_code": kwargs["lang_code"],
                "sample_rate": kwargs["sample_rate"],
                "audio_format": kwargs["audio_format"],
                "duration_seconds": 1.25,
                "token_name": "member-01",
            }

    monkeypatch.setattr(dashboard_api, "ModalTTSPoolManager", FakePool)
    monkeypatch.setattr(dashboard_api, "AudiobookGenerationService", FakeAudiobookService)

    with store.session_factory() as session:
        from saga.storage.models import Series

        series = Series(series_id="series-1", title="Series One")
        session.add(series)
        session.flush()
        book = Book(series_id="series-1", book_index=1, title="Book One")
        session.add(book)
        session.flush()
        session.add(Chapter(book_id=book.id, chapter_index=1, title="Chapter 1", text="Opening line.", word_count=2))
        session.commit()
        book_id = book.id

    staged = client.post(
        "/runtime/audiobook/runs/stage",
        json={
            "scope": "book",
            "series_id": "series-1",
            "book_ref": f"db://book/{book_id}",
            "tone": "epic",
            "rewrite_provider": "general_compute",
            "rewrite_fallback_mode": "strict_rewrite",
            "voice": "af_bella",
            "audio_format": "wav",
            "store_transcript": True,
            "store_audio": True,
        },
    ).json()["run"]

    job_id = "audiobook_test_job"
    dashboard_api.save_job(
        {
            "id": job_id,
            "type": "audiobook-pipeline",
            "status": "queued",
            "created_at": dashboard_api.utc_now(),
            "command": f"db-audiobook:{staged['id']}",
            "artifacts": {"audiobook_run_id": staged["id"]},
            "progress": {"stage": "queued", "current": 0, "total": 1, "label": "Queued audiobook pipeline", "status": "queued", "details": {"run_id": staged["id"], "chapter_count": 1}},
        }
    )

    dashboard_api.run_audiobook_job(job_id, staged["id"])

    run = store.get_audiobook_run(staged["id"])
    assert run is not None
    assert run["status"] == "completed"
    assert run["chapters"][0]["transcript_status"] == "completed"
    assert run["chapters"][0]["audio_status"] == "completed"
    assert run["chapters"][0]["transcript_text"].startswith("Narrated Chapter 1:")
    assert Path(run["chapters"][0]["audio_path"]).exists()

    job = dashboard_api.load_job(job_id)
    assert job["status"] == "completed"
    assert job["progress"]["current"] == 1
    assert job["progress"]["total"] == 1
    logs = client.get(f"/runtime/jobs/{job_id}/logs").json()["lines"]
    rendered_logs = [line if isinstance(line, str) else line.get("line_text", "") for line in logs]
    assert any("tts app ready" in line for line in rendered_logs)


def test_audiobook_audio_endpoint_returns_missing_until_render_exists(monkeypatch, tmp_path):
    store, client = _temp_runtime(monkeypatch, tmp_path)
    run = store.create_audiobook_run(
        {
            "series_id": "series-1",
            "book_id": "book-1",
            "scope_type": "book",
            "title": "Book One audiobook",
            "status": "staged",
            "voice": "af_bella",
            "audio_format": "wav",
        }
    )
    store.upsert_audiobook_chapter(
        {
            "run_id": run["id"],
            "book_id": "book-1",
            "chapter_id": "chapter-1",
            "chapter_index": 1,
            "chapter_title": "Chapter 1",
            "audio_status": "staged",
            "audio_path": str(tmp_path / "missing.wav"),
        }
    )

    response = client.get(f"/runtime/audiobook/runs/{run['id']}/chapters/chapter-1/audio")
    assert response.status_code == 404
