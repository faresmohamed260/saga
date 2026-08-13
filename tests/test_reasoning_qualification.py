from __future__ import annotations

from pathlib import Path

from packages.reasoning_runtime import (
    JsonQualificationCheckpointStore,
    QualificationTask,
    ReasoningQualificationRunner,
)


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
