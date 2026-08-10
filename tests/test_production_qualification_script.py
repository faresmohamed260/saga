from scripts.run_production_qualification import _request_cancellation, _resume_stage


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
