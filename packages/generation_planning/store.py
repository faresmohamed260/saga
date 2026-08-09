"""Persistence mapping for generation planning artifacts."""

from __future__ import annotations

from typing import Any

from packages.analysis_foundation.contracts import BookArtifact, CanonicalIdentityBundle
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.canon_extraction.contracts import EntityArtifact, EventArtifact, RelationshipArtifact, TimelineArtifact
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.contracts import CharacterProfileArtifact, StableCharacterStateArtifact, WorldStateArtifact
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.generation_planning.contracts import CanonGroundingArtifact, GenerationBlueprintArtifact, StoryIntentArtifact
from packages.persistence_runtime import PersistenceRuntimeClient


class GenerationPlanningStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.analysis = AnalysisFoundationStore(persistence)
        self.canon = CanonExtractionStore(persistence)
        self.character_world = CharacterWorldModelingStore(persistence)

    def load_series_context(self, *, series_id: str) -> dict[str, Any]:
        books: list[BookArtifact] = self.analysis.list_books(series_id=series_id)
        identity_bundle: CanonicalIdentityBundle | None = self.analysis.load_identity_bundle(series_id=series_id)
        events: list[EventArtifact] = self.canon.list_events(series_id=series_id)
        entities: list[EntityArtifact] = self.canon.list_entities(series_id=series_id)
        relationships: list[RelationshipArtifact] = self.canon.list_relationships(series_id=series_id)
        timeline: list[TimelineArtifact] = self.canon.list_timeline(series_id=series_id)
        profiles: list[CharacterProfileArtifact] = self.character_world.list_character_profiles(series_id=series_id)
        states: list[StableCharacterStateArtifact] = self.character_world.list_stable_character_states(series_id=series_id)
        world_states: list[WorldStateArtifact] = self.character_world.list_world_states(series_id=series_id)
        return {
            "series_id": series_id,
            "books": books,
            "identity_bundle": identity_bundle,
            "events": events,
            "entities": entities,
            "relationships": relationships,
            "timeline": timeline,
            "character_profiles": profiles,
            "stable_character_states": states,
            "world_states": world_states,
        }

    def upsert_intent(self, *, series_id: str, intent: StoryIntentArtifact) -> StoryIntentArtifact:
        payload = self.persistence.library.upsert_record(
            intent.intent_id,
            record_type="generation_story_intent",
            series_id=series_id,
            title=intent.premise[:160],
            payload=intent.model_dump(),
        )
        return StoryIntentArtifact.model_validate(dict(payload.get("payload") or {}))

    def upsert_grounding(self, *, series_id: str, grounding: CanonGroundingArtifact) -> CanonGroundingArtifact:
        payload = self.persistence.library.upsert_record(
            grounding.grounding_id,
            record_type="generation_canon_grounding",
            series_id=series_id,
            title=f"Grounding for {series_id}",
            payload=grounding.model_dump(),
        )
        return CanonGroundingArtifact.model_validate(dict(payload.get("payload") or {}))

    def upsert_blueprint(self, *, series_id: str, blueprint: GenerationBlueprintArtifact) -> GenerationBlueprintArtifact:
        payload = self.persistence.library.upsert_record(
            blueprint.blueprint_id,
            record_type="generation_blueprint",
            series_id=series_id,
            title=blueprint.title or blueprint.premise[:160],
            payload=blueprint.model_dump(),
        )
        return GenerationBlueprintArtifact.model_validate(dict(payload.get("payload") or {}))

    def list_blueprints(self, *, series_id: str) -> list[GenerationBlueprintArtifact]:
        return _validated_records(
            self.persistence.library.list_records(record_type="generation_blueprint", series_id=series_id, limit=1000),
            GenerationBlueprintArtifact,
        )

    def list_intents(self, *, series_id: str) -> list[StoryIntentArtifact]:
        return _validated_records(
            self.persistence.library.list_records(record_type="generation_story_intent", series_id=series_id, limit=1000),
            StoryIntentArtifact,
        )


def _validated_records(rows: list[dict[str, Any]], model_type):
    results = []
    for row in rows:
        payload = dict(row.get("payload") or {})
        if payload:
            results.append(model_type.model_validate(payload))
    return results
