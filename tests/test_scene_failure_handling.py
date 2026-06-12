from __future__ import annotations

from pathlib import Path

import pytest

from analysis.scene_analyzer import SceneAnalyzer
from infrastructure.llm_client import LLMClient
from services.encoder_persistence_service import EncoderPersistenceService, SceneFailurePolicyError


def _service(**overrides) -> EncoderPersistenceService:
    return EncoderPersistenceService(
        analysis_model=overrides.pop("analysis_model", LLMClient.MODE_GENERAL_COMPUTE),
        identity_model=overrides.pop("identity_model", LLMClient.MODE_GENERAL_COMPUTE),
        identity_provider="booknlp_clean",
        scene_failure_policy=overrides.pop("scene_failure_policy", "fail_fast"),
        analysis_provider_mode=overrides.pop("analysis_provider_mode", "single_provider"),
        max_failed_scenes_absolute=overrides.pop("max_failed_scenes_absolute", 3),
        max_failed_scene_ratio=overrides.pop("max_failed_scene_ratio", 0.10),
        min_nonempty_scene_ratio=overrides.pop("min_nonempty_scene_ratio", 0.80),
        **overrides,
    )


def _book(tmp_path: Path) -> list[dict]:
    book_path = tmp_path / "book.epub"
    book_path.write_text("placeholder", encoding="utf-8")
    return [{"path": str(book_path), "type": "epub", "title": "book.epub"}]


def _chapter() -> list[dict]:
    return [{"book_index": 1, "chapter_index": 1, "chapter_title": "One", "content": "Text", "source_file": "book.epub"}]


def _scene() -> dict:
    return {"book_index": 1, "chapter_index": 1, "scene_index": 1, "length": 10, "text": "Scene text"}


def test_general_compute_key_pool_exhaustion_classifies_as_provider_exhausted() -> None:
    category = LLMClient.classify_error(
        "max_retries_exceeded",
        "General Compute key pool exhausted; next safe slot is in 18119s, which exceeds the configured max wait of 300s.",
    )
    assert category == "provider_exhausted"


def test_max_retries_exceeded_classifies_correctly() -> None:
    assert LLMClient.classify_error("max_retries_exceeded", "other error") == "max_retries_exceeded"


def test_fail_fast_stops_book_run_on_provider_exhaustion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(scene_failure_policy="fail_fast")
    monkeypatch.setattr(service, "_build_chapters", lambda _books: _chapter())

    class _Extractor:
        def extract_many(self, chapters, allow_cross_chapter=True):
            return [_scene()]

    monkeypatch.setattr("services.encoder_persistence_service.SceneExtractor.from_target_words", lambda *_args, **_kwargs: _Extractor())
    monkeypatch.setattr(
        service,
        "_analyze_scene_with_heartbeat",
        lambda *args, **kwargs: ([{
            **_scene(),
            "scene_summary": "",
            "events": [],
            "entities_present": [],
            "entity_descriptions": [],
            "state_changes": [],
            "relationship_changes": [],
            "location": {},
            "time_signals": [],
            "canonical_characters": [],
            "character_mentions": [],
            "alias_updates": [],
            "rejected_identity_candidates": [],
            "provider": "general_compute",
            "model": "deepseek-v3.1",
            "attempt_count": 2,
            "final_status": "failed",
            "error": "max_retries_exceeded",
            "error_category": "provider_exhausted",
            "last_error": "General Compute key pool exhausted; next safe slot is in 18119s, which exceeds the configured max wait of 300s.",
        }], [0]),
    )

    with pytest.raises(SceneFailurePolicyError) as exc:
        service.encode_books(_book(tmp_path))

    contract = exc.value.contract
    assert contract["run_status"] == "failed"
    assert contract["runtime"]["scene_analysis_quality"]["failed_scenes"] == 1
    assert contract["outputs"]["artifact_validity"]["timeline"]["invalid_due_to_scene_failure"] is True


