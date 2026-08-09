from __future__ import annotations

from pathlib import Path

from packages.analysis_foundation.contracts import BookArtifact, CanonicalCharacter, CanonicalIdentityBundle
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.canon_extraction.contracts import EntityArtifact, EventArtifact, RelationshipArtifact, TimelineArtifact
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.contracts import CharacterProfileArtifact, StableCharacterStateArtifact, WorldStateArtifact
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.generation_planning import GenerationPlanningRuntime, evaluate_generation_blueprint
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


class StubGenerationPlanningReasoningRuntime:
    def __init__(self, *, include_bad_refs: bool = False) -> None:
        self.include_bad_refs = include_bad_refs
        self._last = {}

    def provider_name(self) -> str:
        return "ollama"

    def resolved_model_name(self) -> str:
        return "gpt-oss:120b-cloud"

    def generate_json(self, prompt: str, strict: bool = False, validator=None, max_tokens: int = 4096, response_format=None, tools=None, tool_choice=None):
        del prompt, strict, validator, max_tokens, response_format, tools, tool_choice
        canon_refs = ["event-meeting", "timeline-meeting"]
        character_refs = ["char-fares", "char-kareem"]
        entity_refs = ["entity-silver-notebook"]
        if self.include_bad_refs:
            canon_refs.append("event-invented")
            character_refs.append("char-invented")
            entity_refs.append("entity-invented")
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        return {
            "title": "A Grounded Sequel Plan",
            "continuation_plan": "Fares and Kareem continue from the notebook discussion.",
            "divergence_plan": "No unsupported divergence.",
            "chapter_outline": [
                {
                    "chapter_index": 1,
                    "title": "The Notebook Reopens",
                    "goal": "Use the notebook as the grounded inciting object.",
                    "canon_refs": canon_refs,
                    "character_refs": character_refs,
                    "entity_refs": entity_refs,
                }
            ],
            "scene_plan": [
                {
                    "scene_id": "planned-scene-1-1",
                    "chapter_index": 1,
                    "scene_index": 1,
                    "summary": "Fares and Kareem revisit the silver notebook.",
                    "purpose": "Anchor the continuation in known character and object continuity.",
                    "canon_refs": canon_refs,
                    "character_refs": character_refs,
                    "entity_refs": entity_refs,
                    "visual_requirements": ["Show the hallway, notebook, and both collaborators."],
                    "audio_requirements": ["Use calm collaborative dialogue pacing."],
                }
            ],
            "visual_requirements": ["Plan image briefs from each scene."],
            "audio_requirements": ["Plan audiobook narration from each scene."],
            "canon_refs": canon_refs,
            "character_refs": character_refs,
            "entity_refs": entity_refs,
        }

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class FailingGenerationPlanningReasoningRuntime(StubGenerationPlanningReasoningRuntime):
    def generate_json(self, *args, **kwargs):
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "error"}
        return {"error": "max_retries_exceeded"}


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="generation-planning-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'generation_planning.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="generation-planning-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _seed_upstream_outputs(client, *, series_id: str = "series-1") -> None:
    analysis = AnalysisFoundationStore(client)
    canon = CanonExtractionStore(client)
    cwm = CharacterWorldModelingStore(client)
    analysis.upsert_book(
        BookArtifact(
            book_id="book-1",
            series_id=series_id,
            title="Fixture Book",
            book_index=1,
            source_type="txt",
            chapter_count=1,
            word_count=20,
        )
    )
    analysis.save_identity_bundle(
        CanonicalIdentityBundle(
            series_id=series_id,
            provider_name="modal_xcore_litbank",
            book_ids=["book-1"],
            characters=[
                CanonicalCharacter(character_id="char-fares", display_name="Fares"),
                CanonicalCharacter(character_id="char-kareem", display_name="Kareem"),
            ],
        )
    )
    canon.replace_events(
        series_id=series_id,
        events=[
            EventArtifact(
                event_id="event-meeting",
                series_id=series_id,
                book_id="book-1",
                scene_id="scene-1",
                chapter_index=1,
                scene_index=1,
                event_index=1,
                title="Fares meets Kareem",
                summary="Fares greets Kareem and discusses the silver notebook.",
                event_type="meeting",
                participant_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-silver-notebook"],
            )
        ],
    )
    canon.replace_entities(
        series_id=series_id,
        entities=[
            EntityArtifact(
                entity_id="entity-silver-notebook",
                series_id=series_id,
                canonical_name="silver notebook",
                entity_type="object",
                description="A silver notebook used during the discussion.",
            )
        ],
    )
    canon.replace_relationships(
        series_id=series_id,
        relationships=[
            RelationshipArtifact(
                relationship_id="relationship-fares-kareem",
                series_id=series_id,
                source_ref="char-fares",
                target_ref="char-kareem",
                relationship_type="collaborator",
                description="Fares and Kareem collaborate calmly.",
            )
        ],
    )
    canon.replace_timeline(
        series_id=series_id,
        timeline=[
            TimelineArtifact(
                timeline_id="timeline-meeting",
                series_id=series_id,
                book_id="book-1",
                scene_id="scene-1",
                event_id="event-meeting",
                sequence_index=1,
                chapter_index=1,
                scene_index=1,
                title="Fares meets Kareem",
                summary="The notebook discussion begins.",
                event_type="meeting",
                participant_refs=["char-fares", "char-kareem"],
            )
        ],
    )
    cwm.replace_character_profiles(
        series_id=series_id,
        profiles=[
            CharacterProfileArtifact(
                profile_id="profile-fares",
                series_id=series_id,
                character_id="char-fares",
                canonical_name="Fares",
                overview="Fares is a focused collaborator.",
                latest_state_summary="Fares discusses the notebook.",
                important_event_ids=["event-meeting"],
            ),
            CharacterProfileArtifact(
                profile_id="profile-kareem",
                series_id=series_id,
                character_id="char-kareem",
                canonical_name="Kareem",
                overview="Kareem is a steady collaborator.",
                latest_state_summary="Kareem opens the notebook.",
                important_event_ids=["event-meeting"],
            ),
        ],
    )
    cwm.replace_stable_character_states(
        series_id=series_id,
        states=[
            StableCharacterStateArtifact(
                stable_state_id="state-fares",
                series_id=series_id,
                character_id="char-fares",
                canonical_name="Fares",
                stable_attributes={"role": "collaborator"},
                summary="Fares is established as a collaborator.",
            )
        ],
    )
    cwm.replace_world_states(
        series_id=series_id,
        world_states=[
            WorldStateArtifact(
                world_state_id="world-notebook",
                series_id=series_id,
                entity_id="entity-silver-notebook",
                canonical_name="silver notebook",
                entity_type="object",
                description="A silver notebook.",
                current_state_summary="The notebook is open during the review.",
                story_relevance="It anchors the scene.",
                supporting_event_ids=["event-meeting"],
            )
        ],
    )


