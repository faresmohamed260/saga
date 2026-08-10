from __future__ import annotations

from pathlib import Path

import pytest

from packages.persistence_runtime import (
    AUDIO_OUTPUT_BUCKET,
    GENERATED_IMAGE_BUCKET,
    RUNTIME_REPORT_BUCKET,
    PersistenceProfile,
    PersistenceRuntimeConfig,
    SOURCE_DOCUMENT_BUCKET,
    STORY_EXPORT_BUCKET,
    create_persistence_client,
    create_persistence_provider,
)
from packages.persistence_runtime.database_url import build_database_url_from_env
from integrations.comfyui.token_pool import (
    load_active_token_name,
    load_start_index,
    load_token_stats,
    mark_render_success,
    save_next_index,
    update_token_stat,
)
from packages.modal_runtime.state import clear_runtime_state_cache


def _client(tmp_path):
    profile = PersistenceProfile(
        name="test",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'persistence-runtime.sqlite3'}",
    )
    client = create_persistence_client(config=PersistenceRuntimeConfig(profile=profile), profile=profile)
    client.initialize()
    return client


def test_provider_config_store_round_trips(tmp_path):
    client = _client(tmp_path)

    saved = client.provider_configs.upsert_provider_config(
        "modal_comfyui",
        {"accounts": [{"label": "member-01"}], "active_index": 0},
    )
    assert saved["provider_name"] == "modal_comfyui"

    loaded = client.provider_configs.get_provider_config("modal_comfyui")
    assert loaded is not None
    assert loaded["payload"]["accounts"][0]["label"] == "member-01"


def test_provider_status_store_round_trips(tmp_path):
    client = _client(tmp_path)

    saved = client.provider_configs.upsert_provider_status(
        "modal_comfyui",
        "member-01",
        {"last_health_ok": True, "api_url": "https://image.example/api"},
    )
    listed = client.provider_configs.list_provider_statuses("modal_comfyui")

    assert saved["provider_name"] == "modal_comfyui"
    assert saved["label"] == "member-01"
    assert listed[0]["payload"]["last_health_ok"] is True
    assert listed[0]["status"]["last_health_ok"] is True
    assert listed[0]["status"]["api_url"] == "https://image.example/api"


def test_provider_status_replace_rejects_duplicate_labels(tmp_path):
    client = _client(tmp_path)

    try:
        client.provider_configs.replace_provider_statuses(
            "modal_comfyui",
            [
                {"label": "member-01", "api_url": "https://a.example/api"},
                {"label": "member-01", "api_url": "https://b.example/api"},
            ],
        )
    except ValueError as exc:
        assert "Duplicate provider status label" in str(exc)
    else:
        raise AssertionError("Expected duplicate provider status labels to be rejected.")


def test_library_store_persists_series_books_scenes_and_records(tmp_path):
    client = _client(tmp_path)

    client.library.upsert_series("acotar", title="ACOTAR", metadata={"book_count": 5})
    client.library.upsert_book(
        "book-acotar-1",
        series_id="acotar",
        title="A Court of Thorns and Roses",
        book_index=1,
        source_type="epub",
    )
    client.library.upsert_scene(
        "scene-1",
        book_id="book-acotar-1",
        chapter_index=1,
        scene_index=1,
        summary="Feyre hunts in the forest.",
        text="Feyre tracks the wolf through the snow.",
        payload={"characters": ["Feyre"]},
    )
    client.library.upsert_record(
        "entity-feyre",
        record_type="entity",
        series_id="acotar",
        book_id="book-acotar-1",
        scene_id="scene-1",
        title="Feyre Archeron",
        ordinal=1,
        payload={"entity_type": "character"},
    )

    books = client.library.list_books(series_id="acotar")
    scenes = client.library.list_scenes(book_id="book-acotar-1")
    records = client.library.list_records(record_type="entity", series_id="acotar")

    assert books[0]["title"] == "A Court of Thorns and Roses"
    assert scenes[0]["payload"]["characters"] == ["Feyre"]
    assert records[0]["title"] == "Feyre Archeron"


