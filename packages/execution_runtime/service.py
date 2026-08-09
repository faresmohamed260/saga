"""Production composition root for durable orchestration execution."""

from __future__ import annotations

import json
import os
import socket
import uuid
from dataclasses import dataclass, field
from typing import Any

from packages.agent_runtime import SqlCheckpointSaver
from packages.execution_runtime.contracts import (
    ExecutionQueuePolicy,
    ExecutionSubmission,
    WorkerExecutionResult,
)
from packages.execution_runtime.queue import ExecutionQueueRuntime, queue_id_for_run
from packages.execution_runtime.worker import ExecutionWorker
from packages.observability_runtime import (
    CostRate,
    ObservabilityRuntime,
    ObservabilityRuntimeConfig,
    OTLPHTTPExporter,
    SLODefinition,
)
from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    create_persistence_client,
)
from packages.production_orchestration import (
    OrchestrationRequest,
    ProductionOrchestrationService,
    ProductionOrchestrationServiceConfig,
)


@dataclass(frozen=True)
class ExecutionRuntimeServiceConfig:
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    lineage_version_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    queue_name: str = "production-orchestration"
    lease_seconds: int = 180
    global_limit: int = 2
    per_series_limit: int = 1
    default_capability_limit: int = 2
    observability_retention_days: int = 30
    otlp_http_endpoint: str = ""
    usage_cost_rates: tuple[CostRate, ...] = field(default_factory=tuple)
    release_id: str = ""
    capability_limits: dict[str, int] = field(
        default_factory=lambda: {
            "modal_coreference": 1,
            "modal_image": 1,
            "modal_tts": 1,
            "reasoning": 2,
            "retrieval": 2,
            "vision_reasoning": 1,
            "audio_transcription": 1,
            "artifact_storage": 4,
        }
    )


class PersistenceTelemetryExporter:
    def __init__(self, persistence) -> None:
        self.persistence = persistence

    def export(
        self, *, run_id: str, queue_item: dict[str, Any], events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        request = (
            dict(queue_item.get("payload") or {}).get("orchestration_request") or {}
        )
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{run_id}-execution-telemetry.json",
            payload={
                "run_id": run_id,
                "queue_item": _sanitized_queue_item(queue_item),
                "events": events,
            },
            series_id=str(request.get("series_id") or ""),
            story_id=str(request.get("story_id") or ""),
            run_id=run_id,
            provider_name="execution_runtime",
            report_kind="telemetry",
            metadata={
                "queue_name": queue_item.get("queue_name"),
                "terminal_status": queue_item.get("status"),
            },
        )


class PersistenceExecutionObserver:
    def __init__(
        self, persistence, *, retention_days: int = 30, otlp_http_endpoint: str = ""
    ) -> None:
        self.persistence = persistence
        exporters = (
            [OTLPHTTPExporter(otlp_http_endpoint)]
            if str(otlp_http_endpoint or "").strip()
            else []
        )
        self.runtime = ObservabilityRuntime(
            store=persistence.observability,
            exporters=exporters,
            config=ObservabilityRuntimeConfig(retention_days=retention_days),
        )

    def observe(
        self,
        *,
        run_id: str,
        queue_item: dict[str, Any],
        events: list[dict[str, Any]],
        orchestration_result,
    ) -> dict[str, Any]:
        request = (
            dict(queue_item.get("payload") or {}).get("orchestration_request") or {}
        )
        series_id = str(queue_item.get("series_id") or request.get("series_id") or "")
        current_lineage = self.persistence.lineage.list(run_id=run_id, limit=1000)
        lineage = list(current_lineage)
        for stage in {str(row.get("stage") or "") for row in current_lineage}:
            lineage.extend(
                self.persistence.lineage.list(
                    series_id=series_id, stage=stage, limit=1000
                )
            )
        active_statuses = {"queued", "retry_wait", "leased", "cancel_requested"}
        queue_depth = sum(
            1
            for item in self.persistence.execution_queue.list(
                queue_name=queue_item.get("queue_name"), limit=10000
            )
            if item.get("status") in active_statuses
        )
        observed = self.runtime.observe_execution(
            run_id=run_id,
            queue_item=queue_item,
            events=events,
            orchestration_result=orchestration_result,
            lineage_records=lineage,
            trace_payloads=load_lineage_trace_snapshots(
                self.persistence, current_lineage
            ),
            queue_depth=queue_depth,
        )
        evaluations = self.runtime.evaluate_slos(default_execution_slos())
        observed["slo_evaluations"] = [item.model_dump() for item in evaluations]
        return observed


