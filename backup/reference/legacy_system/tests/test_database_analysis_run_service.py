from saga.services.database_analysis_run_service import DatabaseAnalysisRunService
from saga.storage.persistence import SagaSQLiteStore


def test_agent_stage_groups_parallelize_expected_branches(tmp_path):
    service = DatabaseAnalysisRunService(SagaSQLiteStore(tmp_path / "service.sqlite"))

    groups = service._agent_stage_groups({})

    assert [group.name for group in groups] == [
        "events",
        "entities",
        "canon_synthesis",
        "character_visuals",
        "stable_states",
        "world_state",
        "visual_prompts",
    ]
    assert groups[2].parallel is True
    assert groups[2].stages == [
        "character_profiles",
        "noncharacter_visual_baselines",
        "relationships",
        "timeline",
        "noncharacter_scene_states",
    ]


def test_execute_stage_blocks_downstream_when_events_empty(tmp_path):
    service = DatabaseAnalysisRunService(SagaSQLiteStore(tmp_path / "service.sqlite"))

    service._log = lambda *args, **kwargs: None
    service._raise_if_cancelled = lambda *args, **kwargs: None
    service._run_one_stage = lambda **kwargs: {"inserted_event_count": 0}

    try:
        service._execute_stage(
            stage="events",
            book_ref="db://book/test",
            chapter_indices=[1],
            shared_config={},
            job_id="job-test",
            book_result={"book_id": "book-1", "title": "Book"},
            completed_units=0,
            total_units=3,
        )
    except ValueError as exc:
        assert "zero events" in str(exc).lower()
    else:
        raise AssertionError("Expected stage gate to fail when events stage returns zero rows.")


def test_execute_stage_allows_entities_when_agent_reports_inserted_and_updated_counts(tmp_path):
    service = DatabaseAnalysisRunService(SagaSQLiteStore(tmp_path / "service.sqlite"))

    service._log = lambda *args, **kwargs: None
    service._raise_if_cancelled = lambda *args, **kwargs: None
    service._run_one_stage = lambda **kwargs: {"inserted_count": 7, "updated_count": 8}

    result = service._execute_stage(
        stage="entities",
        book_ref="db://book/test",
        chapter_indices=[1],
        shared_config={},
        job_id="job-test",
        book_result={"book_id": "book-1", "title": "Book"},
        completed_units=0,
        total_units=3,
    )

    assert result == {"inserted_count": 7, "updated_count": 8}


