from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    event_type: str = Field(description="Stable event type for runtime lifecycle diagnostics.")
    message: str = Field(default="", description="Human-readable event summary.")
    timestamp_ms: int = Field(default=0, description="Unix epoch time in milliseconds when the event occurred.")
    component: str = Field(default="", description="Runtime component that emitted the event.")
    operation: str = Field(default="", description="Logical operation associated with the event.")
    status: str = Field(default="", description="Event-level status such as started, ok, or error.")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional structured event details.")


class RuntimeErrorInfo(BaseModel):
    code: str = Field(description="Stable error code for agent/runtime handling.")
    category: str = Field(default="runtime", description="Stable error category for routing, observability, and retry policy.")
    message: str = Field(description="Human-readable error message.")
    retryable: bool = Field(default=False, description="Whether the failure is safe to retry.")
    exception_type: str = Field(default="", description="Concrete exception class name when available.")
    status_code: int = Field(default=0, description="Upstream HTTP status code when available.")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional structured error details.")


class RuntimeRequestMetadata(BaseModel):
    trace_id: str = ""
    run_id: str = ""
    parent_trace_id: str = ""
    component: str = ""
    operation: str = ""
    provider: str = ""
    started_at_ms: int = 0
    completed_at_ms: int = 0
    latency_ms: int = 0
    status: str = ""
    error_code: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    """Provider-reported or directly measured billable usage for one request."""

    request_count: float = Field(default=1.0, ge=0)
    input_tokens: float = Field(default=0.0, ge=0)
    output_tokens: float = Field(default=0.0, ge=0)
    cached_input_tokens: float = Field(default=0.0, ge=0)
    compute_seconds: float = Field(default=0.0, ge=0)
    image_count: float = Field(default=0.0, ge=0)
    audio_seconds: float = Field(default=0.0, ge=0)
    native_cost_usd: float | None = Field(default=None, ge=0)
    source: Literal["provider", "measured", "declared"] = "provider"
    evidence_id: str = ""


class UsageAttribution(BaseModel):
    release_id: str = ""
    project_id: str = ""
    run_id: str = ""
    series_id: str = ""
    stage: str = ""
    agent: str = ""
    component: str = ""
    provider: str = ""
    account_alias: str = ""
    model: str = ""
    operation: str = ""


class UsageReservation(BaseModel):
    reservation_id: str
    attribution: UsageAttribution
    projected: ProviderUsage
    projected_cost_usd: float = Field(default=0.0, ge=0)
    cost_status: Literal["native", "estimated", "unpriced"] = "unpriced"
    pricing_version: str = ""
    authorized: bool = True
    reasons: list[str] = Field(default_factory=list)


class UsageGovernor(Protocol):
    def reserve(self, attribution: UsageAttribution, projected: ProviderUsage) -> UsageReservation: ...

    def settle(self, reservation: UsageReservation, actual: ProviderUsage, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def release(self, reservation: UsageReservation, *, reason: str = "") -> dict[str, Any]: ...


class RuntimeTrace(BaseModel):
    trace_id: str = Field(description="Unique identifier for the runtime operation.")
    run_id: str = Field(default="", description="Agent or workflow run identifier if available.")
    parent_trace_id: str = Field(default="", description="Optional parent trace identifier.")
    component: str = Field(description="Runtime component name.")
    operation: str = Field(description="Logical operation name.")
    provider: str = Field(default="", description="Resolved provider or provider family.")
    status: str = Field(default="ok", description="Operation outcome status.")
    started_at_ms: int = Field(description="Unix epoch time in milliseconds when the operation started.")
    completed_at_ms: int = Field(default=0, description="Unix epoch time in milliseconds when the operation completed.")
    latency_ms: int = Field(default=0, description="Operation latency in milliseconds.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured trace metadata.")
    events: list[RuntimeEvent] = Field(default_factory=list, description="Structured runtime lifecycle events.")
    error: RuntimeErrorInfo | None = Field(default=None, description="Structured error payload when status is not ok.")


class RuntimeToolEnvelope(BaseModel):
    ok: bool = Field(description="Whether the tool execution succeeded.")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured tool output payload.")
    trace: RuntimeTrace = Field(description="Structured runtime trace metadata.")
    error: RuntimeErrorInfo | None = Field(default=None, description="Structured error payload when ok is false.")
