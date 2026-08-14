from __future__ import annotations

from pathlib import Path

from packages.reasoning_runtime import (
    JsonQualificationCheckpointStore,
    QualificationTask,
    ReasoningQualificationRunner,
    qualification_trial_id,
)
from scripts.qualify_local_reasoning import _load_completed_trials


class FakeReasoningClient:
    timeout = 30

    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.calls = 0

    def resolved_model_name(self) -> str:
        return "local-model"

    def provider_name(self) -> str:
        return "local-engine"

    def generate_json(self, *args, **kwargs):
        self.calls += 1
        self.last_json_kwargs = kwargs
        return {"answer": 42} if self.valid else {"error": "parse_failed"}

    def generate_text(self, *args, **kwargs):
        self.calls += 1
        return "ready" if self.valid else ""

    def last_request_metadata(self):
        return {"status": "ok", "latency_ms": 10}


def _task() -> QualificationTask:
    return QualificationTask(
        task_id="structured-answer", operation="json", prompt="Answer.",
        expected_keys=["answer"],
    )


def test_qualification_checkpoints_each_trial_and_resumes_without_inference(tmp_path: Path):
    store = JsonQualificationCheckpointStore(tmp_path / "trials")
    runner = ReasoningQualificationRunner(checkpoint_store=store)
    first_client = FakeReasoningClient()

    first = runner.run_model(
        suite_id="suite", corpus_version="v1", client=first_client,
        tasks=[_task()], repetitions=3,
    )
    second_client = FakeReasoningClient()
    second = runner.run_model(
        suite_id="suite", corpus_version="v1", client=second_client,
        tasks=[_task()], repetitions=3,
    )

    assert len(first) == len(second) == 3
    assert all(item.status == "accepted" for item in first)
    assert first_client.calls == 3
    assert second_client.calls == 0


def test_qualification_plan_can_resolve_complete_checkpoints_before_model_load(tmp_path: Path):
    store = JsonQualificationCheckpointStore(tmp_path / "trials")
    task = _task()
    trials = ReasoningQualificationRunner(checkpoint_store=store).run_model(
        suite_id="suite", corpus_version="v1", client=FakeReasoningClient(),
        tasks=[task], repetitions=1, run_variant="profile-a",
    )

    expected_id = qualification_trial_id(
        "suite", "v1", "local-engine", "local-model", "profile-a",
        task.model_dump(mode="json"), 1,
    )
    assert trials[0].trial_id == expected_id
    assert _load_completed_trials(
        store=store, tasks=[task], repetitions=1, suite_id="suite",
        corpus_version="v1", provider="local-engine", model="local-model",
        run_variant="profile-a",
    ) == trials
    assert _load_completed_trials(
        store=store, tasks=[task], repetitions=2, suite_id="suite",
        corpus_version="v1", provider="local-engine", model="local-model",
        run_variant="profile-a",
    ) is None


def test_qualification_eliminates_a_model_after_repeated_contract_failures(tmp_path: Path):
    client = FakeReasoningClient(valid=False)
    runner = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(tmp_path / "trials"),
        min_trials_before_elimination=3,
        minimum_acceptance_rate=0.5,
    )

    results = runner.run_model(
        suite_id="suite", corpus_version="v1", client=client,
        tasks=[_task()], repetitions=5,
    )

    assert len(results) == 3
    assert all(item.status == "rejected" for item in results)
    assert client.calls == 3


def test_qualification_rejects_clients_with_an_unbounded_timeout(tmp_path: Path):
    client = FakeReasoningClient()
    client.timeout = 301
    runner = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(tmp_path / "trials"),
        max_request_seconds=300,
    )

    try:
        runner.run_model(
            suite_id="suite", corpus_version="v1", client=client,
            tasks=[_task()], repetitions=1,
        )
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("Expected an explicit timeout-bound failure.")


def test_qualification_forwards_provider_neutral_tools(tmp_path: Path):
    client = FakeReasoningClient()
    task = QualificationTask(
        task_id="tool", operation="json", prompt="Load the book.",
        expected_keys=["answer"],
        tools=[{"type": "function", "function": {
            "name": "load_book", "parameters": {"type": "object"},
        }}],
    )

    ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(tmp_path / "trials"),
    ).run_model(
        suite_id="suite", corpus_version="v1", client=client,
        tasks=[task], repetitions=1,
    )

    assert client.last_json_kwargs["tools"] == task.tools


def test_qualification_records_resource_monitor_metrics(tmp_path: Path):
    class Monitor:
        def start(self):
            self.started = True

        def stop(self):
            assert self.started
            return {"peak_ram_bytes": 123, "peak_vram_bytes": 456}

    trials = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(tmp_path / "trials"),
        resource_monitor_factory=Monitor,
    ).run_model(
        suite_id="suite", corpus_version="v1", client=FakeReasoningClient(),
        tasks=[QualificationTask(task_id="resource", operation="text", prompt="test")],
        repetitions=1,
    )

    assert trials[0].request_metadata["resource_metrics"]["peak_vram_bytes"] == 456
    assert trials[0].task_metadata == {}


def test_qualification_fails_trials_that_violate_resource_headroom(tmp_path: Path):
    class Monitor:
        def start(self):
            pass

        def stop(self):
            return {"peak_vram_used_bytes": 11 * 1024 ** 3, "peak_host_used_bytes": 1}

    trials = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(tmp_path / "trials"),
        resource_monitor_factory=Monitor, max_peak_vram_bytes=10 * 1024 ** 3,
    ).run_model(
        suite_id="suite", corpus_version="v1", client=FakeReasoningClient(),
        tasks=[QualificationTask(task_id="resource", operation="text", prompt="test")],
        repetitions=1,
    )

    assert trials[0].status == "failed"
    assert trials[0].error_type == "ResourceLimitExceeded"
