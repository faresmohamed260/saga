"""Dependency and selection policy for the production pipeline."""

from __future__ import annotations

from packages.production_orchestration.contracts import OrchestrationRequest, StageName


STAGE_ORDER: tuple[StageName, ...] = (
    "analysis_foundation",
    "canon_extraction",
    "character_world_modeling",
    "generation_planning",
    "narrative_generation",
    "narrative_support",
    "visual_generation",
    "audiobook_generation",
    "artifact_packaging",
)

STAGE_DEPENDENCIES: dict[StageName, tuple[StageName, ...]] = {
    "analysis_foundation": (),
    "canon_extraction": ("analysis_foundation",),
    "character_world_modeling": ("canon_extraction",),
    "generation_planning": ("character_world_modeling",),
    "narrative_generation": ("generation_planning",),
    "narrative_support": ("narrative_generation",),
    "visual_generation": ("narrative_support",),
    "audiobook_generation": ("narrative_support",),
    "artifact_packaging": ("narrative_support",),
}


def resolve_stage_plan(request: OrchestrationRequest) -> list[StageName]:
    requested = set(request.selected_stages)
    expanded: set[StageName] = set()

    def add(stage: StageName) -> None:
        if stage in expanded:
            return
        for dependency in STAGE_DEPENDENCIES[stage]:
            add(dependency)
        expanded.add(stage)

    for stage in requested:
        add(stage)
    return [stage for stage in STAGE_ORDER if stage in expanded]
