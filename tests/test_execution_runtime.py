from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packages.execution_runtime import (
    ExecutionQueuePolicy,
    ExecutionQueueRuntime,
    ExecutionSubmission,
    ExecutionWorker,
    required_capabilities,
)
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.production_orchestration import (
    OrchestrationDecisionArtifact,
    OrchestrationRequest,
    OrchestrationResult,
)


class FakeExecutor:
    def __init__(self, request_cancelled, *, status="accepted", error=None, on_run=None) -> None:
        self.request_cancelled = request_cancelled
        self.status = status
        self.error = error
        self.on_run = on_run

    def run(self, request, *, thread_id=""):
        del thread_id
        if self.on_run:
            self.on_run()
        if self.error:
            raise self.error
        status = "cancelled" if self.request_cancelled(request.run_id) else self.status
        accepted = status == "accepted"
        return OrchestrationResult(
            request=request,
            planned_stages=["artifact_packaging"],
            decision=OrchestrationDecisionArtifact(
                decision_id=f"decision-{request.run_id}", run_id=request.run_id, series_id=request.series_id,
                accepted=accepted, status=status, failed_stage=None if accepted else "artifact_packaging",
                completed_stages=["artifact_packaging"] if accepted else [], reasons=[] if accepted else [status],
            ),
        )


class FakeTelemetryExporter:
    def __init__(self) -> None:
        self.calls = []

    def export(self, **kwargs):
        self.calls.append(kwargs)
        return {"exported": True, "event_count": len(kwargs["events"])}


class FailingTelemetryExporter:
    def export(self, **kwargs):
        del kwargs
        raise ConnectionError("telemetry sink unavailable")


class FakeObserver:
    def __init__(self, *, fail=False) -> None:
        self.calls = []
        self.fail = fail

    def observe(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("observer unavailable")
        return {"observed": True}


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="execution-runtime-test", provider="supabase", mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'execution.sqlite3'}", local_storage_root_dir=str(tmp_path / "storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _request(run_id: str, series_id: str = "series-1"):
    return OrchestrationRequest(
        run_id=run_id, series_id=series_id, story_id=f"story-{series_id}", selected_stages=["artifact_packaging"],
        include_visuals=False, include_audiobook=False,
    )


def _submit(queue: ExecutionQueueRuntime, run_id: str, series_id="series-1", *, priority=0, max_attempts=3, backoff=0):
    request = _request(run_id, series_id)
    return queue.submit(ExecutionSubmission(
        queue_id=f"queue-{run_id}", request=request, priority=priority,
        max_attempts=max_attempts, backoff_seconds=backoff,
    ))


def test_capabilities_are_derived_from_dependency_plan_not_user_secrets():
    capabilities = required_capabilities(_request("run-1"))
    assert capabilities == ["artifact_storage", "modal_coreference", "reasoning", "retrieval"]


def test_admission_enforces_series_and_capability_limits(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 3, "per_series_limit": 1, "default_capability_limit": 3, "capability_limits": {"reasoning": 2}})
    store.enqueue("q-a", run_id="a", queue_name="q", series_id="series-1", priority=10, capabilities=["reasoning"], backoff_seconds=0)
    store.enqueue("q-b", run_id="b", queue_name="q", series_id="series-1", priority=9, capabilities=["artifact_storage"], backoff_seconds=0)
    store.enqueue("q-c", run_id="c", queue_name="q", series_id="series-2", priority=8, capabilities=["reasoning"], backoff_seconds=0)
    now = int(time.time() * 1000) + 10

    first = store.claim("q", worker_id="w1", now_ms=now)
    second = store.claim("q", worker_id="w2", now_ms=now)
    assert (first["queue_id"], second["queue_id"]) == ("q-a", "q-c")
    assert store.claim("q", worker_id="w3", now_ms=now) is None
    store.complete("q-a", worker_id="w1", lease_token=first["lease_token"], now_ms=now)
    assert store.claim("q", worker_id="w3", now_ms=now)["queue_id"] == "q-b"