def test_library_store_bulk_upserts_scenes_in_one_ordered_contract(tmp_path):
    client = _client(tmp_path)
    client.library.upsert_series("series-bulk", title="Bulk")
    client.library.upsert_book("book-bulk", series_id="series-bulk", title="Bulk Book")

    inserted = client.library.upsert_scenes([
        {
            "scene_id": "scene-b",
            "book_id": "book-bulk",
            "chapter_index": 1,
            "scene_index": 2,
            "summary": "Second",
            "text": "Second scene.",
            "payload": {"version": 1},
        },
        {
            "scene_id": "scene-a",
            "book_id": "book-bulk",
            "chapter_index": 1,
            "scene_index": 1,
            "summary": "First",
            "text": "First scene.",
            "payload": {"version": 1},
        },
    ])
    updated = client.library.upsert_scenes([
        {**inserted[0], "summary": "Second revised", "payload": {"version": 2}},
        {**inserted[1], "summary": "First revised", "payload": {"version": 2}},
    ])

    assert [row["scene_id"] for row in inserted] == ["scene-b", "scene-a"]
    assert [row["summary"] for row in updated] == ["Second revised", "First revised"]
    persisted = client.library.list_scenes(book_id="book-bulk")
    assert [row["scene_id"] for row in persisted] == ["scene-a", "scene-b"]
    assert all(row["payload"]["version"] == 2 for row in persisted)


def test_library_store_bulk_scene_upsert_rejects_duplicate_ids(tmp_path):
    client = _client(tmp_path)
    duplicate = {
        "scene_id": "scene-duplicate",
        "book_id": "book-duplicate",
        "chapter_index": 1,
        "scene_index": 1,
    }

    with pytest.raises(ValueError, match="unique scene_id"):
        client.library.upsert_scenes([duplicate, duplicate])


def test_job_story_identity_and_audiobook_stores_round_trip(tmp_path):
    client = _client(tmp_path)

    client.identity.upsert_identity_series("acotar", provider_name="modal_xcore", payload={"clusters": []})
    client.jobs.create_job("job-1", job_type="analysis", status="queued", payload={"series_id": "acotar"})
    client.jobs.add_job_log("job-1", stage="queue", message="Queued for processing.", payload={"position": 1})
    client.stories.upsert_story("story-1", series_id="acotar", title="Alternate Spring Court", payload={"chapters": 12})
    client.audiobooks.upsert_run("run-1", series_id="acotar", title="ACOTAR Audio", status="staged", payload={"voice": "bella"})
    client.audiobooks.upsert_chapter(
        "chapter-1",
        run_id="run-1",
        book_index=1,
        chapter_index=1,
        payload={"audio_artifact": {"bucket_name": AUDIO_OUTPUT_BUCKET, "object_path": "series/acotar/audio/runs/run-1/chapters/chapter-1/ch1.wav"}},
    )

    identity = client.identity.get_identity_series("acotar")
    job = client.jobs.get_job("job-1")
    stories = client.stories.list_stories(series_id="acotar")
    run = client.audiobooks.get_run("run-1")

    assert identity is not None and identity["provider_name"] == "modal_xcore"
    assert job is not None and job["logs"][0]["stage"] == "queue"
    assert stories[0]["payload"]["chapters"] == 12
    assert run is not None and run["chapters"][0]["payload"]["audio_artifact"]["bucket_name"] == AUDIO_OUTPUT_BUCKET


def test_persistence_runtime_exposes_langgraph_tools(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name for tool in client.as_langgraph_tools()}

    assert "persistence_upsert_provider_config" in tools
    assert "persistence_get_provider_config" in tools
    assert "persistence_get_provider_operational_state" in tools
    assert "persistence_upsert_series" in tools
    assert "persistence_upsert_book" in tools
    assert "persistence_upsert_scene" in tools
    assert "persistence_upsert_record" in tools
    assert "persistence_list_books" in tools
    assert "persistence_list_scenes" in tools
    assert "persistence_list_records" in tools
    assert "persistence_upsert_identity_series" in tools
    assert "persistence_get_identity_series" in tools
    assert "persistence_create_job" in tools
    assert "persistence_add_job_log" in tools
    assert "persistence_get_job" in tools
    assert "persistence_list_jobs" in tools
    assert "persistence_upsert_story" in tools
    assert "persistence_list_stories" in tools
    assert "persistence_upsert_audiobook_run" in tools
    assert "persistence_upsert_audiobook_chapter" in tools
    assert "persistence_get_audiobook_run" in tools
    assert "persistence_list_audiobook_runs" in tools
    assert "persistence_upsert_vector_documents" in tools
    assert "persistence_query_vector_documents" in tools
    assert "persistence_delete_vector_documents" in tools
    assert "persistence_ensure_bucket" in tools
    assert "persistence_upload_text_object" in tools
    assert "persistence_upload_json_object" in tools
    assert "persistence_download_text_object" in tools
    assert "persistence_list_objects" in tools
    assert "persistence_delete_object" in tools
    assert "persistence_store_text_artifact" in tools
    assert "persistence_store_json_artifact" in tools


