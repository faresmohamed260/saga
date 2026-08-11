from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

from packages.analysis_foundation import AnalysisFoundationRuntime
from packages.canon_extraction import CanonExtractionRuntime
from packages.canon_extraction.contracts import EntityArtifact, RelationshipArtifact
from packages.canon_extraction import pipeline as canon_pipeline
from packages.canon_extraction.service import load_canon_extraction_service_config_from_env
from packages.canon_extraction.pipeline import (
    EntityAgent,
    EventAgent,
    _augment_participant_names_from_event_text,
    _batched_scene_slices,
    _chunk_scene_text,
    _entities_for_scene_slice_batch,
    _has_participant_text_support,
    _identity_character_context,
    _normalize_entity_type,
    _normalize_relationship_type,
    _resolve_participant_refs,
    _resolve_name_refs,
    _resolve_single_name_ref,
    _should_keep_relationship_artifact,
    _should_retry_split_extraction_error,
    _split_scene_slices_for_retry,
)
from packages.canon_extraction.store import CanonExtractionStore, normalize_entity_name
from packages.analysis_foundation.contracts import BookArtifact, CanonicalCharacter, CanonicalIdentityBundle, ChapterArtifact, SceneArtifact
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.runtime_common import RuntimeCancelledError


def test_parallel_canon_jobs_stop_scheduling_after_cancellation(monkeypatch):
    monkeypatch.setattr(canon_pipeline, "CANON_EXTRACTION_PARALLELISM", 2)
    cancelled = threading.Event()
    started: list[int] = []

    def worker(job):
        started.append(job["job_index"])
        if job["job_index"] == 0:
            cancelled.set()
        time.sleep(0.01)
        return job

    with pytest.raises(RuntimeCancelledError):
        canon_pipeline._run_ordered_parallel_jobs(
            [{"job_index": index} for index in range(20)],
            worker,
            cancellation_checker=cancelled.is_set,
        )

    assert len(started) <= 2


def test_mistral_canon_profile_defaults_to_extraction_model(monkeypatch):
    monkeypatch.setenv("SAGA_CANON_EXTRACTION_REASONING_MODE", "mistral")
    monkeypatch.delenv("SAGA_CANON_EXTRACTION_REASONING_MODEL", raising=False)

    config = load_canon_extraction_service_config_from_env()

    assert config.reasoning_model == "mistral-small-2603"


class StubIdentityRuntime:
    def provider_name(self) -> str:
        return "modal_xcore_litbank"

    def analyze_chapters(self, *, chapters: list[dict], use_chunking: bool | None = None):
        del use_chunking
        return _SimpleResult(
            {
                "provider_name": "modal_xcore_litbank",
                "app_name": "saga-coref-runtime",
                "model_name": "xcore-litbank",
                "runtime_seconds": 1.0,
                "chunk_count": 1,
                "input_stats": {"chapter_count": len(chapters)},
                "clusters": [
                    {
                        "display_name": "Fares",
                        "aliases": [],
                        "proper_mentions": ["Fares"],
                        "pronoun_mentions": ["he"],
                        "mention_count": 2,
                    },
                    {
                        "display_name": "Kareem",
                        "aliases": [],
                        "proper_mentions": ["Kareem"],
                        "pronoun_mentions": [],
                        "mention_count": 2,
                    },
                ],
            }
        )