def test_concurrent_workers_cannot_claim_same_capacity_slot(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 1, "per_series_limit": 1})
    store.enqueue("q-a", run_id="a", queue_name="q", series_id="one")
    store.enqueue("q-b", run_id="b", queue_name="q", series_id="two")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda worker: store.claim("q", worker_id=worker), ["w1", "w2"]))
    assert len([item for item in results if item]) == 1


def test_expired_worker_cannot_heartbeat_or_complete_and_work_is_recovered(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 1})
    store.enqueue("q-a", run_id="a", queue_name="q", backoff_seconds=0)
    now = int(time.time() * 1000) + 10
    item = store.claim("q", worker_id="old", lease_seconds=1, now_ms=now)
    expired = now + 1001
    assert store.heartbeat("q-a", worker_id="old", lease_token=item["lease_token"], now_ms=expired) is None
    assert store.complete("q-a", worker_id="old", lease_token=item["lease_token"], now_ms=expired) is None
    recovered = store.recover_expired("q", now_ms=expired)
    assert recovered[0]["status"] == "retry_wait"
    replacement = store.claim("q", worker_id="new", now_ms=expired)
    assert replacement["attempt_count"] == 2
    assert replacement["lease_token"] != item["lease_token"]


def test_retry_backoff_then_dead_letter(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 1})
    store.enqueue("q-a", run_id="a", queue_name="q", max_attempts=2, backoff_seconds=1)
    now = int(time.time() * 1000) + 10
    first = store.claim("q", worker_id="w1", now_ms=now)
    waiting = store.fail("q-a", worker_id="w1", lease_token=first["lease_token"], error={"code": "temporary"}, retryable=True, now_ms=now)
    assert waiting["status"] == "retry_wait"
    assert store.claim("q", worker_id="w2", now_ms=now + 999) is None
    second = store.claim("q", worker_id="w2", now_ms=now + 1000)
    dead = store.fail("q-a", worker_id="w2", lease_token=second["lease_token"], error={"code": "temporary"}, retryable=True, now_ms=now + 1000)
    assert dead["status"] == "dead_letter"


def test_cancellation_prevents_queued_claim_and_marks_leased_work(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 2})
    store.enqueue("queued", run_id="queued-run", queue_name="q")
    assert store.request_cancel("queued", reason="user request")["status"] == "cancelled"
    assert store.claim("q", worker_id="w1") is None
    store.enqueue("leased", run_id="leased-run", queue_name="q")
    item = store.claim("q", worker_id="w1")
    assert store.request_cancel("leased")["status"] == "cancel_requested"
    assert store.is_cancellation_requested("leased") is True
    assert store.complete("leased", worker_id="w1", lease_token=item["lease_token"])["status"] == "cancelled"


def test_worker_completes_once_and_exports_structured_telemetry(tmp_path: Path):
    client = _persistence(tmp_path)
    queue = ExecutionQueueRuntime(persistence=client)
    queue.configure(ExecutionQueuePolicy(global_limit=1))
    _submit(queue, "run-ok")
    exporter = FakeTelemetryExporter()
    worker = ExecutionWorker(
        queue=queue, worker_id="worker-1", enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker), telemetry_exporter=exporter,
    )
    result = worker.run_once()
    assert result.status == "succeeded"
    assert result.orchestration_result.decision.accepted is True
    assert exporter.calls and result.telemetry_export["event_count"] >= 4
    assert ExecutionWorker(queue=queue, worker_id="worker-2", enable_heartbeat=False, executor_factory=lambda checker: FakeExecutor(checker)).run_once().status == "idle"