def test_run_import_plan_job_persists_booknlp_identity_before_agents(monkeypatch, tmp_path):
    db_path = tmp_path / "service.sqlite"
    source_path = tmp_path / "book.txt"
    source_path.write_text(
        "Chapter One\n\nFeyre walked through the woods.\n\n"
        "Chapter Two\n\nTamlin waited in the manor.\n",
        encoding="utf-8",
    )
    store = SagaSQLiteStore(db_path)
    source = store.register_uploaded_source(
        original_name="book.txt",
        stored_path=str(source_path),
        size_bytes=source_path.stat().st_size,
        mime_type="text/plain",
        sha256="identity-test",
        source_kind="book",
        metadata={},
    )
    service = DatabaseAnalysisRunService(store)

    monkeypatch.setattr(
        "saga.services.database_analysis_run_service.generate_book_identity_bundle",
        lambda **kwargs: {
            "book_index": kwargs["book_index"],
            "book_slug": "book_01_test",
            "title": kwargs["book"]["title"],
            "output_dir": str(tmp_path / "identity"),
            "pipeline_identity_path": str(tmp_path / "identity" / "booknlp_small_pipeline_identity.json"),
            "character_count": 2,
            "alias_count": 2,
            "reference_entity_count": 0,
            "suppressed_cluster_count": 0,
            "narrator": {},
        },
    )
    monkeypatch.setattr(
        "saga.services.database_analysis_run_service.build_series_pipeline_identity",
        lambda **kwargs: {
            "series_id": "test-series",
            "provider": "booknlp_clean",
            "characters": [
                {"id": "char_feyre", "display_name": "Feyre", "aliases": ["Feyre"], "book_sources": [], "risk_flags": []},
                {"id": "char_tamlin", "display_name": "Tamlin", "aliases": ["Tamlin"], "book_sources": [], "risk_flags": []},
            ],
            "alias_index": {"feyre": "char_feyre", "tamlin": "char_tamlin"},
            "reference_entities": [],
            "narrators": [],
            "diagnostics": {},
            "book_identity_paths": {"book_01_test": str(tmp_path / "identity" / "booknlp_small_pipeline_identity.json")},
        },
    )

    stage_order: list[str] = []

    def fake_run_agent_stages(**kwargs):
        stage_order.append("agents")
        assert store.get_identity_series_payload("test-series") is not None
        return [], kwargs["completed_units"]

    monkeypatch.setattr(service, "_run_agent_stages", fake_run_agent_stages)

    store.upsert_dashboard_job({"id": "job-1", "type": "db-native-analysis", "status": "queued", "request": {}})
    service.run_import_plan_job(
        "job-1",
        {
            "series_id": "test-series",
            "series_title": "Test Series",
            "books": [{"source_id": source["id"], "title": "Test Book", "book_index": 1, "selected": True}],
            "shared_config": {
                "scene_target_words": 80,
                "analysis_model": "gpt_oss",
                "identity_provider": "booknlp_clean",
                "run_agents": True,
            },
        },
    )

    identity_payload = store.get_identity_series_payload("test-series")
    assert identity_payload is not None
    assert len(identity_payload.get("characters") or []) == 2
    assert stage_order == ["agents"]


def test_noncharacter_visual_baselines_stage_emits_entity_progress(monkeypatch, tmp_path):
    service = DatabaseAnalysisRunService(SagaSQLiteStore(tmp_path / "service.sqlite"))
    progress_updates = []

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        def analyze_book(self, **kwargs):
            callback = kwargs["progress_callback"]
            callback(
                {
                    "event": "started",
                    "total_entities": 5,
                    "completed_entities": 0,
                    "persisted_visual_baselines": 0,
                    "skipped_entities": 0,
                    "current_entity_name": "",
                    "current_entity_type": "",
                }
            )
            callback(
                {
                    "event": "entity_completed",
                    "total_entities": 5,
                    "completed_entities": 2,
                    "persisted_visual_baselines": 2,
                    "skipped_entities": 0,
                    "current_entity_name": "Velaris",
                    "current_entity_type": "location",
                    "skipped": False,
                }
            )
            return {"persisted_visual_baselines": 5}

    monkeypatch.setattr(
        "saga.services.database_analysis_run_service.DatabaseNonCharacterVisualBaselineAgent",
        FakeAgent,
    )
    service._log = lambda *args, **kwargs: None
    service._set_job = lambda job_id, **updates: progress_updates.append(updates.get("progress") or {})

    result = service._run_one_stage(
        stage="noncharacter_visual_baselines",
        book_ref="db://book/test",
        chapter_indices=[1],
        shared_config={},
        llm_client=None,
        job_id="job-test",
        book_result={"book_id": "book-1", "title": "Book"},
        completed_units=3,
        total_units=12,
    )

    assert result == {"persisted_visual_baselines": 5}
    assert any(update.get("details", {}).get("entity_current") == 2 for update in progress_updates)
    assert any(update.get("details", {}).get("current_entity_name") == "Velaris" for update in progress_updates)


