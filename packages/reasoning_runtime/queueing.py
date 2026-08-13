"""Provider-neutral bounded admission for reasoning clients."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from packages.runtime_common import CancellationChecker, raise_if_cancelled

from .contracts import ReasoningClient


class ReasoningOverloadedError(RuntimeError):
    """Raised when the bounded reasoning queue has no admission capacity."""


class ReasoningQueueTimeoutError(TimeoutError):
    """Raised when an admitted request cannot acquire an inference slot in time."""


@dataclass(frozen=True)
class ReasoningQueuePolicy:
    max_concurrency: int = 1
    queue_capacity: int = 8
    queue_wait_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive.")
        if self.queue_capacity < 0:
            raise ValueError("queue_capacity cannot be negative.")
        if self.queue_wait_seconds <= 0:
            raise ValueError("queue_wait_seconds must be positive.")


class QueuedReasoningClient:
    """Bounded decorator that preserves the portable ReasoningClient contract."""

    def __init__(self, client: ReasoningClient, *, policy: ReasoningQueuePolicy) -> None:
        self.client = client
        self.policy = policy
        self.mode = client.mode
        self._slots = threading.BoundedSemaphore(policy.max_concurrency)
        self._state_lock = threading.Lock()
        self._pending = 0
        self._request_state = threading.local()

    def generate_json(self, prompt: str, **kwargs) -> dict[str, Any]:
        checker = kwargs.get("cancellation_checker")
        return self._execute(lambda: self.client.generate_json(prompt, **kwargs), checker)

    def generate_text(self, prompt: str, **kwargs) -> str:
        checker = kwargs.get("cancellation_checker")
        return self._execute(lambda: self.client.generate_text(prompt, **kwargs), checker)

    def provider_name(self) -> str:
        return self.client.provider_name()

    def resolved_model_name(self) -> str:
        return self.client.resolved_model_name()

    def last_request_metadata(self) -> dict[str, Any]:
        queue_metadata = getattr(self._request_state, "metadata", {})
        return {**dict(self.client.last_request_metadata() or {}), **queue_metadata}

    def _execute(self, call: Callable[[], Any], checker: CancellationChecker | None) -> Any:
        admitted_at = time.perf_counter()
        self._request_state.metadata = {
            "queue_wait_seconds": 0.0,
            "queue_max_concurrency": self.policy.max_concurrency,
            "queue_capacity": self.policy.queue_capacity,
            "queue_outcome": "admitted",
        }
        with self._state_lock:
            capacity = self.policy.max_concurrency + self.policy.queue_capacity
            if self._pending >= capacity:
                self._request_state.metadata["queue_outcome"] = "overloaded"
                raise ReasoningOverloadedError("Reasoning queue capacity is exhausted.")
            self._pending += 1
        acquired = False
        try:
            deadline = admitted_at + self.policy.queue_wait_seconds
            while not acquired:
                raise_if_cancelled(checker)
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    self._request_state.metadata.update(
                        queue_wait_seconds=round(time.perf_counter() - admitted_at, 6),
                        queue_outcome="timeout",
                    )
                    raise ReasoningQueueTimeoutError("Reasoning queue wait deadline exceeded.")
                acquired = self._slots.acquire(timeout=min(0.1, remaining))
            queue_wait = time.perf_counter() - admitted_at
            self._request_state.metadata = {
                "queue_wait_seconds": round(queue_wait, 6),
                "queue_max_concurrency": self.policy.max_concurrency,
                "queue_capacity": self.policy.queue_capacity,
                "queue_outcome": "acquired",
            }
            return call()
        finally:
            if acquired:
                self._slots.release()
            with self._state_lock:
                self._pending -= 1