def test_persistence_runtime_builds_self_hosted_supabase_url_from_env(monkeypatch):
    monkeypatch.delenv("SAGA_SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SUPABASE_DB_PORT", "5433")
    monkeypatch.setenv("SUPABASE_DB_NAME", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-password")
    monkeypatch.setenv("POOLER_TENANT_ID", "tenant-123")

    url = build_database_url_from_env()

    assert url == (
        "postgresql+psycopg://postgres.tenant-123:secret-password@127.0.0.1:5433/postgres?sslmode=disable"
    )


def test_persistence_profile_rejects_invalid_runtime_values():
    try:
        PersistenceProfile(name="", provider="supabase", mode="supabase_postgres")
    except ValueError as exc:
        assert "name is required" in str(exc)
    else:
        raise AssertionError("Expected invalid persistence profile to be rejected.")

    try:
        PersistenceProfile(name="bad", provider="supabase", mode="supabase_postgres", pool_size=0)
    except ValueError as exc:
        assert "pool_size" in str(exc)
    else:
        raise AssertionError("Expected invalid persistence pool size to be rejected.")

    try:
        PersistenceProfile(name="bad", provider="supabase", mode="sqlite")
    except ValueError as exc:
        assert "must be one of" in str(exc)
    else:
        raise AssertionError("Expected unsupported persistence mode to be rejected.")


def test_persistence_runtime_production_mode_requires_explicit_storage_api_url(monkeypatch):
    for key in (
        "SAGA_SUPABASE_STORAGE_API_URL",
        "SUPABASE_STORAGE_API_URL",
        "SAGA_SUPABASE_API_URL",
        "SUPABASE_API_URL",
        "SUPABASE_PUBLIC_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    profile = PersistenceProfile(
        name="prod-missing-storage-url",
        provider="supabase",
        mode="supabase_postgres",
        database_url="postgresql+psycopg://postgres:secret@127.0.0.1:5432/postgres",
        local_storage_root_dir="",
    )
    try:
        create_persistence_provider(
            config=PersistenceRuntimeConfig(
                profile=profile,
                supabase_service_role_key="service-role-key",
            ),
            profile=profile,
        )
    except ValueError as exc:
        assert "requires either a Supabase storage API URL or PersistenceProfile.local_storage_root_dir" in str(exc)
    else:
        raise AssertionError("Expected production mode to reject missing storage API URL.")


def test_persistence_runtime_production_mode_accepts_explicit_storage_api_url():
    profile = PersistenceProfile(
        name="prod-explicit-storage-url",
        provider="supabase",
        mode="supabase_postgres",
        database_url="postgresql+psycopg://postgres:secret@127.0.0.1:5432/postgres",
    )
    provider = create_persistence_provider(
        config=PersistenceRuntimeConfig(
            profile=profile,
            supabase_api_url="https://supabase.example",
            supabase_service_role_key="service-role-key",
        ),
        profile=profile,
    )

    assert provider.provider_name() == "supabase"
    assert provider.objects.base_url == "https://supabase.example/storage/v1"


def test_persistence_runtime_production_mode_falls_back_to_local_object_storage():
    profile = PersistenceProfile(
        name="prod-local-storage-fallback",
        provider="supabase",
        mode="supabase_postgres",
        database_url="postgresql+psycopg://postgres:secret@127.0.0.1:5432/postgres",
        local_storage_root_dir="analysis_outputs/runtime_validation_storage",
    )
    provider = create_persistence_provider(
        config=PersistenceRuntimeConfig(
            profile=profile,
            supabase_api_url="",
            supabase_service_role_key="",
        ),
        profile=profile,
    )

    assert provider.provider_name() == "supabase"
    assert provider.objects.__class__.__name__ == "LocalObjectStorageStore"


def test_persistence_runtime_exposes_provider_shape(tmp_path):
    profile = PersistenceProfile(
        name="test-provider",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'provider-runtime.sqlite3'}",
    )
    provider = create_persistence_provider(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    provider.initialize()

    assert provider.provider_name() == "test_harness"
    assert hasattr(provider, "library")
    assert hasattr(provider, "vectors")


def test_persistence_runtime_vector_store_round_trips(tmp_path):
    client = _client(tmp_path)

    upserted = client.vectors.upsert_documents(
        "library-scenes",
        [
            {
                "document_id": "doc-1",
                "content": "Nesta trains in the library.",
                "summary": "Training scene",
                "metadata": {"character": "Nesta", "kind": "scene"},
                "embedding": [0.91, 0.05, 0.12, 0.33],
            },
            {
                "document_id": "doc-2",
                "content": "Cassian plans in the war room.",
                "summary": "Planning scene",
                "metadata": {"character": "Cassian", "kind": "scene"},
                "embedding": [0.11, 0.82, 0.07, 0.14],
            },
        ],
    )
    results = client.vectors.query_documents(
        "library-scenes",
        query_vector=[0.9, 0.04, 0.1, 0.31],
        top_k=1,
        metadata_filters={"kind": "scene"},
    )

    assert upserted["document_count"] == 2
    assert len(results) == 1
    assert results[0]["document_id"] == "doc-1"


def test_persistence_runtime_object_store_round_trips(tmp_path):
    client = _client(tmp_path)

    ensured = client.objects.ensure_bucket("runtime-bucket")
    uploaded = client.objects.upload_text("runtime-bucket", "notes/hello.txt", "hello unified runtime")
    downloaded = client.objects.download_text("runtime-bucket", "notes/hello.txt")
    info = client.objects.get_object_info("runtime-bucket", "notes/hello.txt")
    listed = client.objects.list_objects("runtime-bucket", prefix="notes", limit=10)
    deleted = client.objects.delete_object("runtime-bucket", "notes/hello.txt")

    assert ensured["exists"] is True
    assert uploaded["bytes_written"] > 0
    assert downloaded == "hello unified runtime"
    assert info["content_type"] == "text/plain; charset=utf-8"
    assert listed[0]["path"] == "notes/hello.txt"
    assert listed[0]["content_type"] == "text/plain; charset=utf-8"
    assert deleted["deleted"] is True


def test_supabase_object_listing_normalizes_recursive_paths(monkeypatch):
    from packages.persistence_runtime.stores import SupabaseObjectStorageStore

    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def post(url, *, json, **kwargs):
        if json["prefix"] == "":
            return Response([{"name": "series", "id": None, "metadata": None}])
        if json["prefix"] == "series":
            return Response([{"name": "book.txt", "id": "object-1", "metadata": {"mimetype": "text/plain", "size": 4}}])
        return Response([])

    monkeypatch.setattr("packages.persistence_runtime.stores.requests.post", post)
    store = SupabaseObjectStorageStore(base_url="https://storage.example", service_role_key="test-key")
    rows = store.list_objects("sources", prefix="series", limit=10)
    assert rows[0]["path"] == "series/book.txt"
    assert rows[0]["content_type"] == "text/plain"


def test_persistence_runtime_artifact_manager_enforces_bucket_path_and_metadata_linkage(tmp_path):
    client = _client(tmp_path)

    stored = client.artifacts.store_text(
        artifact_type="generated_image",
        filename="hero.png",
        text="fake-png-bytes",
        content_type="image/png",
        series_id="series-1",
        entity_id="entity-hero",
        metadata={"variant": "main"},
    )
    downloaded = client.objects.download_text(GENERATED_IMAGE_BUCKET, "series/series-1/assets/entity-hero/hero.png")
    records = client.library.list_records(record_type="artifact", series_id="series-1")

    assert stored["bucket_name"] == GENERATED_IMAGE_BUCKET
    assert stored["object_path"] == "series/series-1/assets/entity-hero/hero.png"
    assert downloaded == "fake-png-bytes"
    assert records[0]["payload"]["artifact_type"] == "generated_image"
    assert records[0]["payload"]["variant"] == "main"


def test_persistence_runtime_artifact_manager_supports_multiple_artifact_families(tmp_path):
    client = _client(tmp_path)

    source_doc = client.artifacts.store_text(
        artifact_type="source_document",
        filename="book.epub",
        text="epub payload",
        series_id="series-2",
        book_id="book-2",
    )
    story_export = client.artifacts.store_json(
        artifact_type="story_export",
        filename="story.json",
        payload={"title": "Story"},
        series_id="series-2",
        story_id="story-2",
    )
    audio_output = client.artifacts.store_text(
        artifact_type="audio_output",
        filename="chapter-1.flac",
        text="audio bytes",
        content_type="audio/flac",
        series_id="series-2",
        run_id="run-2",
        chapter_id="chapter-2-1",
    )
    runtime_report = client.artifacts.store_json(
        artifact_type="runtime_report",
        filename="render.json",
        payload={"ok": True},
        provider_name="modal_comfyui",
        report_kind="render",
    )

    assert source_doc["bucket_name"] == SOURCE_DOCUMENT_BUCKET
    assert source_doc["object_path"] == "series/series-2/books/book-2/source/book.epub"
    assert story_export["bucket_name"] == STORY_EXPORT_BUCKET
    assert story_export["object_path"] == "series/series-2/stories/story-2/story.json"
    assert audio_output["bucket_name"] == AUDIO_OUTPUT_BUCKET
    assert audio_output["object_path"] == "series/series-2/audio/runs/run-2/chapters/chapter-2-1/chapter-1.flac"
    assert runtime_report["bucket_name"] == RUNTIME_REPORT_BUCKET
    assert runtime_report["object_path"].startswith("providers/modal-comfyui/reports/render/")


def test_persistence_runtime_rejects_invalid_vector_namespace(tmp_path):
    client = _client(tmp_path)

    try:
        client.vectors.upsert_documents(
            "bad namespace/with spaces",
            [{"document_id": "doc-1", "content": "x", "summary": "", "metadata": {}, "embedding": [1.0, 0.0]}],
        )
    except ValueError as exc:
        assert "Invalid vector namespace" in str(exc)
    else:
        raise AssertionError("Expected invalid vector namespace to be rejected.")


def test_persistence_runtime_ephemeral_workspace_cleanup(tmp_path):
    client = _client(tmp_path)

    created = client.ephemeral.create_file(category="render-cache", suffix=".tmp", prefix="job", ttl_seconds=1)
    target = Path(created["path"])
    target.write_text("temp", encoding="utf-8")
    cleaned = client.ephemeral.cleanup_expired(now=int(created["expires_at"]) + 5)

    assert cleaned["deleted_files"] >= 1
    assert not target.exists()


def test_persistence_runtime_tools_round_trip_identity_jobs_story_and_audiobook(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    identity = tools["persistence_upsert_identity_series"].invoke(
        {"series_id": "series-x", "provider_name": "xcore_litbank", "payload": {"clusters": [{"id": 1}]}}
    )
    job = tools["persistence_create_job"].invoke(
        {"job_id": "job-x", "job_type": "analysis", "status": "queued", "payload": {"series_id": "series-x"}}
    )
    log = tools["persistence_add_job_log"].invoke(
        {"job_id": "job-x", "stage": "queue", "message": "Queued", "payload": {"position": 1}}
    )
    story = tools["persistence_upsert_story"].invoke(
        {"story_id": "story-x", "series_id": "series-x", "title": "Story X", "payload": {"chapters": 3}}
    )
    run = tools["persistence_upsert_audiobook_run"].invoke(
        {"run_id": "run-x", "series_id": "series-x", "title": "Audio X", "status": "staged", "payload": {"voice": "bella"}}
    )
    chapter = tools["persistence_upsert_audiobook_chapter"].invoke(
        {
            "chapter_id": "chapter-x",
            "run_id": "run-x",
            "book_index": 1,
            "chapter_index": 1,
            "payload": {"audio_artifact": {"bucket_name": AUDIO_OUTPUT_BUCKET, "object_path": "series/series-x/audio/runs/run-x/chapters/chapter-x/chapter-x.wav"}},
        }
    )
    loaded_job = tools["persistence_get_job"].invoke({"job_id": "job-x"})
    loaded_run = tools["persistence_get_audiobook_run"].invoke({"run_id": "run-x"})
    listed_jobs = tools["persistence_list_jobs"].invoke({"job_type": "analysis", "limit": 10})
    listed_stories = tools["persistence_list_stories"].invoke({"series_id": "series-x", "limit": 10})
    listed_runs = tools["persistence_list_audiobook_runs"].invoke({"series_id": "series-x", "limit": 10})
    loaded_identity = tools["persistence_get_identity_series"].invoke({"series_id": "series-x"})

    assert identity["ok"] is True and identity["data"]["provider_name"] == "xcore_litbank"
    assert loaded_identity["ok"] is True and loaded_identity["data"]["provider_name"] == "xcore_litbank"
    assert loaded_identity["data"]["request_metadata"]["operation"] == "get_identity_series"
    assert job["ok"] is True and job["data"]["job_id"] == "job-x"
    assert log["ok"] is True and log["data"]["stage"] == "queue"
    assert story["ok"] is True and story["data"]["story_id"] == "story-x"
    assert run["ok"] is True and run["data"]["run_id"] == "run-x"
    assert chapter["ok"] is True and chapter["data"]["chapter_id"] == "chapter-x"
    assert loaded_job["data"]["logs"][0]["message"] == "Queued"
    assert loaded_job["data"]["request_metadata"]["operation"] == "get_job"
    assert loaded_run["data"]["found"] is True
    assert loaded_run["data"]["run"]["chapters"][0]["payload"]["audio_artifact"]["object_path"].endswith("/chapter-x.wav")
    assert listed_jobs["data"]["result_count"] == 1
    assert listed_jobs["data"]["request_metadata"]["operation"] == "list_jobs"
    assert listed_stories["data"]["results"][0]["story_id"] == "story-x"
    assert listed_stories["data"]["request_metadata"]["operation"] == "list_stories"
    assert listed_runs["data"]["results"][0]["run_id"] == "run-x"
    assert listed_runs["data"]["request_metadata"]["operation"] == "list_audiobook_runs"
    assert identity["trace"]["component"] == "persistence_runtime"


def test_persistence_runtime_library_list_tools_include_request_metadata(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    client.library.upsert_series("series-lib", title="Series Lib", metadata={"genre": "fantasy"})
    client.library.upsert_book("book-lib", series_id="series-lib", title="Book Lib", book_index=1, source_type="epub")
    client.library.upsert_scene(
        "scene-lib",
        book_id="book-lib",
        chapter_index=1,
        scene_index=1,
        summary="Opening scene.",
        text="A hero enters the city.",
        payload={"characters": ["Hero"]},
    )
    client.library.upsert_record(
        "record-lib",
        record_type="entity",
        series_id="series-lib",
        book_id="book-lib",
        scene_id="scene-lib",
        title="Hero",
        ordinal=1,
        payload={"entity_type": "character"},
    )

    books = tools["persistence_list_books"].invoke({"series_id": "series-lib", "limit": 10})
    scenes = tools["persistence_list_scenes"].invoke({"book_id": "book-lib", "limit": 10})
    records = tools["persistence_list_records"].invoke({"record_type": "entity", "series_id": "series-lib", "limit": 10})

    assert books["data"]["results"][0]["book_id"] == "book-lib"
    assert books["data"]["request_metadata"]["operation"] == "list_books"
    assert scenes["data"]["results"][0]["scene_id"] == "scene-lib"
    assert scenes["data"]["request_metadata"]["operation"] == "list_scenes"
    assert records["data"]["results"][0]["record_id"] == "record-lib"
    assert records["data"]["request_metadata"]["operation"] == "list_records"


def test_persistence_runtime_tools_round_trip_provider_statuses(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    config = tools["persistence_upsert_provider_config"].invoke(
        {"provider_name": "modal_comfyui", "payload": {"runtime_state": {"active_token_name": "member-01", "active_api_url": "https://image.example/api"}}}
    )
    loaded_config = tools["persistence_get_provider_config"].invoke({"provider_name": "modal_comfyui"})
    status = tools["persistence_upsert_provider_status"].invoke(
        {
            "provider_name": "modal_comfyui",
            "label": "member-01",
            "payload": {"last_health_ok": True, "last_request_ok": True, "api_url": "https://image.example/api"},
        }
    )
    operational = tools["persistence_get_provider_operational_state"].invoke({"provider_name": "modal_comfyui"})
    statuses = tools["persistence_list_provider_statuses"].invoke({"provider_name": "modal_comfyui"})

    assert config["ok"] is True
    assert loaded_config["ok"] is True
    assert loaded_config["data"]["found"] is True
    assert loaded_config["data"]["config"]["payload"]["runtime_state"]["active_token_name"] == "member-01"
    assert loaded_config["data"]["request_metadata"]["component"] == "persistence_runtime"
    assert config["data"]["request_metadata"]["operation"] == "upsert_provider_config"
    assert operational["ok"] is True
    assert operational["data"]["found"] is True
    assert operational["data"]["runtime_state"]["active_label"] == "member-01"
    assert operational["data"]["runtime_state"]["active_api_url"] == "https://image.example/api"
    assert operational["data"]["request_metadata"]["operation"] == "get_provider_operational_state"
    assert status["ok"] is True
    assert status["data"]["label"] == "member-01"
    assert status["data"]["request_metadata"]["operation"] == "upsert_provider_status"
    assert status["data"]["status"]["last_health_ok"] is True
    assert statuses["ok"] is True
    assert statuses["data"]["result_count"] == 1
    assert statuses["data"]["results"][0]["payload"]["api_url"] == "https://image.example/api"
    assert statuses["data"]["results"][0]["status"]["api_url"] == "https://image.example/api"
    assert statuses["data"]["request_metadata"]["operation"] == "list_provider_statuses"
    assert "member-01" in operational["data"]["healthy_labels"]
    assert "member-01" in operational["data"]["ready_labels"]


def test_persistence_runtime_get_provider_config_tool_reports_missing_record(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    loaded = tools["persistence_get_provider_config"].invoke({"provider_name": "missing_provider"})

    assert loaded["ok"] is True
    assert loaded["data"]["provider_name"] == "missing_provider"
    assert loaded["data"]["found"] is False
    assert loaded["data"]["config"] is None


def test_persistence_runtime_provider_operational_state_reports_missing_provider(tmp_path):
    client = _client(tmp_path)
    state = client.provider_configs.get_provider_operational_state("missing_provider")

    assert state["provider_name"] == "missing_provider"
    assert state["found"] is False
    assert state["config"] is None
    assert state["status_count"] == 0
    assert state["runtime_state"]["active_label"] == ""
    assert state["runtime_state"]["active_status_found"] is False
    assert state["runtime_state"]["status_count"] == 0
    assert state["runtime_state"]["diagnostics"] == []


def test_persistence_runtime_provider_operational_state_surfaces_runtime_state_diagnostics(tmp_path):
    client = _client(tmp_path)
    client.provider_configs.upsert_provider_config(
        "modal_comfyui",
        {
            "runtime_state": {
                "active_token_name": "member-01",
                "active_api_url": "https://wrong.example/api",
                "active_ui_url": "",
                "active_health_url": "",
            }
        },
    )
    client.provider_configs.upsert_provider_status(
        "modal_comfyui",
        "member-01",
        {
            "api_url": "https://image.example/api",
            "ui_url": "https://image.example/ui",
            "health_url": "https://image.example/health",
            "last_health_ok": True,
            "last_request_ok": True,
        },
    )

    state = client.provider_configs.get_provider_operational_state("modal_comfyui")

    assert state["runtime_state"]["active_label"] == "member-01"
    assert state["runtime_state"]["active_status_found"] is True
    assert state["runtime_state"]["status_labels"] == ["member-01"]
    assert state["runtime_state"]["status_count"] == 1
    assert state["runtime_state"]["active_api_url"] == "https://wrong.example/api"
    assert state["runtime_state"]["active_ui_url"] == "https://image.example/ui"
    assert state["runtime_state"]["active_health_url"] == "https://image.example/health"
    assert "active_api_url_mismatch" in state["runtime_state"]["diagnostics"]


def test_persistence_runtime_provider_operational_state_flags_invalid_runtime_state_payload_type(tmp_path):
    client = _client(tmp_path)
    client.provider_configs.upsert_provider_config(
        "modal_comfyui",
        {"runtime_state": "invalid"},
    )
    client.provider_configs.upsert_provider_status(
        "modal_comfyui",
        "member-02",
        {"api_url": "https://image.example/api"},
    )

    state = client.provider_configs.get_provider_operational_state("modal_comfyui")

    assert state["runtime_state"]["active_label"] == ""
    assert state["runtime_state"]["active_status_found"] is False
    assert state["runtime_state"]["status_labels"] == ["member-02"]
    assert "runtime_state_invalid_type" in state["runtime_state"]["diagnostics"]


def test_persistence_runtime_artifact_tools_store_durable_artifacts(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    ensured = tools["persistence_ensure_bucket"].invoke({"bucket_name": "story-exports", "public": False})
    result = tools["persistence_store_json_artifact"].invoke(
        {
            "artifact_type": "story_export",
            "filename": "story.json",
            "payload": {"chapters": 2},
            "series_id": "series-z",
            "story_id": "story-z",
            "metadata": {"format": "json"},
        }
    )
    downloaded = client.objects.download_text(STORY_EXPORT_BUCKET, "series/series-z/stories/story-z/story.json")

    assert ensured["ok"] is True
    assert ensured["data"]["request_metadata"]["operation"] == "ensure_bucket"
    assert result["ok"] is True
    assert result["data"]["bucket_name"] == STORY_EXPORT_BUCKET
    assert result["data"]["request_metadata"]["operation"] == "store_json_artifact"
    assert "\"chapters\": 2" in downloaded


def test_persistence_runtime_object_tools_include_request_metadata(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    ensured = tools["persistence_ensure_bucket"].invoke({"bucket_name": "notes-bucket", "public": False})
    uploaded = tools["persistence_upload_text_object"].invoke(
        {
            "bucket_name": "notes-bucket",
            "object_path": "notes/hello.txt",
            "text": "hello runtime",
        }
    )
    downloaded = tools["persistence_download_text_object"].invoke(
        {
            "bucket_name": "notes-bucket",
            "object_path": "notes/hello.txt",
        }
    )
    listed = tools["persistence_list_objects"].invoke(
        {
            "bucket_name": "notes-bucket",
            "prefix": "notes",
            "limit": 10,
            "offset": 0,
        }
    )
    deleted = tools["persistence_delete_object"].invoke(
        {
            "bucket_name": "notes-bucket",
            "object_path": "notes/hello.txt",
        }
    )

    assert ensured["data"]["request_metadata"]["component"] == "persistence_runtime"
    assert uploaded["data"]["request_metadata"]["operation"] == "upload_text_object"
    assert downloaded["data"]["request_metadata"]["operation"] == "download_text_object"
    assert downloaded["data"]["text"] == "hello runtime"
    assert listed["data"]["request_metadata"]["operation"] == "list_objects"
    assert listed["data"]["results"][0]["path"] == "notes/hello.txt"
    assert deleted["data"]["request_metadata"]["operation"] == "delete_object"


def test_persistence_runtime_vector_tools_include_request_metadata(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}

    upserted = tools["persistence_upsert_vector_documents"].invoke(
        {
            "namespace": "vector-scenes",
            "documents": [
                {
                    "document_id": "doc-1",
                    "content": "Nesta trains in the library.",
                    "summary": "Training scene",
                    "metadata": {"character": "Nesta", "kind": "scene"},
                    "embedding": [0.91, 0.05, 0.12, 0.33],
                }
            ],
        }
    )
    queried = tools["persistence_query_vector_documents"].invoke(
        {
            "namespace": "vector-scenes",
            "query_vector": [0.9, 0.04, 0.1, 0.31],
            "top_k": 1,
            "metadata_filters": {"kind": "scene"},
        }
    )
    deleted = tools["persistence_delete_vector_documents"].invoke(
        {
            "namespace": "vector-scenes",
            "document_ids": ["doc-1"],
        }
    )

    assert upserted["data"]["document_count"] == 1
    assert upserted["data"]["request_metadata"]["operation"] == "upsert_vector_documents"
    assert queried["data"]["results"][0]["document_id"] == "doc-1"
    assert queried["data"]["request_metadata"]["operation"] == "query_vector_documents"
    assert deleted["data"]["deleted_count"] == 1
    assert deleted["data"]["request_metadata"]["operation"] == "delete_vector_documents"


def test_persistence_runtime_tool_failures_are_categorized(tmp_path):
    client = _client(tmp_path)
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    tools["persistence_ensure_bucket"].invoke({"bucket_name": "safe-bucket", "public": False})

    result = tools["persistence_upload_text_object"].invoke(
        {
            "bucket_name": "safe-bucket",
            "object_path": "../escape.txt",
            "text": "blocked",
        }
    )

    assert result["ok"] is False
    assert result["error"]["category"] == "validation"
    assert result["error"]["exception_type"] == "ValueError"


def test_modal_provider_state_round_trips_through_unified_runtime(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'modal-state.sqlite3'}"
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    clear_runtime_state_cache()
    state_path = Path(tmp_path / "unused-pool-state.json")

    save_next_index(3, state_path, app_name="saga-image-runtime", runtime_generation=7)
    update_token_stat(
        "member-01",
        state_path=state_path,
        health_ok=True,
        render_ok=True,
        warm_until=123456789,
        last_error="",
        api_url="https://image.example/api",
        ui_url="https://image.example/ui",
        health_url="https://image.example/health",
        live_payload={"ready": True},
        app_name="saga-image-runtime",
        runtime_generation=7,
    )
    mark_render_success(
        "member-01",
        state_path=state_path,
        api_url="https://image.example/api",
        ui_url="https://image.example/ui",
        health_url="https://image.example/health",
        live_payload={"ready": True},
        last_successful_request={"operation": "render", "response_keys": ["image_url"]},
        app_name="saga-image-runtime",
        runtime_generation=7,
    )

    assert load_start_index(state_path, expected_app_name="saga-image-runtime", expected_generation=7) == 3
    assert load_active_token_name(state_path, expected_app_name="saga-image-runtime", expected_generation=7) == "member-01"
    stats = load_token_stats(state_path, expected_app_name="saga-image-runtime", expected_generation=7)
    assert stats["member-01"]["api_url"] == "https://image.example/api"
    assert stats["member-01"]["last_successful_request"]["operation"] == "render"
    assert not state_path.exists()

    profile = PersistenceProfile(name="test-modal-state", mode="test_harness", database_url=database_url)
    client = create_persistence_client(config=PersistenceRuntimeConfig(profile=profile), profile=profile)
    client.initialize()
    config_row = client.provider_configs.get_provider_config("modal_comfyui")
    statuses = client.provider_configs.list_provider_statuses("modal_comfyui")
    assert config_row is not None
    assert config_row["payload"]["runtime_state"]["active_token_name"] == "member-01"
    assert statuses[0]["label"] == "member-01"

    clear_runtime_state_cache()