class ExecutionRuntimeService:
    def __init__(self, *, config: ExecutionRuntimeServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name="execution-runtime",
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-execution-runtime",
            local_storage_root_dir=config.local_storage_root_dir,
        )
        self.persistence = create_persistence_client(
            profile=profile,
            config=PersistenceRuntimeConfig(
                profile=profile,
                supabase_api_url=config.supabase_api_url,
                supabase_anon_key=config.supabase_anon_key,
                supabase_service_role_key=config.supabase_service_role_key,
            ),
        )
        self.persistence.initialize()
        self.queue = ExecutionQueueRuntime(
            persistence=self.persistence, queue_name=config.queue_name
        )
        self.queue.configure(
            ExecutionQueuePolicy(
                global_limit=config.global_limit,
                per_series_limit=config.per_series_limit,
                default_capability_limit=config.default_capability_limit,
                capability_limits=config.capability_limits,
            )
        )
        self.orchestration_config = ProductionOrchestrationServiceConfig(
            persistence_mode=config.persistence_mode,
            persistence_provider=config.persistence_provider,
            database_url=config.database_url,
            local_storage_root_dir=config.local_storage_root_dir,
            supabase_api_url=config.supabase_api_url,
            supabase_anon_key=config.supabase_anon_key,
            supabase_service_role_key=config.supabase_service_role_key,
            lineage_version_overrides=config.lineage_version_overrides,
            usage_cost_rates=config.usage_cost_rates,
            release_id=config.release_id,
        )

    @classmethod
    def from_env(cls) -> ExecutionRuntimeService:
        return cls(config=load_execution_runtime_service_config_from_env())

    def submit(
        self,
        request: OrchestrationRequest,
        *,
        priority: int = 0,
        max_attempts: int = 3,
        backoff_seconds: int = 10,
    ) -> dict[str, Any]:
        return self.queue.submit(
            ExecutionSubmission(
                queue_id=queue_id_for_run(request.run_id),
                request=request,
                priority=priority,
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
            )
        )

    def cancel(self, queue_id: str, *, reason: str = "") -> dict[str, Any] | None:
        return self.queue.cancel(queue_id, reason=reason)

    def retry(
        self, request: OrchestrationRequest, *, priority: int = 0, max_attempts: int = 3
    ) -> dict[str, Any] | None:
        queue_id = queue_id_for_run(request.run_id)
        current = self.queue.get(queue_id)
        if current is None:
            return None
        if current.get("status") not in {"cancelled", "dead_letter"}:
            raise ValueError(
                f"Queue item '{queue_id}' cannot be retried from status '{current.get('status')}'."
            )
        # Preserve stage outputs and nested agent checkpoints, but reset the
        # terminal top-level graph state before making the run claimable.
        SqlCheckpointSaver(engine=self.persistence.engine).delete_thread(request.run_id)
        return self.queue.requeue(
            ExecutionSubmission(
                queue_id=queue_id,
                request=request,
                priority=priority,
                max_attempts=max_attempts,
            )
        )

    def run_worker_once(self, *, worker_id: str = "") -> WorkerExecutionResult:
        resolved_worker = (
            worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        )
        worker = ExecutionWorker(
            queue=self.queue,
            executor_factory=lambda checker: ProductionOrchestrationService(
                config=self.orchestration_config, cancellation_checker=checker
            ),
            telemetry_exporter=PersistenceTelemetryExporter(self.persistence),
            observer=PersistenceExecutionObserver(
                self.persistence,
                retention_days=self.config.observability_retention_days,
                otlp_http_endpoint=self.config.otlp_http_endpoint,
            ),
            worker_id=resolved_worker,
            lease_seconds=self.config.lease_seconds,
        )
        return worker.run_once()


