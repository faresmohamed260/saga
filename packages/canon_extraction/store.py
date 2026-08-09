"""Persistence mapping for canon extraction artifacts."""

from __future__ import annotations

import re
from typing import Any

from packages.analysis_foundation.contracts import BookArtifact, CanonicalIdentityBundle, ChapterArtifact, SceneArtifact
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.canon_extraction.contracts import EntityArtifact, EventArtifact, RelationshipArtifact, TimelineArtifact
from packages.persistence_runtime import PersistenceRuntimeClient


class CanonExtractionStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.analysis = AnalysisFoundationStore(persistence)

    def load_series_context(self, *, series_id: str) -> dict[str, Any]:
        books = self.analysis.list_books(series_id=series_id)
        book_map = {book.book_id: book for book in books}
        chapters: list[ChapterArtifact] = []
        scenes: list[SceneArtifact] = []
        for book in books:
            chapters.extend(self.analysis.list_chapters(book_id=book.book_id))
            scenes.extend(self.analysis.list_scenes(book_id=book.book_id))
        scenes.sort(key=lambda item: (item.book_id, item.chapter_index, item.scene_index))
        chapters.sort(key=lambda item: (item.book_id, item.chapter_index))
        identity_bundle = self.analysis.load_identity_bundle(series_id=series_id)
        return {
            "series_id": series_id,
            "books": books,
            "book_map": book_map,
            "chapters": chapters,
            "scenes": scenes,
            "identity_bundle": identity_bundle,
        }

    def replace_events(self, *, series_id: str, events: list[EventArtifact]) -> list[EventArtifact]:
        self.persistence.library.delete_records(record_type="event", series_id=series_id)
        persisted: list[EventArtifact] = []
        for event in events:
            payload = self.persistence.library.upsert_record(
                event.event_id,
                record_type="event",
                series_id=event.series_id,
                book_id=event.book_id,
                scene_id=event.scene_id,
                title=event.title,
                ordinal=event.event_index,
                payload=event.model_dump(),
            )
            persisted.append(EventArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_entities(self, *, series_id: str, entities: list[EntityArtifact]) -> list[EntityArtifact]:
        self.persistence.library.delete_records(record_type="entity", series_id=series_id)
        persisted: list[EntityArtifact] = []
        for entity in entities:
            payload = self.persistence.library.upsert_record(
                entity.entity_id,
                record_type="entity",
                series_id=entity.series_id,
                title=entity.canonical_name,
                payload=entity.model_dump(),
            )
            persisted.append(EntityArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_relationships(self, *, series_id: str, relationships: list[RelationshipArtifact]) -> list[RelationshipArtifact]:
        self.persistence.library.delete_records(record_type="relationship", series_id=series_id)
        persisted: list[RelationshipArtifact] = []
        for relationship in relationships:
            payload = self.persistence.library.upsert_record(
                relationship.relationship_id,
                record_type="relationship",
                series_id=relationship.series_id,
                title=f"{relationship.source_ref}:{relationship.relationship_type}:{relationship.target_ref}",
                payload=relationship.model_dump(),
            )
            persisted.append(RelationshipArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_timeline(self, *, series_id: str, timeline: list[TimelineArtifact]) -> list[TimelineArtifact]:
        self.persistence.library.delete_records(record_type="timeline", series_id=series_id)
        persisted: list[TimelineArtifact] = []
        for item in timeline:
            payload = self.persistence.library.upsert_record(
                item.timeline_id,
                record_type="timeline",
                series_id=item.series_id,
                book_id=item.book_id,
                scene_id=item.scene_id,
                title=item.title,
                ordinal=item.sequence_index,
                payload=item.model_dump(),
            )
            persisted.append(TimelineArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def delete_stage_jobs(self, *, series_id: str, stage_name: str) -> int:
        rows = self.persistence.library.list_records(record_type="canon_extraction_job", series_id=series_id, limit=10000)
        deleted = 0
        for row in rows:
            payload = dict(row.get("payload") or {})
            if payload.get("stage_name") != stage_name:
                continue
            deleted += self.persistence.library.delete_records(record_type="canon_extraction_job", series_id=series_id, scene_id=str(payload.get("job_id") or ""))
        return deleted

    def upsert_stage_job(
        self,
        *,
        series_id: str,
        stage_name: str,
        job_id: str,
        job_index: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "series_id": series_id,
            "stage_name": stage_name,
            "job_id": job_id,
            "job_index": int(job_index),
            **dict(payload or {}),
        }
        return self.persistence.library.upsert_record(
            f"canon-job-{series_id}-{stage_name}-{job_id}",
            record_type="canon_extraction_job",
            series_id=series_id,
            scene_id=job_id,
            title=f"{stage_name}:{job_id}",
            ordinal=int(job_index),
            payload=record,
        )

    def list_stage_jobs(self, *, series_id: str, stage_name: str) -> dict[str, dict[str, Any]]:
        rows = self.persistence.library.list_records(record_type="canon_extraction_job", series_id=series_id, limit=10000)
        results: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = dict(row.get("payload") or {})
            if payload.get("stage_name") != stage_name:
                continue
            job_id = str(payload.get("job_id") or "").strip()
            if job_id:
                results[job_id] = payload
        return results

    def list_events(self, *, series_id: str) -> list[EventArtifact]:
        return _validated_records(self.persistence.library.list_records(record_type="event", series_id=series_id, limit=10000), EventArtifact)

    def list_entities(self, *, series_id: str) -> list[EntityArtifact]:
        return _validated_records(self.persistence.library.list_records(record_type="entity", series_id=series_id, limit=10000), EntityArtifact)

    def list_relationships(self, *, series_id: str) -> list[RelationshipArtifact]:
        return _validated_records(self.persistence.library.list_records(record_type="relationship", series_id=series_id, limit=10000), RelationshipArtifact)

    def list_timeline(self, *, series_id: str) -> list[TimelineArtifact]:
        results = _validated_records(self.persistence.library.list_records(record_type="timeline", series_id=series_id, limit=10000), TimelineArtifact)
        return sorted(results, key=lambda item: item.sequence_index)


def _validated_records(rows: list[dict[str, Any]], model_type):
    results = []
    for row in rows:
        payload = dict(row.get("payload") or {})
        if not payload:
            continue
        results.append(model_type.model_validate(payload))
    return results


def normalize_entity_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    cleaned = cleaned.strip(" ,.;:!?\"'()[]{}")
    return re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE).strip()
