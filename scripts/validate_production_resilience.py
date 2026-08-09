"""Validate durable cancellation, lease recovery, and transient failure on real Supabase."""

from __future__ import annotations

import json
import time
import uuid

from packages.execution_runtime import (
    ExecutionQueuePolicy,
    ExecutionQueueRuntime,
    ExecutionRuntimeService,
    ExecutionSubmission,
    ExecutionWorker,
)
from packages.production_orchestration import OrchestrationDecisionArtifact, OrchestrationRequest, OrchestrationResult


class ProbeExecutor:
    def __init__(self, cancellation_checker, *, error: Exception | None = None, before_run=None) -> None:
        self.cancellation_checker = cancellation_checker
        self.error = error
        self.before_run = before_run

    def run(self, request: OrchestrationRequest, *, thread_id: str = "") -> OrchestrationResult:
        del thread_id
        if self.before_run:
            self.before_run()
        if self.error:
            raise self.error
        cancelled = self.cancellation_checker(request.run_id)
        return OrchestrationResult(
            request=request,
            planned_stages=["artifact_packaging"],
            decision=OrchestrationDecisionArtifact(
                decision_id=f"decision-{request.run_id}", run_id=request.run_id, series_id=request.series_id,
                accepted=not cancelled, status="cancelled" if cancelled else "accepted",
                failed_stage="artifact_packaging" if cancelled else None,
                completed_stages=[] if cancelled else ["artifact_packaging"],
                reasons=["controlled cancellation"] if cancelled else [],
            ),
        )


def main() -> int:
    suffix = uuid.uuid4().hex[:10]
    queue_name = f"qualification-resilience-{suffix}"
    service = ExecutionRuntimeService.from_env()
    queue = ExecutionQueueRuntime(persistence=service.persistence, queue_name=queue_name)
    queue.configure(ExecutionQueuePolicy(global_limit=1, per_series_limit=1))
    run_ids: list[str] = []
    checks: dict[str, object] = {}
    try:
        cancel_run = f"resilience-cancel-{suffix}"
        cancel_item = _submit(queue, cancel_run)
        run_ids.append(cancel_run)
        cancelled = ExecutionWorker(
            queue=queue, worker_id=f"cancel-worker-{suffix}", enable_heartbeat=False,
            executor_factory=lambda checker: ProbeExecutor(checker, before_run=lambda: queue.cancel(cancel_item["queue_id"], reason="controlled qualification cancellation")),
        ).run_once()
        checks["cancellation"] = cancelled.status == "cancelled" and queue.get(cancel_item["queue_id"])["status"] == "cancelled"

        restart_run = f"resilience-restart-{suffix}"
        restart_item = _submit(queue, restart_run)
        run_ids.append(restart_run)
        abandoned = queue.claim(worker_id=f"abandoned-worker-{suffix}", lease_seconds=1)
        if not abandoned or abandoned["queue_id"] != restart_item["queue_id"]:
            raise RuntimeError("Restart probe could not claim its queue item.")
        time.sleep(1.1)
        recovered = queue.recover()
        restarted = ExecutionWorker(
            queue=queue, worker_id=f"replacement-worker-{suffix}", enable_heartbeat=False,
            executor_factory=lambda checker: ProbeExecutor(checker),
        ).run_once()
        checks["worker_restart"] = (
            any(item["queue_id"] == restart_item["queue_id"] for item in recovered)
            and restarted.status == "succeeded"
            and restarted.queue_item.get("attempt_count") == 2
        )

        failure_run = f"resilience-provider-{suffix}"
        failure_item = _submit(queue, failure_run)
        run_ids.append(failure_run)
        failed_once = ExecutionWorker(
            queue=queue, worker_id=f"failure-worker-{suffix}", enable_heartbeat=False,
            executor_factory=lambda checker: ProbeExecutor(checker, error=ConnectionError("controlled provider outage")),
        ).run_once()
        recovered_failure = ExecutionWorker(
            queue=queue, worker_id=f"recovery-worker-{suffix}", enable_heartbeat=False,
            executor_factory=lambda checker: ProbeExecutor(checker),
        ).run_once()
        failure_events = queue.events(failure_run)
        checks["provider_failure"] = (
            failed_once.status == "retry_wait"
            and recovered_failure.status == "succeeded"
            and recovered_failure.queue_item.get("attempt_count") == 2
            and any(item.get("event_type") == "queue.failed" for item in failure_events)
            and queue.get(failure_item["queue_id"])["status"] == "succeeded"
        )

        accepted = all(value is True for value in checks.values())
        print(json.dumps({"accepted": accepted, "queue_name": queue_name, "checks": checks}, sort_keys=True), flush=True)
        return 0 if accepted else 2
    finally:
        cleanup = queue.purge_terminal(run_ids=run_ids)
        remaining = queue.list(limit=100)
        print(json.dumps({"cleanup": cleanup, "remaining": len(remaining)}, sort_keys=True), flush=True)
        service.persistence.close()


def _submit(queue: ExecutionQueueRuntime, run_id: str) -> dict[str, object]:
    request = OrchestrationRequest(
        run_id=run_id, series_id=f"series-{run_id}", story_id=f"story-{run_id}",
        selected_stages=["artifact_packaging"], include_visuals=False, include_audiobook=False,
    )
    return queue.submit(ExecutionSubmission(
        queue_id=f"queue-{run_id}", request=request, max_attempts=2, backoff_seconds=0,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
