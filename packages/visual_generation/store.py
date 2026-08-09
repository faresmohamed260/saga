"""Persistence mapping for visual-generation artifacts."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.canon_extraction.store import CanonExtractionStore
from packages.narrative_generation import require_narrative_semantic_acceptance
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.visual_generation.contracts import (
    CharacterSceneStateArtifact,
    CharacterVisualBaselineArtifact,
    EntityVisualDossierArtifact,
    SceneVisualPlanArtifact,
    VisualGenerationDecisionArtifact,
    VisualPromptArtifact,
    VisualQualityDecisionArtifact,
    VisualRenderArtifact,
)


T = TypeVar("T", bound=BaseModel)


class VisualGenerationStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.narrative = NarrativeGenerationStore(persistence)
        self.canon = CanonExtractionStore(persistence)
        self.character_world = CharacterWorldModelingStore(persistence)

    def load_context(self, *, series_id: str, story_id: str) -> dict[str, Any]:
        story = self.narrative.load_story(series_id=series_id, story_id=story_id)
        require_narrative_semantic_acceptance(story)
        narrative_context = self.narrative.load_series_context(series_id=series_id, blueprint_id=story.blueprint_id)
        return {
            **narrative_context,
            "story": story,
            "scene_prose": self.narrative.list_scene_prose(series_id=series_id, story_id=story_id),
        }

    def replace_baselines(self, *, series_id: str, story_id: str, items: list[CharacterVisualBaselineArtifact]) -> list[CharacterVisualBaselineArtifact]:
        return self._replace("visual_character_baseline", series_id, story_id, items, CharacterVisualBaselineArtifact, "baseline_id")

    def replace_scene_states(self, *, series_id: str, story_id: str, items: list[CharacterSceneStateArtifact]) -> list[CharacterSceneStateArtifact]:
        return self._replace("visual_character_scene_state", series_id, story_id, items, CharacterSceneStateArtifact, "state_id")

    def replace_dossiers(self, *, series_id: str, story_id: str, items: list[EntityVisualDossierArtifact]) -> list[EntityVisualDossierArtifact]:
        return self._replace("visual_entity_dossier", series_id, story_id, items, EntityVisualDossierArtifact, "dossier_id")

    def replace_scene_plans(self, *, series_id: str, story_id: str, items: list[SceneVisualPlanArtifact]) -> list[SceneVisualPlanArtifact]:
        return self._replace("visual_scene_plan", series_id, story_id, items, SceneVisualPlanArtifact, "plan_id")

    def replace_prompts(self, *, series_id: str, story_id: str, items: list[VisualPromptArtifact]) -> list[VisualPromptArtifact]:
        return self._replace("visual_prompt", series_id, story_id, items, VisualPromptArtifact, "prompt_id")

    def replace_renders(self, *, series_id: str, story_id: str, items: list[VisualRenderArtifact]) -> list[VisualRenderArtifact]:
        return self._replace("visual_render", series_id, story_id, items, VisualRenderArtifact, "render_id")

    def replace_audits(self, *, series_id: str, story_id: str, items: list[VisualQualityDecisionArtifact]) -> list[VisualQualityDecisionArtifact]:
        return self._replace("visual_quality_audit", series_id, story_id, items, VisualQualityDecisionArtifact, "audit_id")

    def upsert_decision(self, item: VisualGenerationDecisionArtifact) -> VisualGenerationDecisionArtifact:
        payload = self.persistence.library.upsert_record(
            item.decision_id,
            record_type="visual_generation_decision",
            series_id=item.series_id,
            scene_id=item.story_id,
            title=f"Visual generation: {item.status}",
            payload=item.model_dump(),
        )
        return VisualGenerationDecisionArtifact.model_validate(dict(payload.get("payload") or {}))

    def store_image(self, *, render: VisualRenderArtifact, image_bytes: bytes) -> dict[str, Any]:
        return self.persistence.artifacts.store_bytes(
            artifact_type="generated_image",
            data=image_bytes,
            filename=f"{render.render_id}.png",
            content_type="image/png",
            series_id=render.series_id,
            story_id=render.story_id,
            scene_id=str((render.metadata or {}).get("source_scene_id") or ""),
            entity_id=render.target_ref,
            provider_name=render.provider_name,
            metadata={
                "render_id": render.render_id,
                "prompt_id": render.prompt_id,
                "target_type": render.target_type,
                "seed": render.seed,
                "attempt": render.attempt,
                "workflow_mode": (render.metadata or {}).get("workflow_mode"),
            },
            record_type="generated_image",
        )

    def load_image(self, render: VisualRenderArtifact) -> bytes:
        return self.persistence.objects.download_bytes(render.bucket_name, render.object_path)

    def list_baselines(self, *, series_id: str, story_id: str) -> list[CharacterVisualBaselineArtifact]:
        return self._list("visual_character_baseline", series_id, story_id, CharacterVisualBaselineArtifact)

    def list_scene_states(self, *, series_id: str, story_id: str) -> list[CharacterSceneStateArtifact]:
        return self._list("visual_character_scene_state", series_id, story_id, CharacterSceneStateArtifact)

    def list_dossiers(self, *, series_id: str, story_id: str) -> list[EntityVisualDossierArtifact]:
        return self._list("visual_entity_dossier", series_id, story_id, EntityVisualDossierArtifact)

    def list_scene_plans(self, *, series_id: str, story_id: str) -> list[SceneVisualPlanArtifact]:
        return self._list("visual_scene_plan", series_id, story_id, SceneVisualPlanArtifact)

    def list_prompts(self, *, series_id: str, story_id: str) -> list[VisualPromptArtifact]:
        return self._list("visual_prompt", series_id, story_id, VisualPromptArtifact)

    def list_renders(self, *, series_id: str, story_id: str) -> list[VisualRenderArtifact]:
        return self._list("visual_render", series_id, story_id, VisualRenderArtifact)

    def list_audits(self, *, series_id: str, story_id: str) -> list[VisualQualityDecisionArtifact]:
        return self._list("visual_quality_audit", series_id, story_id, VisualQualityDecisionArtifact)

    def _replace(self, record_type: str, series_id: str, story_id: str, items: list[T], model: type[T], id_field: str) -> list[T]:
        self.persistence.library.delete_records(record_type=record_type, series_id=series_id, scene_id=story_id)
        persisted: list[T] = []
        for ordinal, item in enumerate(items, start=1):
            payload = self.persistence.library.upsert_record(
                str(getattr(item, id_field)),
                record_type=record_type,
                series_id=series_id,
                scene_id=story_id,
                title=str(getattr(item, "canonical_name", "") or getattr(item, "title", "") or getattr(item, "target_ref", "")),
                ordinal=ordinal,
                payload=item.model_dump(),
            )
            persisted.append(model.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def _list(self, record_type: str, series_id: str, story_id: str, model: type[T]) -> list[T]:
        rows = self.persistence.library.list_records(
            record_type=record_type,
            series_id=series_id,
            scene_id=story_id,
            limit=10000,
        )
        return [model.model_validate(dict(row.get("payload") or {})) for row in rows]