class StubReasoningRuntime:
    def provider_name(self) -> str:
        return "ollama"

    def resolved_model_name(self) -> str:
        return "gpt-oss:120b-cloud"

    def __init__(self) -> None:
        self._last = {}
        self.response_schema_names: list[str] = []

    def generate_json(self, prompt: str, strict: bool = False, validator=None, max_tokens: int = 4096, response_format=None, tools=None, tool_choice=None, cancellation_checker=None):
        del strict, validator, max_tokens, tools, tool_choice, cancellation_checker
        self.response_schema_names.append(str(((response_format or {}).get("json_schema") or {}).get("name") or ""))
        lowered = prompt.lower()
        scene_id = _first_scene_id(prompt)
        if "key 'events'" in lowered:
            payload = {
                "events": [
                    {
                        "scene_id": scene_id,
                        "title": "Fares meets Kareem",
                        "summary": "Fares greets Kareem and they review the project deadline.",
                        "event_type": "meeting",
                        "participant_names": ["Fares", "Kareem"],
                        "entity_names": ["project deadline"],
                    }
                ]
            }
        elif "key 'entities'" in lowered:
            payload = {
                "entities": [
                    {
                        "canonical_name": "project deadline",
                        "entity_type": "concept",
                        "description": "The deadline the team is discussing.",
                        "aliases": ["deadline"],
                        "scene_ids": [scene_id],
                    }
                ]
            }
        else:
            payload = {
                "relationships": [
                    {
                        "source_name": "Fares",
                        "target_name": "Kareem",
                        "relationship_type": "collaborates_with",
                        "description": "They work together on the same project review.",
                        "scene_ids": [scene_id],
                    }
                ]
            }
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        return payload

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class AlwaysFailReasoningRuntime(StubReasoningRuntime):
    def generate_json(self, *args, **kwargs):
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "error"}
        return {"error": "max_retries_exceeded"}


class EmptyThenGroundedEntityRuntime(StubReasoningRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.entity_calls = 0
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **kwargs):
        if "key 'entities'" not in prompt.lower():
            return super().generate_json(prompt, **kwargs)
        self.entity_calls += 1
        self.prompts.append(prompt)
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        if self.entity_calls == 1:
            return {"entities": []}
        return {
            "entities": [{
                "canonical_name": "Glass Palace",
                "entity_type": "location",
                "description": "A palace named in the source scene.",
                "aliases": [],
                "scene_ids": [_first_scene_id(prompt)],
            }]
        }


class AlwaysEmptyEntityRuntime(StubReasoningRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.entity_calls = 0

    def generate_json(self, prompt: str, **kwargs):
        if "key 'entities'" not in prompt.lower():
            return super().generate_json(prompt, **kwargs)
        self.entity_calls += 1
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        return {"entities": []}


class EntityStoreStub:
    def __init__(self) -> None:
        self.persisted: list[EntityArtifact] | None = None

    def list_stage_jobs(self, **kwargs):
        return {}

    def delete_stage_jobs(self, **kwargs):
        return 0

    def upsert_stage_job(self, **kwargs):
        return kwargs["payload"]

    def replace_entities(self, *, series_id: str, entities: list[EntityArtifact]):
        del series_id
        self.persisted = entities
        return entities


class _SimpleResult:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self) -> dict:
        return dict(self.payload)


def _first_scene_id(prompt: str) -> str:
    marker = '"scene_id": "'
    start = prompt.find(marker)
    if start == -1:
        return "scene-001"
    start += len(marker)
    end = prompt.find('"', start)
    return prompt[start:end] if end > start else "scene-001"


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="canon-extraction-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'canon_extraction.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="canon-extraction-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _analysis_source(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.txt"
    path.write_text(
        "Chapter 1\n\n"
        "Fares greeted Kareem in the hallway and asked about the project deadline.\n\n"
        "Kareem answered calmly and opened the notebook.\n",
        encoding="utf-8",
    )
    return path


def _entity_agent_inputs(*, text: str = "Taryn enters the Glass Palace."):
    book = BookArtifact(
        book_id="book-1",
        series_id="series-1",
        title="Fixture",
        book_index=1,
        source_uri="fixture.txt",
        metadata={},
    )
    chapter = ChapterArtifact(
        chapter_id="chapter-1",
        series_id="series-1",
        book_id="book-1",
        chapter_index=1,
        title="One",
        content=text,
        source_id="source-1",
        word_count=len(text.split()),
        metadata={},
    )
    scene = SceneArtifact(
        scene_id="scene-1",
        series_id="series-1",
        book_id="book-1",
        chapter_id="chapter-1",
        chapter_index=1,
        scene_index=1,
        title="Arrival",
        summary="Taryn enters the Glass Palace.",
        text=text,
        word_count=len(text.split()),
        metadata={},
    )
    identity = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        book_ids=["book-1"],
        characters=[CanonicalCharacter(character_id="char-taryn", display_name="Taryn")],
        alias_map={},
    )
    return book, chapter, scene, identity