def test_single_provider_metadata_recorded_in_contract() -> None:
    service = _service(scene_failure_policy="write_partial", analysis_provider_mode="single_provider")
    contract = service._build_contract(
        prepared_books=[],
        series_id="acotar",
        series_title="ACOTAR",
        chapters=[],
        scene_analyses=[],
        resolved_scene_analyses=[],
        entity_registry=[],
        state_result={"transitions": [], "latest_state": []},
        canon_snapshot=[],
        timeline=[],
        event_ledger=[],
        character_timelines=[],
        character_profiles=[],
        stable_character_states=[],
        identity_result={"alias_map": {}},
        causal_graph_result={"graph": {}, "metrics": {}},
        story_index_summary={"document_count": 0},
        elapsed_seconds=0.1,
        run_status="partial",
        scene_analysis_quality={"total_scenes": 1, "successful_scenes": 0, "failed_scenes": 1, "failure_ratio": 1.0, "nonempty_scene_ratio": 0.0},
        failed_scenes=[{"error_category": "provider_exhausted"}],
        artifacts_invalid=True,
    )
    assert contract["configuration"]["analysis_provider_mode"] == "single_provider"
    assert contract["runtime"]["analysis_provider_mode"] == "single_provider"


def test_acosf_style_failed_scene_quality_is_marked_failed() -> None:
    service = _service(scene_failure_policy="skip_failed")
    quality = service._scene_quality_metrics([], [{"error_category": "provider_exhausted"} for _ in range(66)], 66)
    assert service._scene_quality_failed(quality) is True
    assert service._run_status_from_policy(quality, [{"error_category": "provider_exhausted"}]) == "failed"


def test_skip_failed_below_threshold_marks_contract_partial() -> None:
    service = _service(scene_failure_policy="skip_failed", max_failed_scenes_absolute=3, max_failed_scene_ratio=0.5, min_nonempty_scene_ratio=0.4)
    quality = {
        "total_scenes": 10,
        "successful_scenes": 9,
        "failed_scenes": 1,
        "failure_ratio": 0.1,
        "nonempty_scene_ratio": 0.9,
    }
    assert service._scene_quality_failed(quality) is False
    assert service._run_status_from_policy(quality, [{"error_category": "validation_failed"}]) == "partial"


def test_artifact_validity_marks_outputs_invalid_due_to_scene_failure() -> None:
    service = _service()
    validity = service._artifact_validity(True)
    assert validity["entity_registry"]["invalid_due_to_scene_failure"] is True
    assert validity["story_index_summary"]["status"] == "invalid_due_to_scene_failure"


def test_no_automatic_rotation_flags_used_for_canonical_scene_analysis() -> None:
    llm = LLMClient(
        mode=LLMClient.MODE_GENERAL_COMPUTE,
        allow_account_rotation=False,
        allow_cross_provider_fallback=False,
    )
    assert llm.allow_account_rotation is False
    assert llm.allow_cross_provider_fallback is False


def test_same_provider_rotating_policy_enables_account_rotation() -> None:
    service = _service(analysis_provider_mode="same_provider_rotating")
    policy = service._analysis_client_policy()
    assert policy["allow_account_rotation"] is True
    assert policy["allow_cross_provider_fallback"] is False
    assert policy["canonical_consistency_status"] == "same_provider_rotating"


def test_cross_provider_fallback_marks_experimental_contract() -> None:
    service = _service(scene_failure_policy="write_partial", analysis_provider_mode="cross_provider_fallback")
    contract = service._build_contract(
        prepared_books=[],
        series_id="acotar",
        series_title="ACOTAR",
        chapters=[],
        scene_analyses=[],
        resolved_scene_analyses=[],
        entity_registry=[],
        state_result={"transitions": [], "latest_state": []},
        canon_snapshot=[],
        timeline=[],
        event_ledger=[],
        character_timelines=[],
        character_profiles=[],
        stable_character_states=[],
        identity_result={"alias_map": {}},
        causal_graph_result={"graph": {}, "metrics": {}},
        story_index_summary={"document_count": 0},
        elapsed_seconds=0.1,
        run_status="success",
        scene_analysis_quality={"total_scenes": 1, "successful_scenes": 1, "failed_scenes": 0, "failure_ratio": 0.0, "nonempty_scene_ratio": 1.0},
        failed_scenes=[],
        artifacts_invalid=False,
    )
    assert contract["runtime"]["canonical_consistency_status"] == "mixed_provider_experimental"
    assert contract["runtime"]["cross_provider_fallback_allowed"] is True


