"""Production-facing service helpers for canon extraction."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.analysis_foundation import AnalysisFoundationRunRequest, AnalysisFoundationService
from packages.canon_extraction.contracts import CanonExtractionResult
from packages.canon_extraction.pipeline import CanonExtractionRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client
from packages.runtime_common import CancellationChecker


@dataclass(frozen=True)
class CanonExtractionServiceConfig:
    persistence_profile_name: str = "canon-extraction-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    reasoning_profile_name: str = "canon-extraction"
    reasoning_mode: str = "gpt_oss"
    reasoning_timeout_seconds: int = 180
    reasoning_max_retries: int = 2


@dataclass(frozen=True)
class CanonExtractionRunRequest:
    series_id: str
    thread_id: str = "canon-extraction"
    source_paths: list[str] | None = None
    run_analysis_foundation: bool = False


class CanonExtractionService:
    def __init__(self, *, config: CanonExtractionServiceConfig, cancellation_checker: CancellationChecker | None = None) -> None:
        self.config = config
        profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-canon-extraction",
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
        reasoning_profile = ReasoningProfile(
            name=config.reasoning_profile_name,
            mode=config.reasoning_mode,
            timeout_seconds=config.reasoning_timeout_seconds,
            max_retries=config.reasoning_max_retries,
        )
        reasoning_config = ReasoningRuntimeConfig(profiles={config.reasoning_profile_name: reasoning_profile})
        reasoning_runtime = create_reasoning_client(
            profile_name=config.reasoning_profile_name,
            config=reasoning_config,
            persistence_client=self.persistence,
        )
        self.runtime = CanonExtractionRuntime(
            persistence=self.persistence, reasoning_runtime=reasoning_runtime,
            cancellation_checker=cancellation_checker,
        )

    @classmethod
    def from_env(cls, *, cancellation_checker: CancellationChecker | None = None) -> "CanonExtractionService":
        return cls(config=load_canon_extraction_service_config_from_env(), cancellation_checker=cancellation_checker)

    def run(self, request: CanonExtractionRunRequest) -> CanonExtractionResult:
        if request.run_analysis_foundation:
            source_paths = [str(Path(path).resolve()) for path in list(request.source_paths or []) if str(path or "").strip()]
            if not source_paths:
                raise ValueError("source_paths are required when run_analysis_foundation=True")
            analysis_service = AnalysisFoundationService.from_env()
            analysis_service.run(
                AnalysisFoundationRunRequest(
                    series_id=request.series_id,
                    source_paths=source_paths,
                    thread_id=f"{request.thread_id}-analysis-foundation",
                )
            )
        return self.runtime.invoke(series_id=request.series_id, thread_id=request.thread_id)

    def build_quality_audit(self, *, result: CanonExtractionResult) -> dict[str, Any]:
        event_ids = {item.event_id for item in result.events}
        entity_ids = {item.entity_id for item in result.entities}
        ref_ids = event_ids | entity_ids
        invalid_event_participants = [
            {"event_id": item.event_id, "invalid_refs": [ref for ref in item.participant_refs if ref not in ref_ids and not ref.startswith("char-")]}
            for item in result.events
            if any(ref not in ref_ids and not ref.startswith("char-") for ref in item.participant_refs)
        ]
        invalid_relationships = [
            {
                "relationship_id": item.relationship_id,
                "source_ref": item.source_ref,
                "target_ref": item.target_ref,
            }
            for item in result.relationships
            if not item.source_ref or not item.target_ref
        ]
        orphan_timeline = [item.timeline_id for item in result.timeline if item.event_id not in event_ids]
        return {
            "event_quality": {
                "count": len(result.events),
                "all_titles_present": all(bool(str(item.title or "").strip()) for item in result.events),
                "invalid_participant_refs": invalid_event_participants,
            },
            "entity_quality": {
                "count": len(result.entities),
                "all_names_present": all(bool(str(item.canonical_name or "").strip()) for item in result.entities),
                "entity_types": sorted({item.entity_type for item in result.entities if item.entity_type}),
            },
            "relationship_quality": {
                "count": len(result.relationships),
                "invalid_relationships": invalid_relationships,
                "relationship_types": sorted({item.relationship_type for item in result.relationships if item.relationship_type}),
            },
            "timeline_quality": {
                "count": len(result.timeline),
                "sequence_is_contiguous": [item.sequence_index for item in result.timeline] == list(range(1, len(result.timeline) + 1)),
                "orphan_timeline_ids": orphan_timeline,
            },
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(self, *, request: CanonExtractionRunRequest, result: CanonExtractionResult, quality_audit: dict[str, Any]) -> dict[str, Any]:
        report_payload = {
            "report_id": f"canon-extraction-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "generated_at": int(time.time()),
            "used_upstream_analysis_foundation": bool(request.run_analysis_foundation),
            "source_paths": [str(path) for path in list(request.source_paths or [])],
            "result_summary": {
                "event_count": len(result.events),
                "entity_count": len(result.entities),
                "relationship_count": len(result.relationships),
                "timeline_count": len(result.timeline),
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.thread_id}-canon-extraction-report.json",
            payload=report_payload,
            provider_name="canon_extraction",
            report_kind="validation",
            metadata={"series_id": request.series_id, "thread_id": request.thread_id},
        )


def load_canon_extraction_service_config_from_env() -> CanonExtractionServiceConfig:
    return CanonExtractionServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_CANON_EXTRACTION_PERSISTENCE_PROFILE") or "canon-extraction-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        reasoning_profile_name=str(os.getenv("SAGA_CANON_EXTRACTION_REASONING_PROFILE") or "canon-extraction").strip(),
        reasoning_mode=str(os.getenv("SAGA_CANON_EXTRACTION_REASONING_MODE") or "gpt_oss").strip() or "gpt_oss",
        reasoning_timeout_seconds=max(30, int(os.getenv("SAGA_CANON_EXTRACTION_REASONING_TIMEOUT_SECONDS") or "180")),
        reasoning_max_retries=max(1, int(os.getenv("SAGA_CANON_EXTRACTION_REASONING_MAX_RETRIES") or "2")),
    )