def test_entity_extraction_repairs_schema_valid_empty_response_once():
    runtime = EmptyThenGroundedEntityRuntime()
    agent = EntityAgent(store=None, reasoning_runtime=runtime)  # type: ignore[arg-type]
    book, chapter, scene, identity = _entity_agent_inputs()

    payloads = agent._extract_chapter_entities_with_fallback(
        book=book,
        chapter=chapter,
        scene_slices=[{
            "scene_id": scene.scene_id,
            "chapter_index": 1,
            "scene_index": 1,
            "chunk_index": 1,
            "summary": scene.summary,
            "excerpt": scene.text,
            "narrative_grounding": {},
        }],
        identity_bundle=identity,
    )

    assert runtime.entity_calls == 2
    assert len(payloads[0].entities) == 1
    assert "previous extraction returned an empty entities list" in runtime.prompts[1]


def test_entity_extraction_fails_closed_after_one_empty_repair_for_long_source():
    runtime = AlwaysEmptyEntityRuntime()
    store = EntityStoreStub()
    book, chapter, scene, identity = _entity_agent_inputs(text="The abandoned glass palace has a silver gate. " * 80)

    with pytest.raises(RuntimeError, match="Entity extraction completeness failed"):
        EntityAgent(store=store, reasoning_runtime=runtime).run(
            series_id="series-1",
            books=[book],
            chapters=[chapter],
            scenes=[scene],
            identity_bundle=identity,
        )

    assert runtime.entity_calls == 2
    assert store.persisted is None


def test_entity_extraction_discards_model_invented_scene_ids():
    class InventedSceneRuntime(StubReasoningRuntime):
        def generate_json(self, prompt: str, **kwargs):
            payload = super().generate_json(prompt, **kwargs)
            if "key 'entities'" in prompt.lower():
                payload["entities"][0]["scene_ids"] = ["scene-1", "chapter-999-scene-999"]
            return payload

    store = EntityStoreStub()
    book, chapter, scene, identity = _entity_agent_inputs()
    result = EntityAgent(store=store, reasoning_runtime=InventedSceneRuntime()).run(
        series_id="series-1",
        books=[book],
        chapters=[chapter],
        scenes=[scene],
        identity_bundle=identity,
    )

    assert result["entities"][0]["mention_scene_ids"] == ["scene-1"]


