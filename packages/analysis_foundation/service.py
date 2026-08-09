"""Production-facing service helpers for the analysis foundation slice."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.analysis_foundation.contracts import AnalysisFoundationResult
from packages.analysis_foundation.narrative_grounding import narrative_grounding_summary
from packages.analysis_foundation.pipeline import AnalysisFoundationRuntime
from packages.identity_runtime import IdentityRuntimeClient, IdentityRuntimeConfig, IdentityRuntimeProfile
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


DEFAULT_PROVIDER_NAME = "modal_xcore_litbank"


@dataclass(frozen=True)
class AnalysisFoundationServiceConfig:
    persistence_profile_name: str = "analysis-foundation-runtime"
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    identity_provider_name: str = DEFAULT_PROVIDER_NAME
    identity_timeout_seconds: int = 300


@dataclass(frozen=True)
class AnalysisFoundationRunRequest:
    series_id: str
    source_paths: list[str]
    book_index_start: int = 1
    thread_id: str = "analysis-foundation"


class AnalysisFoundationService:
    def __init__(self, *, config: AnalysisFoundationServiceConfig) -> None:
        self.config = config
        profile = PersistenceProfile(
            name=config.persistence_profile_name,
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-analysis-foundation",
            local_storage_root_dir=config.local_storage_root_dir,
        )
        persistence = create_persistence_client(
            profile=profile,
            config=PersistenceRuntimeConfig(
                profile=profile,
                supabase_api_url=config.supabase_api_url,
                supabase_anon_key=config.supabase_anon_key,
                supabase_service_role_key=config.supabase_service_role_key,
            ),
        )
        identity_profile = IdentityRuntimeProfile(
            name="analysis-foundation-identity",
            provider_name=config.identity_provider_name,
            request_timeout_seconds=config.identity_timeout_seconds,
        )
        identity_runtime = IdentityRuntimeClient(
            profile=identity_profile,
            config=IdentityRuntimeConfig(profile=identity_profile),
        )
        self.runtime = AnalysisFoundationRuntime(persistence=persistence, identity_runtime=identity_runtime)

    @classmethod
    def from_env(cls) -> "AnalysisFoundationService":
        return cls(config=load_analysis_foundation_service_config_from_env())

    def run(self, request: AnalysisFoundationRunRequest) -> AnalysisFoundationResult:
        return self.runtime.invoke(
            series_id=request.series_id,
            source_paths=request.source_paths,
            book_index_start=request.book_index_start,
            thread_id=request.thread_id,
        )

    def build_quality_audit(self, *, result: AnalysisFoundationResult, source_paths: list[str]) -> dict[str, Any]:
        identity_bundle = result.identity_bundle
        books = result.books
        chapters = result.chapters
        scenes = result.scenes
        title_rows = [
            {
                "book_id": book.book_id,
                "title": book.title,
                "is_reasonable": bool(str(book.title or "").strip()) and len(str(book.title).split()) <= 20,
            }
            for book in books
        ]
        chapter_counts = {book.book_id: 0 for book in books}
        for chapter in chapters:
            chapter_counts[chapter.book_id] = chapter_counts.get(chapter.book_id, 0) + 1
        scene_counts = {book.book_id: 0 for book in books}
        for scene in scenes:
            scene_counts[scene.book_id] = scene_counts.get(scene.book_id, 0) + 1
        scene_word_counts = [scene.word_count for scene in scenes]
        identity_characters = list(identity_bundle.characters if identity_bundle else [])
        provider_name = str(identity_bundle.provider_name if identity_bundle else "")
        model_name = str((identity_bundle.metadata if identity_bundle else {}).get("model_name") or "")
        return {
            "source_paths": [str(Path(path)) for path in source_paths],
            "book_count": len(books),
            "chapter_count": len(chapters),
            "scene_count": len(scenes),
            "identity_character_count": len(identity_characters),
            "identity_provider_name": provider_name,
            "identity_model_name": model_name,
            "books": [
                {
                    "book_id": book.book_id,
                    "title": book.title,
                    "chapter_count": chapter_counts.get(book.book_id, 0),
                    "scene_count": scene_counts.get(book.book_id, 0),
                    "word_count": book.word_count,
                }
                for book in books
            ],
            "title_quality": title_rows,
            "chapter_quality": {
                "has_chapters": bool(chapters),
                "all_titles_present": all(bool(str(chapter.title or "").strip()) for chapter in chapters),
                "max_chapter_words": max((chapter.word_count for chapter in chapters), default=0),
                "min_chapter_words": min((chapter.word_count for chapter in chapters), default=0),
            },
            "scene_quality": {
                "has_scenes": bool(scenes),
                "deterministic_count_shape": bool(scenes),
                "max_scene_words": max(scene_word_counts, default=0),
                "min_scene_words": min(scene_word_counts, default=0),
            },
            "narrative_grounding_quality": narrative_grounding_summary(scenes),
            "identity_quality": {
                "has_identity_bundle": identity_bundle is not None,
                "has_characters": bool(identity_characters),
                "has_alias_map": bool(identity_bundle.alias_map if identity_bundle else {}),
                "narrator_perspective": str(identity_bundle.narrator.perspective if identity_bundle else ""),
                "top_characters": [character.display_name for character in identity_characters[:8]],
                "review_kept_cluster_count": int((identity_bundle.source_stats if identity_bundle else {}).get("identity_kept_cluster_count") or 0),
                "review_dropped_cluster_count": int((identity_bundle.source_stats if identity_bundle else {}).get("identity_dropped_cluster_count") or 0),
                "review_rejected_alias_count": int((identity_bundle.source_stats if identity_bundle else {}).get("identity_rejected_alias_count") or 0),
                "review_diagnostic_codes": sorted(
                    {
                        str(item.get("code") or "").strip()
                        for item in list(((identity_bundle.metadata if identity_bundle else {}).get("identity_review") or {}).get("diagnostics") or [])
                        if str(item.get("code") or "").strip()
                    }
                ),
            },
            "run_metadata": dict(result.run_metadata or {}),
        }

    def persist_runtime_report(
        self,
        *,
        request: AnalysisFoundationRunRequest,
        result: AnalysisFoundationResult,
        quality_audit: dict[str, Any],
    ) -> dict[str, Any]:
        report_payload = {
            "report_id": f"analysis-foundation-{uuid.uuid4().hex[:12]}",
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "requested_sources": [str(path) for path in request.source_paths],
            "book_index_start": request.book_index_start,
            "generated_at": int(time.time()),
            "result_summary": {
                "book_count": len(result.books),
                "chapter_count": len(result.chapters),
                "scene_count": len(result.scenes),
                "identity_provider_name": str(result.identity_bundle.provider_name if result.identity_bundle else ""),
                "identity_character_count": len(result.identity_bundle.characters if result.identity_bundle else []),
            },
            "quality_audit": quality_audit,
            "result": result.model_dump(),
        }
        return self.runtime.persistence.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{request.series_id}-{request.thread_id}-analysis-foundation-report.json",
            payload=report_payload,
            provider_name="analysis_foundation",
            report_kind="validation",
            metadata={
                "series_id": request.series_id,
                "thread_id": request.thread_id,
                "book_count": len(result.books),
            },
        )


def load_analysis_foundation_service_config_from_env() -> AnalysisFoundationServiceConfig:
    return AnalysisFoundationServiceConfig(
        persistence_profile_name=str(os.getenv("SAGA_ANALYSIS_PERSISTENCE_PROFILE") or "analysis-foundation-runtime").strip(),
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip() or "supabase",
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(
            os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        ).strip(),
        identity_provider_name=str(os.getenv("SAGA_ANALYSIS_IDENTITY_PROVIDER") or DEFAULT_PROVIDER_NAME).strip() or DEFAULT_PROVIDER_NAME,
        identity_timeout_seconds=max(30, int(os.getenv("SAGA_ANALYSIS_IDENTITY_TIMEOUT_SECONDS") or "300")),
    )
