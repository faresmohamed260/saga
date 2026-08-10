from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packages.observability_runtime import (
    CostRate,
    ObservationBatch,
    ObservationRecord,
    ObservabilityRuntime,
    ObservabilityRuntimeConfig,
    OpenTelemetryJsonExporter,
    OTLPHTTPExporter,
    SLODefinition,
    to_opentelemetry_payload,
)
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.observability_runtime.safety import sanitize


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(name="observability-test", mode="test_harness", database_url=f"sqlite:///{tmp_path / 'observability.sqlite3'}")
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _execution(run_id: str = "run-1", *, status: str = "succeeded"):
    trace = {
        "trace_id": f"trace-{run_id}", "run_id": run_id, "component": "reasoning_runtime", "operation": "complete",
        "provider": "general_compute", "status": "ok", "started_at_ms": 1200, "completed_at_ms": 1800,
        "latency_ms": 600, "metadata": {"model": "model-a", "rotation_attempt_count": 1, "cold_start_ms": 90,
        "usage": {"input_tokens": 1000, "output_tokens": 500}, "api_token": "must-not-persist"},
    }
    result = {"outcomes": [{"stage": "narrative_generation", "status": "accepted", "accepted": True, "reused": False,
        "elapsed_seconds": 2.5, "metrics": {"continuity": 0.98}, "metadata": {"provider_trace": trace}}]}
    item = {"run_id": run_id, "series_id": "series-1", "status": status, "attempt_count": 1, "queue_name": "q",
            "payload": {"orchestration_request": {"run_id": run_id, "series_id": "series-1", "password": "must-not-persist"}}}
    events = [
        {"event_type": "queue.enqueued", "timestamp_ms": 1000},
        {"event_type": "worker.started", "timestamp_ms": 1100},
        {"event_type": "worker.finished", "timestamp_ms": 2000},
    ]
    lineage = [
        {"run_id": "older", "stage": "narrative_generation", "status": "accepted", "input_fingerprint": "old"},
        {"run_id": run_id, "stage": "narrative_generation", "status": "accepted", "input_fingerprint": "new"},
    ]
    return item, events, result, lineage