def test_canon_extraction_persists_event_entity_relationship_and_timeline(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = _analysis_source(tmp_path)
    analysis = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    analysis.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-foundation-test")
    reasoning = StubReasoningRuntime()
    runtime = CanonExtractionRuntime(
        persistence=client,
        reasoning_runtime=reasoning,
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-1", thread_id="canon-extraction-test")

    assert len(result.events) == 1
    assert len(result.entities) == 1
    assert len(result.relationships) == 1
    assert len(result.timeline) == 1
    assert result.timeline[0].event_id == result.events[0].event_id
    assert result.run_metadata["stage_order"] == [
        "event_extraction",
        "entity_extraction",
        "relationship_extraction",
        "timeline_construction",
    ]
    assert result.run_metadata["stage_details"]["event_extraction"]["parallelism"] >= 1
    assert result.run_metadata["stage_details"]["event_extraction"]["job_latency_seconds"]["count"] >= 1
    assert set(reasoning.response_schema_names) == {"canon_events", "canon_entities", "canon_relationships"}
    persisted_events = client.library.list_records(record_type="event", series_id="series-1", limit=20)
    persisted_entities = client.library.list_records(record_type="entity", series_id="series-1", limit=20)
    persisted_relationships = client.library.list_records(record_type="relationship", series_id="series-1", limit=20)
    persisted_timeline = client.library.list_records(record_type="timeline", series_id="series-1", limit=20)
    assert len(persisted_events) == 1
    assert len(persisted_entities) == 1
    assert len(persisted_relationships) == 1
    assert len(persisted_timeline) == 1


def test_schema_invalid_canon_payload_is_eligible_for_bounded_split_retry():
    error = RuntimeError("Event extraction payload_validation_failed: event_type is required")
    assert _should_retry_split_extraction_error(error) is True


def test_event_agent_rebuilds_from_persisted_stage_jobs_without_reasoning(tmp_path: Path, monkeypatch):
    client = _persistence(tmp_path)
    source_path = _analysis_source(tmp_path)
    analysis = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    analysis.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-foundation-test")
    runtime = CanonExtractionRuntime(
        persistence=client,
        reasoning_runtime=StubReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    runtime.invoke(series_id="series-1", thread_id="canon-extraction-test")
    client.library.delete_records(record_type="event", series_id="series-1")
    context = CanonExtractionStore(client).load_series_context(series_id="series-1")

    monkeypatch.setenv("SAGA_CANON_RESUME_STAGES", "event_extraction")
    payload = EventAgent(
        store=CanonExtractionStore(client),
        reasoning_runtime=AlwaysFailReasoningRuntime(),
    ).run(
        series_id="series-1",
        books=list(context["books"]),
        chapters=list(context["chapters"]),
        scenes=list(context["scenes"]),
        identity_bundle=context["identity_bundle"],
    )

    assert len(payload["events"]) == 1
    assert client.library.list_records(record_type="event", series_id="series-1", limit=20)
    assert client.library.list_records(record_type="canon_extraction_job", series_id="series-1", limit=20)


def test_canon_resume_configuration_is_read_at_execution_time(monkeypatch):
    monkeypatch.delenv("SAGA_CANON_RESUME_STAGES", raising=False)
    assert canon_pipeline._resume_stage_enabled("event_extraction") is False

    monkeypatch.setenv("SAGA_CANON_RESUME_STAGES", "event_extraction,relationship_extraction")
    assert canon_pipeline._resume_stage_enabled("event_extraction") is True
    assert canon_pipeline._resume_stage_enabled("relationship_extraction") is True


def test_canon_extraction_requires_persisted_identity_bundle(tmp_path: Path):
    client = _persistence(tmp_path)
    runtime = CanonExtractionRuntime(
        persistence=client,
        reasoning_runtime=StubReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    try:
        runtime.invoke(series_id="missing-series", thread_id="canon-extraction-missing")
    except ValueError as exc:
        assert "requires a persisted identity bundle" in str(exc)
    else:
        raise AssertionError("Expected canon extraction to reject missing upstream analysis foundation state.")


def test_chunk_scene_text_covers_tail_content_for_long_scenes():
    text = " ".join([f"beat-{index:04d}" for index in range(1, 900)])
    chunks = _chunk_scene_text(text, max_chars=1800, overlap_chars=250)

    assert len(chunks) >= 2
    assert "beat-0001" in chunks[0]
    assert "beat-0899" in chunks[-1]


def test_event_extraction_terminal_retry_falls_back_to_grounded_scene_beat():
    agent = EventAgent(store=None, reasoning_runtime=AlwaysFailReasoningRuntime())  # type: ignore[arg-type]

    payloads = agent._extract_chapter_events_with_fallback(
        book=BookArtifact(
            book_id="book-1",
            series_id="series-1",
            title="Fixture",
            book_index=1,
            source_uri="fixture.txt",
            metadata={},
        ),
        chapter=ChapterArtifact(
            chapter_id="chapter-1",
            series_id="series-1",
            book_id="book-1",
            chapter_index=1,
            title="One",
            content="",
            source_id="source-1",
            word_count=0,
            metadata={},
        ),
        scene_slices=[
            {
                "scene_id": "scene-1",
                "chapter_index": 1,
                "scene_index": 1,
                "chunk_index": 1,
                "summary": "Taryn waits beside the window.",
                "excerpt": "Taryn waits.",
                "narrative_grounding": {"narrator_name": "Taryn"},
            }
        ],
        identity_bundle=CanonicalIdentityBundle(series_id="series-1", provider_name="test", book_ids=["book-1"], characters=[], alias_map={}),
    )

    assert len(payloads) == 1
    assert payloads[0].events[0].scene_id == "scene-1"
    assert payloads[0].events[0].event_type == "scene_beat"
    assert payloads[0].events[0].participant_names == ["Taryn"]


def test_event_participants_are_augmented_from_grounded_event_text():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="test",
        book_ids=["book-1"],
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn", aliases=[]),
            CanonicalCharacter(character_id="char-locke", display_name="Locke", aliases=[]),
        ],
        alias_map={},
    )

    names = _augment_participant_names_from_event_text(
        ["Taryn"],
        identity_bundle=bundle,
        event_title="Locke sets marriage conditions",
        event_summary="Locke agrees to marry Taryn but imposes three conditions.",
    )

    assert names == ["Taryn", "Locke"]


def test_dialogue_actor_supports_event_participant_claim():
    scene = SceneArtifact(
        scene_id="scene-1",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        summary="Locke sets conditions for marriage.",
        text="Then Locke said, \"We will marry on three conditions.\"",
        word_count=8,
        metadata={},
    )

    assert _has_participant_text_support(
        "Locke",
        scene=scene,
        event_title="Locke sets marriage conditions",
        event_summary="Locke agrees to marry Taryn but imposes three conditions.",
        narrative_grounding={},
    )


def test_batched_scene_slices_bound_prompt_coverage():
    scene = SceneArtifact(
        scene_id="scene-001",
        series_id="series-1",
        book_id="book-1",
        chapter_id="chapter-1",
        chapter_index=1,
        scene_index=1,
        title="Long Scene",
        summary="",
        text=" ".join([f"beat-{index:04d}" for index in range(1, 900)]),
        word_count=899,
        metadata={},
    )
    batches = _batched_scene_slices([scene], max_slices_per_batch=4)

    assert len(batches) >= 2
    assert all(len(batch) <= 4 for batch in batches)
    assert "beat-0001" in batches[0][0]["excerpt"]
    assert "beat-0899" in batches[-1][-1]["excerpt"]


def test_identity_context_only_includes_characters_relevant_to_scene_batch():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="test",
        characters=[
            CanonicalCharacter(character_id="char-feyre", display_name="Feyre Archeron", aliases=["Feyre"]),
            CanonicalCharacter(character_id="char-rhys", display_name="Rhysand", aliases=["Rhys"]),
            CanonicalCharacter(character_id="char-cassian", display_name="Cassian", aliases=["he"]),
        ],
    )
    context = _identity_character_context(
        bundle,
        scene_slices=[
            {
                "summary": "Feyre meets the High Lord.",
                "excerpt": "She waits for him.",
                "narrative_grounding": {
                    "narrator_character_id": "char-cassian",
                    "narrator_name": "Cassian",
                },
            }
        ],
    )

    assert [row["character_id"] for row in context] == ["char-feyre", "char-cassian"]


def test_identity_context_matches_names_on_token_boundaries():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="test",
        characters=[
            CanonicalCharacter(character_id="char-rhys", display_name="Rhys", aliases=[]),
            CanonicalCharacter(character_id="char-rhy", display_name="Rhy", aliases=[]),
        ],
    )

    context = _identity_character_context(
        bundle,
        scene_slices=[{"summary": "", "excerpt": "Rhys entered quietly."}],
    )

    assert [row["character_id"] for row in context] == ["char-rhys"]


