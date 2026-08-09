"""Persistence mapping for narrative generation artifacts."""

from __future__ import annotations

from typing import Any

from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.generation_planning.contracts import GenerationBlueprintArtifact
from packages.generation_planning.store import GenerationPlanningStore
from packages.narrative_generation.contracts import (
    ChapterDraftArtifact,
    ContinuityCheckArtifact,
    GeneratedStoryArtifact,
    NarrativeSupportDecisionArtifact,
    RevisionRecordArtifact,
    SceneSupportAuditArtifact,
    SceneProseArtifact,
)
from packages.persistence_runtime import PersistenceRuntimeClient


class NarrativeGenerationStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.generation_planning = GenerationPlanningStore(persistence)
        self.canon = CanonExtractionStore(persistence)
        self.character_world = CharacterWorldModelingStore(persistence)

    def load_series_context(self, *, series_id: str, blueprint_id: str = "") -> dict[str, Any]:
        source_context = self.canon.load_series_context(series_id=series_id)
        blueprints = self.generation_planning.list_blueprints(series_id=series_id)
        if blueprint_id:
            blueprints = [item for item in blueprints if item.blueprint_id == blueprint_id]
        blueprint = blueprints[0] if blueprints else None
        return {
            "series_id": series_id,
            "blueprint": blueprint,
            "books": list(source_context.get("books") or []),
            "source_scenes": list(source_context.get("scenes") or []),
            "events": self.canon.list_events(series_id=series_id),
            "entities": self.canon.list_entities(series_id=series_id),
            "relationships": self.canon.list_relationships(series_id=series_id),
            "timeline": self.canon.list_timeline(series_id=series_id),
            "character_profiles": self.character_world.list_character_profiles(series_id=series_id),
            "stable_character_states": self.character_world.list_stable_character_states(series_id=series_id),
            "world_states": self.character_world.list_world_states(series_id=series_id),
        }

    def load_story(self, *, series_id: str, story_id: str) -> GeneratedStoryArtifact:
        rows = self.persistence.stories.list_stories(series_id=series_id, limit=1000)
        row = next((item for item in rows if str(item.get("story_id") or "") == story_id), None)
        if row is None:
            raise FileNotFoundError(f"Generated story '{story_id}' was not found for series '{series_id}'.")
        return GeneratedStoryArtifact.model_validate(dict(row.get("payload") or {}))

    def list_scene_prose(self, *, series_id: str, story_id: str) -> list[SceneProseArtifact]:
        rows = self.persistence.library.list_records(
            record_type="narrative_scene_prose",
            series_id=series_id,
            scene_id=story_id,
            limit=5000,
        )
        scenes = [SceneProseArtifact.model_validate(dict(row.get("payload") or {})) for row in rows]
        scenes.sort(key=lambda item: (item.chapter_index, item.scene_index))
        return scenes

    def replace_scene_prose(self, *, series_id: str, story_id: str, scenes: list[SceneProseArtifact]) -> list[SceneProseArtifact]:
        self._delete_story_records(series_id=series_id, story_id=story_id, record_type="narrative_scene_prose")
        persisted: list[SceneProseArtifact] = []
        for item in scenes:
            payload = self.persistence.library.upsert_record(
                item.scene_prose_id,
                record_type="narrative_scene_prose",
                series_id=series_id,
                scene_id=story_id,
                title=item.title,
                ordinal=item.scene_index,
                payload=item.model_dump(),
            )
            persisted.append(SceneProseArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_chapter_drafts(self, *, series_id: str, story_id: str, chapters: list[ChapterDraftArtifact]) -> list[ChapterDraftArtifact]:
        self._delete_story_records(series_id=series_id, story_id=story_id, record_type="narrative_chapter_draft")
        persisted: list[ChapterDraftArtifact] = []
        for item in chapters:
            payload = self.persistence.library.upsert_record(
                item.chapter_draft_id,
                record_type="narrative_chapter_draft",
                series_id=series_id,
                scene_id=story_id,
                title=item.title,
                ordinal=item.chapter_index,
                payload=item.model_dump(),
            )
            persisted.append(ChapterDraftArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_continuity_checks(self, *, series_id: str, story_id: str, checks: list[ContinuityCheckArtifact]) -> list[ContinuityCheckArtifact]:
        self._delete_story_records(series_id=series_id, story_id=story_id, record_type="narrative_continuity_check")
        persisted: list[ContinuityCheckArtifact] = []
        for item in checks:
            payload = self.persistence.library.upsert_record(
                item.continuity_check_id,
                record_type="narrative_continuity_check",
                series_id=series_id,
                scene_id=story_id,
                title=f"Continuity check {item.chapter_index}",
                ordinal=item.chapter_index,
                payload=item.model_dump(),
            )
            persisted.append(ContinuityCheckArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_revisions(self, *, series_id: str, story_id: str, revisions: list[RevisionRecordArtifact]) -> list[RevisionRecordArtifact]:
        self._delete_story_records(series_id=series_id, story_id=story_id, record_type="narrative_revision")
        persisted: list[RevisionRecordArtifact] = []
        for item in revisions:
            payload = self.persistence.library.upsert_record(
                item.revision_id,
                record_type="narrative_revision",
                series_id=series_id,
                scene_id=story_id,
                title=item.reason[:160],
                ordinal=item.chapter_index,
                payload=item.model_dump(),
            )
            persisted.append(RevisionRecordArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_support_audits(
        self,
        *,
        series_id: str,
        story_id: str,
        audits: list[SceneSupportAuditArtifact],
    ) -> list[SceneSupportAuditArtifact]:
        self._delete_story_records(series_id=series_id, story_id=story_id, record_type="narrative_support_audit")
        persisted: list[SceneSupportAuditArtifact] = []
        for item in audits:
            payload = self.persistence.library.upsert_record(
                item.audit_id,
                record_type="narrative_support_audit",
                series_id=series_id,
                scene_id=story_id,
                title=f"Support audit {item.source_scene_id}",
                ordinal=item.evaluation_round,
                payload=item.model_dump(),
            )
            persisted.append(SceneSupportAuditArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def upsert_support_decision(self, decision: NarrativeSupportDecisionArtifact) -> NarrativeSupportDecisionArtifact:
        payload = self.persistence.library.upsert_record(
            decision.decision_id,
            record_type="narrative_support_decision",
            series_id=decision.series_id,
            scene_id=decision.story_id,
            title=f"Narrative support decision: {decision.status}",
            payload=decision.model_dump(),
        )
        return NarrativeSupportDecisionArtifact.model_validate(dict(payload.get("payload") or {}))

    def upsert_story(self, story: GeneratedStoryArtifact) -> GeneratedStoryArtifact:
        payload = self.persistence.stories.upsert_story(
            story.story_id,
            series_id=story.series_id,
            title=story.title,
            payload=story.model_dump(),
        )
        return GeneratedStoryArtifact.model_validate(dict(payload.get("payload") or {}))

    def _delete_story_records(self, *, series_id: str, story_id: str, record_type: str) -> None:
        self.persistence.library.delete_records(record_type=record_type, series_id=series_id, scene_id=story_id)


def blueprint_ref_sets(blueprint: GenerationBlueprintArtifact) -> dict[str, set[str]]:
    canon_refs = set(blueprint.canon_refs)
    character_refs = set(blueprint.character_refs)
    entity_refs = set(blueprint.entity_refs)
    for chapter in blueprint.chapter_outline:
        canon_refs.update(chapter.canon_refs)
        character_refs.update(chapter.character_refs)
        entity_refs.update(chapter.entity_refs)
    for scene in blueprint.scene_plan:
        canon_refs.update(scene.canon_refs)
        character_refs.update(scene.character_refs)
        entity_refs.update(scene.entity_refs)
    return {
        "canon_refs": {item for item in canon_refs if item},
        "character_refs": {item for item in character_refs if item},
        "entity_refs": {item for item in entity_refs if item},
    }
