"""Persistence mapping for audiobook-generation artifacts and audio objects."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from packages.audiobook_generation.contracts import (
    AudioQualityDecisionArtifact,
    AudioSynthesisArtifact,
    AudiobookChapterArtifact,
    AudiobookDecisionArtifact,
    AudiobookManifestArtifact,
    AudiobookPlanArtifact,
    NarrationSegmentArtifact,
)
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.narrative_generation.quality import require_narrative_semantic_acceptance
from packages.persistence_runtime import PersistenceRuntimeClient


T = TypeVar("T", bound=BaseModel)


class AudiobookGenerationStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.narrative = NarrativeGenerationStore(persistence)

    def load_context(self, *, series_id: str, story_id: str) -> dict[str, Any]:
        story = self.narrative.load_story(series_id=series_id, story_id=story_id)
        require_narrative_semantic_acceptance(story)
        return {
            "story": story,
            "scene_prose": self.narrative.list_scene_prose(series_id=series_id, story_id=story_id),
            **self.narrative.load_series_context(series_id=series_id, blueprint_id=story.blueprint_id),
        }

    def upsert_plan(self, item: AudiobookPlanArtifact) -> AudiobookPlanArtifact:
        self.persistence.audiobooks.upsert_run(
            item.run_id,
            series_id=item.series_id,
            title=item.title,
            status="planned",
            payload={"story_id": item.story_id, "plan": item.model_dump()},
        )
        return self._upsert_record("audiobook_plan", item.run_id, item.series_id, item.run_id, item, AudiobookPlanArtifact)

    def replace_segments(self, *, series_id: str, story_id: str, run_id: str, items: list[NarrationSegmentArtifact]) -> list[NarrationSegmentArtifact]:
        return self._replace("audiobook_narration_segment", series_id, story_id, run_id, items, NarrationSegmentArtifact, "segment_id")

    def replace_syntheses(self, *, series_id: str, story_id: str, run_id: str, items: list[AudioSynthesisArtifact]) -> list[AudioSynthesisArtifact]:
        return self._replace("audiobook_synthesis", series_id, story_id, run_id, items, AudioSynthesisArtifact, "synthesis_id")

    def replace_audits(self, *, series_id: str, story_id: str, run_id: str, items: list[AudioQualityDecisionArtifact]) -> list[AudioQualityDecisionArtifact]:
        return self._replace("audiobook_quality_audit", series_id, story_id, run_id, items, AudioQualityDecisionArtifact, "audit_id")

    def replace_chapters(self, *, series_id: str, story_id: str, run_id: str, items: list[AudiobookChapterArtifact]) -> list[AudiobookChapterArtifact]:
        persisted = self._replace("audiobook_chapter_artifact", series_id, story_id, run_id, items, AudiobookChapterArtifact, "chapter_audio_id")
        for item in persisted:
            self.persistence.audiobooks.upsert_chapter(
                item.chapter_audio_id,
                run_id=run_id,
                book_index=1,
                chapter_index=item.chapter_index,
                payload=item.model_dump(),
            )
        return persisted

    def upsert_manifest(self, item: AudiobookManifestArtifact) -> AudiobookManifestArtifact:
        return self._upsert_record("audiobook_manifest", item.manifest_id, item.series_id, item.run_id, item, AudiobookManifestArtifact)

    def upsert_decision(self, item: AudiobookDecisionArtifact) -> AudiobookDecisionArtifact:
        status = "completed" if item.accepted else "rejected"
        current = self.persistence.audiobooks.get_run(item.run_id) or {}
        run_payload = dict(current.get("payload") or {})
        run_payload["story_id"] = item.story_id
        run_payload["decision"] = item.model_dump()
        self.persistence.audiobooks.upsert_run(
            item.run_id,
            series_id=item.series_id,
            title=str(current.get("title") or item.story_id),
            status=status,
            payload=run_payload,
        )
        return self._upsert_record("audiobook_decision", item.decision_id, item.series_id, item.run_id, item, AudiobookDecisionArtifact)

    def store_segment_audio(self, *, synthesis: AudioSynthesisArtifact, audio_bytes: bytes) -> dict[str, Any]:
        return self.persistence.artifacts.store_bytes(
            artifact_type="audio_output",
            data=audio_bytes,
            filename=f"{synthesis.synthesis_id}.wav",
            content_type="audio/wav",
            series_id=synthesis.series_id,
            story_id=synthesis.story_id,
            run_id=synthesis.run_id,
            chapter_id=f"chapter-{synthesis.chapter_index:03d}",
            provider_name=synthesis.provider_name,
            metadata={"segment_id": synthesis.segment_id, "attempt": synthesis.attempt, "kind": "segment"},
        )

    def store_assembled_audio(
        self,
        *,
        data: bytes,
        filename: str,
        series_id: str,
        story_id: str,
        run_id: str,
        chapter_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.persistence.artifacts.store_bytes(
            artifact_type="audio_output",
            data=data,
            filename=filename,
            content_type="audio/wav",
            series_id=series_id,
            story_id=story_id,
            run_id=run_id,
            chapter_id=chapter_id,
            provider_name="audiobook_generation",
            metadata=dict(metadata or {}),
        )

    def load_audio(self, item: AudioSynthesisArtifact | AudiobookChapterArtifact | AudiobookManifestArtifact) -> bytes:
        return self.persistence.objects.download_bytes(item.bucket_name, item.object_path)

    def list_plan(self, *, series_id: str, story_id: str, run_id: str) -> AudiobookPlanArtifact:
        rows = self._list("audiobook_plan", series_id, story_id, run_id, AudiobookPlanArtifact)
        if not rows:
            raise FileNotFoundError(f"Audiobook plan '{run_id}' was not found.")
        return rows[0]

    def list_segments(self, *, series_id: str, story_id: str, run_id: str) -> list[NarrationSegmentArtifact]:
        return self._list("audiobook_narration_segment", series_id, story_id, run_id, NarrationSegmentArtifact)

    def list_syntheses(self, *, series_id: str, story_id: str, run_id: str) -> list[AudioSynthesisArtifact]:
        return self._list("audiobook_synthesis", series_id, story_id, run_id, AudioSynthesisArtifact)

    def list_audits(self, *, series_id: str, story_id: str, run_id: str) -> list[AudioQualityDecisionArtifact]:
        return self._list("audiobook_quality_audit", series_id, story_id, run_id, AudioQualityDecisionArtifact)

    def list_chapters(self, *, series_id: str, story_id: str, run_id: str) -> list[AudiobookChapterArtifact]:
        return self._list("audiobook_chapter_artifact", series_id, story_id, run_id, AudiobookChapterArtifact)

    def list_manifests(self, *, series_id: str, story_id: str, run_id: str) -> list[AudiobookManifestArtifact]:
        return self._list("audiobook_manifest", series_id, story_id, run_id, AudiobookManifestArtifact)

    def list_decisions(self, *, series_id: str, story_id: str, run_id: str) -> list[AudiobookDecisionArtifact]:
        return self._list("audiobook_decision", series_id, story_id, run_id, AudiobookDecisionArtifact)

    def _replace(self, record_type: str, series_id: str, story_id: str, run_id: str, items: list[T], model: type[T], id_field: str) -> list[T]:
        self.persistence.library.delete_records(record_type=record_type, series_id=series_id, scene_id=run_id)
        persisted = []
        for ordinal, item in enumerate(items, start=1):
            row = self.persistence.library.upsert_record(
                str(getattr(item, id_field)),
                record_type=record_type,
                series_id=series_id,
                scene_id=run_id,
                title=str(getattr(item, "title", "") or getattr(item, "segment_id", "") or getattr(item, id_field)),
                ordinal=ordinal,
                payload=item.model_dump(),
            )
            persisted.append(model.model_validate(dict(row.get("payload") or {})))
        return persisted

    def _list(self, record_type: str, series_id: str, story_id: str, run_id: str, model: type[T]) -> list[T]:
        del story_id
        rows = self.persistence.library.list_records(record_type=record_type, series_id=series_id, scene_id=run_id, limit=10000)
        return [model.model_validate(dict(row.get("payload") or {})) for row in rows]

    def _upsert_record(self, record_type: str, record_id: str, series_id: str, run_id: str, item: T, model: type[T]) -> T:
        row = self.persistence.library.upsert_record(
            record_id,
            record_type=record_type,
            series_id=series_id,
            scene_id=run_id,
            title=str(getattr(item, "title", "") or record_id),
            payload=item.model_dump(),
        )
        return model.model_validate(dict(row.get("payload") or {}))
