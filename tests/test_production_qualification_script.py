from scripts.run_production_qualification import _request_cancellation


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
