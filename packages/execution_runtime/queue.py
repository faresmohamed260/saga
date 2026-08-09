"""Provider-neutral durable queue facade and admission capability policy."""

from __future__ import annotations

import hashlib
from typing import Any

from packages.execution_runtime.contracts import ExecutionQueuePolicy, ExecutionSubmission
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.production_orchestration import OrchestrationRequest
from packages.production_orchestration.policy import resolve_stage_plan


STAGE_CAPABILITIES = {
    "analysis_foundation": {"modal_coreference"},
    "canon_extraction": {"reasoning"},
    "character_world_modeling": {"reasoning"},
    "generation_planning": {"reasoning"},
    "narrative_generation": {"reasoning"},
    "narrative_support": {"reasoning", "retrieval"},
    "visual_generation": {"modal_image", "vision_reasoning"},
    "audiobook_generation": {"modal_tts", "audio_transcription"},
    "artifact_packaging": {"artifact_storage"},
}


class ExecutionQueueRuntime:
    def __init__(self, *, persistence: PersistenceRuntimeClient, queue_name: str = "production-orchestration") -> None:
        self.persistence = persistence
        self.store = persistence.execution_queue
        self.queue_name = str(queue_name or "production-orchestration").strip()

    def configure(self, policy: ExecutionQueuePolicy) -> dict[str, Any]:
        return self.store.set_policy(self.queue_name, policy.model_dump())

    def submit(self, submission: ExecutionSubmission) -> dict[str, Any]:
        return self.store.enqueue(
            submission.queue_id,
            run_id=submission.request.run_id,
            queue_name=self.queue_name,
            series_id=submission.request.series_id,
            priority=submission.priority,
            capabilities=required_capabilities(submission.request),
            payload={"orchestration_request": submission.request.model_dump()},
            max_attempts=submission.max_attempts,
            backoff_seconds=submission.backoff_seconds,
        )

    def requeue(self, submission: ExecutionSubmission) -> dict[str, Any] | None:
        return self.store.requeue(
            submission.queue_id,
            payload={"orchestration_request": submission.request.model_dump()},
            priority=submission.priority,
            max_attempts=submission.max_attempts,
        )

    def claim(self, *, worker_id: str, lease_seconds: int, now_ms: int | None = None) -> dict[str, Any] | None:
        return self.store.claim(self.queue_name, worker_id=worker_id, lease_seconds=lease_seconds, now_ms=now_ms)

    def recover(self, *, now_ms: int | None = None) -> list[dict[str, Any]]:
        return self.store.recover_expired(self.queue_name, now_ms=now_ms)

    def heartbeat(self, item: dict[str, Any], *, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        return self.store.heartbeat(item["queue_id"], worker_id=worker_id, lease_token=item["lease_token"], lease_seconds=lease_seconds)

    def complete(self, item: dict[str, Any], *, worker_id: str, status: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self.store.complete(item["queue_id"], worker_id=worker_id, lease_token=item["lease_token"], status=status, payload=payload)

    def fail(self, item: dict[str, Any], *, worker_id: str, error: dict[str, Any], retryable: bool) -> dict[str, Any] | None:
        return self.store.fail(item["queue_id"], worker_id=worker_id, lease_token=item["lease_token"], error=error, retryable=retryable)

    def cancel(self, queue_id: str, *, reason: str = "") -> dict[str, Any] | None:
        return self.store.request_cancel(queue_id, reason=reason)

    def cancellation_requested(self, queue_id: str) -> bool:
        return self.store.is_cancellation_requested(queue_id)

    def emit(self, item: dict[str, Any], *, event_type: str, status: str, worker_id: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.store.emit_event(
            queue_name=self.queue_name, queue_id=item["queue_id"], run_id=item["run_id"],
            event_type=event_type, status=status, worker_id=worker_id, payload=payload,
        )

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(run_id=run_id, queue_name=self.queue_name, limit=10000)

    def get(self, queue_id: str) -> dict[str, Any] | None:
        return self.store.get(queue_id)

    def list(self, *, status: str = "", limit: int = 1000) -> list[dict[str, Any]]:
        return self.store.list(queue_name=self.queue_name, status=status or None, limit=limit)

    def purge_terminal(self, *, run_ids: list[str]) -> dict[str, int]:
        return self.store.purge_terminal(self.queue_name, run_ids=run_ids)


def required_capabilities(request: OrchestrationRequest) -> list[str]:
    capabilities = set()
    for stage in resolve_stage_plan(request):
        capabilities.update(STAGE_CAPABILITIES[stage])
    return sorted(capabilities)


def queue_id_for_run(run_id: str) -> str:
    return f"execution-{hashlib.sha256(str(run_id).encode('utf-8')).hexdigest()[:24]}"
