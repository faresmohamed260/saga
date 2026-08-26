"""Provider-neutral, resumable reasoning model qualification."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, Field

from packages.reasoning_runtime.contracts import ReasoningClient


class QualificationTask(BaseModel):
    task_id: str
    operation: Literal["json", "text"]
    prompt: str
    system_prompt: str = ""
    max_tokens: int = Field(default=1024, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    response_format: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any | None = None
    expected_keys: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualificationEvaluation(BaseModel):
    accepted: bool
    metrics: dict[str, float | int | bool | str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class QualificationTrial(BaseModel):
    trial_id: str
    suite_id: str
    corpus_version: str
    model: str
    provider: str
    run_variant: str = ""
    task_id: str
    task_metadata: dict[str, Any] = Field(default_factory=dict)
    repetition: int
    status: Literal["accepted", "rejected", "failed"]
    wall_seconds: float
    output: dict[str, Any] = Field(default_factory=dict)
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    evaluation: QualificationEvaluation
    error_type: str = ""
    error_message: str = ""
    created_at_ms: int


class QualificationCheckpointStore(Protocol):
    def load(self, trial_id: str) -> QualificationTrial | None: ...

    def save(self, trial: QualificationTrial) -> None: ...


class QualificationResourceMonitor(Protocol):
    def start(self) -> None: ...

    def stop(self) -> dict[str, Any]: ...


class JsonQualificationCheckpointStore:
    """Atomic local checkpoint store for portable benchmark artifacts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, trial_id: str) -> QualificationTrial | None:
        path = self._path(trial_id)
        return QualificationTrial.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def save(self, trial: QualificationTrial) -> None:
        path = self._path(trial.trial_id)
        temporary = path.with_suffix(f".tmp-{os.getpid()}")
        temporary.write_text(trial.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def _path(self, trial_id: str) -> Path:
        safe = "".join(character if character.isalnum() or character in "-_" else "_" for character in trial_id)
        return self.root / f"{safe}.json"


QualificationEvaluator = Callable[[QualificationTask, dict[str, Any]], QualificationEvaluation]
QualificationResourceMonitorFactory = Callable[[], QualificationResourceMonitor]


class ReasoningQualificationRunner:
    def __init__(
        self,
        *,
        checkpoint_store: QualificationCheckpointStore,
        max_request_seconds: int = 300,
        min_trials_before_elimination: int = 3,
        minimum_acceptance_rate: float = 0.34,
        resource_monitor_factory: QualificationResourceMonitorFactory | None = None,
        max_peak_vram_bytes: int | None = None,
        max_peak_host_ram_bytes: int | None = None,
    ) -> None:
        self.checkpoints = checkpoint_store
        self.max_request_seconds = max(1, int(max_request_seconds))
        self.min_trials_before_elimination = max(1, int(min_trials_before_elimination))
        self.minimum_acceptance_rate = min(1.0, max(0.0, float(minimum_acceptance_rate)))
        self.resource_monitor_factory = resource_monitor_factory
        self.max_peak_vram_bytes = max_peak_vram_bytes
        self.max_peak_host_ram_bytes = max_peak_host_ram_bytes

    def run_model(
        self,
        *,
        suite_id: str,
        corpus_version: str,
        client: ReasoningClient,
        tasks: list[QualificationTask],
        repetitions: int,
        evaluator: QualificationEvaluator | None = None,
        run_variant: str = "",
    ) -> list[QualificationTrial]:
        if int(getattr(client, "timeout", self.max_request_seconds)) > self.max_request_seconds:
            raise ValueError("Reasoning client timeout exceeds the qualification request deadline.")
        model, provider = client.resolved_model_name(), client.provider_name()
        results: list[QualificationTrial] = []
        resolved_evaluator = evaluator or required_keys_evaluator
        for task in tasks:
            for repetition in range(1, max(1, int(repetitions)) + 1):
                trial_id = qualification_trial_id(
                    suite_id, corpus_version, provider, model, run_variant,
                    task.model_dump(mode="json"), repetition,
                )
                existing = self.checkpoints.load(trial_id)
                if existing is not None:
                    results.append(existing)
                    continue
                trial = self._execute(
                    trial_id=trial_id, suite_id=suite_id, corpus_version=corpus_version,
                    model=model, provider=provider, client=client, task=task,
                    repetition=repetition, evaluator=resolved_evaluator,
                    run_variant=run_variant,
                )
                self.checkpoints.save(trial)
                results.append(trial)
                if self._should_eliminate(results):
                    return results
        return results

    def _execute(
        self, *, trial_id: str, suite_id: str, corpus_version: str, model: str,
        provider: str, client: ReasoningClient, task: QualificationTask,
        repetition: int, evaluator: QualificationEvaluator, run_variant: str,
    ) -> QualificationTrial:
        output: dict[str, Any] = {}
        error_type = ""
        error_message = ""
        monitor = self.resource_monitor_factory() if self.resource_monitor_factory else None
        if monitor is not None:
            monitor.start()
        started = time.perf_counter()
        try:
            if task.operation == "json":
                payload = client.generate_json(
                    task.prompt, strict=True, max_tokens=task.max_tokens,
                    response_format=task.response_format or None,
                    tools=task.tools or None, tool_choice=task.tool_choice,
                )
                output = {"payload": payload}
            else:
                text = client.generate_text(
                    task.prompt, system_prompt=task.system_prompt,
                    temperature=task.temperature, max_tokens=task.max_tokens,
                )
                output = {"text": text}
            elapsed = time.perf_counter() - started
            if elapsed > self.max_request_seconds:
                raise TimeoutError(f"Qualification request exceeded {self.max_request_seconds} seconds.")
            evaluation = evaluator(task, output)
            status: Literal["accepted", "rejected", "failed"] = "accepted" if evaluation.accepted else "rejected"
        except Exception as exc:
            elapsed = time.perf_counter() - started
            error_type, error_message = type(exc).__name__, str(exc)[:2000]
            evaluation = QualificationEvaluation(accepted=False, reasons=[error_message])
            status = "failed"
        resource_metrics = monitor.stop() if monitor is not None else {}
        resource_reasons = self._resource_limit_reasons(resource_metrics)
        if resource_reasons:
            evaluation = QualificationEvaluation(
                accepted=False,
                metrics={**evaluation.metrics, "resource_limit_exceeded": True},
                reasons=[*evaluation.reasons, *resource_reasons],
            )
            status = "failed"
            error_type = error_type or "ResourceLimitExceeded"
            error_message = error_message or "; ".join(resource_reasons)
        request_metadata = dict(client.last_request_metadata() or {})
        if resource_metrics:
            request_metadata["resource_metrics"] = resource_metrics
        return QualificationTrial(
            trial_id=trial_id, suite_id=suite_id, corpus_version=corpus_version,
            model=model, provider=provider, run_variant=run_variant, task_id=task.task_id,
            task_metadata=dict(task.metadata),
            repetition=repetition, status=status, wall_seconds=round(elapsed, 6),
            output=output, request_metadata=request_metadata,
            evaluation=evaluation, error_type=error_type, error_message=error_message,
            created_at_ms=int(time.time() * 1000),
        )

    def _resource_limit_reasons(self, metrics: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if self.max_peak_vram_bytes is not None and int(metrics.get("peak_vram_used_bytes") or 0) > self.max_peak_vram_bytes:
            reasons.append("peak_vram_limit_exceeded")
        if self.max_peak_host_ram_bytes is not None and int(metrics.get("peak_host_used_bytes") or 0) > self.max_peak_host_ram_bytes:
            reasons.append("peak_host_ram_limit_exceeded")
        return reasons

    def _should_eliminate(self, results: list[QualificationTrial]) -> bool:
        if len(results) < self.min_trials_before_elimination:
            return False
        accepted = sum(item.status == "accepted" for item in results)
        return accepted / len(results) < self.minimum_acceptance_rate


def required_keys_evaluator(task: QualificationTask, output: dict[str, Any]) -> QualificationEvaluation:
    if task.operation == "text":
        accepted = bool(str(output.get("text") or "").strip())
        return QualificationEvaluation(
            accepted=accepted,
            metrics={"nonempty": accepted},
            reasons=[] if accepted else ["empty_text"],
        )
    payload = output.get("payload")
    if not isinstance(payload, dict) or payload.get("error"):
        return QualificationEvaluation(accepted=False, metrics={"schema_valid": False}, reasons=["invalid_json_payload"])
    missing = sorted(set(task.expected_keys) - set(payload))
    return QualificationEvaluation(
        accepted=not missing,
        metrics={"schema_valid": True, "required_key_coverage": (len(task.expected_keys) - len(missing)) / max(1, len(task.expected_keys))},
        reasons=[f"missing_keys:{','.join(missing)}"] if missing else [],
    )


def qualification_trial_id(*parts: Any) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"reasoning-trial-{hashlib.sha256(encoded).hexdigest()[:24]}"
