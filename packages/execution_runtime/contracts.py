"""Portable contracts for durable production execution control."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from packages.production_orchestration import OrchestrationRequest, OrchestrationResult


class ExecutionQueuePolicy(BaseModel):
    global_limit: int = Field(default=1, ge=1)
    per_series_limit: int = Field(default=1, ge=1)
    default_capability_limit: int = Field(default=1, ge=1)
    capability_limits: dict[str, int] = Field(default_factory=dict)


class ExecutionSubmission(BaseModel):
    queue_id: str
    request: OrchestrationRequest
    priority: int = 0
    max_attempts: int = 3
    backoff_seconds: int = 10


class WorkerExecutionResult(BaseModel):
    worker_id: str
    queue_id: str = ""
    run_id: str = ""
    status: str
    orchestration_result: OrchestrationResult | None = None
    queue_item: dict[str, Any] = Field(default_factory=dict)
    telemetry_export: dict[str, Any] = Field(default_factory=dict)
    observation: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)


class OrchestrationExecutor(Protocol):
    def run(self, request: OrchestrationRequest, *, thread_id: str = "") -> OrchestrationResult: ...


class TelemetryExporter(Protocol):
    def export(self, *, run_id: str, queue_item: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]: ...


class ExecutionObserver(Protocol):
    def observe(self, *, run_id: str, queue_item: dict[str, Any], events: list[dict[str, Any]], orchestration_result: OrchestrationResult | None) -> dict[str, Any]: ...