def load_execution_runtime_service_config_from_env() -> ExecutionRuntimeServiceConfig:
    limits_raw = str(os.getenv("SAGA_EXECUTION_CAPABILITY_LIMITS_JSON") or "").strip()
    limits = (
        json.loads(limits_raw)
        if limits_raw
        else ExecutionRuntimeServiceConfig().capability_limits
    )
    lineage_raw = str(os.getenv("SAGA_STAGE_LINEAGE_VERSIONS_JSON") or "").strip()
    lineage_overrides = json.loads(lineage_raw) if lineage_raw else {}
    if not isinstance(lineage_overrides, dict):
        raise TypeError("SAGA_STAGE_LINEAGE_VERSIONS_JSON must be a JSON object.")
    cost_rates_raw = str(os.getenv("SAGA_PROVIDER_COST_RATES_JSON") or "").strip()
    cost_rates_payload = json.loads(cost_rates_raw) if cost_rates_raw else []
    if not isinstance(cost_rates_payload, list):
        raise TypeError("SAGA_PROVIDER_COST_RATES_JSON must be a JSON array.")
    return ExecutionRuntimeServiceConfig(
        persistence_mode=str(
            os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres"
        ).strip(),
        persistence_provider=str(
            os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase"
        ).strip(),
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(
            os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT")
            or "analysis_outputs/unified_storage"
        ).strip(),
        supabase_api_url=str(
            os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or ""
        ).strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(
            os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or ""
        ).strip(),
        queue_name=str(
            os.getenv("SAGA_EXECUTION_QUEUE_NAME") or "production-orchestration"
        ).strip(),
        lease_seconds=max(30, int(os.getenv("SAGA_EXECUTION_LEASE_SECONDS") or "180")),
        global_limit=max(1, int(os.getenv("SAGA_EXECUTION_GLOBAL_LIMIT") or "2")),
        per_series_limit=max(
            1, int(os.getenv("SAGA_EXECUTION_PER_SERIES_LIMIT") or "1")
        ),
        default_capability_limit=max(
            1, int(os.getenv("SAGA_EXECUTION_DEFAULT_CAPABILITY_LIMIT") or "2")
        ),
        observability_retention_days=max(
            1, int(os.getenv("SAGA_OBSERVABILITY_RETENTION_DAYS") or "30")
        ),
        otlp_http_endpoint=str(os.getenv("SAGA_OTLP_HTTP_ENDPOINT") or "").strip(),
        capability_limits={
            str(key): max(1, int(value)) for key, value in dict(limits).items()
        },
        lineage_version_overrides={
            str(stage): dict(values) for stage, values in lineage_overrides.items()
        },
        usage_cost_rates=tuple(
            CostRate.model_validate(item) for item in cost_rates_payload
        ),
        release_id=str(os.getenv("SAGA_RELEASE_ID") or "").strip(),
    )


def _sanitized_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key not in {"lease_token"}}


def load_lineage_trace_snapshots(
    persistence,
    records: list[dict[str, Any]],
    *,
    max_snapshots: int = 100,
    max_characters: int = 10_000_000,
    max_total_characters: int = 25_000_000,
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen_objects: set[tuple[str, str]] = set()
    total_characters = 0
    for row in records[-max(1, max_snapshots) :]:
        reference = dict(row.get("payload") or {}).get("output_artifact_version") or {}
        bucket, path = (
            str(reference.get("bucket_name") or ""),
            str(reference.get("object_path") or ""),
        )
        object_key = (bucket, path)
        if not bucket or not path or object_key in seen_objects:
            continue
        seen_objects.add(object_key)
        try:
            text = persistence.objects.download_text(bucket, path)
            if (
                len(text) <= max_characters
                and total_characters + len(text) <= max_total_characters
            ):
                payload = json.loads(text)
                if isinstance(payload, dict):
                    snapshots.append(payload)
                    total_characters += len(text)
        except Exception:  # noqa: BLE001, S110 - trace export must not change terminal work.
            # Snapshot telemetry is best-effort and cannot affect terminal work.
            pass
    return snapshots


def default_execution_slos() -> list[SLODefinition]:
    return [
        SLODefinition(
            slo_id="run-success-rate",
            metric_name="run.success",
            comparator="gte",
            threshold=0.95,
            aggregation="average",
            minimum_samples=5,
            severity="critical",
        ),
        SLODefinition(
            slo_id="queue-wait-p95",
            metric_name="queue.wait",
            comparator="lte",
            threshold=60.0,
            aggregation="p95",
            minimum_samples=5,
        ),
        SLODefinition(
            slo_id="dead-letter-free",
            metric_name="queue.dead_letter",
            comparator="lte",
            threshold=0.0,
            aggregation="sum",
            minimum_samples=1,
            severity="critical",
        ),
        SLODefinition(
            slo_id="lease-expiry-free",
            metric_name="queue.lease_expiry",
            comparator="lte",
            threshold=0.0,
            aggregation="sum",
            minimum_samples=1,
        ),
        SLODefinition(
            slo_id="stage-acceptance",
            metric_name="stage.accepted",
            comparator="gte",
            threshold=0.95,
            aggregation="average",
            minimum_samples=5,
            severity="critical",
        ),
        SLODefinition(
            slo_id="provider-error-rate",
            metric_name="provider.error",
            comparator="lte",
            threshold=0.05,
            aggregation="average",
            minimum_samples=5,
            severity="critical",
        ),
    ]
