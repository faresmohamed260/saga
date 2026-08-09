"""Exporter helpers with an OpenTelemetry-compatible semantic mapping."""

from __future__ import annotations

from typing import Any, Callable
import hashlib

import requests

from packages.observability_runtime.contracts import ObservationBatch


def to_opentelemetry_payload(batch: ObservationBatch) -> dict[str, Any]:
    spans, metrics, logs = [], [], []
    for record in batch.records:
        attributes = {
            "service.name": record.component or "saga",
            "saga.run_id": record.run_id,
            "saga.series_id": record.series_id,
            "saga.stage": record.stage,
            "saga.provider": record.provider,
            **{f"saga.{key}": value for key, value in record.dimensions.items()},
        }
        if record.kind == "span":
            spans.append({"traceId": record.payload.get("trace_id", ""), "parentSpanId": record.payload.get("parent_trace_id", ""), "name": record.name, "startTimeUnixMilli": record.payload.get("started_at_ms", record.timestamp_ms), "endTimeUnixMilli": record.timestamp_ms, "status": record.status, "attributes": attributes})
        elif record.kind == "metric":
            metrics.append({"name": record.name, "unit": record.unit, "value": record.value, "timeUnixMilli": record.timestamp_ms, "attributes": attributes})
        else:
            logs.append({"eventName": record.name, "timeUnixMilli": record.timestamp_ms, "severityText": record.dimensions.get("severity", record.status), "attributes": attributes, "body": record.payload})
    return {"resourceSpans": spans, "resourceMetrics": metrics, "resourceLogs": logs}


class OpenTelemetryJsonExporter:
    """Transport-injected exporter; HTTP and vendor SDK choices stay outside the runtime."""

    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.transport = transport

    def export(self, batch: ObservationBatch) -> dict[str, Any]:
        return self.transport(to_opentelemetry_payload(batch))


class OTLPHTTPExporter:
    """Standards-shaped OTLP/HTTP JSON exporter with bounded request timeouts."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 5.0, session=None) -> None:
        self.endpoint = str(endpoint or "").strip().rstrip("/")
        if not self.endpoint:
            raise ValueError("OTLP HTTP endpoint is required.")
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.session = session or requests.Session()

    def export(self, batch: ObservationBatch) -> dict[str, Any]:
        payloads = _otlp_payloads(batch)
        delivered = {}
        for signal, payload in payloads.items():
            if not payload:
                continue
            response = self.session.post(f"{self.endpoint}/v1/{signal}", json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            delivered[signal] = len([item for item in batch.records if _signal(item.kind) == signal])
        return {"exporter": "otlp_http", "delivered": delivered}


def _otlp_payloads(batch: ObservationBatch) -> dict[str, dict[str, Any]]:
    metrics, spans, logs = [], [], []
    for record in batch.records:
        attributes = _attributes(record)
        if record.kind == "metric":
            metrics.append({"name": record.name, "unit": record.unit, "gauge": {"dataPoints": [{"timeUnixNano": str(record.timestamp_ms * 1_000_000), "asDouble": record.value or 0.0, "attributes": attributes}]}})
        elif record.kind == "span":
            trace_id = _hex_id(str(record.payload.get("trace_id") or record.observation_id), 32)
            spans.append({"traceId": trace_id, "spanId": _hex_id(record.observation_id, 16), "parentSpanId": _hex_id(str(record.payload.get("parent_trace_id") or ""), 16) if record.payload.get("parent_trace_id") else "", "name": record.name, "kind": 1, "startTimeUnixNano": str(int(record.payload.get("started_at_ms") or record.timestamp_ms) * 1_000_000), "endTimeUnixNano": str(record.timestamp_ms * 1_000_000), "attributes": attributes, "status": {"code": 2 if record.status in {"error", "failed"} else 1}})
        else:
            logs.append({"timeUnixNano": str(record.timestamp_ms * 1_000_000), "severityText": record.dimensions.get("severity", record.status), "body": {"stringValue": str(record.payload)[:4000]}, "attributes": attributes})
    resource = {"attributes": [{"key": "service.namespace", "value": {"stringValue": "saga"}}]}
    return {
        "metrics": {"resourceMetrics": [{"resource": resource, "scopeMetrics": [{"scope": {"name": "saga.observability"}, "metrics": metrics}]}]} if metrics else {},
        "traces": {"resourceSpans": [{"resource": resource, "scopeSpans": [{"scope": {"name": "saga.observability"}, "spans": spans}]}]} if spans else {},
        "logs": {"resourceLogs": [{"resource": resource, "scopeLogs": [{"scope": {"name": "saga.observability"}, "logRecords": logs}]}]} if logs else {},
    }


def _attributes(record) -> list[dict[str, Any]]:
    values = {"service.name": record.component or "saga", "saga.run_id": record.run_id, "saga.series_id": record.series_id, "saga.stage": record.stage, "saga.provider": record.provider, **{f"saga.{key}": value for key, value in record.dimensions.items()}}
    return [{"key": key, "value": {"stringValue": str(value)}} for key, value in values.items() if value != ""]


def _hex_id(value: str, length: int) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def _signal(kind: str) -> str:
    return "metrics" if kind == "metric" else "traces" if kind == "span" else "logs"
