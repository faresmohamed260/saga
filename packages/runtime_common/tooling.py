from __future__ import annotations

from typing import Any, Callable

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from packages.runtime_common.contracts import RuntimeRequestMetadata, RuntimeToolEnvelope, RuntimeTrace
from packages.runtime_common.tracing import create_trace, finalize_trace, record_trace_event, runtime_tool_failure


def build_structured_runtime_tool(
    *,
    name: str,
    description: str,
    args_schema: type[BaseModel],
    component: str,
    operation: str,
    provider_name: Callable[[], str],
    metadata: Callable[[], dict[str, Any]] | None = None,
    response_model: type[BaseModel] | None = None,
    error_code: str,
    func: Callable[..., Any],
    error_details: Callable[..., dict[str, Any]] | None = None,
) -> StructuredTool:
    def wrapped(**kwargs):
        trace = create_trace(
            component=component,
            operation=operation,
            provider=provider_name(),
            metadata=dict(metadata() if metadata else {}),
        )
        record_trace_event(
            trace,
            event_type="runtime_tool.started",
            message=f"{name} started.",
            status="started",
            details={"tool_name": name, "input_keys": sorted(kwargs.keys())},
        )
        try:
            raw = func(**kwargs)
            payload = response_model.model_validate(raw).model_dump() if response_model else _normalize_payload(raw)
            finalized_trace = finalize_trace(
                trace,
                status="ok",
                metadata={"response_keys": sorted(payload.keys())},
            )
            record_trace_event(
                finalized_trace,
                event_type="runtime_tool.succeeded",
                message=f"{name} succeeded.",
                status="ok",
                details={"tool_name": name, "response_keys": sorted(payload.keys()), "latency_ms": finalized_trace.latency_ms},
            )
            payload = _inject_request_metadata(payload, trace=finalized_trace, response_model=response_model)
            envelope = RuntimeToolEnvelope(ok=True, data=payload, trace=finalized_trace, error=None)
            return envelope.model_dump()
        except Exception as exc:  # noqa: BLE001
            return runtime_tool_failure(
                trace,
                code=error_code,
                category=_categorize_exception(exc),
                message=str(exc),
                retryable=_is_retryable_exception(exc),
                exception_type=type(exc).__name__,
                status_code=_status_code(exc),
                details={**dict(error_details(**kwargs) if error_details else {}), "tool_name": name},
            )

    return StructuredTool.from_function(
        func=wrapped,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {"value": raw}


def _inject_request_metadata(
    payload: dict[str, Any],
    *,
    trace: RuntimeTrace,
    response_model: type[BaseModel] | None,
) -> dict[str, Any]:
    normalized = dict(payload or {})
    existing_request_metadata = normalized.get("request_metadata")
    if _has_meaningful_request_metadata(existing_request_metadata):
        return normalized
    if response_model is None:
        return normalized
    model_fields = getattr(response_model, "model_fields", {}) or {}
    if "request_metadata" not in model_fields:
        return normalized
    normalized["request_metadata"] = RuntimeRequestMetadata(
        trace_id=trace.trace_id,
        run_id=trace.run_id,
        parent_trace_id=trace.parent_trace_id,
        component=trace.component,
        operation=trace.operation,
        provider=trace.provider,
        started_at_ms=trace.started_at_ms,
        completed_at_ms=trace.completed_at_ms,
        latency_ms=trace.latency_ms,
        status=trace.status,
        error_code=str((trace.error.code if trace.error else "") or ""),
    ).model_dump()
    return normalized


def _has_meaningful_request_metadata(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return any(
        str(value.get(key) or "").strip()
        for key in ("trace_id", "component", "operation", "provider", "status")
    )


def _status_code(exc: Exception) -> int:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return int(exc.response.status_code or 0)
    return 0


def _categorize_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "not_found"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, requests.Timeout):
        return "upstream_timeout"
    if isinstance(exc, requests.HTTPError):
        status = _status_code(exc)
        if status == 404:
            return "upstream_not_found"
        if status == 429:
            return "rate_limit"
        if status >= 500:
            return "upstream_server"
        if status >= 400:
            return "upstream_http"
        return "upstream_http"
    if isinstance(exc, requests.RequestException):
        return "upstream_network"
    if isinstance(exc, ValueError):
        return "validation"
    return "runtime"


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        status = _status_code(exc)
        return status == 429 or status >= 500
    return False
