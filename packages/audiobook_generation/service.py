"""Production composition root for the audiobook-generation runtime."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from integrations.kokoro_tts.pool_manager import ModalTTSPoolManager
from integrations.kokoro_tts.token_pool import load_tokens
from packages.audiobook_generation.contracts import AudiobookGenerationResult
from packages.audiobook_generation.pipeline import AudiobookGenerationRuntime
from packages.modal_runtime import clear_modal_provider_config_cache, load_modal_provider_secret_config
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client


@dataclass(frozen=True)
class AudiobookGenerationServiceConfig:
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    transcription_model: str = "voxtral-mini-latest"
    transcription_timeout_seconds: int = 180
    tts_timeout_seconds: int = 300
    tts_failover_attempts: int = 3


@dataclass(frozen=True)
class AudiobookGenerationRunRequest:
    series_id: str
    story_id: str
    run_id: str = ""
    thread_id: str = ""
    narrator_voice: str = "af_bella"
    max_chapters: int = 0
    max_segment_chars: int = 1800
    max_attempts: int = 2


class AudiobookGenerationService:
    def __init__(self, *, config: AudiobookGenerationServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name="audiobook-generation-runtime",
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-audiobook-generation",
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
        transcription_profile = ReasoningProfile(
            name="audiobook-transcription",
            mode="mistral",
            model_override=config.transcription_model,
            timeout_seconds=config.transcription_timeout_seconds,
            max_retries=2,
        )
        transcription_runtime = create_reasoning_client(
            profile_name=transcription_profile.name,
            config=ReasoningRuntimeConfig(profiles={transcription_profile.name: transcription_profile}),
            persistence_client=self.persistence,
        )
        clear_modal_provider_config_cache()
        modal_config = load_modal_provider_secret_config("modal_kokoro_tts")
        speech_provider = ModalTTSPoolManager(
            app_name=modal_config.app_name,
            tokens=load_tokens(),
            request_timeout_seconds=config.tts_timeout_seconds,
            max_failover_attempts=config.tts_failover_attempts,
        )
        self.runtime = AudiobookGenerationRuntime(
            persistence=self.persistence,
            synthesis_provider=speech_provider,
            transcription_provider=transcription_runtime,
        )

    @classmethod
    def from_env(cls) -> "AudiobookGenerationService":
        return cls(config=load_audiobook_generation_service_config_from_env())

    def run(self, request: AudiobookGenerationRunRequest) -> AudiobookGenerationResult:
        run_id = request.run_id or f"audiobook-{request.story_id}-{uuid.uuid4().hex[:10]}"
        thread_id = request.thread_id or f"audiobook-generation-{run_id}"
        return self.runtime.invoke(
            series_id=request.series_id,
            story_id=request.story_id,
            run_id=run_id,
            thread_id=thread_id,
            narrator_voice=request.narrator_voice,
            max_chapters=request.max_chapters,
            max_segment_chars=request.max_segment_chars,
            max_attempts=request.max_attempts,
        )

    def retry_rejected(self, request: AudiobookGenerationRunRequest) -> AudiobookGenerationResult:
        if not request.run_id:
            raise ValueError("run_id is required to resume an audiobook run.")
        return self.runtime.retry_rejected(
            series_id=request.series_id,
            story_id=request.story_id,
            run_id=request.run_id,
            max_attempts=request.max_attempts,
        )

    def build_quality_audit(self, result: AudiobookGenerationResult) -> dict[str, Any]:
        accepted = [item for item in result.audits if item.accepted]
        latest = {}
        for item in sorted(result.audits, key=lambda row: row.attempt):
            latest[item.segment_id] = item
        return {
            "decision": result.decision.model_dump(),
            "segment_count": len(result.segments),
            "synthesis_attempt_count": len(result.syntheses),
            "accepted_segment_count": len([item for item in latest.values() if item.accepted]),
            "mean_word_error_rate": round(sum(item.word_error_rate for item in latest.values()) / max(1, len(latest)), 4),
            "provider_accounts": sorted({item.provider_account for item in result.syntheses if item.provider_account}),
            "duration_seconds": result.manifest.duration_seconds if result.manifest else 0.0,
            "manifest": result.manifest.model_dump() if result.manifest else None,
            "accepted_audit_count": len(accepted),
            "run_metadata": result.run_metadata,
        }

    def persist_runtime_report(self, *, request: AudiobookGenerationRunRequest, result: AudiobookGenerationResult, quality_audit: dict[str, Any]) -> dict[str, Any]:
        return self.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{result.plan.run_id}-audiobook-generation-report.json",
            payload={
                "report_id": f"audiobook-generation-{uuid.uuid4().hex[:12]}",
                "generated_at": int(time.time()),
                "request": {
                    "series_id": request.series_id,
                    "story_id": request.story_id,
                    "run_id": result.plan.run_id,
                    "narrator_voice": request.narrator_voice,
                    "max_chapters": request.max_chapters,
                    "max_segment_chars": request.max_segment_chars,
                    "max_attempts": request.max_attempts,
                },
                "quality_audit": quality_audit,
                "result": result.model_dump(),
            },
            provider_name="audiobook_generation",
            report_kind="validation",
            metadata={"series_id": request.series_id, "story_id": request.story_id, "run_id": result.plan.run_id},
        )


def load_audiobook_generation_service_config_from_env() -> AudiobookGenerationServiceConfig:
    return AudiobookGenerationServiceConfig(
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip(),
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip(),
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        transcription_model=str(os.getenv("SAGA_AUDIOBOOK_TRANSCRIPTION_MODEL") or "voxtral-mini-latest").strip(),
        transcription_timeout_seconds=max(30, int(os.getenv("SAGA_AUDIOBOOK_TRANSCRIPTION_TIMEOUT_SECONDS") or "180")),
        tts_timeout_seconds=max(60, int(os.getenv("SAGA_AUDIOBOOK_TTS_TIMEOUT_SECONDS") or "300")),
        tts_failover_attempts=max(1, int(os.getenv("SAGA_AUDIOBOOK_TTS_FAILOVER_ATTEMPTS") or "3")),
    )
