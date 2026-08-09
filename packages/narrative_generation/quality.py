"""Quality gates for narrative generation outputs."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field

from packages.generation_planning.contracts import GenerationBlueprintArtifact
from packages.narrative_generation.contracts import (
    ChapterDraftArtifact,
    ContinuityCheckArtifact,
    GeneratedStoryArtifact,
    NarrativeGenerationResult,
)
from packages.narrative_generation.store import blueprint_ref_sets


class NarrativeGenerationQualityMetrics(BaseModel):
    chapter_completeness_rate: float = 1.0
    scene_coverage_rate: float = 1.0
    canon_reference_validity_rate: float = 1.0
    character_reference_validity_rate: float = 1.0
    entity_reference_validity_rate: float = 1.0
    continuity_pass_rate: float = 1.0
    prose_substance_rate: float = 1.0
    live_provider_success_rate: float = 1.0
    pass_quality_gate: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


def evaluate_chapter_continuity(
    *, blueprint: GenerationBlueprintArtifact, chapter: ChapterDraftArtifact, minimum_words: int = 80,
) -> ContinuityCheckArtifact:
    outline = next((item for item in blueprint.chapter_outline if item.chapter_index == chapter.chapter_index), None)
    expected_canon = set(outline.canon_refs if outline else chapter.canon_refs)
    expected_characters = set(outline.character_refs if outline else chapter.character_refs)
    expected_entities = set(outline.entity_refs if outline else chapter.entity_refs)
    actual_canon = set(chapter.canon_refs)
    actual_characters = set(chapter.character_refs)
    actual_entities = set(chapter.entity_refs)
    issues: list[str] = []
    if len(chapter.prose.split()) < minimum_words:
        issues.append("chapter prose is too sparse")
    if expected_canon and not actual_canon.intersection(expected_canon):
        issues.append("missing expected canon reference coverage")
    if expected_characters and not actual_characters.intersection(expected_characters):
        issues.append("missing expected character reference coverage")
    if expected_entities and not actual_entities.intersection(expected_entities):
        issues.append("missing expected entity reference coverage")
    return ContinuityCheckArtifact(
        continuity_check_id=_stable_id("continuity-check", chapter.story_id, chapter.chapter_index),
        series_id=chapter.series_id,
        story_id=chapter.story_id,
        blueprint_id=chapter.blueprint_id,
        chapter_index=chapter.chapter_index,
        passed=not issues,
        issues=issues,
        canon_ref_coverage_rate=_ratio(len(actual_canon.intersection(expected_canon)), len(expected_canon)),
        character_ref_coverage_rate=_ratio(len(actual_characters.intersection(expected_characters)), len(expected_characters)),
        entity_ref_coverage_rate=_ratio(len(actual_entities.intersection(expected_entities)), len(expected_entities)),
        metadata={"agent": "ContinuityGuardAgent"},
    )


def evaluate_narrative_generation(result: NarrativeGenerationResult, *, blueprint: GenerationBlueprintArtifact) -> NarrativeGenerationQualityMetrics:
    expected_chapters = {item.chapter_index for item in blueprint.chapter_outline}
    expected_scenes = {item.scene_id for item in blueprint.scene_plan}
    actual_chapters = {item.chapter_index for item in result.story.chapters}
    actual_scenes = {item.source_scene_id for item in result.scene_prose}
    refs = blueprint_ref_sets(blueprint)
    canon_refs = _collect_refs(result, "canon_refs")
    character_refs = _collect_refs(result, "character_refs")
    entity_refs = _collect_refs(result, "entity_refs")
    invalid_canon = sorted(canon_refs - refs["canon_refs"])
    invalid_characters = sorted(character_refs - refs["character_refs"])
    invalid_entities = sorted(entity_refs - refs["entity_refs"])
    checks = list(result.story.continuity_checks or [])
    substantive_chapters = [chapter for chapter in result.story.chapters if len(chapter.prose.split()) >= 80]
    live_provider_successes = [
        scene
        for scene in result.scene_prose
        if (scene.metadata or {}).get("reasoning_status") == "ok"
        and not dict((scene.metadata or {}).get("request_metadata") or {}).get("deterministic_fallback")
    ]
    metrics = NarrativeGenerationQualityMetrics(
        chapter_completeness_rate=_ratio(len(expected_chapters & actual_chapters), len(expected_chapters)),
        scene_coverage_rate=_ratio(len(expected_scenes & actual_scenes), len(expected_scenes)),
        canon_reference_validity_rate=_valid_rate(canon_refs, invalid_canon),
        character_reference_validity_rate=_valid_rate(character_refs, invalid_characters),
        entity_reference_validity_rate=_valid_rate(entity_refs, invalid_entities),
        continuity_pass_rate=_ratio(len([item for item in checks if item.passed]), len(checks)),
        prose_substance_rate=_ratio(len(substantive_chapters), len(result.story.chapters)),
        live_provider_success_rate=_ratio(len(live_provider_successes), len(result.scene_prose)),
        details={
            "missing_chapter_indices": sorted(expected_chapters - actual_chapters),
            "missing_scene_ids": sorted(expected_scenes - actual_scenes),
            "invalid_canon_refs": invalid_canon[:100],
            "invalid_character_refs": invalid_characters[:100],
            "invalid_entity_refs": invalid_entities[:100],
            "continuity_issues": [issue for check in checks for issue in check.issues][:100],
            "fallback_scene_ids": [
                scene.source_scene_id
                for scene in result.scene_prose
                if dict((scene.metadata or {}).get("request_metadata") or {}).get("deterministic_fallback")
            ],
        },
    )
    metrics.pass_quality_gate = (
        metrics.chapter_completeness_rate == 1.0
        and metrics.scene_coverage_rate == 1.0
        and metrics.canon_reference_validity_rate == 1.0
        and metrics.character_reference_validity_rate == 1.0
        and metrics.entity_reference_validity_rate == 1.0
        and metrics.continuity_pass_rate >= 0.95
        and metrics.prose_substance_rate >= 0.95
        and metrics.live_provider_success_rate == 1.0
    )
    return metrics


def require_narrative_semantic_acceptance(story: GeneratedStoryArtifact) -> None:
    """Fail closed before expensive downstream rendering or narration."""
    support = dict((story.metadata or {}).get("semantic_support") or {})
    if support.get("accepted") is True and str(support.get("status") or "") == "accepted":
        return
    raise ValueError(
        f"Story '{story.story_id}' has not passed narrative semantic support validation "
        f"(status={support.get('status') or 'missing'})."
    )


def require_narrative_generation_acceptance(
    result: NarrativeGenerationResult, *, blueprint: GenerationBlueprintArtifact,
) -> NarrativeGenerationQualityMetrics:
    metrics = evaluate_narrative_generation(result, blueprint=blueprint)
    if not metrics.pass_quality_gate:
        raise ValueError(f"Story '{result.story.story_id}' failed narrative generation quality: {metrics.details}")
    return metrics


def _collect_refs(result: NarrativeGenerationResult, field: str) -> set[str]:
    values: set[str] = set(getattr(result.story, field, []) or [])
    for chapter in result.story.chapters:
        values.update(getattr(chapter, field, []) or [])
    for scene in result.scene_prose:
        values.update(getattr(scene, field, []) or [])
    return {str(value or "").strip() for value in values if str(value or "").strip()}


def _valid_rate(values: set[str], invalid_values: list[str]) -> float:
    if not values:
        return 1.0
    return _ratio(len(values) - len(invalid_values), len(values))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = ":".join([prefix, *(str(item or "") for item in parts)])
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"
