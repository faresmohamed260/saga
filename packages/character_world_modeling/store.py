"""Persistence mapping for character and world modeling artifacts."""

from __future__ import annotations

from typing import Any

from packages.analysis_foundation.contracts import BookArtifact, CanonicalIdentityBundle, ChapterArtifact, SceneArtifact
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.canon_extraction.contracts import EntityArtifact, EventArtifact, RelationshipArtifact, TimelineArtifact
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.contracts import (
    CharacterProfileArtifact,
    StableCharacterStateArtifact,
    WorldStateArtifact,
)
from packages.persistence_runtime import PersistenceRuntimeClient


class CharacterWorldModelingStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.analysis = AnalysisFoundationStore(persistence)
        self.canon = CanonExtractionStore(persistence)

    def load_series_context(self, *, series_id: str) -> dict[str, Any]:
        books = self.analysis.list_books(series_id=series_id)
        book_map = {book.book_id: book for book in books}
        chapters: list[ChapterArtifact] = []
        scenes: list[SceneArtifact] = []
        for book in books:
            chapters.extend(self.analysis.list_chapters(book_id=book.book_id))
            scenes.extend(self.analysis.list_scenes(book_id=book.book_id))
        identity_bundle = self.analysis.load_identity_bundle(series_id=series_id)
        events = self.canon.list_events(series_id=series_id)
        entities = self.canon.list_entities(series_id=series_id)
        relationships = self.canon.list_relationships(series_id=series_id)
        timeline = self.canon.list_timeline(series_id=series_id)
        scenes.sort(key=lambda item: (item.book_id, item.chapter_index, item.scene_index))
        chapters.sort(key=lambda item: (item.book_id, item.chapter_index))
        return {
            "series_id": series_id,
            "books": books,
            "book_map": book_map,
            "chapters": chapters,
            "scenes": scenes,
            "identity_bundle": identity_bundle,
            "events": events,
            "entities": entities,
            "relationships": relationships,
            "timeline": timeline,
        }

    def replace_character_profiles(
        self,
        *,
        series_id: str,
        profiles: list[CharacterProfileArtifact],
    ) -> list[CharacterProfileArtifact]:
        self.persistence.library.delete_records(record_type="character_profile", series_id=series_id)
        persisted: list[CharacterProfileArtifact] = []
        for item in profiles:
            payload = self.persistence.library.upsert_record(
                item.profile_id,
                record_type="character_profile",
                series_id=item.series_id,
                title=item.canonical_name,
                payload=item.model_dump(),
            )
            persisted.append(CharacterProfileArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_stable_character_states(
        self,
        *,
        series_id: str,
        states: list[StableCharacterStateArtifact],
    ) -> list[StableCharacterStateArtifact]:
        self.persistence.library.delete_records(record_type="stable_character_state", series_id=series_id)
        persisted: list[StableCharacterStateArtifact] = []
        for item in states:
            payload = self.persistence.library.upsert_record(
                item.stable_state_id,
                record_type="stable_character_state",
                series_id=item.series_id,
                title=item.canonical_name,
                payload=item.model_dump(),
            )
            persisted.append(StableCharacterStateArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def replace_world_states(
        self,
        *,
        series_id: str,
        world_states: list[WorldStateArtifact],
    ) -> list[WorldStateArtifact]:
        self.delete_world_states(series_id=series_id)
        return self.upsert_world_states(world_states=world_states)

    def delete_world_states(self, *, series_id: str) -> int:
        return self.persistence.library.delete_records(record_type="world_state", series_id=series_id)

    def upsert_world_states(
        self,
        *,
        world_states: list[WorldStateArtifact],
    ) -> list[WorldStateArtifact]:
        persisted: list[WorldStateArtifact] = []
        for item in world_states:
            payload = self.persistence.library.upsert_record(
                item.world_state_id,
                record_type="world_state",
                series_id=item.series_id,
                title=item.canonical_name,
                payload=item.model_dump(),
            )
            persisted.append(WorldStateArtifact.model_validate(dict(payload.get("payload") or {})))
        return persisted

    def list_character_profiles(self, *, series_id: str) -> list[CharacterProfileArtifact]:
        return _validated_records(
            self.persistence.library.list_records(record_type="character_profile", series_id=series_id, limit=10000),
            CharacterProfileArtifact,
        )

    def list_stable_character_states(self, *, series_id: str) -> list[StableCharacterStateArtifact]:
        return _validated_records(
            self.persistence.library.list_records(record_type="stable_character_state", series_id=series_id, limit=10000),
            StableCharacterStateArtifact,
        )

    def list_world_states(self, *, series_id: str) -> list[WorldStateArtifact]:
        return _validated_records(
            self.persistence.library.list_records(record_type="world_state", series_id=series_id, limit=10000),
            WorldStateArtifact,
        )


def _validated_records(rows: list[dict[str, Any]], model_type):
    results = []
    for row in rows:
        payload = dict(row.get("payload") or {})
        if not payload:
            continue
        results.append(model_type.model_validate(payload))
    return results