def test_scene_runtime_metadata_records_rotation_usage() -> None:
    class _FakeLLM:
        def provider_name(self):
            return "ollama"

        def resolved_model_name(self):
            return "gpt-oss:120b-cloud"

        def last_request_metadata(self):
            return {
                "provider_family": "ollama",
                "resolved_model": "gpt-oss:120b-cloud",
                "provider_account_alias": "acct-2",
                "rotation_used": True,
                "rotation_attempt_count": 1,
                "fallback_used": False,
            }

    analyzer = SceneAnalyzer(llm_client=_FakeLLM())
    meta = analyzer._scene_runtime_metadata(attempt_count=2, final_status="success")
    assert meta["provider_account_alias"] == "acct-2"
    assert meta["rotation_used"] is True
    assert meta["rotation_attempt_count"] == 1


def test_same_provider_rotating_rejects_provider_model_drift() -> None:
    service = _service(analysis_provider_mode="same_provider_rotating", analysis_model=LLMClient.MODE_GPT_OSS)
    with pytest.raises(SceneFailurePolicyError):
        service._enforce_provider_consistency({
            "provider_family": "ollama",
            "resolved_model": "different-model",
            "fallback_used": False,
        })


def test_contract_records_account_rotation_allowed() -> None:
    service = _service(scene_failure_policy="write_partial", analysis_provider_mode="same_provider_rotating", analysis_model=LLMClient.MODE_GPT_OSS)
    contract = service._build_contract(
        prepared_books=[],
        series_id="acotar",
        series_title="ACOTAR",
        chapters=[],
        scene_analyses=[{
            "provider_account_alias": "acct-1",
            "provider_family": "ollama",
            "resolved_model": "gpt-oss:120b-cloud",
            "rotation_used": True,
            "rotation_attempt_count": 1,
            "fallback_used": False,
        }],
        resolved_scene_analyses=[],
        entity_registry=[],
        state_result={"transitions": [], "latest_state": []},
        canon_snapshot=[],
        timeline=[],
        event_ledger=[],
        character_timelines=[],
        character_profiles=[],
        stable_character_states=[],
        identity_result={"alias_map": {}},
        causal_graph_result={"graph": {}, "metrics": {}},
        story_index_summary={"document_count": 0},
        elapsed_seconds=0.1,
        run_status="success",
        scene_analysis_quality={"total_scenes": 1, "successful_scenes": 1, "failed_scenes": 0, "failure_ratio": 0.0, "nonempty_scene_ratio": 1.0},
        failed_scenes=[],
        artifacts_invalid=False,
    )
    assert contract["runtime"]["account_rotation_allowed"] is True
    assert contract["runtime"]["unique_account_aliases_used_count"] == 1


def test_max_chapters_caps_bounded_encode_input(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(max_chapters=3)
    source = [
        {"book_index": 1, "chapter_index": 1, "chapter_title": "One", "content": "A", "source_file": "book.epub"},
        {"book_index": 1, "chapter_index": 2, "chapter_title": "Two", "content": "B", "source_file": "book.epub"},
        {"book_index": 1, "chapter_index": 3, "chapter_title": "Three", "content": "C", "source_file": "book.epub"},
        {"book_index": 1, "chapter_index": 4, "chapter_title": "Four", "content": "D", "source_file": "book.epub"},
    ]

    class _Processor:
        def process(self, _book_inputs):
            return list(source)

    monkeypatch.setattr("services.encoder_persistence_service.SeriesProcessor", lambda llm_client: _Processor())
    chapters = service._build_chapters(_book(Path(".")))
    assert [row["chapter_index"] for row in chapters] == [1, 2, 3]
