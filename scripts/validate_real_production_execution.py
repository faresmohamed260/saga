from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from pathlib import Path

from packages.execution_runtime import ExecutionRuntimeService
from packages.production_orchestration import OrchestrationExecutionLimits, OrchestrationRequest


def _emit(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded real-book job through the durable production worker.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--series-id", default="")
    parser.add_argument(
        "--premise",
        default="A faerie courier must return a stolen memory before dawn without betraying the rival who saved her.",
    )
    parser.add_argument("--target-words-per-scene", type=int, default=100)
    parser.add_argument("--visual-type", default="object")
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    suffix = uuid.uuid4().hex[:10]
    run_id = args.run_id or f"real-production-{suffix}"
    series_id = args.series_id or f"real-production-series-{suffix}"
    request = OrchestrationRequest(
        run_id=run_id,
        series_id=series_id,
        project_id=f"validation-project-{suffix}",
        source_paths=[str(source)],
        premise=args.premise,
        target_audience="young adult fantasy readers",
        tone="tense, lyrical, emotionally precise",
        desired_chapter_count=1,
        selected_stages=["visual_generation", "audiobook_generation", "artifact_packaging"],
        include_visuals=True,
        include_audiobook=True,
        max_attempts=2 if args.retry else 1,
        execution_limits=OrchestrationExecutionLimits(
            target_words_per_scene=args.target_words_per_scene,
            visual_include_types=[args.visual_type],
            max_visual_renders_per_type=1,
            audiobook_max_chapters=1,
            audiobook_max_segment_chars=900,
        ),
        metadata={"validation_kind": "lineage_input_invalidation", "source_title": source.stem},
    )

    service = ExecutionRuntimeService.from_env()
    queued = service.retry(request, max_attempts=1) if args.retry else service.submit(request, max_attempts=1, backoff_seconds=0)
    if queued is None:
        raise RuntimeError(f"Queue item for run '{run_id}' was not found.")
    queue_id = str(queued["queue_id"])
    _emit("submitted", queue_id=queue_id, run_id=run_id, series_id=series_id, source=str(source))

    outcome: dict[str, object] = {}

    def work() -> None:
        try:
            outcome["result"] = service.run_worker_once(worker_id=f"real-validation-{suffix}")
        except BaseException as exc:  # noqa: BLE001
            outcome["error"] = {"type": type(exc).__name__, "message": str(exc)}

    worker = threading.Thread(target=work, name=f"real-validation-{suffix}", daemon=True)
    worker.start()
    deadline = time.monotonic() + max(60, args.timeout_seconds)
    seen_logs: set[int] = set()
    last_status = ""
    started = time.monotonic()
    while worker.is_alive() and time.monotonic() < deadline:
        item = service.queue.get(queue_id) or {}
        status = str(item.get("status") or "missing")
        if status != last_status:
            _emit("queue_status", status=status, elapsed_seconds=round(time.monotonic() - started, 1))
            last_status = status
        job = service.persistence.jobs.get_job(run_id) or {}
        for log in job.get("logs") or []:
            log_id = int(log.get("id") or 0)
            if log_id in seen_logs:
                continue
            seen_logs.add(log_id)
            _emit(
                "stage_transition",
                stage=log.get("stage"),
                message=log.get("message"),
                status=dict(log.get("payload") or {}).get("status", ""),
                elapsed_seconds=round(time.monotonic() - started, 1),
            )
        worker.join(timeout=max(0.2, args.poll_seconds))

    if worker.is_alive():
        service.cancel(queue_id, reason=f"Validation deadline exceeded ({args.timeout_seconds}s).")
        _emit("deadline_exceeded", elapsed_seconds=round(time.monotonic() - started, 1), queue_id=queue_id)
        return 3
    if "error" in outcome:
        _emit("worker_error", **dict(outcome["error"]))
        return 2

    result = outcome["result"]
    orchestration = result.orchestration_result
    _emit(
        "completed",
        worker_status=result.status,
        elapsed_seconds=round(time.monotonic() - started, 1),
        decision=orchestration.decision.model_dump() if orchestration else None,
        stages=[
            {
                "stage": item.stage,
                "status": item.status,
                "reused": item.reused,
                "elapsed_seconds": item.elapsed_seconds,
                "metrics": item.metrics,
                "lineage_mode": dict((item.metadata or {}).get("lineage") or {}).get("execution_mode", ""),
                "lineage_fingerprint": dict((item.metadata or {}).get("lineage") or {}).get("lineage_fingerprint", ""),
            }
            for item in (orchestration.outcomes if orchestration else [])
        ],
        manifest=orchestration.manifest.model_dump() if orchestration and orchestration.manifest else None,
        telemetry_export=result.telemetry_export,
    )
    return 0 if result.status == "succeeded" and orchestration and orchestration.decision.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
