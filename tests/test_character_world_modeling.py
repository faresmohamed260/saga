from __future__ import annotations

from pathlib import Path

from packages.analysis_foundation import AnalysisFoundationRuntime
from packages.canon_extraction import CanonExtractionRuntime
from packages.canon_extraction.contracts import EventArtifact
from packages.character_world_modeling import CharacterWorldModelingRuntime
from packages.character_world_modeling import pipeline as cwm_pipeline
from packages.character_world_modeling.pipeline import (
    CharacterProfileSynthesis,
    StableStateAgent,
    StableCharacterStateSynthesis,
    WorldStateSynthesis,
    _build_character_evidence,
    _build_character_profile_prompt,
    _character_event_role,
    _profile_artifact_from_evidence,
    _world_state_artifact_from_evidence,
    _sanitize_notable_relationships,
    _matches_direct_recipient,
    _should_retry_split_synthesis_error,
    _split_evidence_batch_for_retry,
)
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.analysis_foundation.contracts import CanonicalCharacter, SceneArtifact


class StubIdentityRuntime:
    def provider_name(self) -> str:
        return "modal_xcore_litbank"

    def analyze_chapters(self, *, chapters: list[dict], use_chunking: bool | None = None):
        del chapters, use_chunking
        return _SimpleResult(
            {
                "provider_name": "modal_xcore_litbank",
                "app_name": "saga-coref-runtime",
                "model_name": "xcore-litbank",
                "runtime_seconds": 1.0,
                "chunk_count": 1,
                "input_stats": {"chapter_count": 1},
                "clusters": [
                    {
                        "display_name": "Fares",
                        "aliases": ["he"],
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


class StubCanonReasoningRuntime:
    def provider_name(self) -> str:
        return "ollama"

    def resolved_model_name(self) -> str:
        return "gpt-oss:120b-cloud"

    def __init__(self) -> None:
        self._last = {}

    def generate_json(self, prompt: str, strict: bool = False, validator=None, max_tokens: int = 4096, response_format=None, tools=None, tool_choice=None):
        del strict, validator, max_tokens, response_format, tools, tool_choice
        scene_id = _first_scene_id(prompt)
        lowered = prompt.lower()
        if "key 'events'" in lowered:
            payload = {
                "events": [
                    {
                        "scene_id": scene_id,
                        "title": "Fares meets Kareem",
                        "summary": "Fares greets Kareem and they discuss a silver notebook.",
                        "event_type": "meeting",
                        "participant_names": ["Fares", "Kareem"],
                        "entity_names": ["silver notebook"],
                    }
                ]
            }
        elif "key 'entities'" in lowered:
            payload = {
                "entities": [
                    {
                        "canonical_name": "silver notebook",
                        "entity_type": "artifact",
                        "description": "A silver notebook used during the discussion.",
                        "aliases": ["notebook"],
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
                        "relationship_type": "friendship",
                        "description": "They collaborate calmly on the same task.",
                        "scene_ids": [scene_id],
                    }
                ]
            }
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        return payload

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class StubCharacterWorldReasoningRuntime:
    def provider_name(self) -> str:
        return "ollama"

    def resolved_model_name(self) -> str:
        return "gpt-oss:120b-cloud"

    def __init__(self) -> None:
        self._last = {}

    def generate_json(self, prompt: str, strict: bool = False, validator=None, max_tokens: int = 4096, response_format=None, tools=None, tool_choice=None):
        del strict, validator, max_tokens, response_format, tools, tool_choice
        lowered = prompt.lower()
        if '"profiles"' in lowered and '"character_id"' in lowered:
            payload = {
                "profiles": [
                    {
                        "character_id": "char-fares",
                        "overview": "Fares is a focused collaborator reviewing work with Kareem.",
                        "role_or_archetype": "collaborator",
                        "traits": ["focused", "calm"],
                        "motivations": ["finish the review"],
                        "loyalties": ["Kareem"],
                        "tensions": [],
                        "notable_relationships": ["Works closely with Kareem"],
                        "visual_cues": [],
                        "first_seen_summary": "Fares greets Kareem in the hallway.",
                        "latest_state_summary": "Fares is discussing the project deadline.",
                    },
                    {
                        "character_id": "char-kareem",
                        "overview": "Kareem is a steady collaborator who responds thoughtfully.",
                        "role_or_archetype": "collaborator",
                        "traits": ["steady"],
                        "motivations": ["review the notebook"],
                        "loyalties": ["Fares"],
                        "tensions": [],
                        "notable_relationships": ["Works closely with Fares"],
                        "visual_cues": [],
                        "first_seen_summary": "Kareem meets Fares in the hallway.",
                        "latest_state_summary": "Kareem opens the notebook.",
                    },
                ]
            }
        elif '"stable_states"' in lowered:
            payload = {
                "stable_states": [
                    {
                        "character_id": "char-fares",
                        "stable_attributes": {"role": "collaborator"},
                        "summary": "Fares is established as a collaborator.",
                    },
                    {
                        "character_id": "char-kareem",
                        "stable_attributes": {"role": "collaborator"},
                        "summary": "Kareem is established as a collaborator.",
                    },
                ]
            }
        else:
            payload = {
                "world_states": [
                    {
                        "entity_id": "entity-silver-notebook",
                        "stable_facts": {"material": "silver"},
                        "active_conditions": ["being used in discussion"],
                        "current_state_summary": "The silver notebook is opened during the review.",
                        "story_relevance": "It is the main object in the meeting scene.",
                    }
                ]
            }
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "ok"}
        return payload

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class FailingCharacterWorldReasoningRuntime(StubCharacterWorldReasoningRuntime):
    def generate_json(self, *args, **kwargs):
        self._last = {"provider": "ollama", "resolved_model": self.resolved_model_name(), "status": "error"}
        return {"error": "max_retries_exceeded"}


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
        name="character-world-modeling-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'character_world_modeling.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="character-world-modeling-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def test_character_world_modeling_persists_profiles_states_and_world_state(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = tmp_path / "fixture.txt"
    source_path.write_text(
        "Chapter 1\n\n"
        "Fares greeted Kareem in the hallway and asked about the silver notebook.\n\n"
        "Kareem opened the silver notebook and answered calmly.\n",
        encoding="utf-8",
    )
    analysis = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    analysis.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-test")
    canon = CanonExtractionRuntime(
        persistence=client,
        reasoning_runtime=StubCanonReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    canon.invoke(series_id="series-1", thread_id="canon-test")
    runtime = CharacterWorldModelingRuntime(
        persistence=client,
        reasoning_runtime=StubCharacterWorldReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-1", thread_id="character-world-test")

    assert len(result.character_profiles) == 2
    assert len(result.stable_character_states) == 2
    assert len(result.world_states) == 1
    assert result.character_profiles[0].metadata["reasoning_model"] == "gpt-oss:120b-cloud"
    assert result.run_metadata["stage_order"] == [
        "character_profile_synthesis",
        "stable_state_synthesis",
        "world_state_synthesis",
    ]

    persisted_profiles = client.library.list_records(record_type="character_profile", series_id="series-1", limit=20)
    persisted_states = client.library.list_records(record_type="stable_character_state", series_id="series-1", limit=20)
    persisted_world = client.library.list_records(record_type="world_state", series_id="series-1", limit=20)
    assert len(persisted_profiles) == 2
    assert len(persisted_states) == 2
    assert len(persisted_world) == 1


def test_character_world_modeling_resumes_persisted_stages_without_reasoning(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = tmp_path / "fixture.txt"
    source_path.write_text(
        "Chapter 1\n\n"
        "Fares greeted Kareem in the hallway and asked about the silver notebook.\n\n"
        "Kareem opened the silver notebook and answered calmly.\n",
        encoding="utf-8",
    )
    analysis = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    analysis.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-test")
    canon = CanonExtractionRuntime(
        persistence=client,
        reasoning_runtime=StubCanonReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    canon.invoke(series_id="series-1", thread_id="canon-test")
    CharacterWorldModelingRuntime(
        persistence=client,
        reasoning_runtime=StubCharacterWorldReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", thread_id="character-world-initial")

    original_resume_stages = set(cwm_pipeline.CWM_RESUME_STAGES)
    cwm_pipeline.CWM_RESUME_STAGES.update(
        {"character_profile_synthesis", "stable_state_synthesis", "world_state_synthesis"}
    )
    try:
        result = CharacterWorldModelingRuntime(
            persistence=client,
            reasoning_runtime=FailingCharacterWorldReasoningRuntime(),
            allow_in_memory_checkpointer=True,
        ).invoke(series_id="series-1", thread_id="character-world-resume")
    finally:
        cwm_pipeline.CWM_RESUME_STAGES.clear()
        cwm_pipeline.CWM_RESUME_STAGES.update(original_resume_stages)

    assert len(result.character_profiles) == 2
    assert len(result.stable_character_states) == 2
    assert len(result.world_states) == 1
    assert result.run_metadata["stage_metrics"]["world_state_synthesis"]["resumed"] is True
    assert result.run_metadata["stage_metrics"]["world_state_synthesis"]["reasoning_calls"] == 0


def test_stable_state_terminal_retry_returns_empty_payload():
    agent = StableStateAgent(store=None, reasoning_runtime=FailingCharacterWorldReasoningRuntime())  # type: ignore[arg-type]

    payloads = agent._synthesize_stable_states_with_fallback(
        batch=[
            {
                "character_id": "char-fares",
                "canonical_name": "Fares",
                "event_evidence": [],
                "relationship_evidence": [],
            }
        ]
    )

    assert len(payloads) == 1
    assert payloads[0].stable_states == []


def test_character_world_modeling_requires_upstream_canon_outputs(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = tmp_path / "fixture.txt"
    source_path.write_text("Fares greeted Kareem.", encoding="utf-8")
    analysis = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    analysis.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-test")
    runtime = CharacterWorldModelingRuntime(
        persistence=client,
        reasoning_runtime=StubCharacterWorldReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    )
    try:
        runtime.invoke(series_id="series-1", thread_id="character-world-test")
    except ValueError as exc:
        assert "requires persisted canon extraction outputs" in str(exc)
    else:
        raise AssertionError("Expected runtime to reject missing canon extraction outputs.")


def test_character_world_modeling_prompt_preserves_event_roles_and_participant_refs():
    character = CanonicalCharacter(character_id="char-locke", display_name="Locke")
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Taryn writes a note to Locke and seals it with Madoc's seal.",
    )
    event = EventArtifact(
        event_id="event-001",
        series_id="series-1",
        book_id="book-1",
        scene_id="scene-001",
        chapter_index=1,
        scene_index=1,
        event_index=1,
        title="Taryn sends a note to Locke",
        summary="Taryn sends a secret note to Locke with Madoc's seal.",
        event_type="communication",
        participant_refs=["char-taryn", "char-locke"],
    )

    evidence = _build_character_evidence(
        character=character,
        scene_map={"scene-001": scene},
        events=[event],
        relationships=[],
        timeline=[],
    )
    prompt = _build_character_profile_prompt(batch=[evidence])

    assert evidence["event_evidence"] == []
    assert evidence["contextual_event_evidence"][0]["participant_refs"] == ["char-taryn", "char-locke"]
    assert evidence["contextual_event_evidence"][0]["character_event_role"] == "recipient"
    assert "recipient, observer, addressee, and mentioned-only roles" in prompt
    assert "contextual_event_evidence is background only" in prompt
    assert "Possessive object phrases" in prompt


def test_character_world_modeling_keeps_tertiary_mentions_out_of_primary_evidence():
    madoc = CanonicalCharacter(character_id="char-madoc", display_name="Madoc")
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Taryn told Locke to inform Madoc that they were to be wed.",
    )
    event = EventArtifact(
        event_id="event-001",
        series_id="series-1",
        book_id="book-1",
        scene_id="scene-001",
        chapter_index=1,
        scene_index=1,
        event_index=1,
        title="Taryn asks Locke to inform Madoc",
        summary="Taryn asks Locke to inform Madoc that she and Locke are to be wed.",
        event_type="conversation",
        participant_refs=["char-taryn", "char-locke", "char-madoc"],
    )

    evidence = _build_character_evidence(
        character=madoc,
        scene_map={"scene-001": scene},
        events=[event],
        relationships=[],
        timeline=[],
    )

    assert _character_event_role(event, character=madoc, scene_map={"scene-001": scene}) == "recipient"
    assert evidence["event_evidence"] == []
    assert evidence["contextual_event_evidence"][0]["character_event_role"] == "recipient"
    assert evidence["latest_state_summary"] == ""


def test_character_world_modeling_uses_conservative_profile_for_low_support_character():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "character_id": "char-heather",
        "canonical_name": "Heather",
        "aliases": [],
        "book_ids": ["book-1"],
        "chapter_indices": [1],
        "scene_ids": ["scene-001"],
        "event_evidence": [],
        "relationship_evidence": [{"relationship_type": "reference", "description": "Heather is mentioned."}],
        "scene_evidence": [{"excerpt": "Heather turned out to be a pink-haired artist. Taryn wondered about love."}],
    }
    synthesis = CharacterProfileSynthesis(
        character_id="char-heather",
        overview="Heather helped Taryn send a secret note to Locke.",
        role_or_archetype="supportive friend",
        motivations=["help Taryn"],
        latest_state_summary="Heather helped with the note.",
    )

    profile = _profile_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert profile.overview == "Heather turned out to be a pink-haired artist."
    assert profile.role_or_archetype == ""
    assert profile.motivations == []
    assert profile.first_seen_summary == "Heather turned out to be a pink-haired artist."
    assert profile.latest_state_summary == ""


def test_character_world_modeling_rejects_ungrounded_first_seen_for_supported_character():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "character_id": "char-taryn",
        "canonical_name": "Taryn",
        "aliases": [],
        "book_ids": ["book-1"],
        "chapter_indices": [1],
        "scene_ids": ["scene-001"],
        "event_evidence": [{"event_id": "event-1", "title": "Taryn sends a note", "summary": "Taryn sends a note to Locke."}],
        "relationship_evidence": [],
        "scene_evidence": [{"excerpt": "Taryn sends a note to Locke. Fairy tales have rules."}],
        "latest_state_summary": "Taryn sends a note to Locke.",
    }
    synthesis = CharacterProfileSynthesis(
        character_id="char-taryn",
        overview="Taryn is active.",
        first_seen_summary="Fairy tales have a moral.",
        latest_state_summary="Taryn sends a note to Locke.",
    )

    profile = _profile_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert profile.first_seen_summary == "Taryn sends a note to Locke."
    assert profile.latest_state_summary == "Taryn sends a note to Locke."


def test_character_world_modeling_rejects_ungrounded_latest_summary_fallback():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "character_id": "char-valerian",
        "canonical_name": "Valerian",
        "aliases": [],
        "book_ids": ["book-1"],
        "chapter_indices": [1],
        "scene_ids": ["scene-001"],
        "event_evidence": [{"event_id": "event-1", "title": "Locke pushes Taryn", "summary": "Locke pushes Taryn into a river."}],
        "relationship_evidence": [],
        "scene_evidence": [{"excerpt": "Valerian stood nearby. Locke pushes Taryn into a river."}],
        "latest_state_summary": "Locke pushes Taryn into a river.",
    }
    synthesis = CharacterProfileSynthesis(
        character_id="char-valerian",
        overview="Locke pushes Taryn into a river.",
        latest_state_summary="Locke pushes Taryn into a river.",
    )

    profile = _profile_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert profile.overview == "Valerian stood nearby."
    assert profile.latest_state_summary == ""


def test_character_world_modeling_title_stripped_name_counts_as_grounded():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "character_id": "char-princess-rhyia",
        "canonical_name": "Princess Rhyia",
        "aliases": [],
        "book_ids": ["book-1"],
        "chapter_indices": [1],
        "scene_ids": ["scene-001"],
        "event_evidence": [{"event_id": "event-1", "title": "Rhyia rides", "summary": "Rhyia invites Taryn to ride."}],
        "relationship_evidence": [],
        "scene_evidence": [{"excerpt": "Rhyia invites Taryn to ride."}],
        "latest_state_summary": "Rhyia invites Taryn to ride.",
    }
    synthesis = CharacterProfileSynthesis(
        character_id="char-princess-rhyia",
        overview="Rhyia invites Taryn to ride.",
        latest_state_summary="Rhyia invites Taryn to ride.",
    )

    profile = _profile_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert profile.overview == "Rhyia invites Taryn to ride."
    assert profile.latest_state_summary == "Rhyia invites Taryn to ride."


def test_character_world_modeling_sanitizes_unsupported_possessive_object_actions():
    evidence = {
        "event_evidence": [
            {
                "title": "Taryn sends a note to Locke",
                "summary": "Taryn sends a secret note to Locke with Madoc's seal.",
            }
        ],
        "timeline_evidence": [],
    }

    assert _sanitize_notable_relationships(
        ["Locke uses Madoc's seal on a note sent by Taryn."],
        canonical_name="Locke",
        evidence=evidence,
    ) == []
    assert _sanitize_notable_relationships(
        ["Uses Madoc's seal on notes she sends to Locke."],
        canonical_name="Taryn",
        evidence=evidence,
    ) == []
    assert _sanitize_notable_relationships(
        ["self with char-prince-cardan", "ally with char-prince-cardan: unsupported"],
        canonical_name="Prince Cardan",
        evidence={"character_id": "char-prince-cardan"},
    ) == []
    assert _sanitize_notable_relationships(
        ["associated with a wax seal (Madoc's seal)", "serves Taryn purple liquid from a decanter"],
        canonical_name="Locke",
        evidence={"character_id": "char-locke"},
    ) == []
    assert _sanitize_notable_relationships(
        ["artifact_usage with entity-rope", "artifact_usage with entity-apple-blossoms"],
        canonical_name="Taryn",
        evidence={"character_id": "char-taryn"},
    ) == []
    assert _sanitize_notable_relationships(
        ["Rides and converses with Vivi during the hunt.", "companion with char-vivi"],
        canonical_name="Princess Rhyia",
        evidence={"character_id": "char-princess-rhyia"},
    ) == ["companion with char-vivi"]


def test_character_world_modeling_does_not_treat_involvement_with_as_direct_role():
    assert not _matches_direct_recipient(
        "Locke confesses his involvement with Nicasia and asks Taryn to keep it secret.",
        ["Nicasia"],
    )
    assert _matches_direct_recipient("Taryn sends a note to Locke.", ["Locke"])


def test_character_world_modeling_does_not_promote_contextual_object_to_actor():
    nicasia = CanonicalCharacter(character_id="char-nicasia", display_name="Nicasia")
    scene = SceneArtifact(
        scene_id="scene-001",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text="Locke confesses his involvement with Nicasia and asks Taryn to keep it secret.",
    )
    event = EventArtifact(
        event_id="event-001",
        series_id="series-1",
        book_id="book-1",
        scene_id="scene-001",
        chapter_index=1,
        scene_index=1,
        event_index=1,
        title="Locke asks Taryn to keep his secret",
        summary="Locke confesses his involvement with Nicasia and asks Taryn to keep it secret.",
        event_type="promise",
        participant_refs=["char-locke", "char-taryn", "char-nicasia"],
    )

    assert _character_event_role(event, character=nicasia, scene_map={"scene-001": scene}) == "mentioned_only"


def test_character_world_modeling_coerces_provider_scalar_shape_variants():
    profile = CharacterProfileSynthesis.model_validate(
        {
            "character_id": "char-locke",
            "overview": {"summary": "Secret courtier."},
            "role_or_archetype": ["Companion", "Court conspirator"],
            "first_seen_summary": ["At court", "At window"],
            "latest_state_summary": None,
        }
    )
    state = StableCharacterStateSynthesis.model_validate(
        {"character_id": "char-locke", "summary": ["Secret", "courtier"], "stable_attributes": {"role": ["courtier"]}}
    )
    world = WorldStateSynthesis.model_validate(
        {
            "entity_id": "entity-seal",
            "current_state_summary": {"description": "A wax seal."},
            "story_relevance": ["Used in a note"],
            "active_conditions": "sealed",
        }
    )

    assert profile.overview == "Secret courtier."
    assert profile.role_or_archetype == "Companion; Court conspirator"
    assert profile.first_seen_summary == "At court; At window"
    assert state.summary == "Secret; courtier"
    assert state.stable_attributes == {"role": "courtier"}
    assert world.current_state_summary == "A wax seal."
    assert world.story_relevance == "Used in a note"
    assert world.active_conditions == ["sealed"]


def test_character_world_modeling_sanitizes_redundant_world_stable_facts():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "entity_id": "entity-forest",
        "canonical_name": "forest",
        "entity_type": "location",
        "description": "Woods surrounding the walk.",
    }
    synthesis = WorldStateSynthesis(
        entity_id="entity-forest",
        stable_facts={
            "type": "location",
            "canonical_name": "forest",
            "description": "Woods surrounding the walk.",
            "danger": "quiet but unsafe",
        },
        active_conditions=["location", "characters are walking there"],
        current_state_summary="The forest is quiet but unsafe.",
    )

    artifact = _world_state_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert artifact.stable_facts == {}
    assert artifact.active_conditions == []


def test_character_world_modeling_requires_world_fact_evidence_support():
    class Runtime:
        def provider_name(self) -> str:
            return "ollama"

        def resolved_model_name(self) -> str:
            return "gpt-oss:120b-cloud"

    evidence = {
        "entity_id": "entity-balcony",
        "canonical_name": "Balcony",
        "entity_type": "location",
        "description": "The balcony attached to Taryn's room, accessed by rope.",
        "scene_evidence": [{"excerpt": "Locke climbed the rope to the balcony outside Taryn's room."}],
    }
    synthesis = WorldStateSynthesis(
        entity_id="entity-balcony",
        stable_facts={
            "aliases": "upper terrace",
            "access_method": "rope lowered from window",
            "location": "outside Taryn's room",
        },
    )

    artifact = _world_state_artifact_from_evidence(
        series_id="series-1",
        evidence=evidence,
        synthesis=synthesis,
        reasoning_runtime=Runtime(),
    )

    assert artifact.stable_facts == {"location": "outside Taryn's room"}


def test_character_world_modeling_split_retry_helpers_handle_empty_responses():
    left, right = _split_evidence_batch_for_retry([{"id": "a"}, {"id": "b"}, {"id": "c"}])

    assert left == [{"id": "a"}]
    assert right == [{"id": "b"}, {"id": "c"}]
    assert _should_retry_split_synthesis_error(RuntimeError("Character profile synthesis failed: empty_response"))
    assert _should_retry_split_synthesis_error(RuntimeError("Character profile synthesis failed: max_retries_exceeded"))
    assert not _should_retry_split_synthesis_error(RuntimeError("Character profile synthesis failed: auth_failed"))