def test_generation_planning_persists_blueprint_and_passes_quality(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed_upstream_outputs(client)
    result = GenerationPlanningRuntime(
        persistence=client,
        reasoning_runtime=StubGenerationPlanningReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    ).invoke(
        series_id="series-1",
        premise="Plan a canon-grounded sequel.",
        target_audience="YA fantasy readers",
        tone="quiet intrigue",
        desired_chapter_count=2,
        thread_id="generation-planning-test",
    )

    assert len(result.blueprint.chapter_outline) == 2
    assert len(result.blueprint.scene_plan) == 4
    assert result.blueprint.metadata["reasoning_model"] == "gpt-oss:120b-cloud"
    rows = client.library.list_records(record_type="generation_blueprint", series_id="series-1", limit=20)
    assert len(rows) == 1
    metrics = evaluate_generation_blueprint(
        result,
        valid_canon_refs={"event-meeting", "timeline-meeting"},
        valid_character_refs={"char-fares", "char-kareem"},
        valid_entity_refs={"entity-silver-notebook"},
    )
    assert metrics.pass_quality_gate is True


def test_generation_planning_sanitizes_provider_refs(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed_upstream_outputs(client)
    result = GenerationPlanningRuntime(
        persistence=client,
        reasoning_runtime=StubGenerationPlanningReasoningRuntime(include_bad_refs=True),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", premise="Plan a canon-grounded sequel.", thread_id="generation-planning-test")

    rendered = result.model_dump_json()
    assert "event-invented" not in rendered
    assert "char-invented" not in rendered
    assert "entity-invented" not in rendered


def test_generation_planning_fallback_remains_usable(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed_upstream_outputs(client)
    result = GenerationPlanningRuntime(
        persistence=client,
        reasoning_runtime=FailingGenerationPlanningReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", premise="Plan a canon-grounded sequel.", desired_chapter_count=2)

    assert len(result.blueprint.chapter_outline) == 2
    assert len(result.blueprint.scene_plan) == 4
    assert result.blueprint.metadata["request_metadata"]["deterministic_fallback"] is True
