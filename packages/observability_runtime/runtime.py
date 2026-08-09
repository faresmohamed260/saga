"""Provider-neutral normalization, aggregation, retention, and SLO evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

from packages.observability_runtime.contracts import (
    CostRate,
    ObservationBatch,
    ObservationRecord,
    ObservabilityExporter,
    ObservationStore,
    SLODefinition,
    SLOEvaluation,
)
from packages.observability_runtime.safety import bounded_dimensions, sanitize


QUALITY_METRIC_KEYS = frozenset({
    "accepted_render_count", "artifact_count", "book_count", "chapter_count", "character_profile_count",
    "continuity", "contradiction_rate", "duration_seconds", "entity_count", "event_count", "factual_support_rate",
    "identity_count", "manifest_version", "scene_count", "timeline_count", "unsupported_rate", "word_count",
    "world_state_count",
})


@dataclass(frozen=True)
class ObservabilityRuntimeConfig:
    retention_days: int = 30
    cost_rates: tuple[CostRate, ...] = field(default_factory=tuple)


class ObservabilityRuntime:
    def __init__(self, *, store: ObservationStore, exporters: list[ObservabilityExporter] | None = None, config: ObservabilityRuntimeConfig | None = None) -> None:
        self.store = store
        self.exporters = list(exporters or [])
        self.config = config or ObservabilityRuntimeConfig()

    def observe_execution(self, *, run_id: str, queue_item: dict[str, Any], events: list[dict[str, Any]], orchestration_result: Any = None, lineage_records: list[dict[str, Any]] | None = None, trace_payloads: list[dict[str, Any]] | None = None, queue_depth: int | None = None) -> dict[str, Any]:
        result = orchestration_result.model_dump() if hasattr(orchestration_result, "model_dump") else dict(orchestration_result or {})
        request = dict(queue_item.get("payload") or {}).get("orchestration_request") or result.get("request") or {}
        series_id = str(queue_item.get("series_id") or request.get("series_id") or "")
        event_timestamps = [int(item.get("timestamp_ms") or 0) for item in events if int(item.get("timestamp_ms") or 0) > 0]
        terminal_ms = max(event_timestamps) if event_timestamps else _now_ms()
        records: list[ObservationRecord] = []

        records.extend(self._queue_records(run_id, series_id, queue_item, events, terminal_ms, queue_depth))
        records.extend(self._outcome_records(run_id, series_id, result, terminal_ms, lineage_records or []))
        for trace in _find_traces({"result": result, "lineage": lineage_records or [], "snapshots": trace_payloads or []}):
            records.extend(self._trace_records(run_id, series_id, trace))
        batch = ObservationBatch(batch_id=_stable_id("batch", run_id, queue_item.get("status"), terminal_ms), records=_dedupe(records))
        return self.record_batch(batch)

    def record_batch(self, batch: ObservationBatch) -> dict[str, Any]:
        persisted = self.store.append_many([item.model_dump() for item in batch.records])
        export_results, export_errors = [], []
        for exporter in self.exporters:
            try:
                export_results.append(exporter.export(batch))
            except Exception as exc:
                export_errors.append({"exporter": type(exporter).__name__, "exception_type": type(exc).__name__, "message": str(exc)[:500]})
        return {"batch_id": batch.batch_id, "record_count": len(persisted), "exports": export_results, "export_errors": export_errors}

    def evaluate_slos(self, definitions: list[SLODefinition], *, now_ms: int | None = None, persist_alerts: bool = True) -> list[SLOEvaluation]:
        end = int(now_ms or _now_ms())
        evaluations: list[SLOEvaluation] = []
        alerts: list[ObservationRecord] = []
        for definition in definitions:
            start = end - definition.window_seconds * 1000
            rows = self.store.list(kind="metric", name=definition.metric_name, component=definition.component, provider=definition.provider, since_ms=start, until_ms=end, limit=100000)
            values = [float(item["value"]) for item in rows if item.get("value") is not None and math.isfinite(float(item["value"]))]
            if len(values) < definition.minimum_samples:
                evaluations.append(SLOEvaluation(slo_id=definition.slo_id, status="insufficient_data", threshold=definition.threshold, sample_count=len(values), window_start_ms=start, window_end_ms=end))
                continue
            observed = _aggregate(values, definition.aggregation)
            healthy = observed >= definition.threshold if definition.comparator == "gte" else observed <= definition.threshold
            alert = None
            if not healthy:
                alert = _record(kind="alert", name="slo.breached", timestamp_ms=end, status="breached", value=observed, unit="", dimensions={"severity": definition.severity}, payload={"slo_id": definition.slo_id, "metric_name": definition.metric_name, "comparator": definition.comparator, "threshold": definition.threshold, "aggregation": definition.aggregation, "sample_count": len(values)}, identity=(definition.slo_id, end // (definition.window_seconds * 1000)))
                alerts.append(alert)
            evaluations.append(SLOEvaluation(slo_id=definition.slo_id, status="healthy" if healthy else "breached", observed_value=observed, threshold=definition.threshold, sample_count=len(values), window_start_ms=start, window_end_ms=end, alert=alert))
        if persist_alerts and alerts:
            self.store.append_many([item.model_dump() for item in alerts])
        return evaluations

    def enforce_retention(self, *, now_ms: int | None = None) -> int:
        cutoff = int(now_ms or _now_ms()) - max(1, self.config.retention_days) * 86_400_000
        return self.store.delete_before(cutoff)

    def _queue_records(self, run_id: str, series_id: str, item: dict[str, Any], events: list[dict[str, Any]], timestamp_ms: int, queue_depth: int | None) -> list[ObservationRecord]:
        status = str(item.get("status") or "unknown")
        names = [str(event.get("event_type") or "") for event in events]
        first_ms = min([int(event.get("timestamp_ms") or timestamp_ms) for event in events] + [timestamp_ms])
        worker_ms = next((int(event.get("timestamp_ms") or timestamp_ms) for event in events if event.get("event_type") == "worker.started"), first_ms)
        base = {"run_id": run_id, "series_id": series_id, "component": "execution_runtime", "timestamp_ms": timestamp_ms}
        records = [
            _record(kind="event", name="run.completed", status=status, payload={"attempt_count": item.get("attempt_count", 0)}, identity=(run_id, status), **base),
            _metric("run.throughput", 1.0, unit="count", status=status, identity=(run_id,), **base),
            _metric("run.success", 1.0 if status == "succeeded" else 0.0, unit="ratio", status=status, identity=(run_id,), **base),
            _metric("run.duration", max(0, timestamp_ms - first_ms) / 1000, unit="s", status=status, identity=(run_id,), **base),
            _metric("queue.wait", max(0, worker_ms - first_ms) / 1000, unit="s", status=status, identity=(run_id,), **base),
            _metric("queue.retry", float(sum("retry" in name for name in names)), unit="count", status=status, identity=(run_id,), **base),
            _metric("queue.lease_expiry", float(names.count("queue.lease_expired")), unit="count", status=status, identity=(run_id,), **base),
            _metric("queue.dead_letter", 1.0 if status == "dead_letter" else 0.0, unit="count", status=status, identity=(run_id,), **base),
        ]
        if queue_depth is not None:
            records.append(_metric("queue.depth", float(max(0, queue_depth)), unit="count", status=status, identity=(run_id,), **base))
        return records

    def _outcome_records(self, run_id: str, series_id: str, result: dict[str, Any], timestamp_ms: int, lineage_records: list[dict[str, Any]]) -> list[ObservationRecord]:
        records: list[ObservationRecord] = []
        for outcome in list(result.get("outcomes") or []):
            stage = str(outcome.get("stage") or "unknown")
            status = str(outcome.get("status") or "unknown")
            current = next((row for row in reversed(lineage_records) if row.get("run_id") == run_id and row.get("stage") == stage), None)
            mode = str((current or {}).get("execution_mode") or ("reused" if outcome.get("reused") else dict(outcome.get("metadata") or {}).get("execution_mode") or "executed"))
            base = {"run_id": run_id, "series_id": series_id, "component": "production_orchestration", "stage": stage, "timestamp_ms": timestamp_ms, "status": status}
            records.append(_metric("stage.latency", float(outcome.get("elapsed_seconds") or 0), unit="s", dimensions={"execution_mode": mode}, identity=(run_id, stage), **base))
            records.append(_metric("stage.accepted", 1.0 if outcome.get("accepted") else 0.0, unit="ratio", dimensions={"execution_mode": mode}, identity=(run_id, stage), **base))
            records.append(_metric("artifact.reused", 1.0 if mode in {"reused", "adopted"} else 0.0, unit="count", dimensions={"execution_mode": mode}, identity=(run_id, stage), **base))
            prior = any(row.get("run_id") != run_id and row.get("stage") == stage and row.get("status") == "accepted" and (not current or row.get("input_fingerprint") != current.get("input_fingerprint")) for row in lineage_records)
            records.append(_metric("artifact.invalidated", 1.0 if mode == "executed" and prior else 0.0, unit="count", dimensions={"execution_mode": mode}, identity=(run_id, stage), **base))
            for key, value in dict(outcome.get("metrics") or {}).items():
                if key in QUALITY_METRIC_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                    records.append(_metric(f"quality.{stage}.{_safe_name(key)}", float(value), unit="", identity=(run_id, stage, key), **base))
        return records

    def _trace_records(self, run_id: str, series_id: str, trace: dict[str, Any]) -> list[ObservationRecord]:
        completed = int(trace.get("completed_at_ms") or trace.get("started_at_ms") or _now_ms())
        component, provider = str(trace.get("component") or ""), str(trace.get("provider") or "")
        operation, status = str(trace.get("operation") or "operation"), str(trace.get("status") or "")
        trace_id = str(trace.get("trace_id") or "")
        base = {"run_id": str(trace.get("run_id") or run_id), "series_id": series_id, "component": component, "provider": provider, "timestamp_ms": completed, "status": status}
        records = [
            _record(kind="span", name=operation, payload={"trace_id": trace_id, "parent_trace_id": trace.get("parent_trace_id", ""), "started_at_ms": int(trace.get("started_at_ms") or completed), "error_code": trace.get("error_code", "")}, identity=(trace_id,), **base),
            _metric("provider.latency", float(trace.get("latency_ms") or 0), unit="ms", dimensions={"model": dict(trace.get("metadata") or {}).get("model", "")}, identity=(trace_id,), **base),
            _metric("provider.error", 0.0 if status in {"ok", "accepted", "succeeded"} else 1.0, unit="count", identity=(trace_id,), **base),
        ]
        metadata = dict(trace.get("metadata") or {})
        rotation_count = metadata.get("rotation_attempt_count", trace.get("rotation_attempt_count"))
        if rotation_count is not None:
            records.append(_metric("provider.rotation", float(rotation_count or 0), unit="count", identity=(trace_id,), **base))
        cold_start_ms = metadata.get("cold_start_ms", trace.get("cold_start_ms"))
        if cold_start_ms is not None:
            records.append(_metric("provider.cold_start", float(cold_start_ms), unit="ms", identity=(trace_id,), **base))
        records.extend(self._cost_records(trace_id, metadata, base))
        return records

    def _cost_records(self, trace_id: str, metadata: dict[str, Any], base: dict[str, Any]) -> list[ObservationRecord]:
        usage = dict(metadata.get("usage") or {})
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        compute_seconds = usage.get("compute_seconds")
        if input_tokens is None and output_tokens is None and compute_seconds is None:
            return []
        model = str(metadata.get("model") or "")
        rate = next((item for item in self.config.cost_rates if item.provider == base["provider"] and (not item.model or item.model == model)), None)
        records = []
        for name, value in (("usage.input_tokens", input_tokens), ("usage.output_tokens", output_tokens), ("usage.compute_seconds", compute_seconds)):
            if value is not None:
                records.append(_metric(name, float(value), unit="tokens" if "tokens" in name else "s", identity=(trace_id,), **base))
        if rate:
            cost = float(input_tokens or 0) * rate.input_per_million / 1_000_000 + float(output_tokens or 0) * rate.output_per_million / 1_000_000 + float(compute_seconds or 0) * rate.compute_per_second
            records.append(_metric("usage.estimated_cost", cost, unit="usd", dimensions={"model": model}, payload={"estimated": True, "pricing_version": rate.pricing_version}, identity=(trace_id,), **base))
        return records


def _record(*, kind: str, name: str, timestamp_ms: int, identity: tuple[Any, ...], run_id: str = "", series_id: str = "", component: str = "", stage: str = "", provider: str = "", status: str = "", value: float | None = None, unit: str = "", dimensions: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> ObservationRecord:
    return ObservationRecord(observation_id=_stable_id(kind, name, *identity), kind=kind, timestamp_ms=timestamp_ms, run_id=str(run_id)[:160], series_id=str(series_id)[:120], component=str(component)[:120], stage=str(stage)[:120], provider=str(provider)[:120], name=_safe_name(name), status=str(status)[:64], value=value, unit=str(unit)[:32], dimensions=bounded_dimensions(dimensions), payload=sanitize(payload or {}))


def _metric(name: str, value: float, **kwargs: Any) -> ObservationRecord:
    return _record(kind="metric", name=name, value=value, **kwargs)


def _find_traces(value: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    def visit(item: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(item, dict):
            if item.get("trace_id") and item.get("component") and item.get("operation") and ("latency_ms" in item or "started_at_ms" in item):
                found[str(item["trace_id"])] = item
            for child in item.values():
                visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
    visit(value)
    return list(found.values())


def _aggregate(values: list[float], aggregation: str) -> float:
    ordered = sorted(values)
    if aggregation == "sum": return sum(values)
    if aggregation == "min": return min(values)
    if aggregation == "max": return max(values)
    if aggregation == "p95": return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
    return sum(values) / len(values)


def _stable_id(*parts: Any) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"obs-{hashlib.sha256(encoded).hexdigest()[:32]}"


def _safe_name(value: Any) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in str(value or "unknown").lower())[:160]


def _dedupe(records: list[ObservationRecord]) -> list[ObservationRecord]:
    return list({item.observation_id: item for item in records}.values())


def _now_ms() -> int:
    return int(time.time() * 1000)
