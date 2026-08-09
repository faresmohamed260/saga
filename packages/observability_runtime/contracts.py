"""Portable contracts for operational observations, SLOs, and exporters."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


ObservationKind = Literal["event", "metric", "span", "alert"]


class ObservationRecord(BaseModel):
    observation_id: str
    kind: ObservationKind
    timestamp_ms: int
    run_id: str = ""
    series_id: str = ""
    component: str = ""
    stage: str = ""
    provider: str = ""
    name: str
    status: str = ""
    value: float | None = None
    unit: str = ""
    dimensions: dict[str, str] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class ObservationBatch(BaseModel):
    batch_id: str
    records: list[ObservationRecord] = Field(default_factory=list)


class SLODefinition(BaseModel):
    slo_id: str
    metric_name: str
    comparator: Literal["gte", "lte"]
    threshold: float
    aggregation: Literal["average", "sum", "min", "max", "p95"] = "average"
    window_seconds: int = Field(default=3600, ge=1)
    minimum_samples: int = Field(default=1, ge=1)
    severity: Literal["warning", "critical"] = "warning"
    component: str = ""
    provider: str = ""


class SLOEvaluation(BaseModel):
    slo_id: str
    status: Literal["healthy", "breached", "insufficient_data"]
    observed_value: float | None = None
    threshold: float
    sample_count: int
    window_start_ms: int
    window_end_ms: int
    alert: ObservationRecord | None = None


class CostRate(BaseModel):
    provider: str
    model: str = ""
    input_per_million: float = Field(default=0.0, ge=0)
    output_per_million: float = Field(default=0.0, ge=0)
    compute_per_second: float = Field(default=0.0, ge=0)
    pricing_version: str


class ObservationStore(Protocol):
    def append_many(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def list(self, **filters: Any) -> list[dict[str, Any]]: ...

    def delete_before(self, timestamp_ms: int, *, kind: str = "") -> int: ...


class ObservabilityExporter(Protocol):
    def export(self, batch: ObservationBatch) -> dict[str, Any]: ...
