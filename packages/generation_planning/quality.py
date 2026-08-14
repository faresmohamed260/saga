"""Reusable quality gates for generation planning outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.generation_planning.contracts import GenerationBlueprintArtifact, GenerationPlanningResult


class GenerationPlanningQualityMetrics(BaseModel):
    canon_reference_validity_rate: float = 1.0
    character_reference_validity_rate: float = 1.0
    entity_reference_validity_rate: float = 1.0
    outline_completeness_rate: float = 1.0
    scene_plan_completeness_rate: float = 1.0
    visual_requirement_rate: float = 1.0
    audio_requirement_rate: float = 1.0
    pass_quality_gate: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


def has_live_planning_provider_proof(blueprint: GenerationBlueprintArtifact) -> bool:
    metadata = dict(blueprint.metadata or {})
    request_metadata = dict(metadata.get("request_metadata") or {})
    return (
        bool(str(metadata.get("reasoning_provider") or "").strip())
        and bool(str(metadata.get("reasoning_model") or "").strip())
        and str(metadata.get("reasoning_status") or "").strip() == "ok"
        and not bool(request_metadata.get("fallback_used"))
        and not bool(request_metadata.get("deterministic_fallback"))
    )


def evaluate_generation_blueprint(
    result: GenerationPlanningResult,
    *,
    valid_canon_refs: set[str],
    valid_character_refs: set[str],
    valid_entity_refs: set[str],
) -> GenerationPlanningQualityMetrics:
    blueprint = result.blueprint
    canon_refs = _refs(blueprint.canon_refs)
    character_refs = _refs(blueprint.character_refs)
    entity_refs = _refs(blueprint.entity_refs)
    for chapter in blueprint.chapter_outline:
        canon_refs.extend(_refs(chapter.canon_refs))
        character_refs.extend(_refs(chapter.character_refs))
        entity_refs.extend(_refs(chapter.entity_refs))
    for scene in blueprint.scene_plan:
        canon_refs.extend(_refs(scene.canon_refs))
        character_refs.extend(_refs(scene.character_refs))
        entity_refs.extend(_refs(scene.entity_refs))

    invalid_canon = sorted({ref for ref in canon_refs if ref not in valid_canon_refs})
    invalid_characters = sorted({ref for ref in character_refs if ref not in valid_character_refs})
    invalid_entities = sorted({ref for ref in entity_refs if ref not in valid_entity_refs})

    chapter_count = max(1, int(result.intent.desired_chapter_count or 1))
    complete_chapters = [
        item
        for item in blueprint.chapter_outline
        if item.chapter_index > 0 and item.title.strip() and item.goal.strip() and item.canon_refs
    ]
    scenes = list(blueprint.scene_plan or [])
    complete_scenes = [
        item
        for item in scenes
        if item.scene_id.strip() and item.summary.strip() and item.purpose.strip() and item.canon_refs and item.character_refs
    ]
    visual_scenes = [item for item in scenes if item.visual_requirements]
    audio_scenes = [item for item in scenes if item.audio_requirements]
    expected_chapter_indices = list(range(1, chapter_count + 1))
    actual_chapter_indices = [item.chapter_index for item in blueprint.chapter_outline]
    expected_scene_keys = {
        (chapter_index, scene_index)
        for chapter_index in expected_chapter_indices
        for scene_index in (1, 2)
    }
    actual_scene_keys = [(item.chapter_index, item.scene_index) for item in scenes]
    structure_valid = (
        actual_chapter_indices == expected_chapter_indices
        and len(actual_scene_keys) == len(expected_scene_keys)
        and set(actual_scene_keys) == expected_scene_keys
    )

    metrics = GenerationPlanningQualityMetrics(
        canon_reference_validity_rate=_valid_rate(canon_refs, invalid_canon),
        character_reference_validity_rate=_valid_rate(character_refs, invalid_characters),
        entity_reference_validity_rate=_valid_rate(entity_refs, invalid_entities),
        outline_completeness_rate=_ratio(len(complete_chapters), chapter_count),
        scene_plan_completeness_rate=_ratio(len(complete_scenes), len(scenes)),
        visual_requirement_rate=_ratio(len(visual_scenes), len(scenes)),
        audio_requirement_rate=_ratio(len(audio_scenes), len(scenes)),
        details={
            "invalid_canon_refs": invalid_canon[:100],
            "invalid_character_refs": invalid_characters[:100],
            "invalid_entity_refs": invalid_entities[:100],
            "chapter_outline_count": len(blueprint.chapter_outline),
            "scene_plan_count": len(scenes),
            "expected_chapter_indices": expected_chapter_indices,
            "actual_chapter_indices": actual_chapter_indices,
            "duplicate_scene_keys": len(actual_scene_keys) != len(set(actual_scene_keys)),
            "structure_valid": structure_valid,
        },
    )
    metrics.pass_quality_gate = (
        metrics.canon_reference_validity_rate == 1.0
        and metrics.character_reference_validity_rate == 1.0
        and metrics.entity_reference_validity_rate == 1.0
        and metrics.outline_completeness_rate >= 1.0
        and metrics.scene_plan_completeness_rate >= 0.95
        and metrics.visual_requirement_rate >= 0.95
        and metrics.audio_requirement_rate >= 0.95
        and structure_valid
    )
    return metrics


def _refs(values: list[str]) -> list[str]:
    return [str(value or "").strip() for value in values if str(value or "").strip()]


def _valid_rate(values: list[str], invalid_values: list[str]) -> float:
    if not values:
        return 1.0
    return _ratio(len(values) - len(invalid_values), len(values))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)
