"""Independently scalable deployment process roles."""

from __future__ import annotations

import hashlib
import argparse
import logging
import os
import socket
import threading
import time
from typing import Any

from packages.deployment_runtime.contracts import ProcessTickResult
from packages.execution_runtime import ExecutionRuntimeService, default_execution_slos
from packages.observability_runtime import OTLPHTTPExporter, ObservationBatch, ObservationRecord, ObservabilityRuntime, ObservabilityRuntimeConfig


logger = logging.getLogger(__name__)


def scheduler_tick(service: ExecutionRuntimeService, *, process_id: str = "", release_id: str = "", now_ms: int | None = None) -> ProcessTickResult:
    timestamp = int(now_ms or time.time() * 1000)
    recovered = service.queue.recover(now_ms=timestamp)
    active = {"queued", "retry_wait", "leased", "cancel_requested"}
    items = service.queue.list(limit=10000)
    depth = sum(1 for item in items if item.get("status") in active)
    observation = ObservationRecord(
        observation_id=f"obs-{hashlib.sha256(f'queue-depth:{service.config.queue_name}:{timestamp // 10000}'.encode()).hexdigest()[:32]}",
        kind="metric", timestamp_ms=timestamp, component="execution_runtime", name="queue.depth", value=float(depth), unit="count",
        dimensions={"queue_name": service.config.queue_name}, payload={},
    )
    runtime = _observability(service)
    exported = runtime.record_batch(ObservationBatch(batch_id=observation.observation_id, records=[observation]))
    _heartbeat(service.persistence, process_id or _process_id("scheduler"), "scheduler", release_id, "ready", timestamp, {"queue_depth": depth, "recovered": len(recovered)})
    return ProcessTickResult(role="scheduler", status="ok", release_id=release_id, details={"queue_depth": depth, "recovered": len(recovered), "export_errors": exported["export_errors"]})


def observability_tick(service: ExecutionRuntimeService, *, process_id: str = "", release_id: str = "", now_ms: int | None = None) -> ProcessTickResult:
    timestamp = int(now_ms or time.time() * 1000)
    runtime = _observability(service)
    removed = runtime.enforce_retention(now_ms=timestamp)
    evaluations = runtime.evaluate_slos(default_execution_slos(), now_ms=timestamp)
    alerts = [item.alert for item in evaluations if item.alert is not None]
    exported = runtime.record_batch(ObservationBatch(batch_id=f"alerts-{timestamp}", records=alerts)) if alerts else {"export_errors": []}
    details = {"retention_removed": removed, "slo_breaches": len(alerts), "export_errors": exported["export_errors"]}
    _heartbeat(service.persistence, process_id or _process_id("observability"), "observability", release_id, "ready", timestamp, details)
    return ProcessTickResult(role="observability", status="ok", release_id=release_id, details=details)


def scheduler_main() -> None:
    _loop("scheduler", lambda service, pid, release: scheduler_tick(service, process_id=pid, release_id=release))


def observability_main() -> None:
    _loop("observability", lambda service, pid, release: observability_tick(service, process_id=pid, release_id=release), default_interval=60.0)


def worker_main() -> None:
    service = ExecutionRuntimeService.from_env()
    process_id, release_id = _process_id("worker"), str(os.getenv("SAGA_RELEASE_ID") or "")
    interval = max(0.2, float(os.getenv("SAGA_WORKER_POLL_SECONDS") or "2"))
    heartbeat_interval = max(5.0, float(os.getenv("SAGA_WORKER_HEARTBEAT_SECONDS") or "30"))
    stop = threading.Event()
    _heartbeat(service.persistence, process_id, "worker", release_id, "ready", int(time.time() * 1000), {"state": "starting"})
    heartbeat_thread = threading.Thread(
        target=_worker_heartbeat_loop,
        args=(service.persistence, process_id, release_id, stop, heartbeat_interval),
        name="worker-process-heartbeat",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        while True:
            result = service.run_worker_once(worker_id=process_id)
            _heartbeat(service.persistence, process_id, "worker", release_id, "ready", int(time.time() * 1000), {"last_status": result.status})
            if result.status == "idle":
                time.sleep(interval)
    finally:
        stop.set()
        heartbeat_thread.join(timeout=heartbeat_interval + 1)


def _worker_heartbeat_loop(persistence, process_id: str, release_id: str, stop: threading.Event, interval: float) -> None:
    while not stop.wait(max(0.01, interval)):
        try:
            _heartbeat(
                persistence,
                process_id,
                "worker",
                release_id,
                "ready",
                int(time.time() * 1000),
                {"state": "running"},
            )
        except Exception:
            logger.exception("Worker process heartbeat failed")


def _loop(role: str, tick, *, default_interval: float = 10.0) -> None:
    service = ExecutionRuntimeService.from_env()
    process_id, release_id = _process_id(role), str(os.getenv("SAGA_RELEASE_ID") or "")
    interval = max(1.0, float(os.getenv(f"SAGA_{role.upper()}_INTERVAL_SECONDS") or default_interval))
    while True:
        tick(service, process_id, release_id)
        time.sleep(interval)


def _heartbeat(persistence, process_id: str, role: str, release_id: str, status: str, timestamp: int, metadata: dict[str, Any]) -> None:
    persistence.deployments.heartbeat({"process_id": process_id, "role": role, "release_id": release_id, "status": status, "last_seen_ms": timestamp, "metadata": metadata})


def _observability(service: ExecutionRuntimeService) -> ObservabilityRuntime:
    endpoint = str(service.config.otlp_http_endpoint or "").strip()
    return ObservabilityRuntime(
        store=service.persistence.observability,
        exporters=[OTLPHTTPExporter(endpoint)] if endpoint else [],
        config=ObservabilityRuntimeConfig(retention_days=service.config.observability_retention_days),
    )


def _process_id(role: str) -> str:
    return f"{role}-{socket.gethostname()}-{os.getpid()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one S.A.G.A. production process role.")
    parser.add_argument("role", choices=("worker", "scheduler", "observability"))
    parser.add_argument("--once", action="store_true", help="Run one bounded tick for deployment validation.")
    args = parser.parse_args()
    role = args.role
    if args.once:
        service = ExecutionRuntimeService.from_env()
        process_id, release_id = _process_id(role), str(os.getenv("SAGA_RELEASE_ID") or "")
        if role == "worker":
            result = service.run_worker_once(worker_id=process_id)
            _heartbeat(service.persistence, process_id, role, release_id, "ready", int(time.time() * 1000), {"last_status": result.status})
        else:
            result = {"scheduler": scheduler_tick, "observability": observability_tick}[role](service, process_id=process_id, release_id=release_id)
        print(result.model_dump_json())
        return
    {"worker": worker_main, "scheduler": scheduler_main, "observability": observability_main}[role]()


if __name__ == "__main__":
    main()
