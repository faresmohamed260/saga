"""Production composition root for cross-slice orchestration."""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.production_orchestration.bindings import (
    ActiveDeliverableSource,
    ActiveStageBinding,
    ActiveStageInspector,
    PersistenceDeliverableSink,
)
from packages.production_orchestration.contracts import OrchestrationRequest, OrchestrationResult, StageName, StageOutcomeArtifact
from packages.production_orchestration.packaging import VersionedDeliverablePackager
from packages.production_orchestration.pipeline import ProductionOrchestrationRuntime
from packages.production_orchestration.lineage import active_stage_version_overrides
from packages.observability_runtime import CostRate, UsageGovernanceRuntime


@dataclass(frozen=True)
class ProductionOrchestrationServiceConfig:
    persistence_mode: str = "supabase_postgres"
    persistence_provider: str = "supabase"
    database_url: str = ""
    local_storage_root_dir: str = "analysis_outputs/unified_storage"
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    lineage_version_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    usage_cost_rates: tuple[CostRate, ...] = field(default_factory=tuple)
    release_id: str = ""


class ProductionOrchestrationService:
    def __init__(self, *, config: ProductionOrchestrationServiceConfig, cancellation_checker: Callable[[str], bool] | None = None) -> None:
        self.cancellation_checker = cancellation_checker or (lambda run_id: False)
        profile = PersistenceProfile(
            name="production-orchestration-runtime",
            provider=config.persistence_provider,
            mode=config.persistence_mode,
            database_url=config.database_url,
            application_name="saga-production-orchestration",
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
        inspector = ActiveStageInspector(self.persistence)
        stages = self._stage_bindings(inspector)
        packager = VersionedDeliverablePackager(
            source=ActiveDeliverableSource(self.persistence),
            sink=PersistenceDeliverableSink(self.persistence),
        )
        self.runtime = ProductionOrchestrationRuntime(
            persistence=self.persistence,
            stages=stages,
            packager=packager,
            cancellation_checker=cancellation_checker,
            lineage_version_overrides=active_stage_version_overrides(config.lineage_version_overrides),
            usage_governor=UsageGovernanceRuntime(
                store=self.persistence.usage, cost_rates=config.usage_cost_rates,
                observation_store=self.persistence.observability,
            ),
            release_id=config.release_id,
        )

    @classmethod
    def from_env(cls) -> "ProductionOrchestrationService":
        return cls(config=load_production_orchestration_service_config_from_env())

    def run(self, request: OrchestrationRequest, *, thread_id: str = "") -> OrchestrationResult:
        return self.runtime.invoke(request, thread_id=thread_id or f"production-orchestration-{request.run_id}-{uuid.uuid4().hex[:8]}")

    def close(self) -> None:
        self.persistence.close()

    def _stage_bindings(self, inspector: ActiveStageInspector) -> dict[StageName, ActiveStageBinding]:
        bindings = {
            "analysis_foundation": ActiveStageBinding(inspector=inspector.analysis_foundation, executor=self._run_analysis_foundation),
            "canon_extraction": ActiveStageBinding(inspector=inspector.canon_extraction, executor=self._run_canon_extraction),
            "character_world_modeling": ActiveStageBinding(inspector=inspector.character_world_modeling, executor=self._run_character_world_modeling),
            "generation_planning": ActiveStageBinding(inspector=inspector.generation_planning, executor=self._run_generation_planning),
            "narrative_generation": ActiveStageBinding(inspector=inspector.narrative_generation, executor=self._run_narrative_generation),
            "narrative_support": ActiveStageBinding(inspector=inspector.narrative_support, executor=self._run_narrative_support),
            "visual_generation": ActiveStageBinding(inspector=inspector.visual_generation, executor=self._run_visual_generation),
            "audiobook_generation": ActiveStageBinding(inspector=inspector.audiobook_generation, executor=self._run_audiobook_generation),
        }
        for stage, binding in bindings.items():
            binding.output_builder = lambda request, outcomes, outcome, resolved_stage=stage: inspector.lineage_output(
                resolved_stage, request, outcomes, outcome,
            )
        return bindings

    @staticmethod
    def _run_analysis_foundation(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        del outcomes
        if not request.source_paths:
            raise ValueError("source_paths are required when analysis foundation is not already accepted.")
        from packages.analysis_foundation import AnalysisFoundationRunRequest, AnalysisFoundationService
        _run_scoped_service(
            AnalysisFoundationService.from_env(),
            AnalysisFoundationRunRequest(series_id=request.series_id, source_paths=request.source_paths, thread_id=f"{request.run_id}-analysis"),
        )

    def _run_canon_extraction(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        del outcomes
        from packages.canon_extraction import CanonExtractionRunRequest, CanonExtractionService
        _run_scoped_service(
            CanonExtractionService.from_env(cancellation_checker=lambda: self.cancellation_checker(request.run_id)),
            CanonExtractionRunRequest(series_id=request.series_id, thread_id=f"{request.run_id}-canon"),
        )

    @staticmethod
    def _run_character_world_modeling(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        del outcomes
        from packages.character_world_modeling import CharacterWorldModelingRunRequest, CharacterWorldModelingService
        _run_scoped_service(
            CharacterWorldModelingService.from_env(),
            CharacterWorldModelingRunRequest(series_id=request.series_id, thread_id=f"{request.run_id}-character-world"),
        )

    @staticmethod
    def _run_generation_planning(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        del outcomes
        if not request.premise:
            raise ValueError("premise is required when generation planning is not already accepted.")
        from packages.generation_planning import GenerationPlanningRunRequest, GenerationPlanningService
        _run_scoped_service(
            GenerationPlanningService.from_env(),
            GenerationPlanningRunRequest(
                series_id=request.series_id, premise=request.premise, target_audience=request.target_audience,
                tone=request.tone, desired_chapter_count=request.desired_chapter_count, thread_id=f"{request.run_id}-planning",
            ),
        )

    @staticmethod
    def _run_narrative_generation(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        from packages.narrative_generation import NarrativeGenerationRunRequest, NarrativeGenerationService
        blueprint_id = request.blueprint_id or str(outcomes.get("generation_planning", StageOutcomeArtifact(stage="generation_planning", status="rejected")).output_context.get("blueprint_id") or "")
        _run_scoped_service(
            NarrativeGenerationService.from_env(),
            NarrativeGenerationRunRequest(
                series_id=request.series_id, blueprint_id=blueprint_id, story_id=request.story_id, thread_id=f"{request.run_id}-narrative",
                target_words_per_scene=request.execution_limits.target_words_per_scene,
            ),
        )

    @staticmethod
    def _run_narrative_support(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        from packages.narrative_generation import NarrativeSupportRunRequest, NarrativeSupportService
        story_id = _resolved_story_id(request, outcomes)
        _run_scoped_service(
            NarrativeSupportService.from_env(),
            NarrativeSupportRunRequest(series_id=request.series_id, story_id=story_id, thread_id=f"{request.run_id}-support"),
        )

    @staticmethod
    def _run_visual_generation(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        from packages.visual_generation import VisualGenerationRunRequest, VisualGenerationService
        _run_scoped_service(
            VisualGenerationService.from_env(),
            VisualGenerationRunRequest(
                series_id=request.series_id, story_id=_resolved_story_id(request, outcomes),
                thread_id=f"{request.run_id}-visual",
                max_attempts=request.execution_limits.max_visual_attempts or request.max_attempts,
                include_types=tuple(request.execution_limits.visual_include_types),
                max_renders_per_type=request.execution_limits.max_visual_renders_per_type,
            ),
        )

    @staticmethod
    def _run_audiobook_generation(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> None:
        from packages.audiobook_generation import AudiobookGenerationRunRequest, AudiobookGenerationService
        _run_scoped_service(
            AudiobookGenerationService.from_env(),
            AudiobookGenerationRunRequest(
                series_id=request.series_id, story_id=_resolved_story_id(request, outcomes),
                run_id=request.audiobook_run_id or f"{request.run_id}-audiobook", max_attempts=request.max_attempts,
                max_chapters=request.execution_limits.audiobook_max_chapters,
                max_segment_chars=request.execution_limits.audiobook_max_segment_chars,
            ),
        )


def load_production_orchestration_service_config_from_env() -> ProductionOrchestrationServiceConfig:
    lineage_raw = str(os.getenv("SAGA_STAGE_LINEAGE_VERSIONS_JSON") or "").strip()
    lineage_overrides = json.loads(lineage_raw) if lineage_raw else {}
    if not isinstance(lineage_overrides, dict):
        raise ValueError("SAGA_STAGE_LINEAGE_VERSIONS_JSON must be a JSON object.")
    cost_rates = _cost_rates_from_env()
    return ProductionOrchestrationServiceConfig(
        persistence_mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip(),
        persistence_provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase").strip(),
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip(),
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage").strip(),
        supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or "").strip(),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or "").strip(),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or "").strip(),
        lineage_version_overrides={str(stage): dict(values) for stage, values in lineage_overrides.items()},
        usage_cost_rates=cost_rates,
        release_id=str(os.getenv("SAGA_RELEASE_ID") or "").strip(),
    )


def _cost_rates_from_env() -> tuple[CostRate, ...]:
    raw = str(os.getenv("SAGA_PROVIDER_COST_RATES_JSON") or "").strip()
    if not raw:
        return ()
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("SAGA_PROVIDER_COST_RATES_JSON must be a JSON array.")
    return tuple(CostRate.model_validate(item) for item in payload)


def _resolved_story_id(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> str:
    if request.story_id:
        return request.story_id
    outcome = outcomes.get("narrative_generation")
    story_id = str((outcome.output_context if outcome else {}).get("story_id") or "")
    if not story_id:
        raise ValueError("A story_id is required for downstream generation.")
    return story_id


def _run_scoped_service(service, request) -> Any:
    try:
        return service.run(request)
    finally:
        service.close()