def test_execution_observation_is_idempotent_complete_and_secret_safe(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = ObservabilityRuntime(store=client.observability, config=ObservabilityRuntimeConfig(cost_rates=(CostRate(
        provider="general_compute", model="model-a", input_per_million=1.0, output_per_million=2.0, pricing_version="2026-08",
    ),)))
    item, events, result, lineage = _execution()
    first = runtime.observe_execution(run_id="run-1", queue_item=item, events=events, orchestration_result=result, lineage_records=lineage, queue_depth=3)
    second = runtime.observe_execution(run_id="run-1", queue_item=item, events=events, orchestration_result=result, lineage_records=lineage, queue_depth=3)
    rows = client.observability.list(run_id="run-1", limit=1000)
    names = {row["name"] for row in rows}

    assert first["record_count"] == second["record_count"] == len(rows)
    assert {"run.success", "run.throughput", "queue.depth", "stage.latency", "stage.accepted", "artifact.invalidated",
            "provider.latency", "provider.rotation", "provider.cold_start", "usage.estimated_cost"} <= names
    assert next(row for row in rows if row["name"] == "artifact.invalidated")["value"] == 1.0
    assert next(row for row in rows if row["name"] == "usage.estimated_cost")["value"] == 0.002
    serialized = json.dumps(rows)
    assert "must-not-persist" not in serialized
    assert sanitize({"nested": {"api_token": "must-not-persist"}})["nested"]["api_token"] == "<redacted>"
    assert sanitize({"usage": {"input_tokens": 12}})["usage"]["input_tokens"] == 12


def test_redacted_or_malformed_usage_does_not_drop_execution_observations(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = ObservabilityRuntime(store=client.observability)
    item, events, result, lineage = _execution()
    usage = result["outcomes"][0]["metadata"]["provider_trace"]["metadata"]["usage"]
    usage.update({"input_tokens": "<redacted>", "output_tokens": "not-a-number"})

    observed = runtime.observe_execution(
        run_id="run-1",
        queue_item=item,
        events=events,
        orchestration_result=result,
        lineage_records=lineage,
    )

    assert observed["record_count"] > 0
    names = {row["name"] for row in client.observability.list(run_id="run-1", limit=1000)}
    assert {"run.success", "stage.accepted", "provider.latency"} <= names
    assert "usage.input_tokens" not in names


def test_slo_aggregation_breach_alert_and_retention_are_deterministic(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = ObservabilityRuntime(store=client.observability, config=ObservabilityRuntimeConfig(retention_days=1))
    for index, value in enumerate([1.0, 0.0, 0.0, 1.0]):
        client.observability.append({"observation_id": f"metric-{index}", "kind": "metric", "timestamp_ms": 9_000 + index,
            "run_id": f"run-{index}", "name": "run.success", "value": value, "dimensions": {}, "payload": {}})
    definition = SLODefinition(slo_id="success", metric_name="run.success", comparator="gte", threshold=0.95, minimum_samples=4, window_seconds=10)
    first = runtime.evaluate_slos([definition], now_ms=10_000)[0]
    second = runtime.evaluate_slos([definition], now_ms=10_000)[0]
    assert first.status == "breached" and first.observed_value == 0.5
    assert first.alert.observation_id == second.alert.observation_id
    assert len(client.observability.list(kind="alert")) == 1
    assert runtime.enforce_retention(now_ms=86_410_000) == 4


def test_slo_evaluation_can_be_scoped_to_an_explicit_release_cohort(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = ObservabilityRuntime(store=client.observability)
    for run_id, value in (("candidate-run", 1.0), ("other-release-run", 0.0)):
        client.observability.append({
            "observation_id": f"success-{run_id}",
            "kind": "metric",
            "timestamp_ms": 9_500,
            "run_id": run_id,
            "name": "run.success",
            "value": value,
            "dimensions": {},
            "payload": {},
        })
    definition = SLODefinition(
        slo_id="candidate-success",
        metric_name="run.success",
        comparator="gte",
        threshold=1.0,
        minimum_samples=1,
        window_seconds=10,
    )

    global_evaluation = runtime.evaluate_slos([definition], now_ms=10_000, persist_alerts=False)[0]
    candidate_evaluation = runtime.evaluate_slos(
        [definition], now_ms=10_000, persist_alerts=False, run_ids={"candidate-run"}
    )[0]

    assert global_evaluation.status == "breached"
    assert candidate_evaluation.status == "healthy"
    assert candidate_evaluation.sample_count == 1


def test_exporter_failure_is_isolated_and_otel_mapping_is_portable(tmp_path: Path):
    client = _persistence(tmp_path)
    class FailingExporter:
        def export(self, batch):
            raise ConnectionError(f"sink unavailable for {batch.batch_id}")
    runtime = ObservabilityRuntime(store=client.observability, exporters=[FailingExporter()])
    item, events, result, lineage = _execution()
    observed = runtime.observe_execution(run_id="run-1", queue_item=item, events=events, orchestration_result=result, lineage_records=lineage)
    assert observed["record_count"] > 0
    assert observed["export_errors"][0]["exception_type"] == "ConnectionError"

    batch = ObservationBatch(batch_id="b", records=[ObservationRecord(
        observation_id="m", kind="metric", timestamp_ms=1, name="queue.depth", value=2, unit="count", component="execution_runtime",
    )])
    payload = to_opentelemetry_payload(batch)
    assert payload["resourceMetrics"][0]["attributes"]["service.name"] == "execution_runtime"
    sent = []
    assert OpenTelemetryJsonExporter(lambda body: sent.append(body) or {"ok": True}).export(batch)["ok"] is True
    assert sent == [payload]


def test_otlp_http_exporter_routes_standard_signal_payloads():
    calls = []
    class Response:
        def raise_for_status(self): pass
    class Session:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()
    records = [
        ObservationRecord(observation_id="m", kind="metric", timestamp_ms=1, name="queue.depth", value=2, component="execution_runtime"),
        ObservationRecord(observation_id="s", kind="span", timestamp_ms=2, name="reason", status="ok", component="reasoning_runtime", payload={"trace_id": "trace"}),
        ObservationRecord(observation_id="a", kind="alert", timestamp_ms=3, name="slo.breached", status="breached"),
    ]
    result = OTLPHTTPExporter("http://collector:4318", session=Session()).export(ObservationBatch(batch_id="b", records=records))
    assert result["delivered"] == {"metrics": 1, "traces": 1, "logs": 1}
    assert [item[0] for item in calls] == ["http://collector:4318/v1/metrics", "http://collector:4318/v1/traces", "http://collector:4318/v1/logs"]
    assert "resourceMetrics" in calls[0][1]["json"]
    assert "resourceSpans" in calls[1][1]["json"]
    assert "resourceLogs" in calls[2][1]["json"]


def test_concurrent_duplicate_observations_do_not_duplicate_rows(tmp_path: Path):
    client = _persistence(tmp_path)
    record = {"observation_id": "same", "kind": "metric", "timestamp_ms": 1, "name": "queue.depth", "value": 1, "dimensions": {}, "payload": {}}
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: client.observability.append(record), range(8)))
    assert len(client.observability.list(name="queue.depth")) == 1


def test_cardinality_guard_drops_unbounded_dimensions(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = ObservabilityRuntime(store=client.observability)
    item, events, result, lineage = _execution()
    result["outcomes"][0]["metadata"]["provider_trace"]["metadata"]["request_id"] = "unbounded"
    result["outcomes"][0]["metrics"]["user_supplied_metric_name"] = 1.0
    runtime.observe_execution(run_id="run-1", queue_item=item, events=events, orchestration_result=result, lineage_records=lineage)
    provider_metric = next(row for row in client.observability.list(name="provider.latency"))
    assert "request_id" not in provider_metric["dimensions"]
    assert not client.observability.list(name="quality.narrative_generation.user_supplied_metric_name")