def test_entities_for_scene_slice_batch_filters_to_relevant_scene_ids():
    entities = [
        EntityArtifact(
            entity_id="entity-a",
            series_id="series-1",
            canonical_name="A",
            mention_scene_ids=["scene-001"],
            book_ids=["book-1"],
        ),
        EntityArtifact(
            entity_id="entity-b",
            series_id="series-1",
            canonical_name="B",
            mention_scene_ids=["scene-002"],
            book_ids=["book-1"],
        ),
    ]

    matched = _entities_for_scene_slice_batch(entities, [{"scene_id": "scene-002"}])

    assert [entity.entity_id for entity in matched] == ["entity-b"]


def test_normalize_entity_type_rejects_character_like_labels():
    assert _normalize_entity_type("character", name="Faerie court", description="A court faction") in {
        "organization",
        "concept",
        "artifact",
    }
    assert _normalize_entity_type("event", name="coronation of Prince Dain", description="A future coronation") == "concept"


def test_normalize_entity_type_overrides_event_mislabeled_as_creature():
    assert _normalize_entity_type(
        "creature",
        name="coronation of Prince Dain",
        description="A grand ceremonial space with a throne and hundreds of attendees.",
    ) == "concept"
    assert _normalize_entity_type(
        "creature",
        name="moon wolf",
        description="A silver wolf that guards the court during the coronation.",
    ) == "creature"


