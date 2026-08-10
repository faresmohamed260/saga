"""Lease-owning orchestration worker with heartbeat and terminal telemetry."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from packages.execution_runtime.contracts import ExecutionObserver, OrchestrationExecutor, TelemetryExporter, WorkerExecutionResult
from packages.execution_runtime.queue import ExecutionQueueRuntime
from packages.production_orchestration import OrchestrationRequest


class ExecutionWorker:
    def __init__(
        self,
        *,
        queue: ExecutionQueueRuntime,
        executor_factory: Callable[[Callable[[str], bool]], OrchestrationExecutor],
        telemetry_exporter: TelemetryExporter | None = None,
        observer: ExecutionObserver | None = None,
        worker_id: str,
        lease_seconds: int = 120,
        enable_heartbeat: bool = True,
    ) -> None:
        self.queue = queue
        self.executor_factory = executor_factory
        self.telemetry_exporter = telemetry_exporter
        self.observer = observer
        self.worker_id = str(worker_id or "").strip()
        self.lease_seconds = max(3, int(lease_seconds))
        self.enable_heartbeat = enable_heartbeat
        if not self.worker_id:
            raise ValueError("worker_id is required.")

    def run_once(self) -> WorkerExecutionResult:
        item = self.queue.claim(worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        if item is None:
            return WorkerExecutionResult(worker_id=self.worker_id, status="idle")
        self.queue.emit(item, event_type="worker.started", status="running", worker_id=self.worker_id)
        heartbeat = _LeaseHeartbeat(self.queue, item, self.worker_id, self.lease_seconds) if self.enable_heartbeat else None
        if heartbeat:
            heartbeat.start()
        result = None
        executor = None
        error: dict[str, Any] = {}
        try:
            request = OrchestrationRequest.model_validate(dict(item.get("payload") or {}).get("orchestration_request") or {})
            executor = self.executor_factory(lambda run_id: self.queue.cancellation_requested(item["queue_id"]))
            result = executor.run(request, thread_id=f"worker-{self.worker_id}-{item['attempt_count']}")
            terminal_status = "succeeded" if result.decision.accepted else "cancelled" if result.decision.status == "cancelled" else "failed"
            if terminal_status in {"succeeded", "cancelled"}:
                final = self.queue.complete(item, worker_id=self.worker_id, status=terminal_status, payload={"orchestration_decision": result.decision.model_dump(), "manifest_id": result.manifest.manifest_id if result.manifest else ""})
            else:
                error = {"code": "orchestration_failed", "decision": result.decision.model_dump()}
                final = self.queue.fail(item, worker_id=self.worker_id, error=error, retryable=result.decision.status == "failed")
        except Exception as exc:
            error = {"code": "worker_exception", "exception_type": type(exc).__name__, "message": str(exc)}
            final = self.queue.fail(item, worker_id=self.worker_id, error=error, retryable=_retryable(exc))
        finally:
            close = getattr(executor, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    error = {
                        **error,
                        "executor_close": {
                            "exception_type": type(exc).__name__,
                            "message": str(exc),
                        },
                    }
            if heartbeat:
                heartbeat.stop()
        if final is None:
            self.queue.emit(item, event_type="worker.lease_lost", status="lease_lost", worker_id=self.worker_id)
            return WorkerExecutionResult(worker_id=self.worker_id, queue_id=item["queue_id"], run_id=item["run_id"], status="lease_lost", orchestration_result=result, error=error)
        self.queue.emit(item, event_type="worker.finished", status=final["status"], worker_id=self.worker_id, payload={"attempt": final["attempt_count"]})
        try:
            exported = self._export(final)
        except Exception as exc:
            exported = {}
            error = {
                **error,
                "telemetry_export": {"exception_type": type(exc).__name__, "message": str(exc)},
            }
            self.queue.emit(
                final,
                event_type="worker.telemetry_export_failed",
                status=final["status"],
                worker_id=self.worker_id,
                payload=error["telemetry_export"],
            )
        try:
            observation = self._observe(final, result)
        except Exception as exc:
            observation = {}
            error = {**error, "observation": {"exception_type": type(exc).__name__, "message": str(exc)}}
            self.queue.emit(final, event_type="worker.observation_failed", status=final["status"], worker_id=self.worker_id, payload=error["observation"])
        return WorkerExecutionResult(
            worker_id=self.worker_id, queue_id=item["queue_id"], run_id=item["run_id"], status=final["status"],
            orchestration_result=result, queue_item=final, telemetry_export=exported, observation=observation, error=error,
        )

    def _export(self, item: dict[str, Any]) -> dict[str, Any]:
        if self.telemetry_exporter is None or item["status"] not in {"succeeded", "cancelled", "dead_letter"}:
            return {}
        return self.telemetry_exporter.export(run_id=item["run_id"], queue_item=item, events=self.queue.events(item["run_id"]))

    def _observe(self, item: dict[str, Any], result: Any) -> dict[str, Any]:
        if self.observer is None or item["status"] not in {"succeeded", "cancelled", "dead_letter"}:
            return {}
        return self.observer.observe(run_id=item["run_id"], queue_item=item, events=self.queue.events(item["run_id"]), orchestration_result=result)


class _LeaseHeartbeat:
    def __init__(self, queue: ExecutionQueueRuntime, item: dict[str, Any], worker_id: str, lease_seconds: int) -> None:
        self.queue = queue
        self.item = item
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"lease-heartbeat-{worker_id}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _run(self) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while not self.stop_event.wait(interval):
            if self.queue.heartbeat(self.item, worker_id=self.worker_id, lease_seconds=self.lease_seconds) is None:
                return


def _retryable(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError, OSError)) and not isinstance(exc, (ValueError, FileNotFoundError))
