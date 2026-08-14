from scripts.run_production_qualification import (
    _build_stage_slice_report,
    _qualification_queue_name,
    _request_cancellation,
    _requires_generation_preflight,
    _reasoning_budget_provider,
    _resume_stage,
    _stage_timeout_seconds,
)
from pathlib import Path

from packages.production_orchestration import OrchestrationDecisionArtifact, OrchestrationRequest, OrchestrationResult, StageOutcomeArtifact


def test_qualification_uses_distinct_generation_deadlines():
    assert _stage_timeout_seconds(
        "canon_extraction",
        standard_timeout_seconds=300,
        generation_timeout_seconds=900,
    ) == 300
    assert _stage_timeout_seconds(
        "visual_generation",
        standard_timeout_seconds=300,
        generation_timeout_seconds=900,
    ) == 900


def test_qualification_cancellation_is_requested_only_once():
    calls = []
    service = type(
        "Service",
        (),
        {"cancel": lambda self, queue_id, reason: calls.append((queue_id, reason))},
    )()

    requested = _request_cancellation(
        service,
        queue_id="queue-1",
        reason="stage deadline",
        already_requested=False,
    )
    requested = _request_cancellation(
        service,
        queue_id="queue-1",
        reason="stage deadline",
        already_requested=requested,
    )

    assert requested is True
    assert calls == [("queue-1", "stage deadline")]


def test_resume_skips_historical_logs_and_tracks_failed_stage():
    logs = [
        {"id": 1, "stage": "analysis_foundation", "message": "stage_accepted"},
        {"id": 2, "stage": "canon_extraction", "message": "stage_cancelled"},
        {"id": 3, "stage": "orchestration", "message": "run_cancelled"},
    ]

    assert _resume_stage(logs) == "canon_extraction"


def test_qualification_queue_is_isolated_and_stable_per_run():
    assert _qualification_queue_name("rc16/run 1") == "production-qualification-rc16-run-1"


def test_partial_stage_does_not_probe_unrequested_generation_provider():
    assert _requires_generation_preflight("analysis_foundation") is False
    assert _requires_generation_preflight("canon_extraction") is False
    assert _requires_generation_preflight("generation_planning") is True


def test_reasoning_budget_uses_runtime_provider_identity():
    assert _reasoning_budget_provider("ollama_local") == "ollama_local"
    assert _reasoning_budget_provider("lm_studio_local") == "lm_studio_local"
    assert _reasoning_budget_provider("mistral") == "mistral"
    assert _reasoning_budget_provider("gpt_oss") == "ollama"


def test_partial_stage_report_preserves_accepted_outcome():
    request = OrchestrationRequest(
        run_id="run-1",
        series_id="series-1",
        project_id="project-1",
        selected_stages=["analysis_foundation"],
    )
    outcome = StageOutcomeArtifact(
        stage="analysis_foundation",
        status="accepted",
        accepted=True,
        elapsed_seconds=12.5,
    )
    result = OrchestrationResult(
        request=request,
        planned_stages=["analysis_foundation"],
        outcomes=[outcome],
        decision=OrchestrationDecisionArtifact(
            decision_id="decision-1",
            run_id="run-1",
            series_id="series-1",
            accepted=True,
            status="accepted",
            completed_stages=["analysis_foundation"],
        ),
    )

    report = _build_stage_slice_report(
        result=result,
        source=Path("book.epub"),
        source_sha256="abc",
        release_id="release-1",
        elapsed_seconds=13.0,
    )

    assert report["accepted"] is True
    assert report["completed_stages"] == ["analysis_foundation"]
    assert report["metrics"]["stage_seconds"] == {"analysis_foundation": 12.5}