def test_normalize_entity_type_overrides_legal_proceeding_mislabeled_as_object():
    assert _normalize_entity_type(
        "object",
        name="High King's inquest",
        description="A formal proceeding before the court.",
    ) == "concept"


def test_normalize_entity_type_corrects_natural_spring_mislabeled_as_object():
    assert _normalize_entity_type(
        "object",
        name="glowing spring",
        description="A luminous natural spring marked on a map as the travelers' destination.",
    ) == "location"
    assert _normalize_entity_type(
        "object",
        name="clockwork spring",
        description="A portable coiled metal replacement part.",
    ) == "object"


def test_normalize_entity_name_removes_leading_articles_for_deduplication():
    assert normalize_entity_name("the Folk") == "Folk"
    assert normalize_entity_name("An apple blossom") == "apple blossom"


def test_normalize_relationship_type_maps_variant_labels_to_stable_ontology():
    assert _normalize_relationship_type("friendship/alliance", description="They are close friends and allies") == "friendship"
    assert _normalize_relationship_type("romantic_interest_/_admiration", description="Lingering attraction") == "romantic"
    assert _normalize_relationship_type("conflict/adversarial", description="Active conflict between them") == "antagonistic"


def test_narrative_grounding_resolves_narrator_and_rejects_ambiguous_addressee_placeholders():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-jude", display_name="Jude"),
            CanonicalCharacter(character_id="char-vivi", display_name="Vivi"),
        ],
    )
    grounding = {
        "narrator_character_id": "char-taryn",
        "narrator_name": "Taryn",
        "addressee_character_ids": ["char-jude", "char-vivi"],
    }

    assert _resolve_single_name_ref(
        "narrator",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding=grounding,
    ) == "char-taryn"
    assert _resolve_single_name_ref(
        "you",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding=grounding,
    ) == ""
    assert _resolve_name_refs(
        ["narrator", "Jude"],
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding=grounding,
    ) == ["char-taryn", "char-jude"]


def test_participant_resolution_rejects_possessive_object_ownership_as_participation():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-madoc", display_name="Madoc"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Taryn sealed the note with Madoc's seal and sent it to Locke.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Madoc", "Locke"],
        scene=scene,
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_participant_resolution_uses_event_statement_when_scene_id_is_imperfect():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="A framed fairy tale excerpt opens the chapter.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Locke"],
        scene=scene,
        event_title="Locke sets marriage conditions",
        event_summary="Locke tells Taryn the conditions for marriage.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_participant_resolution_augments_event_recipient_names():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-vivi", display_name="Vivi"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Taryn and Vivi crafted the message.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Vivi"],
        scene=scene,
        event_title="Taryn crafts secret note for Locke",
        event_summary="Taryn, aided by Vivi, writes a secret message for Locke.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-vivi", "char-locke"]


def test_participant_resolution_augments_grounded_narrator_from_possessive_mention():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Locke climbed the balcony and spoke softly.",
    )

    refs = _resolve_participant_refs(
        ["Locke"],
        scene=scene,
        event_title="Locke arrives at Taryn's window",
        event_summary="Locke climbs her balcony and speaks to her.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={"narrator_character_id": "char-taryn", "narrator_name": "Taryn"},
    )

    assert refs == ["char-locke", "char-taryn"]


def test_participant_resolution_rejects_curly_possessive_names_in_event_statement():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-madoc", display_name="Madoc"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Madoc wanted the children trained for war. The note bears Madoc\u2019s seal.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Madoc", "Locke"],
        scene=scene,
        event_title="Taryn sends a note to Locke",
        event_summary="Taryn sends a secret note to Locke with Madoc\u2019s seal.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_participant_resolution_accepts_recipient_possessive_destination():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-vivi", display_name="Vivi"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Vivi suggests that Taryn send the sealed note to Locke's estate using a seabird.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Vivi"],
        scene=scene,
        event_title="Message sent via seabird",
        event_summary="Vivi suggests and Taryn sends the sealed note to Locke's estate using a seabird.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-vivi", "char-locke"]


