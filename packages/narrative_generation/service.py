"""Production-facing service helpers for narrative generation."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from packages.narrative_generation.contracts import NarrativeGenerationResult
from packages.narrative_generation.pipeline import NarrativeGenerationRuntime
from packages.narrative_generation.quality import evaluate_narrative_generation
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client


@dataclass(frozen=True)
class NarrativeGenerationServiceConfig:
    persistence_profile_name: str = "narrative-generation-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    reasoning_profile_name: str = "narrative-generation"
    reasoning_mode: str = "gpt_oss"
    reasoning_timeout_seconds: int = 120
    reasoning_max_retries: int = 1
    reasoning_base_delay_seconds: float = 0.0


@dataclass(frozen=True)
class NarrativeGenerationRunRequest:
    series_id: str
    blueprint_id: str = ""
    story_id: str = ""
    thread_id: str = "narrative-generation"
    target_words_per_scene: int = 180


class NarrativeGenerationService:
    def __init__(self, *, config: NarrativeGenerationServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-narrative-generation",
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
            base_delay_seconds=config.reasoning_base_delay_seconds,
        )
        reasoning_config = ReasoningRuntimeConfig(profiles={config.reasoning_profile_name: reasoning_profile})
        reasoning_runtime = create_reasoning_client(
            profile_name=config.reasoning_profile_name,
            config=reasoning_config,
            persistence_client=self.persistence,
        )
        self.runtime = NarrativeGenerationRuntime(persistence=self.persistence, reasoning_runtime=reasoning_runtime)

    @classmethod
    def from_env(cls) -> "NarrativeGenerationService":
        return cls(config=load_narrative_generation_service_config_from_env())

    def run(self, request: NarrativeGenerationRunRequest) -> NarrativeGenerationResult:
        return self.runtime.invoke(
            series_id=request.series_id,
            blueprint_id=request.blueprint_id,
            story_id=request.story_id,
            thread_id=request.thread_id,
            target_words_per_scene=request.target_words_per_scene,
        )

    def close(self) -> None:
        self.persistence.close()

    def build_quality_audit(self, *, result: NarrativeGenerationResult) -> dict[str, Any]:
        context = self.runtime.store.load_series_context(series_id=result.series_id, blueprint_id=result.story.blueprint_id)
        blueprint = context.get("blueprint")
        if blueprint is None:
            raise ValueError(f"Missing blueprint '{result.story.blueprint_id}' for narrative quality audit.")
        metrics = evaluate_narrative_generation(result, blueprint=blueprint)
        return {
            "story_quality": {
                "story_id": result.story.story_id,
                "chapter_count": len(result.story.chapters),
                "scene_prose_count": len(result.scene_prose),
                "revision_count": len(result.story.revisions),
                "word_count": sum(len(chapter.prose.split()) for chapter in result.story.chapters),
            },
            "quality_metrics": metrics.model_dump(),
            "provider_proof": {
                "scene_models": sorted(
                    {
                        str((scene.metadata or {}).get("reasoning_model") or "")
                        for scene in result.scene_prose
                        if (scene.metadata or {}).get("reasoning_model")
                    }
                ),
                "scene_statuses": sorted(
                    {
                        str((scene.metadata or {}).get("reasoning_status") or "")
                        for scene in result.scene_prose
                        if (scene.metadata or {}).get("reasoning_status")
                    }
                ),
                "fallback_scene_count": len(
                    [
                        scene
                        for scene in result.scene_prose
                        if dict((scene.metadata or {}).get("request_metadata") or {}).get("deterministic_fallback")
                    ]
                ),
            },
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(
        self,
        *,
        request: NarrativeGenerationRunRequest,
        result: NarrativeGenerationResult,
        quality_audit: dict[str, Any],
    ) -> dict[str, Any]:
        report_payload = {
            "report_id": f"narrative-generation-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "generated_at": int(time.time()),
            "result_summary": {
                "story_id": result.story.story_id,
                "chapter_count": len(result.story.chapters),
                "scene_prose_count": len(result.scene_prose),
                "revision_count": len(result.story.revisions),
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.thread_id}-narrative-generation-report.json",
            payload=report_payload,
            provider_name="narrative_generation",
            report_kind="validation",
            metadata={"series_id": request.series_id, "thread_id": request.thread_id, "story_id": result.story.story_id},
        )


def load_narrative_generation_service_config_from_env() -> NarrativeGenerationServiceConfig:
    return NarrativeGenerationServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_NARRATIVE_GENERATION_PERSISTENCE_PROFILE") or "narrative-generation-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        reasoning_profile_name=str(os.getenv("SAGA_NARRATIVE_GENERATION_REASONING_PROFILE") or "narrative-generation").strip(),
        reasoning_mode=str(os.getenv("SAGA_NARRATIVE_GENERATION_REASONING_MODE") or "gpt_oss").strip() or "gpt_oss",
        reasoning_timeout_seconds=max(30, int(os.getenv("SAGA_NARRATIVE_GENERATION_REASONING_TIMEOUT_SECONDS") or "120")),
        reasoning_max_retries=max(1, int(os.getenv("SAGA_NARRATIVE_GENERATION_REASONING_MAX_RETRIES") or "1")),
        reasoning_base_delay_seconds=max(0.0, float(os.getenv("SAGA_NARRATIVE_GENERATION_REASONING_BASE_DELAY_SECONDS") or "0")),
    )
