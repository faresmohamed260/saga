from __future__ import annotations

import contextlib
import contextvars
import time
import uuid
from typing import Any, Iterator

from packages.runtime_common.contracts import RuntimeErrorInfo, RuntimeEvent, RuntimeToolEnvelope, RuntimeTrace


_TRACE_CONTEXT: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar("runtime_trace_context", default={})


def current_trace_context() -> dict[str, str]:
    return dict(_TRACE_CONTEXT.get() or {})


@contextlib.contextmanager
def trace_scope(*, run_id: str = "", parent_trace_id: str = "") -> Iterator[dict[str, str]]:
    current = current_trace_context()
    next_context = {
        "run_id": str(run_id or current.get("run_id") or "").strip(),
        "parent_trace_id": str(parent_trace_id or current.get("parent_trace_id") or "").strip(),
    }
    token = _TRACE_CONTEXT.set(next_context)
    try:
        yield next_context
    finally:
        _TRACE_CONTEXT.reset(token)


def create_trace(
    *,
    component: str,
    operation: str,
    provider: str = "",
    metadata: dict[str, Any] | None = None,
) -> RuntimeTrace:
    context = current_trace_context()
    return RuntimeTrace(
        trace_id=uuid.uuid4().hex,
        run_id=str(context.get("run_id") or "").strip(),
        parent_trace_id=str(context.get("parent_trace_id") or "").strip(),
        component=str(component or "").strip(),
        operation=str(operation or "").strip(),
        provider=str(provider or "").strip(),
        started_at_ms=_now_ms(),
        metadata=dict(metadata or {}),
    )


def record_trace_event(
    trace: RuntimeTrace,
    *,
    event_type: str,
    message: str = "",
    status: str = "",
    details: dict[str, Any] | None = None,
) -> RuntimeTrace:
    trace.events.append(
        RuntimeEvent(
            event_type=str(event_type or "").strip(),
            message=str(message or "").strip(),
            timestamp_ms=_now_ms(),
            component=trace.component,
            operation=trace.operation,
            status=str(status or "").strip(),
            details=dict(details or {}),
        )
    )
    return trace


def finalize_trace(
    trace: RuntimeTrace,
    *,
    status: str = "ok",
    error: RuntimeErrorInfo | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeTrace:
    completed_at_ms = _now_ms()
    merged_metadata = dict(trace.metadata or {})
    if metadata:
        merged_metadata.update(dict(metadata))
    trace.status = str(status or "ok")
    trace.completed_at_ms = completed_at_ms
    trace.latency_ms = max(0, completed_at_ms - int(trace.started_at_ms or completed_at_ms))
    trace.metadata = merged_metadata
    trace.error = error
    if not trace.events:
        record_trace_event(
            trace,
            event_type="runtime.completed",
            message="Runtime operation completed.",
            status=trace.status,
            details={"latency_ms": trace.latency_ms},
        )
    return trace


def runtime_tool_success(data: dict[str, Any], trace: RuntimeTrace) -> dict[str, Any]:
    envelope = RuntimeToolEnvelope(
        ok=True,
        data=dict(data or {}),
        trace=finalize_trace(trace, status="ok"),
        error=None,
    )
    return envelope.model_dump()


def runtime_tool_failure(
    trace: RuntimeTrace,
    *,
    code: str,
    category: str = "runtime",
    message: str,
    retryable: bool = False,
    exception_type: str = "",
    status_code: int = 0,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error = RuntimeErrorInfo(
        code=str(code or "runtime_error").strip(),
        category=str(category or "runtime").strip(),
        message=str(message or "Runtime tool execution failed.").strip(),
        retryable=bool(retryable),
        exception_type=str(exception_type or "").strip(),
        status_code=max(0, int(status_code or 0)),
        details=dict(details or {}),
    )
    record_trace_event(
        trace,
        event_type="runtime_tool.failed",
        message=error.message,
        status="error",
        details={
            "error_code": error.code,
            "error_category": error.category,
            "retryable": error.retryable,
            "status_code": error.status_code,
        },
    )
    envelope = RuntimeToolEnvelope(
        ok=False,
        data={},
        trace=finalize_trace(trace, status="error", error=error),
        error=error,
    )
    return envelope.model_dump()


def _now_ms() -> int:
    return int(time.time() * 1000)