def test_participant_resolution_keeps_actor_named_in_event_title_when_scene_uses_pronoun():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="He nodded and agreed to marry Taryn on three conditions.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Locke"],
        scene=scene,
        event_title="Locke agrees to marry Taryn with conditions",
        event_summary="Locke nods and agrees to marry Taryn, stipulating secrecy.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_participant_resolution_rejects_tertiary_disclosure_targets():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
            CanonicalCharacter(character_id="char-madoc", display_name="Madoc"),
            CanonicalCharacter(character_id="char-jude", display_name="Jude"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Taryn told Locke to inform Madoc that they were to be wed and to tell Jude about his intentions.",
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Locke", "Madoc", "Jude"],
        scene=scene,
        event_title="Taryn asks Locke to explain the marriage",
        event_summary="Taryn asks Locke to inform Madoc that they are to be wed and to tell Jude about his true intentions.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_participant_resolution_rejects_named_actor_without_scene_action_support():
    bundle = CanonicalIdentityBundle(
        series_id="series-1",
        provider_name="modal_xcore_litbank",
        characters=[
            CanonicalCharacter(character_id="char-taryn", display_name="Taryn"),
            CanonicalCharacter(character_id="char-vivi", display_name="Vivi"),
            CanonicalCharacter(character_id="char-heather", display_name="Heather"),
            CanonicalCharacter(character_id="char-locke", display_name="Locke"),
        ],
    )
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text=(
            "I tensed, remembering that she'd helped me send the note to Locke. "
            "Heather turned out to be a pink-haired artist who exchanged a glance with Vivi."
        ),
    )

    refs = _resolve_participant_refs(
        ["Taryn", "Heather", "Locke"],
        scene=scene,
        event_title="Taryn recalls sending a note to Locke",
        event_summary="Taryn remembers that Heather helped her send a secret note to Locke.",
        identity_bundle=bundle,
        entity_name_to_id={},
        narrative_grounding={"narrator_character_id": "char-taryn", "narrator_name": "Taryn"},
    )

    assert refs == ["char-taryn", "char-locke"]


def test_relationship_filter_rejects_character_to_character_artifact_usage():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-locke-artifact-usage-char-madoc",
        series_id="series-1",
        source_ref="char-locke",
        target_ref="char-madoc",
        relationship_type="artifact_usage",
        description="Locke uses Madoc's seal on a note sent by Taryn.",
    )
    good = RelationshipArtifact(
        relationship_id="relationship-char-taryn-artifact-usage-entity-wax-seal",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="entity-wax-seal",
        relationship_type="artifact_usage",
        description="Taryn affixes Madoc's seal to a note.",
    )
    bad_provenance = RelationshipArtifact(
        relationship_id="relationship-char-taryn-protective-char-madoc",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-madoc",
        relationship_type="protective",
        description="Madoc provides a seal for Taryn's note, indicating a protective role.",
    )

    assert not _should_keep_relationship_artifact(bad)
    assert not _should_keep_relationship_artifact(bad_provenance)
    assert _should_keep_relationship_artifact(good)


def test_relationship_filter_rejects_character_to_character_location_association():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-heather-location-association-char-taryn",
        series_id="series-1",
        source_ref="char-heather",
        target_ref="char-taryn",
        relationship_type="location_association",
        description="Heather's home is proposed as a place for Taryn to live.",
    )

    assert not _should_keep_relationship_artifact(bad)


def test_relationship_filter_rejects_romance_with_different_named_partner():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-taryn-romantic-char-heather",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-heather",
        relationship_type="romantic",
        description="Heather is mentioned as an artist whose relationship with Vivi prompts Taryn to consider mortal-faerie love.",
    )
    good = RelationshipArtifact(
        relationship_id="relationship-char-vivi-romantic-char-heather",
        series_id="series-1",
        source_ref="char-vivi",
        target_ref="char-heather",
        relationship_type="romantic",
        description="Heather has a relationship with Vivi.",
    )

    assert not _should_keep_relationship_artifact(bad)
    assert _should_keep_relationship_artifact(good)


