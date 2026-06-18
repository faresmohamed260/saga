import time
from pathlib import Path

from fastapi.testclient import TestClient

import apps.dashboard_api.app as dashboard_api
from saga.storage.models import Book, Chapter, Scene
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
