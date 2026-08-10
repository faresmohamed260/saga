"""Production-facing service helpers for generation planning."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from packages.generation_planning.contracts import GenerationPlanningResult
from packages.generation_planning.pipeline import GenerationPlanningRuntime
from packages.generation_planning.quality import evaluate_generation_blueprint
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client


@dataclass(frozen=True)
class GenerationPlanningServiceConfig:
    persistence_profile_name: str = "generation-planning-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    reasoning_profile_name: str = "generation-planning"
    reasoning_mode: str = "gpt_oss"
    reasoning_timeout_seconds: int = 120
    reasoning_max_retries: int = 1


@dataclass(frozen=True)
class GenerationPlanningRunRequest:
    series_id: str
    thread_id: str = "generation-planning"
    premise: str = ""
    target_audience: str = ""
    tone: str = ""
    continuation_mode: str = "canon_continuation"
    desired_chapter_count: int = 3


class GenerationPlanningService:
    def __init__(self, *, config: GenerationPlanningServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-generation-planning",
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
        self.runtime = GenerationPlanningRuntime(persistence=self.persistence, reasoning_runtime=reasoning_runtime)

    @classmethod
    def from_env(cls) -> "GenerationPlanningService":
        return cls(config=load_generation_planning_service_config_from_env())

    def run(self, request: GenerationPlanningRunRequest) -> GenerationPlanningResult:
        return self.runtime.invoke(
            series_id=request.series_id,
            thread_id=request.thread_id,
            premise=request.premise,
            target_audience=request.target_audience,
            tone=request.tone,
            continuation_mode=request.continuation_mode,
            desired_chapter_count=request.desired_chapter_count,
        )

    def close(self) -> None:
        self.persistence.close()

    def build_quality_audit(self, *, result: GenerationPlanningResult) -> dict[str, Any]:
        context = self.runtime.store.load_series_context(series_id=result.series_id)
        valid_canon_refs = {
            *{item.event_id for item in list(context.get("events") or [])},
            *{item.timeline_id for item in list(context.get("timeline") or [])},
        }
        valid_character_refs = {item.character_id for item in list(context.get("character_profiles") or [])}
        identity_bundle = context.get("identity_bundle")
        if identity_bundle is not None:
            valid_character_refs.update(item.character_id for item in identity_bundle.characters)
        valid_entity_refs = {item.entity_id for item in list(context.get("entities") or [])}
        valid_entity_refs.update(item.entity_id for item in list(context.get("world_states") or []))
        quality_metrics = evaluate_generation_blueprint(
            result,
            valid_canon_refs=valid_canon_refs,
            valid_character_refs=valid_character_refs,
            valid_entity_refs=valid_entity_refs,
        )
        return {
            "blueprint_quality": {
                "chapter_outline_count": len(result.blueprint.chapter_outline),
                "scene_plan_count": len(result.blueprint.scene_plan),
                "canon_ref_count": len(result.blueprint.canon_refs),
                "character_ref_count": len(result.blueprint.character_refs),
                "entity_ref_count": len(result.blueprint.entity_refs),
            },
            "quality_metrics": quality_metrics.model_dump(),
            "provider_proof": {
                "reasoning_provider": result.blueprint.metadata.get("reasoning_provider"),
                "reasoning_model": result.blueprint.metadata.get("reasoning_model"),
                "reasoning_status": result.blueprint.metadata.get("reasoning_status"),
                "fallback_used": bool(
                    dict(result.blueprint.metadata.get("request_metadata") or {}).get("fallback_used")
                    or dict(result.blueprint.metadata.get("request_metadata") or {}).get("deterministic_fallback")
                ),
            },
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(
        self,
        *,
        request: GenerationPlanningRunRequest,
        result: GenerationPlanningResult,
        quality_audit: dict[str, Any],
    ) -> dict[str, Any]:
        report_payload = {
            "report_id": f"generation-planning-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "generated_at": int(time.time()),
            "result_summary": {
                "chapter_outline_count": len(result.blueprint.chapter_outline),
                "scene_plan_count": len(result.blueprint.scene_plan),
                "canon_ref_count": len(result.blueprint.canon_refs),
                "character_ref_count": len(result.blueprint.character_refs),
                "entity_ref_count": len(result.blueprint.entity_refs),
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.thread_id}-generation-planning-report.json",
            payload=report_payload,
            provider_name="generation_planning",
            report_kind="validation",
            metadata={"series_id": request.series_id, "thread_id": request.thread_id},
        )


def load_generation_planning_service_config_from_env() -> GenerationPlanningServiceConfig:
    return GenerationPlanningServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_GENERATION_PLANNING_PERSISTENCE_PROFILE") or "generation-planning-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        reasoning_profile_name=str(os.getenv("SAGA_GENERATION_PLANNING_REASONING_PROFILE") or "generation-planning").strip(),
        reasoning_mode=str(os.getenv("SAGA_GENERATION_PLANNING_REASONING_MODE") or "gpt_oss").strip() or "gpt_oss",
        reasoning_timeout_seconds=max(30, int(os.getenv("SAGA_GENERATION_PLANNING_REASONING_TIMEOUT_SECONDS") or "120")),
        reasoning_max_retries=max(1, int(os.getenv("SAGA_GENERATION_PLANNING_REASONING_MAX_RETRIES") or "1")),
    )
