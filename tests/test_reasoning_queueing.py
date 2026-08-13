import threading

import pytest

from packages.reasoning_runtime import (
    QueuedReasoningClient,
    ReasoningOverloadedError,
    ReasoningQueuePolicy,
    ReasoningQueueTimeoutError,
)
from packages.runtime_common import RuntimeCancelledError


class BlockingClient:
    mode = "test"

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def generate_json(self, prompt, **kwargs):
        self.entered.set()
        self.release.wait(timeout=2)
        return {"prompt": prompt}

    def generate_text(self, prompt, **kwargs):
        return prompt

    def provider_name(self):
        return "test"

    def resolved_model_name(self):
        return "test-model"

    def last_request_metadata(self):
        return {"provider": "test"}


def test_queue_rejects_when_active_and_waiting_capacity_is_exhausted():
    delegate = BlockingClient()
    client = QueuedReasoningClient(
        delegate, policy=ReasoningQueuePolicy(max_concurrency=1, queue_capacity=0),
    )
    worker = threading.Thread(target=lambda: client.generate_json("first"))
    worker.start()
    assert delegate.entered.wait(timeout=1)
    with pytest.raises(ReasoningOverloadedError):
        client.generate_json("second")
    delegate.release.set()
    worker.join(timeout=2)


def test_queue_times_out_admitted_waiters_and_reports_wait_metadata():
    delegate = BlockingClient()
    client = QueuedReasoningClient(
        delegate,
        policy=ReasoningQueuePolicy(max_concurrency=1, queue_capacity=1, queue_wait_seconds=0.05),
    )
    worker = threading.Thread(target=lambda: client.generate_json("first"))
    worker.start()
    assert delegate.entered.wait(timeout=1)
    with pytest.raises(ReasoningQueueTimeoutError):
        client.generate_json("second")
    assert client.last_request_metadata()["queue_outcome"] == "timeout"
    delegate.release.set()
    worker.join(timeout=2)
    assert client.last_request_metadata()["queue_max_concurrency"] == 1


def test_queue_wait_honors_cancellation():
    delegate = BlockingClient()
    client = QueuedReasoningClient(
        delegate,
        policy=ReasoningQueuePolicy(max_concurrency=1, queue_capacity=1, queue_wait_seconds=1),
    )
    worker = threading.Thread(target=lambda: client.generate_json("first"))
    worker.start()
    assert delegate.entered.wait(timeout=1)

    with pytest.raises(RuntimeCancelledError):
        client.generate_json("second", cancellation_checker=lambda: True)

    delegate.release.set()
    worker.join(timeout=2)