def test_terminal_work_remains_succeeded_when_telemetry_export_fails(tmp_path: Path):
    client = _persistence(tmp_path)
    queue = ExecutionQueueRuntime(persistence=client)
    queue.configure(ExecutionQueuePolicy(global_limit=1))
    _submit(queue, "run-telemetry-failure")
    result = ExecutionWorker(
        queue=queue,
        worker_id="worker-telemetry",
        enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker),
        telemetry_exporter=FailingTelemetryExporter(),
    ).run_once()
    assert result.status == "succeeded"
    assert result.error["telemetry_export"]["exception_type"] == "ConnectionError"
    assert queue.get(result.queue_id)["status"] == "succeeded"


def test_terminal_observer_receives_result_and_failure_cannot_reverse_success(tmp_path: Path):
    client = _persistence(tmp_path)
    queue = ExecutionQueueRuntime(persistence=client)
    queue.configure(ExecutionQueuePolicy(global_limit=1))
    _submit(queue, "run-observed")
    observer = FakeObserver()
    result = ExecutionWorker(queue=queue, worker_id="observer-ok", enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker), observer=observer).run_once()
    assert result.status == "succeeded" and result.observation == {"observed": True}
    assert observer.calls[0]["orchestration_result"].decision.accepted is True

    _submit(queue, "run-observer-fails")
    failed_observer = FakeObserver(fail=True)
    result = ExecutionWorker(queue=queue, worker_id="observer-fails", enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker), observer=failed_observer).run_once()
    assert result.status == "succeeded"
    assert result.error["observation"]["exception_type"] == "RuntimeError"
    assert queue.get(result.queue_id)["status"] == "succeeded"


def test_worker_propagates_cancellation_and_nonretryable_error(tmp_path: Path):
    client = _persistence(tmp_path)
    queue = ExecutionQueueRuntime(persistence=client)
    queue.configure(ExecutionQueuePolicy(global_limit=1))
    item = _submit(queue, "run-cancel")
    cancelled = ExecutionWorker(
        queue=queue, worker_id="worker-cancel", enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker, on_run=lambda: queue.cancel(item["queue_id"])),
    ).run_once()
    assert cancelled.status == "cancelled"

    _submit(queue, "run-invalid", max_attempts=3)
    failed = ExecutionWorker(
        queue=queue, worker_id="worker-invalid", enable_heartbeat=False,
        executor_factory=lambda checker: FakeExecutor(checker, error=ValueError("invalid request")),
    ).run_once()
    assert failed.status == "dead_letter"
    assert failed.error["exception_type"] == "ValueError"


def test_dead_letter_can_be_explicitly_requeued_with_new_payload(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("q", {"global_limit": 1})
    store.enqueue("queue-replay", run_id="run-replay", queue_name="q", payload={"version": 1}, max_attempts=1)
    item = store.claim("q", worker_id="worker", lease_seconds=30)
    failed = store.fail(item["queue_id"], worker_id="worker", lease_token=item["lease_token"], error={"code": "invalid"}, retryable=False)
    assert failed["status"] == "dead_letter"
    replay = store.requeue("queue-replay", payload={"version": 2}, max_attempts=2)
    assert replay["status"] == "queued"
    assert replay["attempt_count"] == 0
    assert replay["payload"] == {"version": 2}


def test_terminal_purge_is_scoped_and_rejects_active_work(tmp_path: Path):
    client = _persistence(tmp_path)
    store = client.execution_queue
    store.set_policy("qualification", {"global_limit": 1})
    store.enqueue("terminal", run_id="terminal-run", queue_name="qualification")
    terminal = store.claim("qualification", worker_id="worker")
    store.complete("terminal", worker_id="worker", lease_token=terminal["lease_token"])
    store.enqueue("active", run_id="active-run", queue_name="qualification")

    purged = store.purge_terminal("qualification", run_ids=["terminal-run", "active-run"])

    assert purged["queue_items"] == 1
    assert purged["events"] >= 3
    assert purged["policies"] == 0
    assert store.get("terminal") is None
    assert store.get("active")["status"] == "queued"
    assert store.get_policy("qualification") is not None
