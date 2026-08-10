"""Production-facing service helpers for character and world modeling."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from packages.character_world_modeling.contracts import CharacterWorldModelingResult
from packages.character_world_modeling.pipeline import CharacterWorldModelingRuntime
from packages.character_world_modeling.quality import evaluate_character_world_quality
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client


@dataclass(frozen=True)
class CharacterWorldModelingServiceConfig:
    persistence_profile_name: str = "character-world-modeling-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    reasoning_profile_name: str = "character-world-modeling"
    reasoning_mode: str = "gpt_oss"
    reasoning_timeout_seconds: int = 180
    reasoning_max_retries: int = 2


@dataclass(frozen=True)
class CharacterWorldModelingRunRequest:
    series_id: str
    thread_id: str = "character-world-modeling"


class CharacterWorldModelingService:
    def __init__(self, *, config: CharacterWorldModelingServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-character-world-modeling",
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
        self.runtime = CharacterWorldModelingRuntime(persistence=self.persistence, reasoning_runtime=reasoning_runtime)

    @classmethod
    def from_env(cls) -> "CharacterWorldModelingService":
        return cls(config=load_character_world_modeling_service_config_from_env())

    def run(self, request: CharacterWorldModelingRunRequest) -> CharacterWorldModelingResult:
        return self.runtime.invoke(series_id=request.series_id, thread_id=request.thread_id)

    def close(self) -> None:
        self.persistence.close()

    def build_quality_audit(self, *, result: CharacterWorldModelingResult) -> dict[str, Any]:
        quality_metrics = evaluate_character_world_quality(result)
        character_ids = {item.character_id for item in result.character_profiles}
        stable_state_ids = {item.character_id for item in result.stable_character_states}
        entity_ids = {item.entity_id for item in result.world_states}
        sparse_profiles = [
            item.character_id
            for item in result.character_profiles
            if not item.overview and not item.traits and not item.notable_relationships
        ]
        sparse_world_states = [
            item.entity_id
            for item in result.world_states
            if not item.current_state_summary and not item.stable_facts and not item.active_conditions
        ]
        return {
            "character_profile_quality": {
                "count": len(result.character_profiles),
                "all_character_ids_present": all(bool(item.character_id) for item in result.character_profiles),
                "all_names_present": all(bool(item.canonical_name) for item in result.character_profiles),
                "sparse_profile_ids": sparse_profiles,
            },
            "stable_state_quality": {
                "count": len(result.stable_character_states),
                "profiles_without_state": sorted(character_ids - stable_state_ids),
                "state_without_profile": sorted(stable_state_ids - character_ids),
                "non_empty_state_count": sum(1 for item in result.stable_character_states if item.stable_attributes),
            },
            "world_state_quality": {
                "count": len(result.world_states),
                "all_entity_ids_present": all(bool(item.entity_id) for item in result.world_states),
                "entity_types": sorted({item.entity_type for item in result.world_states if item.entity_type}),
                "sparse_world_state_ids": sparse_world_states,
                "world_state_entity_ids": sorted(entity_ids),
            },
            "provider_proof": {
                "character_profile_models": sorted(
                    {str((item.metadata or {}).get("reasoning_model") or "") for item in result.character_profiles if (item.metadata or {}).get("reasoning_model")}
                ),
                "stable_state_models": sorted(
                    {str((item.metadata or {}).get("reasoning_model") or "") for item in result.stable_character_states if (item.metadata or {}).get("reasoning_model")}
                ),
                "world_state_models": sorted(
                    {str((item.metadata or {}).get("reasoning_model") or "") for item in result.world_states if (item.metadata or {}).get("reasoning_model")}
                ),
            },
            "modeling_quality_metrics": quality_metrics.model_dump(),
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(
        self,
        *,
        request: CharacterWorldModelingRunRequest,
        result: CharacterWorldModelingResult,
        quality_audit: dict[str, Any],
    ) -> dict[str, Any]:
        report_payload = {
            "report_id": f"character-world-modeling-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "generated_at": int(time.time()),
            "result_summary": {
                "character_profile_count": len(result.character_profiles),
                "stable_character_state_count": len(result.stable_character_states),
                "world_state_count": len(result.world_states),
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.thread_id}-character-world-modeling-report.json",
            payload=report_payload,
            provider_name="character_world_modeling",
            report_kind="validation",
            metadata={"series_id": request.series_id, "thread_id": request.thread_id},
        )


def load_character_world_modeling_service_config_from_env() -> CharacterWorldModelingServiceConfig:
    return CharacterWorldModelingServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_CHARACTER_WORLD_MODELING_PERSISTENCE_PROFILE") or "character-world-modeling-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        reasoning_profile_name=str(os.getenv("SAGA_CHARACTER_WORLD_MODELING_REASONING_PROFILE") or "character-world-modeling").strip(),
        reasoning_mode=str(os.getenv("SAGA_CHARACTER_WORLD_MODELING_REASONING_MODE") or "gpt_oss").strip() or "gpt_oss",
        reasoning_timeout_seconds=max(30, int(os.getenv("SAGA_CHARACTER_WORLD_MODELING_REASONING_TIMEOUT_SECONDS") or "180")),
        reasoning_max_retries=max(1, int(os.getenv("SAGA_CHARACTER_WORLD_MODELING_REASONING_MAX_RETRIES") or "2")),
    )
