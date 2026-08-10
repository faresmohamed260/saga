"""Production composition root for the visual-generation runtime."""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from integrations.comfyui.pool_manager import ModalComfyUIPoolManager
from integrations.comfyui.token_pool import load_tokens
from packages.modal_runtime import clear_modal_provider_config_cache, load_modal_provider_secret_config
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client
from packages.visual_generation.contracts import VisualGenerationResult
from packages.visual_generation.pipeline import VisualGenerationRuntime
from packages.visual_generation.vision import ReasoningVisionSemanticEvaluator


@dataclass(frozen=True)
class VisualGenerationServiceConfig:
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    planning_mode: str = "mistral"
    planning_model: str = ""
    planning_timeout_seconds: int = 180
    planning_max_retries: int = 2
    vision_mode: str = "mistral"
    vision_model: str = "mistral-small-2603"
    vision_timeout_seconds: int = 180
    image_timeout_seconds: int = 900
    image_failover_attempts: int = 3


@dataclass(frozen=True)
class VisualGenerationRunRequest:
    series_id: str
    story_id: str
    thread_id: str = ""
    include_types: tuple[str, ...] = ()
    max_renders_per_type: int = 0
    max_attempts: int = 2


class VisualGenerationService:
    def __init__(self, *, config: VisualGenerationServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name="visual-generation-runtime",
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-visual-generation",
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
        planning_profile = ReasoningProfile(
            name="visual-planning",
            mode=config.planning_mode,
            model_override=config.planning_model,
            timeout_seconds=config.planning_timeout_seconds,
            max_retries=config.planning_max_retries,
        )
        vision_profile = ReasoningProfile(
            name="visual-quality",
            mode=config.vision_mode,
            model_override=config.vision_model,
            prefer_local_ollama=config.vision_mode in {"gpt_oss", "deepseek"},
            timeout_seconds=config.vision_timeout_seconds,
            max_retries=2,
        )
        reasoning_config = ReasoningRuntimeConfig(
            profiles={planning_profile.name: planning_profile, vision_profile.name: vision_profile},
        )
        planning_runtime = create_reasoning_client(
            profile_name=planning_profile.name,
            config=reasoning_config,
            persistence_client=self.persistence,
        )
        vision_runtime = create_reasoning_client(
            profile_name=vision_profile.name,
            config=reasoning_config,
            persistence_client=self.persistence,
        )
        clear_modal_provider_config_cache()
        modal_config = load_modal_provider_secret_config("modal_comfyui")
        image_provider = ModalComfyUIPoolManager(
            app_name=modal_config.app_name,
            hf_token=modal_config.hf_token,
            tokens=load_tokens(),
            request_timeout_seconds=config.image_timeout_seconds,
            max_failover_attempts=config.image_failover_attempts,
        )
        self.runtime = VisualGenerationRuntime(
            persistence=self.persistence,
            reasoning_runtime=planning_runtime,
            image_provider=image_provider,
            semantic_evaluator=ReasoningVisionSemanticEvaluator(vision_runtime),
        )

    @classmethod
    def from_env(cls) -> "VisualGenerationService":
        return cls(config=load_visual_generation_service_config_from_env())

    def run(self, request: VisualGenerationRunRequest) -> VisualGenerationResult:
        thread_id = request.thread_id or f"visual-generation-{request.story_id}-{uuid.uuid4().hex[:10]}"
        return self.runtime.invoke(
            series_id=request.series_id,
            story_id=request.story_id,
            thread_id=thread_id,
            include_types=list(request.include_types),
            max_renders_per_type=request.max_renders_per_type,
            max_attempts=request.max_attempts,
            workflow_versions=_workflow_versions(),
        )

    def reaudit(self, request: VisualGenerationRunRequest) -> VisualGenerationResult:
        return self.runtime.reaudit(
            series_id=request.series_id,
            story_id=request.story_id,
            max_attempts=request.max_attempts,
        )

    def retry_rejected(self, request: VisualGenerationRunRequest) -> VisualGenerationResult:
        return self.runtime.retry_rejected(
            series_id=request.series_id,
            story_id=request.story_id,
            max_attempts=request.max_attempts,
        )

    def build_quality_audit(self, result: VisualGenerationResult) -> dict[str, Any]:
        accepted = [item for item in result.audits if item.accepted]
        return {
            "decision": result.decision.model_dump(),
            "target_types": sorted({item.target_type for item in result.prompts}),
            "render_attempt_count": len(result.renders),
            "accepted_render_count": len(accepted),
            "randomized_seed_count": len({item.seed for item in result.renders}),
            "provider_accounts": sorted({item.provider_account for item in result.renders if item.provider_account}),
            "accepted_artifacts": [
                {
                    "target_type": item.target_type,
                    "target_ref": item.target_ref,
                    "render_id": item.render_id,
                    "bucket_name": render.bucket_name if (render := next((row for row in result.renders if row.render_id == item.render_id), None)) else "",
                    "object_path": render.object_path if render else "",
                }
                for item in accepted
            ],
            "run_metadata": result.run_metadata,
        }

    def persist_runtime_report(self, *, request: VisualGenerationRunRequest, result: VisualGenerationResult, quality_audit: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "report_id": f"visual-generation-{uuid.uuid4().hex[:12]}",
            "generated_at": int(time.time()),
            "request": {
                "series_id": request.series_id,
                "story_id": request.story_id,
                "include_types": list(request.include_types),
                "max_renders_per_type": request.max_renders_per_type,
                "max_attempts": request.max_attempts,
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.story_id}-visual-generation-report.json",
            payload=payload,
            provider_name="visual_generation",
            report_kind="validation",
            metadata={"series_id": request.series_id, "story_id": request.story_id},
        )


def load_visual_generation_service_config_from_env() -> VisualGenerationServiceConfig:
    return VisualGenerationServiceConfig(
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip(),
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip(),
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        planning_mode=str(os.getenv("SAGA_VISUAL_PLANNING_MODE") or "mistral").strip(),
        planning_model=str(os.getenv("SAGA_VISUAL_PLANNING_MODEL") or "").strip(),
        planning_timeout_seconds=max(30, int(os.getenv("SAGA_VISUAL_PLANNING_TIMEOUT_SECONDS") or "180")),
        planning_max_retries=max(1, int(os.getenv("SAGA_VISUAL_PLANNING_MAX_RETRIES") or "2")),
        vision_mode=str(os.getenv("SAGA_VISUAL_QUALITY_MODE") or "mistral").strip(),
        vision_model=str(os.getenv("SAGA_VISUAL_QUALITY_MODEL") or "mistral-small-2603").strip(),
        vision_timeout_seconds=max(30, int(os.getenv("SAGA_VISUAL_QUALITY_TIMEOUT_SECONDS") or "180")),
        image_timeout_seconds=max(60, int(os.getenv("SAGA_VISUAL_IMAGE_TIMEOUT_SECONDS") or "900")),
        image_failover_attempts=max(1, int(os.getenv("SAGA_VISUAL_IMAGE_FAILOVER_ATTEMPTS") or "3")),
    )


def _workflow_versions() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2] / "integrations" / "comfyui" / "workflows"
    versions = {}
    for mode, filename in {
        "character_sheet": "character_sheet_workflow.json",
        "entity_generation": "entity_generation_workflow.json",
    }.items():
        data = (root / filename).read_bytes()
        versions[mode] = hashlib.sha256(data).hexdigest()
    return versions
