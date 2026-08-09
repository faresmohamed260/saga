"""Deterministic LangGraph pipeline for canon extraction."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from packages.agent_runtime import SqlCheckpointSaver
from packages.analysis_foundation.contracts import BookArtifact, CanonicalIdentityBundle, ChapterArtifact, SceneArtifact
from packages.canon_extraction.contracts import (
    CanonExtractionResult,
    EntityArtifact,
    EventArtifact,
    RelationshipArtifact,
    TimelineArtifact,
)
from packages.canon_extraction.store import CanonExtractionStore, normalize_entity_name
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient
from packages.runtime_common import CancellationChecker, raise_if_cancelled

SCENE_SLICE_BATCH_SIZE = max(1, int(os.getenv("SAGA_CANON_SCENE_SLICE_BATCH_SIZE") or "8"))
CANON_EXTRACTION_PARALLELISM = max(1, int(os.getenv("SAGA_CANON_EXTRACTION_PARALLELISM") or "4"))
MAX_EVENTS_PER_SCENE = max(1, int(os.getenv("SAGA_CANON_MAX_EVENTS_PER_SCENE") or "5"))
MAX_ENTITIES_PER_SCENE = max(1, int(os.getenv("SAGA_CANON_MAX_ENTITIES_PER_SCENE") or "24"))
MAX_RELATIONSHIPS_PER_SCENE = max(1, int(os.getenv("SAGA_CANON_MAX_RELATIONSHIPS_PER_SCENE") or "14"))
CANON_RESUME_STAGES = {
    value.strip()
    for value in str(os.getenv("SAGA_CANON_RESUME_STAGES") or "").split(",")
    if value.strip()
}
ALLOWED_ENTITY_TYPES = {"location", "object", "creature", "organization", "artifact", "concept"}
ALLOWED_RELATIONSHIP_TYPES = {
    "ally",
    "antagonistic",
    "artifact_usage",
    "co_conspirator",
    "companion",
    "curiosity",
    "family",
    "friendship",
    "location_association",
    "manipulation",
    "marriage",
    "protective",
    "reference",
    "request",
    "romantic",
    "sibling",
}


class CanonExtractionState(TypedDict, total=False):
    series_id: str
    books: list[dict[str, Any]]
    chapters: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    identity_bundle: dict[str, Any]
    events: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    run_metadata: dict[str, Any]
    error: str


class SceneReference(BaseModel):
    scene_id: str
    chapter_index: int
    scene_index: int
    summary: str = ""
    excerpt: str = ""
    narrative_grounding: dict[str, Any] = Field(default_factory=dict)


class SceneSliceReference(BaseModel):
    scene_id: str
    chapter_index: int
    scene_index: int
    chunk_index: int
    summary: str = ""
    excerpt: str = ""
    narrative_grounding: dict[str, Any] = Field(default_factory=dict)


class SceneEventExtraction(BaseModel):
    scene_id: str
    title: str
    summary: str
    event_type: str
    participant_names: list[str] = Field(default_factory=list)
    entity_names: list[str] = Field(default_factory=list)


class SceneEntityExtraction(BaseModel):
    canonical_name: str
    entity_type: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    scene_ids: list[str] = Field(default_factory=list)


class SceneRelationshipExtraction(BaseModel):
    source_name: str
    target_name: str
    relationship_type: str
    description: str = ""
    scene_ids: list[str] = Field(default_factory=list)


class EventsPayload(BaseModel):
    events: list[SceneEventExtraction] = Field(default_factory=list)


class EntitiesPayload(BaseModel):
    entities: list[SceneEntityExtraction] = Field(default_factory=list)


class RelationshipsPayload(BaseModel):
    relationships: list[SceneRelationshipExtraction] = Field(default_factory=list)


class EventAgent:
    def __init__(self, *, store: CanonExtractionStore, reasoning_runtime: ReasoningRuntimeClient, cancellation_checker: CancellationChecker | None = None) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime
        self.cancellation_checker = cancellation_checker

    def run(
        self,
        *,
        series_id: str,
        books: list[BookArtifact],
        chapters: list[ChapterArtifact],
        scenes: list[SceneArtifact],
        identity_bundle: CanonicalIdentityBundle,
    ) -> dict[str, Any]:
        book_map = {book.book_id: book for book in books}
        chapter_map = {(chapter.book_id, chapter.chapter_index): chapter for chapter in chapters}
        scene_groups = _group_scenes_by_chapter(scenes)
        all_events: list[EventArtifact] = []
        request_metadata_rows: list[dict[str, Any]] = []
        seen_event_keys: set[tuple[str, str, str, str]] = set()
        event_counts_by_scene: dict[str, int] = {}
        jobs: list[dict[str, Any]] = []
        for job_index, ((book_id, chapter_index), chapter_scenes) in enumerate(scene_groups.items()):
            chapter = chapter_map.get((book_id, chapter_index))
            if chapter is None:
                continue
            for scene_slices in _batched_scene_slices(chapter_scenes, max_slices_per_batch=SCENE_SLICE_BATCH_SIZE):
                jobs.append(
                    {
                        "job_index": len(jobs),
                        "job_id": _canon_stage_job_id(stage_name="event_extraction", book_id=book_id, chapter_index=chapter_index, scene_slices=scene_slices),
                        "chapter_order": job_index,
                        "book_id": book_id,
                        "chapter_index": chapter_index,
                        "book": book_map[book_id],
                        "chapter": chapter,
                        "chapter_scenes": chapter_scenes,
                        "scene_slices": scene_slices,
                    }
                )

        chapter_events_by_key: dict[tuple[str, int], list[tuple[SceneArtifact, SceneEventExtraction]]] = {}
        resumed_jobs = self.store.list_stage_jobs(series_id=series_id, stage_name="event_extraction") if _resume_stage_enabled("event_extraction") else {}
        if not _resume_stage_enabled("event_extraction"):
            self.store.delete_stage_jobs(series_id=series_id, stage_name="event_extraction")

        def run_job(job: dict[str, Any]) -> dict[str, Any]:
            raise_if_cancelled(self.cancellation_checker)
            runtime = _clone_reasoning_runtime(self.reasoning_runtime)
            started_at = time.perf_counter()
            payloads = self._extract_chapter_events_with_fallback(
                book=job["book"],
                chapter=job["chapter"],
                scene_slices=list(job["scene_slices"]),
                identity_bundle=identity_bundle,
                reasoning_runtime=runtime,
            )
            result = {
                "job_index": int(job["job_index"]),
                "job_id": str(job["job_id"]),
                "book_id": str(job["book_id"]),
                "chapter_index": int(job["chapter_index"]),
                "payloads": [payload.model_dump() for payload in payloads],
                "metadata": _request_metadata_with_job_stats(runtime, started_at=started_at, scene_slice_count=len(job["scene_slices"])),
            }
            self.store.upsert_stage_job(
                series_id=series_id,
                stage_name="event_extraction",
                job_id=str(job["job_id"]),
                job_index=int(job["job_index"]),
                payload=result,
            )
            return {**result, "chapter_scenes": list(job["chapter_scenes"])}

        completed_results = [
            {**resumed_jobs[str(job["job_id"])], "chapter_scenes": list(job["chapter_scenes"])}
            for job in jobs
            if str(job["job_id"]) in resumed_jobs
        ]
        missing_jobs = [job for job in jobs if str(job["job_id"]) not in resumed_jobs]
        for result in _run_ordered_parallel_jobs(missing_jobs, run_job, cancellation_checker=self.cancellation_checker):
            completed_results.append(result)

        for result in sorted(completed_results, key=lambda item: int(item.get("job_index") or 0)):
            request_metadata_rows.append(dict(result.get("metadata") or {}))
            chapter_key = (str(result["book_id"]), int(result["chapter_index"]))
            chapter_events = chapter_events_by_key.setdefault(chapter_key, [])
            chapter_scenes = list(result["chapter_scenes"])
            for raw_payload in list(result["payloads"] or []):
                payload = EventsPayload.model_validate(raw_payload)
                for item in payload.events:
                    resolved_scene = next((row for row in chapter_scenes if row.scene_id == item.scene_id), chapter_scenes[0])
                    event_key = (
                        resolved_scene.scene_id,
                        _normalize_label(item.title),
                        _normalize_label(item.event_type),
                        _normalize_label(item.summary[:120]),
                    )
                    if event_key in seen_event_keys:
                        continue
                    if event_counts_by_scene.get(resolved_scene.scene_id, 0) >= MAX_EVENTS_PER_SCENE:
                        continue
                    seen_event_keys.add(event_key)
                    event_counts_by_scene[resolved_scene.scene_id] = event_counts_by_scene.get(resolved_scene.scene_id, 0) + 1
                    chapter_events.append((resolved_scene, item))

        for (book_id, chapter_index), chapter_scenes in scene_groups.items():
            chapter_events = chapter_events_by_key.get((book_id, chapter_index), [])
            for event_index, (scene, item) in enumerate(chapter_events, start=1):
                narrative_grounding = _scene_narrative_grounding(scene)
                participant_refs = _resolve_participant_refs(
                    _augment_participant_names_from_event_text(
                        item.participant_names,
                        identity_bundle=identity_bundle,
                        event_title=item.title,
                        event_summary=item.summary,
                    ),
                    scene=scene,
                    event_title=item.title,
                    event_summary=item.summary,
                    identity_bundle=identity_bundle,
                    entity_name_to_id={},
                    narrative_grounding=narrative_grounding,
                )
                entity_refs = [_entity_id(name) for name in item.entity_names if _should_keep_entity_name(name, identity_bundle=identity_bundle)]
                all_events.append(
                    EventArtifact(
                        event_id=f"event-{series_id}-{book_id}-{chapter_index:03d}-{event_index:03d}",
                        series_id=series_id,
                        book_id=book_id,
                        scene_id=scene.scene_id,
                        chapter_index=scene.chapter_index,
                        scene_index=scene.scene_index,
                        event_index=event_index,
                        title=item.title,
                        summary=item.summary,
                        event_type=item.event_type,
                        participant_refs=participant_refs,
                        entity_refs=entity_refs,
                        metadata={"reasoning_provider": self.reasoning_runtime.provider_name(), "reasoning_model": self.reasoning_runtime.resolved_model_name()},
                    )
                )
        persisted = self.store.replace_events(series_id=series_id, events=all_events)
        return {"events": [item.model_dump() for item in persisted], "request_metadata_rows": request_metadata_rows}

    def _extract_chapter_events(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> EventsPayload:
        raise_if_cancelled(self.cancellation_checker)
        runtime = reasoning_runtime or self.reasoning_runtime
        prompt = _build_events_prompt(book=book, chapter=chapter, scene_slices=scene_slices, identity_bundle=identity_bundle)
        payload = runtime.generate_json(prompt, strict=True, max_tokens=2600)
        if payload.get("error"):
            raise RuntimeError(f"Event extraction failed: {payload.get('error')}")
        return EventsPayload.model_validate(payload)

    def _extract_chapter_events_with_fallback(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> list[EventsPayload]:
        runtime = reasoning_runtime or self.reasoning_runtime
        try:
            return [
                self._extract_chapter_events(
                    book=book,
                    chapter=chapter,
                    scene_slices=scene_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                )
            ]
        except RuntimeError as exc:
            if not _should_retry_split_extraction_error(exc):
                raise
            try:
                left_slices, right_slices = _split_scene_slices_for_retry(scene_slices)
            except RuntimeError:
                return [_fallback_events_payload_from_scene_slices(scene_slices)]
            return [
                *self._extract_chapter_events_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=left_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                ),
                *self._extract_chapter_events_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=right_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                ),
            ]


class EntityAgent:
    def __init__(self, *, store: CanonExtractionStore, reasoning_runtime: ReasoningRuntimeClient, cancellation_checker: CancellationChecker | None = None) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime
        self.cancellation_checker = cancellation_checker

    def run(
        self,
        *,
        series_id: str,
        books: list[BookArtifact],
        chapters: list[ChapterArtifact],
        scenes: list[SceneArtifact],
        identity_bundle: CanonicalIdentityBundle,
    ) -> dict[str, Any]:
        book_map = {book.book_id: book for book in books}
        chapter_map = {(chapter.book_id, chapter.chapter_index): chapter for chapter in chapters}
        scene_groups = _group_scenes_by_chapter(scenes)
        merged: dict[str, EntityArtifact] = {}
        request_metadata_rows: list[dict[str, Any]] = []
        entity_counts_by_scene: dict[str, int] = {}
        jobs: list[dict[str, Any]] = []
        for (book_id, chapter_index), chapter_scenes in scene_groups.items():
            chapter = chapter_map.get((book_id, chapter_index))
            if chapter is None:
                continue
            for scene_slices in _batched_scene_slices(chapter_scenes, max_slices_per_batch=SCENE_SLICE_BATCH_SIZE):
                jobs.append(
                    {
                        "job_index": len(jobs),
                        "job_id": _canon_stage_job_id(stage_name="entity_extraction", book_id=book_id, chapter_index=chapter_index, scene_slices=scene_slices),
                        "book_id": book_id,
                        "book": book_map[book_id],
                        "chapter": chapter,
                        "scene_slices": scene_slices,
                    }
                )
        resumed_jobs = self.store.list_stage_jobs(series_id=series_id, stage_name="entity_extraction") if _resume_stage_enabled("entity_extraction") else {}
        if not _resume_stage_enabled("entity_extraction"):
            self.store.delete_stage_jobs(series_id=series_id, stage_name="entity_extraction")

        def run_job(job: dict[str, Any]) -> dict[str, Any]:
            raise_if_cancelled(self.cancellation_checker)
            runtime = _clone_reasoning_runtime(self.reasoning_runtime)
            started_at = time.perf_counter()
            payloads = self._extract_chapter_entities_with_fallback(
                book=job["book"],
                chapter=job["chapter"],
                scene_slices=list(job["scene_slices"]),
                identity_bundle=identity_bundle,
                reasoning_runtime=runtime,
            )
            result = {
                "job_index": int(job["job_index"]),
                "job_id": str(job["job_id"]),
                "book_id": str(job["book_id"]),
                "payloads": [payload.model_dump() for payload in payloads],
                "metadata": _request_metadata_with_job_stats(runtime, started_at=started_at, scene_slice_count=len(job["scene_slices"])),
            }
            self.store.upsert_stage_job(
                series_id=series_id,
                stage_name="entity_extraction",
                job_id=str(job["job_id"]),
                job_index=int(job["job_index"]),
                payload=result,
            )
            return result

        completed_results = [resumed_jobs[str(job["job_id"])] for job in jobs if str(job["job_id"]) in resumed_jobs]
        missing_jobs = [job for job in jobs if str(job["job_id"]) not in resumed_jobs]
        for result in _run_ordered_parallel_jobs(missing_jobs, run_job, cancellation_checker=self.cancellation_checker):
            completed_results.append(result)

        for result in sorted(completed_results, key=lambda item: int(item.get("job_index") or 0)):
            request_metadata_rows.append(dict(result.get("metadata") or {}))
            book_id = str(result["book_id"])
            for raw_payload in list(result["payloads"] or []):
                payload = EntitiesPayload.model_validate(raw_payload)
                for item in payload.entities:
                    name = normalize_entity_name(item.canonical_name)
                    if not _should_keep_entity_name(name, identity_bundle=identity_bundle):
                        continue
                    mention_scene_ids = [
                        scene_id
                        for scene_id in sorted(set(scene_id for scene_id in item.scene_ids if scene_id))
                        if entity_counts_by_scene.get(scene_id, 0) < MAX_ENTITIES_PER_SCENE
                    ]
                    if not mention_scene_ids:
                        continue
                    for scene_id in mention_scene_ids:
                        entity_counts_by_scene[scene_id] = entity_counts_by_scene.get(scene_id, 0) + 1
                    entity_id = _entity_id(name)
                    existing = merged.get(entity_id)
                    artifact = EntityArtifact(
                        entity_id=entity_id,
                        series_id=series_id,
                        canonical_name=name,
                        entity_type=_normalize_entity_type(item.entity_type, name=name, description=item.description),
                        description=item.description.strip(),
                        aliases=_unique_strings([normalize_entity_name(alias) for alias in item.aliases if normalize_entity_name(alias)]),
                        mention_scene_ids=mention_scene_ids,
                        book_ids=[book_id],
                        metadata={"reasoning_provider": self.reasoning_runtime.provider_name(), "reasoning_model": self.reasoning_runtime.resolved_model_name()},
                    )
                    if existing is None:
                        merged[entity_id] = artifact
                    else:
                        merged[entity_id] = EntityArtifact(
                            entity_id=existing.entity_id,
                            series_id=existing.series_id,
                            canonical_name=existing.canonical_name,
                            entity_type=existing.entity_type or artifact.entity_type,
                            description=existing.description or artifact.description,
                            aliases=_unique_strings([*existing.aliases, *artifact.aliases]),
                            mention_scene_ids=sorted(set([*existing.mention_scene_ids, *artifact.mention_scene_ids])),
                            book_ids=sorted(set([*existing.book_ids, *artifact.book_ids])),
                            metadata=dict(existing.metadata or artifact.metadata),
                        )
        persisted = self.store.replace_entities(series_id=series_id, entities=sorted(merged.values(), key=lambda item: item.canonical_name.casefold()))
        return {"entities": [item.model_dump() for item in persisted], "request_metadata_rows": request_metadata_rows}

    def _extract_chapter_entities(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> EntitiesPayload:
        raise_if_cancelled(self.cancellation_checker)
        runtime = reasoning_runtime or self.reasoning_runtime
        prompt = _build_entities_prompt(book=book, chapter=chapter, scene_slices=scene_slices, identity_bundle=identity_bundle)
        payload = runtime.generate_json(prompt, strict=True, max_tokens=2400)
        if payload.get("error"):
            raise RuntimeError(f"Entity extraction failed: {payload.get('error')}")
        return EntitiesPayload.model_validate(payload)

    def _extract_chapter_entities_with_fallback(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> list[EntitiesPayload]:
        runtime = reasoning_runtime or self.reasoning_runtime
        try:
            return [
                self._extract_chapter_entities(
                    book=book,
                    chapter=chapter,
                    scene_slices=scene_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                )
            ]
        except RuntimeError as exc:
            if not _should_retry_split_extraction_error(exc):
                raise
            try:
                left_slices, right_slices = _split_scene_slices_for_retry(scene_slices)
            except RuntimeError:
                return [EntitiesPayload()]
            return [
                *self._extract_chapter_entities_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=left_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                ),
                *self._extract_chapter_entities_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=right_slices,
                    identity_bundle=identity_bundle,
                    reasoning_runtime=runtime,
                ),
            ]


class RelationshipAgent:
    def __init__(self, *, store: CanonExtractionStore, reasoning_runtime: ReasoningRuntimeClient, cancellation_checker: CancellationChecker | None = None) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime
        self.cancellation_checker = cancellation_checker

    def run(
        self,
        *,
        series_id: str,
        books: list[BookArtifact],
        chapters: list[ChapterArtifact],
        scenes: list[SceneArtifact],
        identity_bundle: CanonicalIdentityBundle,
        entities: list[EntityArtifact],
    ) -> dict[str, Any]:
        book_map = {book.book_id: book for book in books}
        chapter_map = {(chapter.book_id, chapter.chapter_index): chapter for chapter in chapters}
        entity_name_to_id = _entity_name_to_id(entities)
        scene_groups = _group_scenes_by_chapter(scenes)
        merged: dict[str, RelationshipArtifact] = {}
        request_metadata_rows: list[dict[str, Any]] = []
        relationship_counts_by_scene: dict[str, int] = {}
        jobs: list[dict[str, Any]] = []
        for (book_id, chapter_index), chapter_scenes in scene_groups.items():
            chapter = chapter_map.get((book_id, chapter_index))
            if chapter is None:
                continue
            for scene_slices in _batched_scene_slices(chapter_scenes, max_slices_per_batch=SCENE_SLICE_BATCH_SIZE):
                relevant_entities = _entities_for_scene_slice_batch(entities, scene_slices)
                jobs.append(
                    {
                        "job_index": len(jobs),
                        "job_id": _canon_stage_job_id(stage_name="relationship_extraction", book_id=book_id, chapter_index=chapter_index, scene_slices=scene_slices),
                        "book_id": book_id,
                        "book": book_map[book_id],
                        "chapter": chapter,
                        "scene_slices": scene_slices,
                        "entities": relevant_entities,
                    }
                )
        resumed_jobs = self.store.list_stage_jobs(series_id=series_id, stage_name="relationship_extraction") if _resume_stage_enabled("relationship_extraction") else {}
        if not _resume_stage_enabled("relationship_extraction"):
            self.store.delete_stage_jobs(series_id=series_id, stage_name="relationship_extraction")

        def run_job(job: dict[str, Any]) -> dict[str, Any]:
            raise_if_cancelled(self.cancellation_checker)
            runtime = _clone_reasoning_runtime(self.reasoning_runtime)
            started_at = time.perf_counter()
            payloads = self._extract_chapter_relationships_with_fallback(
                book=job["book"],
                chapter=job["chapter"],
                scene_slices=list(job["scene_slices"]),
                identity_bundle=identity_bundle,
                entities=list(job["entities"]),
                reasoning_runtime=runtime,
            )
            result = {
                "job_index": int(job["job_index"]),
                "job_id": str(job["job_id"]),
                "book_id": str(job["book_id"]),
                "scene_slices": list(job["scene_slices"]),
                "payloads": [payload.model_dump() for payload in payloads],
                "metadata": _request_metadata_with_job_stats(runtime, started_at=started_at, scene_slice_count=len(job["scene_slices"])),
            }
            self.store.upsert_stage_job(
                series_id=series_id,
                stage_name="relationship_extraction",
                job_id=str(job["job_id"]),
                job_index=int(job["job_index"]),
                payload=result,
            )
            return result

        completed_results = [resumed_jobs[str(job["job_id"])] for job in jobs if str(job["job_id"]) in resumed_jobs]
        missing_jobs = [job for job in jobs if str(job["job_id"]) not in resumed_jobs]
        for result in _run_ordered_parallel_jobs(missing_jobs, run_job, cancellation_checker=self.cancellation_checker):
            completed_results.append(result)

        for result in sorted(completed_results, key=lambda item: int(item.get("job_index") or 0)):
            request_metadata_rows.append(dict(result.get("metadata") or {}))
            book_id = str(result["book_id"])
            scene_slices = list(result["scene_slices"])
            for raw_payload in list(result["payloads"] or []):
                payload = RelationshipsPayload.model_validate(raw_payload)
                for item in payload.relationships:
                    narrative_grounding = _batch_narrative_grounding(scene_slices, list(item.scene_ids or []))
                    source_ref = _resolve_single_name_ref(
                        item.source_name,
                        identity_bundle=identity_bundle,
                        entity_name_to_id=entity_name_to_id,
                        narrative_grounding=narrative_grounding,
                    )
                    target_ref = _resolve_single_name_ref(
                        item.target_name,
                        identity_bundle=identity_bundle,
                        entity_name_to_id=entity_name_to_id,
                        narrative_grounding=narrative_grounding,
                    )
                    if not source_ref or not target_ref or source_ref == target_ref:
                        continue
                    scene_ids = [
                        scene_id
                        for scene_id in sorted(set(scene_id for scene_id in item.scene_ids if scene_id))
                        if relationship_counts_by_scene.get(scene_id, 0) < MAX_RELATIONSHIPS_PER_SCENE
                    ]
                    if not scene_ids:
                        continue
                    for scene_id in scene_ids:
                        relationship_counts_by_scene[scene_id] = relationship_counts_by_scene.get(scene_id, 0) + 1
                    relationship_type = _normalize_label(item.relationship_type)
                    relationship_type = _normalize_relationship_type(
                        relationship_type,
                        description=item.description,
                        source_ref=source_ref,
                        target_ref=target_ref,
                    )
                    relationship_id = _relationship_id(source_ref, target_ref, relationship_type)
                    existing = merged.get(relationship_id)
                    artifact = RelationshipArtifact(
                        relationship_id=relationship_id,
                        series_id=series_id,
                        source_ref=source_ref,
                        target_ref=target_ref,
                        relationship_type=relationship_type,
                        description=item.description.strip(),
                        scene_ids=scene_ids,
                        book_ids=[book_id],
                        metadata={"reasoning_provider": self.reasoning_runtime.provider_name(), "reasoning_model": self.reasoning_runtime.resolved_model_name()},
                    )
                    if not _should_keep_relationship_artifact(artifact):
                        continue
                    if existing is None:
                        merged[relationship_id] = artifact
                    else:
                        merged[relationship_id] = RelationshipArtifact(
                            relationship_id=existing.relationship_id,
                            series_id=existing.series_id,
                            source_ref=existing.source_ref,
                            target_ref=existing.target_ref,
                            relationship_type=existing.relationship_type,
                            description=existing.description or artifact.description,
                            scene_ids=sorted(set([*existing.scene_ids, *artifact.scene_ids])),
                            book_ids=sorted(set([*existing.book_ids, *artifact.book_ids])),
                            metadata=dict(existing.metadata or artifact.metadata),
                        )
        persisted = self.store.replace_relationships(series_id=series_id, relationships=sorted(merged.values(), key=lambda item: item.relationship_id))
        return {"relationships": [item.model_dump() for item in persisted], "request_metadata_rows": request_metadata_rows}

    def _extract_chapter_relationships(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        entities: list[EntityArtifact],
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> RelationshipsPayload:
        raise_if_cancelled(self.cancellation_checker)
        runtime = reasoning_runtime or self.reasoning_runtime
        prompt = _build_relationships_prompt(
            book=book,
            chapter=chapter,
            scene_slices=scene_slices,
            identity_bundle=identity_bundle,
            entities=entities,
        )
        payload = runtime.generate_json(prompt, strict=True, max_tokens=2400)
        if payload.get("error"):
            raise RuntimeError(f"Relationship extraction failed: {payload.get('error')}")
        return RelationshipsPayload.model_validate(payload)

    def _extract_chapter_relationships_with_fallback(
        self,
        *,
        book: BookArtifact,
        chapter: ChapterArtifact,
        scene_slices: list[dict[str, Any]],
        identity_bundle: CanonicalIdentityBundle,
        entities: list[EntityArtifact],
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> list[RelationshipsPayload]:
        runtime = reasoning_runtime or self.reasoning_runtime
        try:
            return [
                self._extract_chapter_relationships(
                    book=book,
                    chapter=chapter,
                    scene_slices=scene_slices,
                    identity_bundle=identity_bundle,
                    entities=entities,
                    reasoning_runtime=runtime,
                )
            ]
        except RuntimeError as exc:
            if not _should_retry_split_extraction_error(exc):
                raise
            try:
                left_slices, right_slices = _split_scene_slices_for_retry(scene_slices)
            except RuntimeError:
                return [RelationshipsPayload()]
            return [
                *self._extract_chapter_relationships_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=left_slices,
                    identity_bundle=identity_bundle,
                    entities=entities,
                    reasoning_runtime=runtime,
                ),
                *self._extract_chapter_relationships_with_fallback(
                    book=book,
                    chapter=chapter,
                    scene_slices=right_slices,
                    identity_bundle=identity_bundle,
                    entities=entities,
                    reasoning_runtime=runtime,
                ),
            ]


class TimelineAgent:
    def __init__(self, *, store: CanonExtractionStore) -> None:
        self.store = store

    def run(self, *, series_id: str, scenes: list[SceneArtifact], events: list[EventArtifact]) -> dict[str, Any]:
        by_scene = {scene.scene_id: scene for scene in scenes}
        timeline: list[TimelineArtifact] = []
        ordered_events = sorted(events, key=lambda item: (item.book_id, item.chapter_index, item.scene_index, item.event_index))
        for sequence_index, event in enumerate(ordered_events, start=1):
            scene = by_scene.get(event.scene_id)
            if scene is None:
                continue
            timeline.append(
                TimelineArtifact(
                    timeline_id=f"timeline-{series_id}-{sequence_index:04d}",
                    series_id=series_id,
                    book_id=event.book_id,
                    scene_id=event.scene_id,
                    event_id=event.event_id,
                    sequence_index=sequence_index,
                    chapter_index=scene.chapter_index,
                    scene_index=scene.scene_index,
                    title=event.title,
                    summary=event.summary,
                    event_type=event.event_type,
                    participant_refs=list(event.participant_refs),
                    metadata={"source_event_index": event.event_index},
                )
            )
        persisted = self.store.replace_timeline(series_id=series_id, timeline=timeline)
        return {"timeline": [item.model_dump() for item in persisted]}


def build_canon_extraction_graph(
    *,
    event_agent: EventAgent,
    entity_agent: EntityAgent,
    relationship_agent: RelationshipAgent,
    timeline_agent: TimelineAgent,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    def events_node(state: CanonExtractionState) -> dict[str, Any]:
        started_at = time.perf_counter()
        if _resume_stage_enabled("event_extraction"):
            existing_events = event_agent.store.list_events(series_id=str(state.get("series_id") or ""))
            if existing_events:
                return {
                    "events": [item.model_dump() for item in existing_events],
                    "run_metadata": _append_stage_metadata(
                        state.get("run_metadata"),
                        stage_name="event_extraction",
                        elapsed_seconds=time.perf_counter() - started_at,
                        extra={
                            "event_count": len(existing_events),
                            "resumed": True,
                            "reasoning_calls": 0,
                            "parallelism": CANON_EXTRACTION_PARALLELISM,
                            "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                            "max_events_per_scene": MAX_EVENTS_PER_SCENE,
                            "job_latency_seconds": {"count": 0},
                        },
                    ),
                }
        payload = event_agent.run(
            series_id=str(state.get("series_id") or ""),
            books=[BookArtifact.model_validate(item) for item in list(state.get("books") or [])],
            chapters=[ChapterArtifact.model_validate(item) for item in list(state.get("chapters") or [])],
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
        )
        return {
            "events": list(payload["events"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="event_extraction",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "event_count": len(payload["events"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "parallelism": CANON_EXTRACTION_PARALLELISM,
                    "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                    "max_events_per_scene": MAX_EVENTS_PER_SCENE,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    def entities_node(state: CanonExtractionState) -> dict[str, Any]:
        started_at = time.perf_counter()
        if _resume_stage_enabled("entity_extraction"):
            existing_entities = entity_agent.store.list_entities(series_id=str(state.get("series_id") or ""))
            if existing_entities:
                return {
                    "entities": [item.model_dump() for item in existing_entities],
                    "run_metadata": _append_stage_metadata(
                        state.get("run_metadata"),
                        stage_name="entity_extraction",
                        elapsed_seconds=time.perf_counter() - started_at,
                        extra={
                            "entity_count": len(existing_entities),
                            "resumed": True,
                            "reasoning_calls": 0,
                            "parallelism": CANON_EXTRACTION_PARALLELISM,
                            "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                            "max_entities_per_scene": MAX_ENTITIES_PER_SCENE,
                            "job_latency_seconds": {"count": 0},
                        },
                    ),
                }
        payload = entity_agent.run(
            series_id=str(state.get("series_id") or ""),
            books=[BookArtifact.model_validate(item) for item in list(state.get("books") or [])],
            chapters=[ChapterArtifact.model_validate(item) for item in list(state.get("chapters") or [])],
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
        )
        return {
            "entities": list(payload["entities"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="entity_extraction",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "entity_count": len(payload["entities"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "parallelism": CANON_EXTRACTION_PARALLELISM,
                    "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                    "max_entities_per_scene": MAX_ENTITIES_PER_SCENE,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    def relationships_node(state: CanonExtractionState) -> dict[str, Any]:
        started_at = time.perf_counter()
        if _resume_stage_enabled("relationship_extraction"):
            existing_relationships = relationship_agent.store.list_relationships(series_id=str(state.get("series_id") or ""))
            if existing_relationships:
                return {
                    "relationships": [item.model_dump() for item in existing_relationships],
                    "run_metadata": _append_stage_metadata(
                        state.get("run_metadata"),
                        stage_name="relationship_extraction",
                        elapsed_seconds=time.perf_counter() - started_at,
                        extra={
                            "relationship_count": len(existing_relationships),
                            "resumed": True,
                            "reasoning_calls": 0,
                            "parallelism": CANON_EXTRACTION_PARALLELISM,
                            "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                            "max_relationships_per_scene": MAX_RELATIONSHIPS_PER_SCENE,
                            "job_latency_seconds": {"count": 0},
                        },
                    ),
                }
        payload = relationship_agent.run(
            series_id=str(state.get("series_id") or ""),
            books=[BookArtifact.model_validate(item) for item in list(state.get("books") or [])],
            chapters=[ChapterArtifact.model_validate(item) for item in list(state.get("chapters") or [])],
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
            entities=[EntityArtifact.model_validate(item) for item in list(state.get("entities") or [])],
        )
        return {
            "relationships": list(payload["relationships"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="relationship_extraction",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "relationship_count": len(payload["relationships"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "parallelism": CANON_EXTRACTION_PARALLELISM,
                    "scene_slice_batch_size": SCENE_SLICE_BATCH_SIZE,
                    "max_relationships_per_scene": MAX_RELATIONSHIPS_PER_SCENE,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    def timeline_node(state: CanonExtractionState) -> dict[str, Any]:
        started_at = time.perf_counter()
        if _resume_stage_enabled("timeline_construction"):
            existing_timeline = timeline_agent.store.list_timeline(series_id=str(state.get("series_id") or ""))
            if existing_timeline:
                return {
                    "timeline": [item.model_dump() for item in existing_timeline],
                    "run_metadata": _append_stage_metadata(
                        state.get("run_metadata"),
                        stage_name="timeline_construction",
                        elapsed_seconds=time.perf_counter() - started_at,
                        extra={"timeline_count": len(existing_timeline), "resumed": True},
                    ),
                }
        payload = timeline_agent.run(
            series_id=str(state.get("series_id") or ""),
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            events=[EventArtifact.model_validate(item) for item in list(state.get("events") or [])],
        )
        return {
            "timeline": list(payload["timeline"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="timeline_construction",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={"timeline_count": len(payload["timeline"])},
            ),
        }

    builder = StateGraph(CanonExtractionState)
    builder.add_node("events", events_node)
    builder.add_node("entities", entities_node)
    builder.add_node("relationships", relationships_node)
    builder.add_node("timeline", timeline_node)
    builder.add_edge(START, "events")
    builder.add_edge("events", "entities")
    builder.add_edge("entities", "relationships")
    builder.add_edge("relationships", "timeline")
    builder.add_edge("timeline", END)
    return builder.compile(checkpointer=checkpointer)


class CanonExtractionRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        reasoning_runtime: ReasoningRuntimeClient,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
        cancellation_checker: CancellationChecker | None = None,
    ) -> None:
        self.persistence = persistence
        self.persistence.initialize()
        self.store = CanonExtractionStore(persistence)
        self.event_agent = EventAgent(store=self.store, reasoning_runtime=reasoning_runtime, cancellation_checker=cancellation_checker)
        self.entity_agent = EntityAgent(store=self.store, reasoning_runtime=reasoning_runtime, cancellation_checker=cancellation_checker)
        self.relationship_agent = RelationshipAgent(store=self.store, reasoning_runtime=reasoning_runtime, cancellation_checker=cancellation_checker)
        self.timeline_agent = TimelineAgent(store=self.store)
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_canon_extraction_graph(
            event_agent=self.event_agent,
            entity_agent=self.entity_agent,
            relationship_agent=self.relationship_agent,
            timeline_agent=self.timeline_agent,
            checkpointer=self.checkpointer,
        )

    def invoke(self, *, series_id: str, thread_id: str = "canon-extraction") -> CanonExtractionResult:
        context = self.store.load_series_context(series_id=series_id)
        identity_bundle = context.get("identity_bundle")
        if identity_bundle is None:
            raise ValueError(f"CanonExtractionRuntime requires a persisted identity bundle for series '{series_id}'.")
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "books": [item.model_dump() for item in list(context.get("books") or [])],
                "chapters": [item.model_dump() for item in list(context.get("chapters") or [])],
                "scenes": [item.model_dump() for item in list(context.get("scenes") or [])],
                "identity_bundle": identity_bundle.model_dump(),
            },
            config={"configurable": {"thread_id": str(thread_id or "canon-extraction")}},
        )
        return CanonExtractionResult(
            series_id=series_id,
            events=[EventArtifact.model_validate(item) for item in list(state.get("events") or [])],
            entities=[EntityArtifact.model_validate(item) for item in list(state.get("entities") or [])],
            relationships=[RelationshipArtifact.model_validate(item) for item in list(state.get("relationships") or [])],
            timeline=[TimelineArtifact.model_validate(item) for item in list(state.get("timeline") or [])],
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def _resolve_checkpointer(
    *,
    persistence: PersistenceRuntimeClient,
    checkpointer: BaseCheckpointSaver | None,
    allow_in_memory_checkpointer: bool,
) -> BaseCheckpointSaver:
    if checkpointer is not None:
        return checkpointer
    if getattr(persistence, "engine", None) is not None:
        return SqlCheckpointSaver(engine=persistence.engine)
    if allow_in_memory_checkpointer:
        return InMemorySaver()
    raise ValueError("CanonExtractionRuntime requires a durable checkpointer or an initialized persistence engine.")


def _clone_reasoning_runtime(reasoning_runtime: ReasoningRuntimeClient) -> ReasoningRuntimeClient:
    clone = getattr(reasoning_runtime, "clone", None)
    if callable(clone):
        return clone()
    return reasoning_runtime


def _run_ordered_parallel_jobs(
    jobs: list[dict[str, Any]], worker, *, cancellation_checker: CancellationChecker | None = None,
) -> list[dict[str, Any]]:
    if not jobs:
        return []
    workers = min(CANON_EXTRACTION_PARALLELISM, len(jobs))
    if workers <= 1:
        return [worker(job) for job in jobs]
    results: list[dict[str, Any]] = []
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="canon-extraction")
    pending: dict[Future, dict[str, Any]] = {}
    next_index = 0
    try:
        while next_index < len(jobs) and len(pending) < workers:
            raise_if_cancelled(cancellation_checker)
            job = jobs[next_index]
            pending[executor.submit(worker, job)] = job
            next_index += 1
        while pending:
            raise_if_cancelled(cancellation_checker)
            completed, _ = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
            for future in completed:
                pending.pop(future)
                results.append(future.result())
                if next_index < len(jobs):
                    raise_if_cancelled(cancellation_checker)
                    job = jobs[next_index]
                    pending[executor.submit(worker, job)] = job
                    next_index += 1
    finally:
        cancelled = cancellation_checker is not None and cancellation_checker()
        if cancelled:
            for future in pending:
                future.cancel()
        executor.shutdown(wait=not cancelled, cancel_futures=cancelled)
    return sorted(results, key=lambda item: int(item.get("job_index") or 0))


def _request_metadata_with_job_stats(reasoning_runtime: ReasoningRuntimeClient, *, started_at: float, scene_slice_count: int) -> dict[str, Any]:
    metadata = dict(reasoning_runtime.last_request_metadata() or {})
    metadata["job_elapsed_seconds"] = round(max(0.0, time.perf_counter() - started_at), 4)
    metadata["scene_slice_count"] = int(scene_slice_count)
    metadata["parallelism"] = CANON_EXTRACTION_PARALLELISM
    return metadata


def _job_latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(float(row.get("job_elapsed_seconds") or 0.0) for row in rows if float(row.get("job_elapsed_seconds") or 0.0) > 0)
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": round(values[0], 4),
        "max": round(values[-1], 4),
        "avg": round(sum(values) / len(values), 4),
    }


def _resume_stage_enabled(stage_name: str) -> bool:
    return stage_name in CANON_RESUME_STAGES or "all" in CANON_RESUME_STAGES


def _canon_stage_job_id(*, stage_name: str, book_id: str, chapter_index: int, scene_slices: list[dict[str, Any]]) -> str:
    slice_key = "|".join(
        f"{item.get('scene_id') or ''}:{item.get('chunk_index') or 0}"
        for item in scene_slices
    )
    digest = hashlib.sha1(f"{stage_name}|{book_id}|{chapter_index}|{slice_key}".encode("utf-8")).hexdigest()[:16]
    return f"{stage_name}-{chapter_index:03d}-{digest}"


def _group_scenes_by_chapter(scenes: list[SceneArtifact]) -> dict[tuple[str, int], list[SceneArtifact]]:
    grouped: dict[tuple[str, int], list[SceneArtifact]] = {}
    for scene in scenes:
        grouped.setdefault((scene.book_id, scene.chapter_index), []).append(scene)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=lambda item: item.scene_index)
    return grouped


def _build_events_prompt(*, book: BookArtifact, chapter: ChapterArtifact, scene_slices: list[dict[str, Any]], identity_bundle: CanonicalIdentityBundle) -> str:
    return (
        "Return JSON with key 'events'.\n"
        "Each event must include: scene_id, title, summary, event_type, participant_names, entity_names.\n"
        "Use only the provided chapter/scene slices.\n"
        "Extract concrete canon events that materially happen in the story across the full chapter coverage.\n"
        "Multiple events may come from the same scene when the scene contains several distinct beats.\n"
        "Prefer canonical character names when they exist in the identity bundle.\n"
        "Use narrative_grounding when present: if a slice identifies narrator_name, resolve first-person narrator actions to that canonical character instead of returning 'narrator'.\n"
        "If narrator/addressee grounding is absent or low confidence, omit uncertain participant_names rather than guessing.\n"
        "Do not invent scenes or facts outside the provided scene slices.\n"
        f"Book title: {book.title}\n"
        f"Chapter: {chapter.chapter_index} - {chapter.title}\n"
        f"Canonical characters JSON:\n{json.dumps(_identity_character_context(identity_bundle), ensure_ascii=False, indent=2)}\n"
        f"Scene slices JSON:\n{json.dumps(scene_slices, ensure_ascii=False, indent=2)}\n"
    )


def _build_entities_prompt(*, book: BookArtifact, chapter: ChapterArtifact, scene_slices: list[dict[str, Any]], identity_bundle: CanonicalIdentityBundle) -> str:
    return (
        "Return JSON with key 'entities'.\n"
        "Each entity must include: canonical_name, entity_type, description, aliases, scene_ids.\n"
        "Extract only non-character canon entities that matter for downstream story/world understanding.\n"
        "Use the full provided scene-slice coverage, not just the first slice.\n"
        "Exclude canonical characters already covered by the identity bundle.\n"
        "Do not extract narrator/addressee labels as entities.\n"
        "Allowed entity types only: location, object, creature, organization, artifact, concept.\n"
        "Classify by physical role, not an ambiguous noun: location means a place or natural/spatial feature people can enter, visit, or travel to "
        "(including springs, pools, rivers, forests, buildings, and rooms); object means a portable physical item; artifact means a significant "
        "crafted, historical, or enchanted item. A natural water spring is always a location, never a coiled object.\n"
        "Never return entity_type=character or entity_type=event.\n"
        f"Book title: {book.title}\n"
        f"Chapter: {chapter.chapter_index} - {chapter.title}\n"
        f"Canonical characters JSON:\n{json.dumps(_identity_character_context(identity_bundle), ensure_ascii=False, indent=2)}\n"
        f"Scene slices JSON:\n{json.dumps(scene_slices, ensure_ascii=False, indent=2)}\n"
    )


def _build_relationships_prompt(
    *,
    book: BookArtifact,
    chapter: ChapterArtifact,
    scene_slices: list[dict[str, Any]],
    identity_bundle: CanonicalIdentityBundle,
    entities: list[EntityArtifact],
) -> str:
    return (
        "Return JSON with key 'relationships'.\n"
        "Each relationship must include: source_name, target_name, relationship_type, description, scene_ids.\n"
        "Extract stable or materially important relationships expressed in the chapter scenes.\n"
        "Use the full provided scene-slice coverage, not just the first slice.\n"
        "Source and target may be canonical characters or extracted non-character entities.\n"
        "Use canonical character names when possible.\n"
        "Use narrative_grounding when present: resolve first-person narrator or addressed 'you' references to the grounded canonical character only when supported by that slice.\n"
        "If grounding is absent or uncertain, do not create relationships involving narrator/addressee placeholders.\n"
        "Allowed relationship types only: ally, antagonistic, artifact_usage, co_conspirator, companion, curiosity, family, friendship, location_association, manipulation, marriage, protective, reference, request, romantic, sibling.\n"
        f"Book title: {book.title}\n"
        f"Chapter: {chapter.chapter_index} - {chapter.title}\n"
        f"Canonical characters JSON:\n{json.dumps(_identity_character_context(identity_bundle), ensure_ascii=False, indent=2)}\n"
        f"Available non-character entities JSON:\n{json.dumps(_entity_context(entities), ensure_ascii=False, indent=2)}\n"
        f"Scene slices JSON:\n{json.dumps(scene_slices, ensure_ascii=False, indent=2)}\n"
    )


def _scene_slices(scenes: list[SceneArtifact]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scene in scenes:
        for chunk_index, excerpt in enumerate(_chunk_scene_text(scene.text, max_chars=1800, overlap_chars=250), start=1):
            results.append(
                SceneSliceReference(
                    scene_id=scene.scene_id,
                    chapter_index=scene.chapter_index,
                    scene_index=scene.scene_index,
                    chunk_index=chunk_index,
                    summary=scene.summary,
                    excerpt=excerpt,
                    narrative_grounding=_scene_narrative_grounding(scene),
                ).model_dump()
            )
    return results


def _batched_scene_slices(scenes: list[SceneArtifact], *, max_slices_per_batch: int) -> list[list[dict[str, Any]]]:
    slices = _scene_slices(scenes)
    if max_slices_per_batch <= 0:
        return [slices]
    return [slices[index : index + max_slices_per_batch] for index in range(0, len(slices), max_slices_per_batch)]


def _split_scene_slices_for_retry(scene_slices: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(scene_slices) > 1:
        midpoint = max(1, len(scene_slices) // 2)
        return scene_slices[:midpoint], scene_slices[midpoint:]
    if not scene_slices:
        raise RuntimeError("parse_failed")
    current = dict(scene_slices[0] or {})
    excerpt = str(current.get("excerpt") or "").strip()
    if len(excerpt) < 500:
        raise RuntimeError("parse_failed")
    midpoint = max(1, len(excerpt) // 2)
    split_at = excerpt.rfind(" ", 0, midpoint)
    if split_at < 200:
        split_at = midpoint
    left = dict(current)
    right = dict(current)
    left["excerpt"] = excerpt[:split_at].strip()
    right["excerpt"] = excerpt[split_at:].strip()
    left["chunk_index"] = int(current.get("chunk_index") or 1)
    right["chunk_index"] = int(current.get("chunk_index") or 1)
    return [left], [right]


def _fallback_events_payload_from_scene_slices(scene_slices: list[dict[str, Any]]) -> EventsPayload:
    events: list[SceneEventExtraction] = []
    for scene_slice in scene_slices:
        scene_id = str(scene_slice.get("scene_id") or "").strip()
        if not scene_id:
            continue
        summary = _clean_excerpt(str(scene_slice.get("summary") or scene_slice.get("excerpt") or ""), max_chars=260)
        if not summary:
            continue
        title = _clean_excerpt(summary, max_chars=90)
        grounding = scene_slice.get("narrative_grounding") if isinstance(scene_slice, dict) else None
        narrator_name = str(dict(grounding or {}).get("narrator_name") or "").strip() if isinstance(grounding, dict) else ""
        events.append(
            SceneEventExtraction(
                scene_id=scene_id,
                title=title,
                summary=summary,
                event_type="scene_beat",
                participant_names=[narrator_name] if narrator_name else [],
                entity_names=[],
            )
        )
    return EventsPayload(events=events)


def _should_retry_split_extraction_error(exc: RuntimeError) -> bool:
    message = str(exc)
    return "parse_failed" in message or "empty_response" in message or "max_retries_exceeded" in message


def _identity_character_context(identity_bundle: CanonicalIdentityBundle) -> list[dict[str, Any]]:
    return [
        {
            "character_id": character.character_id,
            "display_name": character.display_name,
            "aliases": list(character.aliases),
        }
        for character in identity_bundle.characters
    ]


def _entity_context(entities: list[EntityArtifact]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": entity.entity_id,
            "canonical_name": entity.canonical_name,
            "aliases": list(entity.aliases),
            "entity_type": entity.entity_type,
        }
        for entity in entities
    ]


def _clean_excerpt(text: str, *, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    return cleaned[:max_chars].strip()


def _chunk_scene_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return [""]
    if len(cleaned) <= max_chars:
        return [cleaned]
    if overlap_chars < 0:
        overlap_chars = 0
    step = max(200, max_chars - overlap_chars)
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        next_start = max(start + step, end - overlap_chars)
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def _append_stage_metadata(current: dict[str, Any] | None, *, stage_name: str, elapsed_seconds: float, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = dict(current or {})
    stage_order = list(metadata.get("stage_order") or [])
    stage_timings = dict(metadata.get("stage_timings_seconds") or {})
    stage_details = dict(metadata.get("stage_details") or {})
    if stage_name not in stage_order:
        stage_order.append(stage_name)
    stage_timings[stage_name] = round(max(0.0, float(elapsed_seconds)), 4)
    stage_details[stage_name] = dict(extra or {})
    metadata["stage_order"] = stage_order
    metadata["stage_timings_seconds"] = stage_timings
    metadata["stage_details"] = stage_details
    metadata["total_runtime_seconds"] = round(sum(float(stage_timings.get(name) or 0.0) for name in stage_order), 4)
    return metadata


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", "_", str(value or "").strip().lower()).strip("_")


def _normalize_entity_type(value: str, *, name: str = "", description: str = "") -> str:
    normalized = _normalize_label(value)
    haystack = f"{name} {description} {value}".casefold()
    natural_place_phrases = {
        "natural spring", "glowing spring", "luminous spring", "hot spring", "mineral spring", "spring-fed",
        "body of water", "waterfall", "riverbank", "river bank",
    }
    if any(phrase in haystack for phrase in natural_place_phrases):
        return "location"
    if re.search(r"\b(spring|pool)\b", haystack) and any(
        marker in haystack for marker in ("water", "luminous", "glowing", "natural", "destination", "terrain", "shore")
    ):
        return "location"
    if normalized in ALLOWED_ENTITY_TYPES:
        return normalized
    if any(token in haystack for token in {"castle", "house", "room", "woods", "forest", "river", "bank", "world", "palace", "hall", "table", "window", "balcony"}):
        return "location"
    if any(token in haystack for token in {"dagger", "knife", "cloak", "gown", "ring", "hand", "seal", "apple", "plum", "note", "sword"}):
        return "object"
    if any(token in haystack for token in {"fiddler", "gentry", "folk", "court", "family"}):
        return "organization"
    if any(token in haystack for token in {"faerie", "monster", "wolf", "bird", "seabird", "serpent"}):
        return "creature"
    if any(token in haystack for token in {"coronation", "kindness", "boldness", "love", "promise", "bargain", "divination"}):
        return "concept"
    return "artifact"


def _normalize_relationship_type(value: str, *, description: str = "", source_ref: str = "", target_ref: str = "") -> str:
    normalized = _normalize_label(value)
    haystack = f"{normalized} {description} {source_ref} {target_ref}".casefold()
    if "sibling" in haystack or "sister" in haystack or "twins" in haystack:
        return "sibling"
    if "mother" in haystack or "father" in haystack or "family" in haystack or "child" in haystack:
        return "family"
    if "romantic" in haystack or "love" in haystack or "lover" in haystack or "liaison" in haystack or "temptation" in haystack:
        return "romantic"
    if "marriage" in haystack or "bride" in haystack:
        return "marriage"
    if "friend" in haystack or "confidante" in haystack or "peer" in haystack:
        return "friendship"
    if "ally" in haystack or "companion" in haystack:
        return "ally" if "ally" in haystack else "companion"
    if "co_conspirator" in haystack or "conspirator" in haystack:
        return "co_conspirator"
    if "protect" in haystack or "shield" in haystack:
        return "protective"
    if "antagon" in haystack or "advers" in haystack or "conflict" in haystack or "suspicion" in haystack:
        return "antagonistic"
    if "manipul" in haystack or "coerc" in haystack:
        return "manipulation"
    if "request" in haystack:
        return "request"
    if "artifact" in haystack or "token" in haystack or "uses" in haystack:
        return "artifact_usage"
    if "setting" in haystack or "location" in haystack:
        return "location_association"
    if "curiosity" in haystack or "observ" in haystack or "admiration" in haystack:
        return "curiosity"
    if "reference" in haystack or "memory" in haystack or "game" in haystack:
        return "reference"
    if normalized in ALLOWED_RELATIONSHIP_TYPES:
        return normalized
    return "reference"


def _entity_id(name: str) -> str:
    normalized = normalize_entity_name(name)
    return f"entity-{_slug(normalized)}"


def _relationship_id(source_ref: str, target_ref: str, relationship_type: str) -> str:
    token = f"{source_ref}:{relationship_type}:{target_ref}"
    return f"relationship-{_slug(token)}"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:8]


def _identity_alias_map(identity_bundle: CanonicalIdentityBundle) -> dict[str, str]:
    results: dict[str, str] = {}
    for character in identity_bundle.characters:
        results[character.display_name.casefold()] = character.character_id
        for alias in character.aliases:
            results[str(alias or "").casefold()] = character.character_id
    return results


def _augment_participant_names_from_event_text(
    participant_names: list[str],
    *,
    identity_bundle: CanonicalIdentityBundle,
    event_title: str,
    event_summary: str,
) -> list[str]:
    results = _unique_strings([normalize_entity_name(name) for name in list(participant_names or []) if normalize_entity_name(name)])
    existing = {name.casefold() for name in results}
    event_text = f"{event_title or ''}\n{event_summary or ''}"
    for character in identity_bundle.characters:
        for alias in _unique_strings([character.display_name, *list(character.aliases or [])]):
            if not _text_mentions_identity_name(event_text, alias):
                continue
            display_name = normalize_entity_name(character.display_name)
            if display_name and display_name.casefold() not in existing:
                results.append(display_name)
                existing.add(display_name.casefold())
            break
    return results


def _text_mentions_identity_name(text: str, name: str) -> bool:
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", text or "", flags=re.IGNORECASE))


def _entities_for_scene_slice_batch(entities: list[EntityArtifact], scene_slices: list[dict[str, Any]]) -> list[EntityArtifact]:
    scene_ids = {str(item.get("scene_id") or "").strip() for item in scene_slices if str(item.get("scene_id") or "").strip()}
    if not scene_ids:
        return list(entities)
    matched = [entity for entity in entities if scene_ids.intersection(set(entity.mention_scene_ids or []))]
    return matched or list(entities)


def _entity_name_to_id(entities: list[EntityArtifact]) -> dict[str, str]:
    results: dict[str, str] = {}
    for entity in entities:
        results[entity.canonical_name.casefold()] = entity.entity_id
        for alias in entity.aliases:
            results[str(alias or "").casefold()] = entity.entity_id
    return results


def _resolve_name_refs(
    names: list[str],
    *,
    identity_bundle: CanonicalIdentityBundle,
    entity_name_to_id: dict[str, str],
    narrative_grounding: dict[str, Any] | None = None,
) -> list[str]:
    results: list[str] = []
    for name in names:
        ref = _resolve_single_name_ref(
            name,
            identity_bundle=identity_bundle,
            entity_name_to_id=entity_name_to_id,
            narrative_grounding=narrative_grounding,
        )
        if ref and ref not in results:
            results.append(ref)
    return results


def _resolve_participant_refs(
    names: list[str],
    *,
    scene: SceneArtifact,
    event_title: str = "",
    event_summary: str = "",
    identity_bundle: CanonicalIdentityBundle,
    entity_name_to_id: dict[str, str],
    narrative_grounding: dict[str, Any] | None = None,
) -> list[str]:
    results: list[str] = []
    candidate_names = _augment_participant_names(
        names,
        identity_bundle=identity_bundle,
        event_title=event_title,
        event_summary=event_summary,
        narrative_grounding=narrative_grounding,
    )
    for name in candidate_names:
        if not _has_participant_text_support(
            name,
            scene=scene,
            event_title=event_title,
            event_summary=event_summary,
            narrative_grounding=narrative_grounding,
        ):
            continue
        ref = _resolve_single_name_ref(
            name,
            identity_bundle=identity_bundle,
            entity_name_to_id=entity_name_to_id,
            narrative_grounding=narrative_grounding,
        )
        if ref and ref not in results:
            results.append(ref)
    return results


def _augment_participant_names(
    names: list[str],
    *,
    identity_bundle: CanonicalIdentityBundle,
    event_title: str = "",
    event_summary: str = "",
    narrative_grounding: dict[str, Any] | None = None,
) -> list[str]:
    results = _unique_strings([str(name or "") for name in names])
    event_text = f"{event_title or ''}\n{event_summary or ''}"
    grounding = dict(narrative_grounding or {})
    narrator_name = str(grounding.get("narrator_name") or "").strip()
    if narrator_name and _name_occurs(event_text, narrator_name) and "narrator" not in {item.casefold() for item in results}:
        results.append("narrator")
    for character in identity_bundle.characters:
        candidate_names = [character.display_name, *list(character.aliases or [])]
        if any(_name_occurs_as_event_recipient(event_text, str(candidate or "")) for candidate in candidate_names):
            if character.display_name not in results:
                results.append(character.display_name)
    return results


def _name_occurs(text: str, name: str) -> bool:
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", text or "", flags=re.IGNORECASE))


def _name_occurs_as_event_recipient(text: str, name: str) -> bool:
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    return bool(
        re.search(
            rf"\b(?:to|for|about|with|toward|towards)\s+{re.escape(cleaned)}(?![A-Za-z0-9])",
            text or "",
            flags=re.IGNORECASE,
        )
    )


def _resolve_single_name_ref(
    name: str,
    *,
    identity_bundle: CanonicalIdentityBundle,
    entity_name_to_id: dict[str, str],
    narrative_grounding: dict[str, Any] | None = None,
) -> str:
    normalized = normalize_entity_name(name).casefold()
    if not normalized:
        return ""
    grounding = dict(narrative_grounding or {})
    if normalized in {"narrator", "the narrator", "i", "me", "myself"}:
        return str(grounding.get("narrator_character_id") or "")
    if normalized in {"you", "yourself", "addressee", "the addressee"}:
        addressee_ids = list(grounding.get("addressee_character_ids") or [])
        return str(addressee_ids[0]) if len(addressee_ids) == 1 else ""
    alias_map = _identity_alias_map(identity_bundle)
    if normalized in alias_map:
        return alias_map[normalized]
    return str(entity_name_to_id.get(normalized) or "")


def _has_participant_text_support(
    name: str,
    *,
    scene: SceneArtifact,
    event_title: str = "",
    event_summary: str = "",
    narrative_grounding: dict[str, Any] | None = None,
) -> bool:
    normalized = normalize_entity_name(name).casefold()
    grounding = dict(narrative_grounding or {})
    if normalized in {"narrator", "the narrator", "i", "me", "myself"}:
        return bool(grounding.get("narrator_character_id"))
    if normalized in {"you", "yourself", "addressee", "the addressee"}:
        return len(list(grounding.get("addressee_character_ids") or [])) == 1
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    if _contains_possessive_reference(cleaned):
        return False
    if _is_tertiary_mentioned_reference(cleaned, event_title=event_title, event_summary=event_summary):
        return False
    if (
        _event_claims_name_as_actor(cleaned, event_title=event_title, event_summary=event_summary)
        and not _event_claims_name_as_actor(cleaned, event_title=event_title, event_summary="")
        and _scene_mentions_name(cleaned, scene=scene)
        and not _scene_supports_named_actor(
        cleaned,
        scene=scene,
        narrative_grounding=narrative_grounding,
        )
    ):
        return False
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", flags=re.IGNORECASE)
    event_texts = [event_title or "", event_summary or ""]
    if any(_has_recipient_possessive_destination_match(cleaned, text) for text in event_texts):
        return True
    if any(pattern.search(text or "") for text in event_texts) and not any(_has_non_possessive_match(pattern, text) for text in event_texts):
        return False
    texts = [*event_texts, scene.text or ""]
    for text in texts:
        if _has_non_possessive_match(pattern, text):
            return True
    return False


def _contains_possessive_reference(value: str) -> bool:
    return bool(re.search(r"\b[\w-]+(?:'s|’s|â€™s)\b", value, flags=re.IGNORECASE))


def _is_possessive_suffix(value: str) -> bool:
    return value.startswith("'s") or value.startswith("’s") or value.startswith("â€™s")


def _has_non_possessive_match(pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text or ""):
        suffix = str(text or "")[match.end(): match.end() + 6].lstrip()
        if _is_possessive_suffix(suffix):
            continue
        return True
    return False


def _has_recipient_possessive_destination_match(name: str, text: str) -> bool:
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    return bool(
        re.search(
            rf"\b(?:to|toward|towards|into|inside|at)\s+{re.escape(cleaned)}(?:'s|\u2019s|\u00e2\u20ac\u2122s)\s+(?:estate|house|home|room|window|door|palace|castle|court|grounds|bag|rucksack)\b",
            text or "",
            flags=re.IGNORECASE,
        )
    )


def _event_claims_name_as_actor(name: str, *, event_title: str = "", event_summary: str = "") -> bool:
    text = f"{event_title or ''}\n{event_summary or ''}"
    actor_verbs = (
        "act|acts|acted|advise|advises|advised|agree|agrees|agreed|ask|asks|asked|call|calls|called|"
        "climb|climbs|climbed|craft|crafts|crafted|demand|demands|demanded|enter|enters|entered|"
        "help|helps|helped|insist|insists|insisted|propose|proposes|proposed|read|reads|send|sends|sent|"
        "say|says|said|set|sets|setting|suggest|suggests|suggested|tell|tells|told|write|writes|wrote"
    )
    return bool(
        re.search(
            rf"\b{re.escape(name)}\b[^\n.?!]{{0,80}}\b(?:{actor_verbs})\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _scene_supports_named_actor(
    name: str,
    *,
    scene: SceneArtifact,
    narrative_grounding: dict[str, Any] | None = None,
) -> bool:
    grounding = dict(narrative_grounding or {})
    if name.casefold() == str(grounding.get("narrator_name") or "").casefold():
        return True
    text = scene.text or ""
    actor_verbs = (
        "act|acts|acted|advise|advises|advised|agree|agrees|agreed|ask|asks|asked|call|calls|called|"
        "climb|climbs|climbed|craft|crafts|crafted|demand|demands|demanded|enter|enters|entered|"
        "help|helps|helped|insist|insists|insisted|propose|proposes|proposed|read|reads|send|sends|sent|"
        "say|says|said|set|sets|setting|suggest|suggests|suggested|tell|tells|told|write|writes|wrote"
    )
    return bool(
        re.search(
            rf"\b{re.escape(name)}\b[^\n.?!]{{0,100}}\b(?:{actor_verbs})\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _scene_mentions_name(name: str, *, scene: SceneArtifact) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", flags=re.IGNORECASE)
    return _has_non_possessive_match(pattern, scene.text or "")


def _is_tertiary_mentioned_reference(name: str, *, event_title: str = "", event_summary: str = "") -> bool:
    text = f"{event_title or ''}\n{event_summary or ''}"
    cleaned = normalize_entity_name(name)
    if not cleaned:
        return False
    disclosure_target = re.compile(
        rf"\b(?:to\s+)?(?:inform|notify|tell|warn)\s+{re.escape(cleaned)}\b[^.?!]{{0,80}}\b(?:about|of|that)\b",
        flags=re.IGNORECASE,
    )
    delegated_disclosure = re.compile(
        rf"\b(?:ask|asks|asked|request|requests|requested)\b[^.?!]{{0,120}}\b(?:to\s+)?(?:inform|notify|tell|warn)\s+{re.escape(cleaned)}\b",
        flags=re.IGNORECASE,
    )
    if not (disclosure_target.search(text) or delegated_disclosure.search(text)):
        return False
    actor_pattern = re.compile(
        rf"\b{re.escape(cleaned)}\b[^\n.?!]{{0,80}}\b(?:act|acts|acted|ask|asks|asked|answer|answers|answered|arrive|arrives|arrived|call|calls|called|go|goes|went|say|says|said|speak|speaks|spoke|write|writes|wrote)\b",
        flags=re.IGNORECASE,
    )
    return not bool(actor_pattern.search(text))


def _contains_possessive_reference(value: str) -> bool:
    return bool(re.search(r"\b[\w-]+(?:'s|\u2019s|\u00e2\u20ac\u2122s)\b", value, flags=re.IGNORECASE))


def _is_possessive_suffix(value: str) -> bool:
    return value.startswith("'s") or value.startswith("\u2019s") or value.startswith("\u00e2\u20ac\u2122s")


def _scene_narrative_grounding(scene: SceneArtifact) -> dict[str, Any]:
    raw = scene.metadata.get("narrative_grounding") if isinstance(scene.metadata, dict) else None
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _batch_narrative_grounding(scene_slices: list[dict[str, Any]], scene_ids: list[str]) -> dict[str, Any]:
    wanted = {str(scene_id or "").strip() for scene_id in scene_ids if str(scene_id or "").strip()}
    for item in scene_slices:
        if wanted and str(item.get("scene_id") or "").strip() not in wanted:
            continue
        grounding = item.get("narrative_grounding")
        if isinstance(grounding, dict) and (grounding.get("narrator_character_id") or grounding.get("addressee_character_ids")):
            return dict(grounding)
    return {}


def _should_keep_relationship_artifact(relationship: RelationshipArtifact) -> bool:
    if (
        relationship.relationship_type == "artifact_usage"
        and relationship.source_ref.startswith("char-")
        and relationship.target_ref.startswith("char-")
    ):
        return False
    if (
        relationship.relationship_type == "location_association"
        and relationship.source_ref.startswith("char-")
        and relationship.target_ref.startswith("char-")
    ):
        return False
    if relationship.source_ref.startswith("char-") and relationship.target_ref.startswith("char-"):
        description = relationship.description.casefold()
        if any(marker in description for marker in [" seal", "wax seal", "object provenance", "artifact provenance"]):
            return False
        if relationship.relationship_type == "romantic" and _romantic_description_names_different_partner(relationship):
            return False
        if relationship.relationship_type == "romantic" and _romantic_description_is_comparative_context(relationship):
            return False
        if relationship.relationship_type == "marriage" and _marriage_description_lacks_pair_support(relationship):
            return False
        if relationship.relationship_type in {"family", "sibling"} and _family_description_is_comparative_context(relationship):
            return False
        if relationship.relationship_type in {"family", "sibling"} and _family_description_lacks_pair_support(relationship):
            return False
    return True


def _romantic_description_names_different_partner(relationship: RelationshipArtifact) -> bool:
    source_name = _character_ref_display_name(relationship.source_ref).casefold()
    target_name = _character_ref_display_name(relationship.target_ref).casefold()
    description = relationship.description.casefold()
    direct_pair_pattern = (
        rf"\b{re.escape(source_name)}\b[^.?!]{{0,120}}\b(?:love|loves|romance|romantic|lover|relationship)\b[^.?!]{{0,120}}\b{re.escape(target_name)}\b"
        rf"|"
        rf"\b{re.escape(target_name)}\b[^.?!]{{0,120}}\b(?:love|loves|romance|romantic|lover|relationship)\b[^.?!]{{0,120}}\b{re.escape(source_name)}\b"
    )
    if re.search(r"\b(?:ability to love|love a mortal|love mortals|mortal[- ]faerie love)\b", description) and not re.search(
        direct_pair_pattern,
        description,
        flags=re.IGNORECASE,
    ):
        return True
    for match in re.finditer(r"\b(?:relationship|romance|lover|love)\s+with\s+([a-z][a-z0-9_-]+)", description):
        partner = match.group(1).replace("-", " ")
        if partner and partner not in {source_name, target_name}:
            return True
    return False


def _romantic_description_is_comparative_context(relationship: RelationshipArtifact) -> bool:
    description = relationship.description.casefold()
    if not re.search(r"\b(?:compare|compares|compared|comparing|comparison|like|unlike|parallel|parallels)\b", description):
        return False
    source_name = _character_ref_display_name(relationship.source_ref).casefold()
    target_name = _character_ref_display_name(relationship.target_ref).casefold()
    direct_pair_pattern = (
        rf"\b{re.escape(source_name)}\b[^\n.?!]{{0,120}}\b(?:kiss|kisses|kissed|love|loves|loved|romance|romantic|lover|relationship|desire|desires|desired|marry|marries|married)\b[^\n.?!]{{0,120}}\b{re.escape(target_name)}\b"
        rf"|"
        rf"\b{re.escape(target_name)}\b[^\n.?!]{{0,120}}\b(?:kiss|kisses|kissed|love|loves|loved|romance|romantic|lover|relationship|desire|desires|desired|marry|marries|married)\b[^\n.?!]{{0,120}}\b{re.escape(source_name)}\b"
    )
    return not bool(re.search(direct_pair_pattern, description, flags=re.IGNORECASE))


def _marriage_description_lacks_pair_support(relationship: RelationshipArtifact) -> bool:
    source_name = _character_ref_display_name(relationship.source_ref).casefold()
    target_name = _character_ref_display_name(relationship.target_ref).casefold()
    description = relationship.description.casefold()
    direct_pair_pattern = (
        rf"\b{re.escape(source_name)}\b[^.?!]{{0,140}}\b(?:marry|marries|married|marriage|wed|weds|wedding)\b[^.?!]{{0,140}}\b{re.escape(target_name)}\b"
        rf"|"
        rf"\b{re.escape(target_name)}\b[^.?!]{{0,140}}\b(?:marry|marries|married|marriage|wed|weds|wedding)\b[^.?!]{{0,140}}\b{re.escape(source_name)}\b"
    )
    return not bool(re.search(direct_pair_pattern, description, flags=re.IGNORECASE))


def _family_description_lacks_pair_support(relationship: RelationshipArtifact) -> bool:
    source_name = _character_ref_display_name(relationship.source_ref).casefold()
    target_name = _character_ref_display_name(relationship.target_ref).casefold()
    description = relationship.description.casefold()
    kinship_terms = (
        "sister|sisters|brother|brothers|sibling|siblings|mother|mothers|father|fathers|parent|parents|daughter|daughters|son|sons|child|children|aunt|aunts|uncle|uncles|cousin|cousins|wife|wives|husband|husbands|spouse|spouses|family"
    )
    direct_pair_pattern = (
        rf"\b{re.escape(source_name)}\b[^\n.?!]{{0,80}}\b(?:and|&)\b[^\n.?!]{{0,80}}\b{re.escape(target_name)}\b[^\n.?!]{{0,80}}\b(?:are|were|remain|remained)\b[^\n.?!]{{0,40}}\b(?:{kinship_terms})\b"
        rf"|"
        rf"\b{re.escape(target_name)}\b[^\n.?!]{{0,80}}\b(?:and|&)\b[^\n.?!]{{0,80}}\b{re.escape(source_name)}\b[^\n.?!]{{0,80}}\b(?:are|were|remain|remained)\b[^\n.?!]{{0,40}}\b(?:{kinship_terms})\b"
        rf"|"
        rf"\b{re.escape(source_name)}(?:'s|\u2019s)?\b[^\n.?!]{{0,80}}\b(?:{kinship_terms})\b[^\n.?!]{{0,80}}\b{re.escape(target_name)}\b"
        rf"|"
        rf"\b{re.escape(target_name)}(?:'s|\u2019s)?\b[^\n.?!]{{0,80}}\b(?:{kinship_terms})\b[^\n.?!]{{0,80}}\b{re.escape(source_name)}\b"
    )
    return not bool(re.search(direct_pair_pattern, description, flags=re.IGNORECASE))


def _family_description_is_comparative_context(relationship: RelationshipArtifact) -> bool:
    return bool(
        re.search(
            r"\b(?:compare|compares|compared|comparing|comparison|similar|similarities|like|unlike|parallel|parallels)\b",
            relationship.description.casefold(),
            flags=re.IGNORECASE,
        )
    )


def _character_ref_display_name(ref: str) -> str:
    value = str(ref or "")
    if value.startswith("char-"):
        value = value[5:]
    return value.replace("-", " ").strip()


def _should_keep_entity_name(name: str, *, identity_bundle: CanonicalIdentityBundle) -> bool:
    normalized = normalize_entity_name(name)
    if not normalized or len(normalized) < 2:
        return False
    alias_map = _identity_alias_map(identity_bundle)
    if normalized.casefold() in alias_map:
        return False
    if normalized.casefold() in {"he", "she", "they", "we", "you", "i", "it", "there", "here"}:
        return False
    if len(normalized.split()) > 8:
        return False
    return True


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = normalize_entity_name(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results
