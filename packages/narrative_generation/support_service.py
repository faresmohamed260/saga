"""Production service surface for narrative semantic-support validation."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from packages.narrative_generation.contracts import NarrativeSupportResult
from packages.narrative_generation.support_pipeline import NarrativeSupportRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client
from packages.retrieval_runtime import RetrievalProfile, RetrievalRuntimeConfig, create_retrieval_client


@dataclass(frozen=True)
class NarrativeSupportServiceConfig:
    persistence_profile_name: str = "narrative-support-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    reasoning_profile_name: str = "narrative-support"
    reasoning_mode: str = "mistral"
    reasoning_model: str = ""
    reasoning_timeout_seconds: int = 120
    reasoning_max_retries: int = 4
    reasoning_base_delay_seconds: float = 1.0
    retrieval_profile_name: str = "narrative-support"
    retrieval_embedding_model: str = "nomic-embed-text:latest"
    retrieval_embedding_url: str = "http://localhost:11434/api/embed"
    retrieval_batch_size: int = 24
    minimum_factual_support_rate: float = 0.85
    maximum_unsupported_invention_rate: float = 0.10


@dataclass(frozen=True)
class NarrativeSupportRunRequest:
    series_id: str
    story_id: str
    thread_id: str = "narrative-support"


class NarrativeSupportService:
    def __init__(self, *, config: NarrativeSupportServiceConfig) -> None:
        self.config = config
        persistence_profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-narrative-support",
            local_storage_root_dir=config.local_storage_root_dir,
        )
        self.persistence = create_persistence_client(
            profile=persistence_profile,
            config=PersistenceRuntimeConfig(
                profile=persistence_profile,
                supabase_api_url=config.supabase_api_url,
                supabase_anon_key=config.supabase_anon_key,
                supabase_service_role_key=config.supabase_service_role_key,
            ),
        )
        reasoning_profile = ReasoningProfile(
            name=config.reasoning_profile_name,
            mode=config.reasoning_mode,
            model_override=config.reasoning_model,
            timeout_seconds=config.reasoning_timeout_seconds,
            max_retries=config.reasoning_max_retries,
            base_delay_seconds=config.reasoning_base_delay_seconds,
        )
        reasoning_runtime = create_reasoning_client(
            profile_name=config.reasoning_profile_name,
            config=ReasoningRuntimeConfig(profiles={config.reasoning_profile_name: reasoning_profile}),
            persistence_client=self.persistence,
        )
        retrieval_profile = RetrievalProfile(
            name=config.retrieval_profile_name,
            embedding_model=config.retrieval_embedding_model,
            ollama_embed_url=config.retrieval_embedding_url,
            batch_size=config.retrieval_batch_size,
        )
        retrieval_runtime = create_retrieval_client(
            config=RetrievalRuntimeConfig(profile=retrieval_profile),
            profile=retrieval_profile,
            persistence_client=self.persistence,
        )
        self.runtime = NarrativeSupportRuntime(
            persistence=self.persistence,
            retrieval_runtime=retrieval_runtime,
            reasoning_runtime=reasoning_runtime,
            minimum_factual_support_rate=config.minimum_factual_support_rate,
            maximum_unsupported_invention_rate=config.maximum_unsupported_invention_rate,
        )

    @classmethod
    def from_env(cls) -> "NarrativeSupportService":
        return cls(config=load_narrative_support_service_config_from_env())

    def run(self, request: NarrativeSupportRunRequest) -> NarrativeSupportResult:
        return self.runtime.invoke(series_id=request.series_id, story_id=request.story_id, thread_id=request.thread_id)

    def close(self) -> None:
        self.persistence.close()

    def build_quality_audit(self, *, result: NarrativeSupportResult) -> dict[str, Any]:
        classifications: dict[str, int] = {}
        for audit in result.audits:
            for claim in audit.claims:
                classifications[claim.classification] = classifications.get(claim.classification, 0) + 1
        return {
            "decision": result.decision.model_dump(),
            "scene_audits": [
                {
                    "source_scene_id": item.source_scene_id,
                    "status": item.status,
                    "evaluation_round": item.evaluation_round,
                    "factual_support_rate": item.factual_support_rate,
                    "unsupported_invention_rate": item.unsupported_invention_rate,
                    "contradiction_rate": item.contradiction_rate,
                    "evidence_count": len(item.evidence),
                    "issues": list(item.issues),
                }
                for item in result.audits
            ],
            "claim_classification_counts": classifications,
            "provider_proof": {
                "models": sorted({str((item.metadata or {}).get("reasoning_model") or "") for item in result.audits if (item.metadata or {}).get("reasoning_model")}),
                "statuses": sorted({str((item.metadata or {}).get("reasoning_status") or "") for item in result.audits}),
            },
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(
        self,
        *,
        request: NarrativeSupportRunRequest,
        result: NarrativeSupportResult,
        quality_audit: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "report_id": f"narrative-support-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "story_id": request.story_id,
            "thread_id": request.thread_id,
            "generated_at": int(time.time()),
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.story_id}-{request.thread_id}-narrative-support-report.json",
            payload=payload,
            provider_name="narrative_support",
            report_kind="validation",
            metadata={"series_id": request.series_id, "story_id": request.story_id, "thread_id": request.thread_id},
        )


def load_narrative_support_service_config_from_env() -> NarrativeSupportServiceConfig:
    return NarrativeSupportServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_NARRATIVE_SUPPORT_PERSISTENCE_PROFILE") or "narrative-support-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or os.getenv("SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        reasoning_profile_name=str(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_PROFILE") or "narrative-support").strip(),
        reasoning_mode=str(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_MODE") or "mistral").strip() or "mistral",
        reasoning_model=str(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_MODEL") or "").strip(),
        reasoning_timeout_seconds=max(30, int(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_TIMEOUT_SECONDS") or "120")),
        reasoning_max_retries=max(1, int(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_MAX_RETRIES") or "4")),
        reasoning_base_delay_seconds=max(0.0, float(os.getenv("SAGA_NARRATIVE_SUPPORT_REASONING_BASE_DELAY_SECONDS") or "1")),
        retrieval_profile_name=str(os.getenv("SAGA_NARRATIVE_SUPPORT_RETRIEVAL_PROFILE") or "narrative-support").strip(),
        retrieval_embedding_model=str(os.getenv("SAGA_NARRATIVE_SUPPORT_EMBEDDING_MODEL") or "nomic-embed-text:latest").strip(),
        retrieval_embedding_url=str(os.getenv("SAGA_NARRATIVE_SUPPORT_EMBEDDING_URL") or "http://localhost:11434/api/embed").strip(),
        retrieval_batch_size=max(1, int(os.getenv("SAGA_NARRATIVE_SUPPORT_EMBEDDING_BATCH_SIZE") or "24")),
        minimum_factual_support_rate=max(0.0, min(1.0, float(os.getenv("SAGA_NARRATIVE_SUPPORT_MIN_FACTUAL_SUPPORT_RATE") or "0.85"))),
        maximum_unsupported_invention_rate=max(0.0, min(1.0, float(os.getenv("SAGA_NARRATIVE_SUPPORT_MAX_UNSUPPORTED_RATE") or "0.10"))),
    )
