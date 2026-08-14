"""Run one bounded, fresh raw-book-to-deliverable production qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path

from packages.execution_runtime import ExecutionRuntimeService
from packages.generation_planning import (
    GenerationPlanningService,
    load_generation_planning_service_config_from_env,
)
from packages.production_orchestration import (
    OrchestrationExecutionLimits,
    OrchestrationRequest,
)

ALL_STAGES = [
    "analysis_foundation",
    "canon_extraction",
    "character_world_modeling",
    "generation_planning",
    "narrative_generation",
    "narrative_support",
    "visual_generation",
    "audiobook_generation",
    "artifact_packaging",
]
GENERATION_STAGES = {"narrative_generation", "visual_generation", "audiobook_generation"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    parser.add_argument("--stage-timeout-seconds", type=int, default=900)
    parser.add_argument("--generation-stage-timeout-seconds", type=int, default=900)
    parser.add_argument("--preflight-timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--visual-max-attempts", type=int, choices=range(1, 7), default=2
    )
    parser.add_argument("--max-attempts", type=int, choices=range(2, 7), default=4)
    parser.add_argument("--retry-backoff-seconds", type=int, default=30)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--series-id", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-stage", choices=ALL_STAGES, default="artifact_packaging")
    args = parser.parse_args()
    if args.resume:
        os.environ["SAGA_CANON_RESUME_STAGES"] = (
            "chapter_canon_extraction"
        )

    source = Path(args.source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    suffix = uuid.uuid4().hex[:10]
    run_id = args.run_id or f"qualification-{suffix}"
    series_id = args.series_id or f"qualification-series-{suffix}"
    os.environ["SAGA_EXECUTION_QUEUE_NAME"] = _qualification_queue_name(run_id)
    service = ExecutionRuntimeService.from_env()
    try:
        _freshness_guard(
            service,
            source=source,
            source_sha256=source_sha256,
            series_id=series_id,
            allow_resume=args.resume,
        )
        if _requires_generation_preflight(args.stop_after_stage):
            _reasoning_preflight(timeout_seconds=args.preflight_timeout_seconds)
        request = OrchestrationRequest(
            run_id=run_id,
            series_id=series_id,
            project_id=f"qualification-project-{args.release_id}",
            source_paths=[str(source)],
            premise="During the first winter after the war, a court archivist discovers that a disputed Solstice oath could reopen an old alliance or destroy the fragile peace.",
            target_audience="adult fantasy readers",
            tone="intimate, wintry, politically tense, and hopeful",
            desired_chapter_count=1,
            selected_stages=[args.stop_after_stage],
            include_visuals=args.stop_after_stage in {"visual_generation", "artifact_packaging"},
            include_audiobook=args.stop_after_stage in {"audiobook_generation", "artifact_packaging"},
            max_attempts=args.max_attempts,
            execution_limits=OrchestrationExecutionLimits(
                target_words_per_scene=100,
                visual_include_types=[
                    "character",
                    "location",
                    "creature",
                    "object",
                    "scene",
                ],
                max_visual_renders_per_type=1,
                max_visual_attempts=args.visual_max_attempts,
                audiobook_max_chapters=1,
                audiobook_max_segment_chars=900,
                provider_request_limits={
                    "analysis_foundation": {"modal": 1},
                    "canon_extraction": {
                        _reasoning_budget_provider(
                            os.getenv("SAGA_CANON_EXTRACTION_REASONING_MODE", "gpt_oss")
                        ): 40
                    },
                },
            ),
            metadata={
                "validation_kind": "fresh_production_qualification",
                "source_title": source.stem,
                "source_sha256": source_sha256,
                "release_id": args.release_id,
                "freshness_required": True,
            },
        )
        queued = service.submit(
            request,
            max_attempts=args.max_attempts,
            backoff_seconds=max(1, args.retry_backoff_seconds),
        )
        if (
            args.resume
            and queued
            and queued.get("status") in {"cancelled", "dead_letter"}
        ):
            queued = service.retry(
                request,
                max_attempts=args.max_attempts,
                backoff_seconds=max(1, args.retry_backoff_seconds),
            )
        if queued is None:
            raise RuntimeError("Qualification queue submission did not return an item.")
        queue_id = str(queued["queue_id"])
        _emit(
            "submitted",
            run_id=run_id,
            series_id=series_id,
            queue_id=queue_id,
            source_sha256=source_sha256,
        )
        historical_logs = (
            list((service.persistence.jobs.get_job(run_id) or {}).get("logs") or [])
            if args.resume
            else []
        )
        started = time.monotonic()
        deadline = started + max(60, args.timeout_seconds)
        current_stage = _resume_stage(historical_logs)
        stage_started = started
        cancellation_reason = ""
        cancellation_requested = False
        seen_logs = {int(log.get("id") or 0) for log in historical_logs}
        worker_result = None
        while time.monotonic() < deadline:
            outcome: dict[str, object] = {}

            def work() -> None:
                try:
                    outcome["result"] = service.run_worker_once(
                        worker_id=f"qualification-worker-{suffix}"
                    )
                except BaseException as exc:  # noqa: BLE001
                    outcome["error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc)[:1000],
                    }

            worker = threading.Thread(
                target=work, name=f"qualification-{suffix}", daemon=True
            )
            worker.start()
            while worker.is_alive() and time.monotonic() < deadline:
                job = service.persistence.jobs.get_job(run_id) or {}
                for log in job.get("logs") or []:
                    log_id = int(log.get("id") or 0)
                    if log_id in seen_logs:
                        continue
                    seen_logs.add(log_id)
                    stage = str(log.get("stage") or "")
                    message = str(log.get("message") or "")
                    if message == "stage_accepted" and stage in ALL_STAGES:
                        stage_index = ALL_STAGES.index(stage)
                        current_stage = (
                            ALL_STAGES[stage_index + 1]
                            if stage_index + 1 < len(ALL_STAGES)
                            else ""
                        )
                        stage_started = time.monotonic()
                    elif stage and stage != "orchestration" and stage != current_stage:
                        current_stage, stage_started = stage, time.monotonic()
                    _emit(
                        "stage_event",
                        stage=stage,
                        message=log.get("message"),
                        elapsed_seconds=round(time.monotonic() - started, 1),
                    )
                if current_stage and time.monotonic() - stage_started > _stage_timeout_seconds(
                    current_stage,
                    standard_timeout_seconds=args.stage_timeout_seconds,
                    generation_timeout_seconds=args.generation_stage_timeout_seconds,
                ):
                    cancellation_reason = f"Stage deadline exceeded: {current_stage}"
                    cancellation_requested = _request_cancellation(
                        service,
                        queue_id=queue_id,
                        reason=cancellation_reason,
                        already_requested=cancellation_requested,
                    )
                    _emit(
                        "stage_deadline",
                        stage=current_stage,
                        elapsed_seconds=round(time.monotonic() - stage_started, 1),
                    )
                    break
                worker.join(timeout=2.0)
            if worker.is_alive():
                cancellation_reason = cancellation_reason or "Qualification global deadline exceeded."
                cancellation_requested = _request_cancellation(
                    service, queue_id=queue_id, reason=cancellation_reason,
                    already_requested=cancellation_requested,
                )
                _emit("deadline", reason=cancellation_reason, elapsed_seconds=round(time.monotonic() - started, 1))
                worker.join(timeout=30.0)
                if worker.is_alive():
                    _emit("cancellation_drain_timeout", queue_id=queue_id, wait_seconds=30)
                return 3
            if "error" in outcome:
                _emit("worker_error", **dict(outcome["error"]))
                return 2
            worker_result = outcome["result"]
            if worker_result.status != "retry_wait":
                break
            retry_at_ms = int((worker_result.queue_item or {}).get("available_at_ms") or 0)
            wait_seconds = max(1.0, min(120.0, retry_at_ms / 1000 - time.time()))
            _emit(
                "worker_retry_wait",
                attempt=(worker_result.queue_item or {}).get("attempt_count"),
                wait_seconds=round(wait_seconds, 1),
            )
            while time.monotonic() < deadline and wait_seconds > 0:
                sleep_for = min(2.0, wait_seconds)
                time.sleep(sleep_for)
                wait_seconds -= sleep_for
        if worker_result is None:
            _emit("worker_terminal", status="deadline", error={"message": "No worker result before deadline."})
            return 3
        if worker_result.orchestration_result is None:
            _emit(
                "worker_terminal",
                status=worker_result.status,
                error=worker_result.error,
            )
            return 2
        if not worker_result.orchestration_result.decision.accepted:
            _emit(
                "orchestration_terminal",
                status=worker_result.orchestration_result.decision.status,
                reasons=worker_result.orchestration_result.decision.reasons,
                worker_status=worker_result.status,
            )
            return (
                3
                if worker_result.orchestration_result.decision.status == "cancelled"
                else 2
            )
        if args.stop_after_stage != "artifact_packaging":
            slice_report = _build_stage_slice_report(
                result=worker_result.orchestration_result,
                source=source,
                source_sha256=source_sha256,
                release_id=args.release_id,
                elapsed_seconds=round(time.monotonic() - started, 1),
            )
            stored = service.persistence.artifacts.store_json(
                artifact_type="runtime_report",
                filename=f"{run_id}-{args.stop_after_stage}-qualification.json",
                payload=slice_report,
                provider_name="qualification_runtime",
                report_kind="production_stage_slice",
                series_id=series_id,
                run_id=run_id,
                metadata={
                    "accepted": True,
                    "release_id": args.release_id,
                    "stop_after_stage": args.stop_after_stage,
                },
            )
            slice_report["artifact_reference"] = stored
            if args.report:
                report_path = Path(args.report).resolve()
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps(slice_report, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
            _emit(
                "stage_slice_complete",
                accepted=True,
                run_id=run_id,
                series_id=series_id,
                stop_after_stage=args.stop_after_stage,
                elapsed_seconds=slice_report["metrics"]["elapsed_seconds"],
                stage_seconds=slice_report["metrics"]["stage_seconds"],
                report_artifact=stored,
            )
            return 0
        from packages.qualification_runtime import ProductionQualificationEvaluator

        evaluator = ProductionQualificationEvaluator(persistence=service.persistence)
        report = evaluator.evaluate(
            result=worker_result.orchestration_result,
            source_path=str(source),
            expected_source_sha256=source_sha256,
            expected_release_id=args.release_id,
        )
        report = evaluator.persist(report)
        if args.report:
            report_path = Path(args.report).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        failed = [
            item.model_dump() for item in report.checks if item.status != "passed"
        ]
        _emit(
            "qualification_complete",
            accepted=report.accepted,
            run_id=run_id,
            series_id=series_id,
            elapsed_seconds=round(time.monotonic() - started, 1),
            failed_checks=failed,
            metrics=report.metrics,
            report_artifact=report.artifact_reference,
        )
        return 0 if report.accepted else 2
    finally:
        service.persistence.close()


def _freshness_guard(
    service: ExecutionRuntimeService,
    *,
    source: Path,
    source_sha256: str,
    series_id: str,
    allow_resume: bool,
) -> None:
    existing_series = next(
        (
            item
            for item in service.persistence.library.list_series(limit=10000)
            if item.get("series_id") == series_id
        ),
        None,
    )
    existing_books = service.persistence.library.list_books(limit=10000)
    source_name = source.name.casefold()
    matching_sources = [
        item
        for item in existing_books
        if source_name in str(item.get("source_uri") or "").casefold()
        or source_sha256 in json.dumps(item, sort_keys=True)
    ]
    if not allow_resume and (existing_series is not None or matching_sources):
        raise RuntimeError(
            f"Freshness guard rejected existing input/state: series={existing_series is not None}, source_matches={len(matching_sources)}"
        )


def _request_cancellation(
    service: ExecutionRuntimeService,
    *,
    queue_id: str,
    reason: str,
    already_requested: bool,
) -> bool:
    if already_requested:
        return True
    service.cancel(queue_id, reason=reason)
    return True


def _resume_stage(logs: list[dict[str, object]]) -> str:
    current_stage = ALL_STAGES[0]
    for log in logs:
        stage = str(log.get("stage") or "")
        message = str(log.get("message") or "")
        if stage not in ALL_STAGES:
            continue
        if message == "stage_accepted":
            index = ALL_STAGES.index(stage) + 1
            current_stage = ALL_STAGES[index] if index < len(ALL_STAGES) else ""
        elif message in {"stage_cancelled", "stage_failed", "stage_rejected"}:
            current_stage = stage
    return current_stage


def _stage_timeout_seconds(
    stage: str,
    *,
    standard_timeout_seconds: int,
    generation_timeout_seconds: int,
) -> int:
    configured = (
        generation_timeout_seconds if stage in GENERATION_STAGES else standard_timeout_seconds
    )
    return max(60, int(configured))


def _requires_generation_preflight(stop_after_stage: str) -> bool:
    return ALL_STAGES.index(stop_after_stage) >= ALL_STAGES.index("generation_planning")


def _reasoning_budget_provider(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"ollama_local", "lm_studio_local", "mistral", "gemini", "general_compute"}:
        return normalized
    if normalized in {"gpt_oss", "deepseek"}:
        return "ollama"
    raise ValueError(f"Unsupported reasoning mode for provider budgeting: {mode!r}")


def _build_stage_slice_report(
    *,
    result,
    source: Path,
    source_sha256: str,
    release_id: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "report_id": f"qualification-{result.request.run_id}-{result.request.selected_stages[-1]}",
        "run_id": result.request.run_id,
        "series_id": result.request.series_id,
        "source_path": str(source),
        "source_sha256": source_sha256,
        "release_id": release_id,
        "accepted": result.decision.accepted,
        "completed_stages": list(result.decision.completed_stages),
        "metrics": {
            "elapsed_seconds": elapsed_seconds,
            "stage_seconds": {
                item.stage: float(item.elapsed_seconds or 0.0) for item in result.outcomes
            },
        },
        "result": result.model_dump(),
    }


def _qualification_queue_name(run_id: str) -> str:
    normalized = "".join(char if char.isalnum() or char in "-_" else "-" for char in str(run_id or "").strip())
    if not normalized:
        raise ValueError("run_id is required to isolate the qualification queue.")
    return f"production-qualification-{normalized}"[:180]


def _reasoning_preflight(*, timeout_seconds: int) -> None:
    config = replace(
        load_generation_planning_service_config_from_env(),
        reasoning_timeout_seconds=max(30, int(timeout_seconds)),
        reasoning_max_retries=1,
    )
    service = GenerationPlanningService(config=config)
    try:
        response = service.runtime.reasoning_runtime.generate_text(
            "Reply with exactly QUALIFICATION_READY.",
            system_prompt="You are a production readiness probe. Follow the output instruction exactly.",
            temperature=0.0,
            max_tokens=128,
        )
        if "QUALIFICATION_READY" not in str(response or "").upper():
            raise RuntimeError(
                "Reasoning provider preflight returned an unexpected response."
            )
        metadata = service.runtime.reasoning_runtime.last_request_metadata()
        _emit(
            "reasoning_preflight",
            provider=service.runtime.reasoning_runtime.provider_name(),
            model=service.runtime.reasoning_runtime.resolved_model_name(),
            status=metadata.get("status")
            if isinstance(metadata, dict)
            else getattr(metadata, "status", ""),
        )
    finally:
        service.persistence.close()


def _emit(event: str, **payload: object) -> None:
    print(
        json.dumps(
            {"event": event, **payload}, ensure_ascii=False, sort_keys=True, default=str
        ),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