def test_relationship_filter_rejects_abstract_love_as_pair_romance():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-taryn-romantic-char-vivi",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-vivi",
        relationship_type="romantic",
        description="Taryn wonders about Vivi's ability to love a mortal and feels uneasy about their relationship.",
    )

    assert not _should_keep_relationship_artifact(bad)


def test_relationship_filter_rejects_comparative_romance_context():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-taryn-romantic-char-mom",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-mom",
        relationship_type="romantic",
        description="Taryn compares Mom's past romantic choices to those of Heather.",
    )

    assert not _should_keep_relationship_artifact(bad)


def test_relationship_filter_rejects_marriage_edges_without_pair_support():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-taryn-marriage-char-jude",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-jude",
        relationship_type="marriage",
        description="Taryn asks Jude to convey Locke's real intentions and the marriage plans.",
    )
    good = RelationshipArtifact(
        relationship_id="relationship-char-taryn-marriage-char-locke",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-locke",
        relationship_type="marriage",
        description="Taryn proposes marriage to Locke and negotiates faerie marriage conditions.",
    )

    assert not _should_keep_relationship_artifact(bad)
    assert _should_keep_relationship_artifact(good)


def test_relationship_filter_rejects_family_edges_without_pair_support():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-taryn-family-char-heather",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-heather",
        relationship_type="family",
        description="Taryn mentions Heather as a pink-haired artist, comparing her to her mother.",
    )
    bad_love_comparison = RelationshipArtifact(
        relationship_id="relationship-char-taryn-family-char-heather",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-heather",
        relationship_type="family",
        description="Taryn compares her mother's early love life to Heather's, noting similarities.",
    )
    good = RelationshipArtifact(
        relationship_id="relationship-char-taryn-family-char-jude",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-jude",
        relationship_type="family",
        description="Taryn and Jude are sisters who protect each other.",
    )

    assert not _should_keep_relationship_artifact(bad)
    assert not _should_keep_relationship_artifact(bad_love_comparison)
    assert _should_keep_relationship_artifact(good)


def test_relationship_filter_rejects_sibling_edges_without_direct_pair_support():
    bad = RelationshipArtifact(
        relationship_id="relationship-char-nicasia-sibling-char-taryn",
        series_id="series-1",
        source_ref="char-nicasia",
        target_ref="char-taryn",
        relationship_type="sibling",
        description="Nicasia attacks Taryn, demands she renounce her sister, and shows intense anger.",
        scene_ids=["scene-1"],
        book_ids=["book-1"],
    )
    good = RelationshipArtifact(
        relationship_id="relationship-char-taryn-sibling-char-jude",
        series_id="series-1",
        source_ref="char-taryn",
        target_ref="char-jude",
        relationship_type="sibling",
        description="Taryn and Jude are sisters.",
        scene_ids=["scene-1"],
        book_ids=["book-1"],
    )

    assert not _should_keep_relationship_artifact(bad)
    assert _should_keep_relationship_artifact(good)


def test_split_scene_slices_for_retry_can_bisect_single_large_slice():
    left, right = _split_scene_slices_for_retry(
        [{"scene_id": "scene-001", "chunk_index": 1, "excerpt": "word " * 300, "summary": ""}]
    )

    assert len(left) == 1
    assert len(right) == 1
    assert left[0]["scene_id"] == "scene-001"
    assert right[0]["scene_id"] == "scene-001"
    assert len(left[0]["excerpt"]) > 100
    assert len(right[0]["excerpt"]) > 100


def test_split_retry_predicate_handles_empty_provider_responses():
    assert _should_retry_split_extraction_error(RuntimeError("Entity extraction failed: empty_response"))
    assert _should_retry_split_extraction_error(RuntimeError("Entity extraction failed: parse_failed"))
    assert not _should_retry_split_extraction_error(RuntimeError("Event extraction failed: max_retries_exceeded"))
    assert not _should_retry_split_extraction_error(RuntimeError("Entity extraction failed: auth_failed"))