def test_completed_stage_names_for_book_reads_structured_logs(tmp_path):
    store = SagaSQLiteStore(tmp_path / "service.sqlite")
    service = DatabaseAnalysisRunService(store)
    store.upsert_dashboard_job({"id": "job-1", "type": "db-native-analysis", "status": "failed", "request": {}})
    store.append_dashboard_job_log(
        "job-1",
        '2026-06-18 05:00:00 UTC INFO {"book_id":"book-1","event":"agent_stage_completed","stage":"events"}',
        level="INFO",
    )
    store.append_dashboard_job_log(
        "job-1",
        '2026-06-18 05:00:01 UTC INFO {"book_id":"book-1","event":"agent_stage_completed","stage":"entities"}',
        level="INFO",
    )
    store.append_dashboard_job_log(
        "job-1",
        '2026-06-18 05:00:02 UTC INFO {"book_id":"book-2","event":"agent_stage_completed","stage":"events"}',
        level="INFO",
    )

    completed = service._completed_stage_names_for_book(job_id="job-1", book_id="book-1")

    assert completed == {"events", "entities"}


def test_run_import_plan_job_resume_reuses_identity_and_ingest(monkeypatch, tmp_path):
    db_path = tmp_path / "service.sqlite"
    source_path = tmp_path / "book.txt"
    source_path.write_text("Chapter One\n\nText.\n", encoding="utf-8")
    store = SagaSQLiteStore(db_path)
    source = store.register_uploaded_source(
        original_name="book.txt",
        stored_path=str(source_path),
        size_bytes=source_path.stat().st_size,
        mime_type="text/plain",
        sha256="resume-test",
        source_kind="book",
        metadata={},
    )
    service = DatabaseAnalysisRunService(store)
    store.persist_identity_bundle(
        series_id="test-series",
        source_path=str(tmp_path / "identity.json"),
        series_payload={
            "series_id": "test-series",
            "provider": "booknlp_clean",
            "characters": [{"id": "char_a", "display_name": "A", "aliases": ["A"]}],
            "alias_index": {"a": "char_a"},
            "reference_entities": [],
            "narrators": [],
            "diagnostics": {},
            "book_identity_paths": {},
        },
        book_summaries=[],
    )
    store.upsert_dashboard_job(
        {
            "id": "failed-job",
            "type": "db-native-analysis",
            "status": "failed",
            "request": {},
        }
    )
    store.append_dashboard_job_log(
        "failed-job",
        '2026-06-18 05:00:00 UTC INFO {"book_id":"book-1","event":"agent_stage_completed","stage":"events"}',
        level="INFO",
    )
    monkeypatch.setattr(
        service,
        "_existing_analysis_book_result",
        lambda **kwargs: {
            "book_id": "book-1",
            "book_ref": "db://book/book-1",
            "title": "Test Book",
            "chapters": 1,
            "scenes": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "_build_booknlp_identity_bundle",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("identity bundle should be reused")),
    )
    monkeypatch.setattr(
        service,
        "_upsert_analysis_book",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("book ingest should be reused")),
    )

    observed = {}

    def fake_run_agent_stages(**kwargs):
        observed["resume_book"] = kwargs.get("resume_book")
        observed["completed_units"] = kwargs.get("completed_units")
        return ([], kwargs["completed_units"])

    monkeypatch.setattr(service, "_run_agent_stages", fake_run_agent_stages)

    store.upsert_dashboard_job({"id": "retry-job", "type": "db-native-analysis", "status": "queued", "request": {}})
    service.run_import_plan_job(
        "retry-job",
        {
            "series_id": "test-series",
            "series_title": "Test Series",
            "books": [{"source_id": source["id"], "title": "Test Book", "book_index": 1, "selected": True}],
            "shared_config": {
                "scene_target_words": 80,
                "analysis_model": "gpt_oss",
                "identity_provider": "booknlp_clean",
                "run_agents": True,
            },
            "resume": {"retry_of": "failed-job"},
        },
    )

    assert observed["resume_book"]["book_result"]["book_id"] == "book-1"
    assert observed["resume_book"]["completed_stages"] == {"events"}
    assert observed["completed_units"] == 4
