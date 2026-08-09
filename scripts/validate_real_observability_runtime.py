"""Validate production observations against an existing Supabase-backed run."""

from __future__ import annotations

import argparse
import json
import os

from packages.observability_runtime import ObservabilityRuntime, ObservabilityRuntimeConfig, SLODefinition
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.persistence_runtime.database_url import build_database_url_from_env
from packages.execution_runtime.service import load_lineage_trace_snapshots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    database_url = build_database_url_from_env()
    if not database_url:
        raise RuntimeError("Supabase database environment is not configured.")
    profile = PersistenceProfile(name="observability-validation", database_url=database_url, application_name="saga-observability-validation")
    persistence = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(
        profile=profile,
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SAGA_SUPABASE_URL") or ""),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or ""),
    ))
    persistence.initialize()
    queue_items = [item for item in persistence.execution_queue.list(limit=10000) if item.get("run_id") == args.run_id]
    if len(queue_items) != 1:
        raise RuntimeError(f"Expected one queue item for run, found {len(queue_items)}.")
    queue_item = queue_items[0]
    events = persistence.execution_queue.list_events(run_id=args.run_id, limit=10000)
    current_lineage = persistence.lineage.list(run_id=args.run_id, limit=1000)
    if not current_lineage:
        raise RuntimeError("No lineage records exist for the selected run.")
    latest_outcomes: dict[str, dict] = {}
    for row in current_lineage:
        outcome = dict(row.get("payload") or {}).get("outcome")
        if isinstance(outcome, dict):
            latest_outcomes[str(row.get("stage") or "")] = outcome
    lineage = list(current_lineage)
    for stage in latest_outcomes:
        lineage.extend(persistence.lineage.list(series_id=queue_item.get("series_id", ""), stage=stage, limit=1000))
    active = {"queued", "retry_wait", "leased", "cancel_requested"}
    queue_depth = sum(1 for item in persistence.execution_queue.list(queue_name=queue_item.get("queue_name"), limit=10000) if item.get("status") in active)

    runtime = ObservabilityRuntime(store=persistence.observability, config=ObservabilityRuntimeConfig(retention_days=args.retention_days))
    observed = runtime.observe_execution(
        run_id=args.run_id, queue_item=queue_item, events=events,
        orchestration_result={"outcomes": list(latest_outcomes.values())}, lineage_records=lineage,
        trace_payloads=load_lineage_trace_snapshots(persistence, current_lineage), queue_depth=queue_depth,
    )
    evaluations = runtime.evaluate_slos(_slos())
    rows = persistence.observability.list(run_id=args.run_id, limit=10000)
    serialized = json.dumps(rows, sort_keys=True)
    exposed = [name for name in ("SAGA_SUPABASE_SERVICE_ROLE_KEY", "SAGA_SUPABASE_DB_PASSWORD") if os.getenv(name) and os.getenv(name) in serialized]
    if exposed:
        raise RuntimeError(f"Secret safety audit failed for environment fields: {', '.join(exposed)}")
    required = {"run.success", "run.duration", "run.throughput", "queue.wait", "queue.depth", "stage.latency", "stage.accepted", "artifact.reused", "artifact.invalidated", "provider.latency", "provider.error"}
    names = {row["name"] for row in rows}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Missing required production observations: {', '.join(missing)}")
    print(json.dumps({
        "run_id": args.run_id,
        "terminal_status": queue_item.get("status"),
        "queue_event_count": len(events),
        "lineage_record_count": len(current_lineage),
        "observed_stage_count": len(latest_outcomes),
        "observation_count": len(rows),
        "metric_names": sorted({row["name"] for row in rows if row["kind"] == "metric"}),
        "slo_statuses": {item.slo_id: item.status for item in evaluations},
        "export_errors": observed["export_errors"],
        "secret_audit": "passed",
    }, indent=2, sort_keys=True))
    return 0


def _slos() -> list[SLODefinition]:
    return [
        SLODefinition(slo_id="run-success-rate", metric_name="run.success", comparator="gte", threshold=0.95, minimum_samples=1, window_seconds=2_592_000),
        SLODefinition(slo_id="queue-wait-p95", metric_name="queue.wait", comparator="lte", threshold=60.0, aggregation="p95", minimum_samples=1, window_seconds=2_592_000),
        SLODefinition(slo_id="dead-letter-free", metric_name="queue.dead_letter", comparator="lte", threshold=0.0, aggregation="sum", minimum_samples=1, window_seconds=2_592_000),
        SLODefinition(slo_id="lease-expiry-free", metric_name="queue.lease_expiry", comparator="lte", threshold=0.0, aggregation="sum", minimum_samples=1, window_seconds=2_592_000),
        SLODefinition(slo_id="stage-acceptance", metric_name="stage.accepted", comparator="gte", threshold=0.95, minimum_samples=1, window_seconds=2_592_000),
        SLODefinition(slo_id="provider-error-rate", metric_name="provider.error", comparator="lte", threshold=0.05, aggregation="average", minimum_samples=1, window_seconds=2_592_000),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
