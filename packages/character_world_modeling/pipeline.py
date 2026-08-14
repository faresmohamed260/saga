"""Deterministic LangGraph pipeline for character and world modeling."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

from packages.agent_runtime import SqlCheckpointSaver
from packages.analysis_foundation.contracts import BookArtifact, CanonicalCharacter, CanonicalIdentityBundle, SceneArtifact
from packages.canon_extraction.contracts import EntityArtifact, EventArtifact, RelationshipArtifact, TimelineArtifact
from packages.character_world_modeling.contracts import (
    CharacterProfileArtifact,
    CharacterWorldModelingResult,
    StableCharacterStateArtifact,
    WorldStateArtifact,
)
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient

CHARACTER_BATCH_SIZE = max(1, int(os.getenv("SAGA_CWM_CHARACTER_BATCH_SIZE") or "6"))
ENTITY_BATCH_SIZE = max(1, int(os.getenv("SAGA_CWM_ENTITY_BATCH_SIZE") or "8"))
CWM_MAX_CHARACTER_PROMPT_CHARS = max(
    8_000, int(os.getenv("SAGA_CWM_MAX_CHARACTER_PROMPT_CHARS") or "14000")
)
CWM_PARALLELISM = max(1, int(os.getenv("SAGA_CWM_PARALLELISM") or "4"))
CWM_RESUME_STAGES = {
    value.strip()
    for value in str(os.getenv("SAGA_CWM_RESUME_STAGES") or "").split(",")
    if value.strip()
}
MAX_EVENT_EVIDENCE = 8
MAX_RELATIONSHIP_EVIDENCE = 8
MAX_SCENE_EVIDENCE = 4
MAX_PROMPT_ALIASES = 12
MAX_PROMPT_REFERENCE_IDS = 8
MAX_PROMPT_TEXT_CHARS = 360
STABLE_ATTRIBUTE_KEYS = {
    "role",
    "title",
    "affiliation",
    "allegiance",
    "residence",
    "court",
    "family_role",
    "power_status",
    "species",
    "profession",
    "bond",
    "relationship_status",
}


class CharacterWorldModelingState(TypedDict, total=False):
    series_id: str
    books: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    identity_bundle: dict[str, Any]
    events: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    character_profiles: list[dict[str, Any]]
    stable_character_states: list[dict[str, Any]]
    world_states: list[dict[str, Any]]
    run_metadata: dict[str, Any]


class CharacterProfileSynthesis(BaseModel):
    character_id: str
    overview: str = ""
    role_or_archetype: str = ""
    traits: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)
    loyalties: list[str] = Field(default_factory=list)
    tensions: list[str] = Field(default_factory=list)
    notable_relationships: list[str] = Field(default_factory=list)
    visual_cues: list[str] = Field(default_factory=list)
    first_seen_summary: str = ""
    latest_state_summary: str = ""

    @field_validator("traits", "motivations", "loyalties", "tensions", "notable_relationships", "visual_cues", mode="before")
    @classmethod
    def _coerce_list_strings(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)

    @field_validator("overview", "role_or_archetype", "first_seen_summary", "latest_state_summary", mode="before")
    @classmethod
    def _coerce_scalar_string(cls, value: Any) -> str:
        return _coerce_string(value)


class CharacterProfilesPayload(BaseModel):
    profiles: list[CharacterProfileSynthesis] = Field(default_factory=list)


class StableCharacterStateSynthesis(BaseModel):
    character_id: str
    stable_attributes: dict[str, str] = Field(default_factory=dict)
    summary: str = ""

    @field_validator("stable_attributes", mode="before")
    @classmethod
    def _coerce_flat_dict(cls, value: Any) -> dict[str, str]:
        return _coerce_flat_string_dict(value)

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_scalar_string(cls, value: Any) -> str:
        return _coerce_string(value)


class StableCharacterStatesPayload(BaseModel):
    stable_states: list[StableCharacterStateSynthesis] = Field(default_factory=list)


class WorldStateSynthesis(BaseModel):
    entity_id: str
    stable_facts: dict[str, str] = Field(default_factory=dict)
    active_conditions: list[str] = Field(default_factory=list)
    current_state_summary: str = ""
    story_relevance: str = ""

    @field_validator("stable_facts", mode="before")
    @classmethod
    def _coerce_flat_dict(cls, value: Any) -> dict[str, str]:
        return _coerce_flat_string_dict(value)

    @field_validator("active_conditions", mode="before")
    @classmethod
    def _coerce_list_strings(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)

    @field_validator("current_state_summary", "story_relevance", mode="before")
    @classmethod
    def _coerce_scalar_string(cls, value: Any) -> str:
        return _coerce_string(value)


class WorldStatesPayload(BaseModel):
    world_states: list[WorldStateSynthesis] = Field(default_factory=list)


class CharacterProfileAgent:
    def __init__(self, *, store: CharacterWorldModelingStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(
        self,
        *,
        series_id: str,
        books: list[BookArtifact],
        scenes: list[SceneArtifact],
        identity_bundle: CanonicalIdentityBundle,
        events: list[EventArtifact],
        relationships: list[RelationshipArtifact],
        timeline: list[TimelineArtifact],
    ) -> dict[str, Any]:
        scene_map = {scene.scene_id: scene for scene in scenes}
        grounded_character_ids = _grounded_character_ids(
            events=events, relationships=relationships
        )
        evidence_rows = [
            _compact_character_prompt_evidence(_build_character_evidence(
                character=character,
                scene_map=scene_map,
                events=events,
                relationships=relationships,
                timeline=timeline,
            ))
            for character in identity_bundle.characters
            if character.character_id in grounded_character_ids
        ]
        existing_by_id = {
            item.character_id: item
            for item in self.store.list_character_profiles(series_id=series_id)
        } if _resume_stage_enabled("character_profile_synthesis") else {}
        if not _resume_stage_enabled("character_profile_synthesis"):
            self.store.delete_character_profiles(series_id=series_id)
        request_metadata_rows: list[dict[str, Any]] = []
        persisted_by_id: dict[str, CharacterProfileArtifact] = dict(existing_by_id)
        missing_rows = [row for row in evidence_rows if row["character_id"] not in existing_by_id]
        for batch in _prompt_batched(
            missing_rows,
            max_rows=CHARACTER_BATCH_SIZE,
            max_chars=CWM_MAX_CHARACTER_PROMPT_CHARS,
            prompt_builder=_build_character_profile_prompt,
        ):
            synthesized_by_id: dict[str, CharacterProfileSynthesis] = {}
            for payload in self._synthesize_profiles_with_fallback(batch=batch):
                request_metadata_rows.append(dict(self.reasoning_runtime.last_request_metadata() or {}))
                for item in payload.profiles:
                    synthesized_by_id[item.character_id] = item
            batch_profiles = [
                _profile_artifact_from_evidence(
                    series_id=series_id,
                    evidence=row,
                    synthesis=synthesized_by_id.get(row["character_id"]),
                    reasoning_runtime=self.reasoning_runtime,
                )
                for row in batch
            ]
            for item in self.store.upsert_character_profiles(profiles=batch_profiles):
                persisted_by_id[item.character_id] = item
        ordered = [persisted_by_id[row["character_id"]] for row in evidence_rows if row["character_id"] in persisted_by_id]
        return {"character_profiles": [item.model_dump() for item in ordered], "request_metadata_rows": request_metadata_rows}

    def _synthesize_profiles(self, *, batch: list[dict[str, Any]]) -> CharacterProfilesPayload:
        prompt = _build_character_profile_prompt(batch=batch)
        payload = self.reasoning_runtime.generate_json(prompt, strict=True, max_tokens=3800)
        if payload.get("error"):
            raise RuntimeError(f"Character profile synthesis failed: {payload.get('error')}")
        return CharacterProfilesPayload.model_validate(payload)

    def _synthesize_profiles_with_fallback(self, *, batch: list[dict[str, Any]]) -> list[CharacterProfilesPayload]:
        try:
            return [self._synthesize_profiles(batch=batch)]
        except RuntimeError as exc:
            if not _should_retry_split_synthesis_error(exc):
                raise
            try:
                left, right = _split_evidence_batch_for_retry(batch)
            except RuntimeError:
                return [CharacterProfilesPayload()]
            return [*self._synthesize_profiles_with_fallback(batch=left), *self._synthesize_profiles_with_fallback(batch=right)]


class StableStateAgent:
    def __init__(self, *, store: CharacterWorldModelingStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(
        self,
        *,
        series_id: str,
        character_profiles: list[CharacterProfileArtifact],
        identity_bundle: CanonicalIdentityBundle,
        events: list[EventArtifact],
        relationships: list[RelationshipArtifact],
        timeline: list[TimelineArtifact],
    ) -> dict[str, Any]:
        evidence_rows = [
            _compact_character_prompt_evidence(_build_stable_state_evidence(
                profile=profile,
                identity_bundle=identity_bundle,
                events=events,
                relationships=relationships,
                timeline=timeline,
            ))
            for profile in character_profiles
        ]
        existing_by_id = {
            item.character_id: item
            for item in self.store.list_stable_character_states(series_id=series_id)
        } if _resume_stage_enabled("stable_state_synthesis") else {}
        if not _resume_stage_enabled("stable_state_synthesis"):
            self.store.delete_stable_character_states(series_id=series_id)
        request_metadata_rows: list[dict[str, Any]] = []
        persisted_by_id: dict[str, StableCharacterStateArtifact] = dict(existing_by_id)
        missing_rows = [row for row in evidence_rows if row["character_id"] not in existing_by_id]
        for batch in _prompt_batched(
            missing_rows,
            max_rows=CHARACTER_BATCH_SIZE,
            max_chars=CWM_MAX_CHARACTER_PROMPT_CHARS,
            prompt_builder=_build_stable_state_prompt,
        ):
            synthesized_by_id: dict[str, StableCharacterStateSynthesis] = {}
            for payload in self._synthesize_stable_states_with_fallback(batch=batch):
                request_metadata_rows.append(dict(self.reasoning_runtime.last_request_metadata() or {}))
                for item in payload.stable_states:
                    synthesized_by_id[item.character_id] = item
            batch_states = [
                _stable_state_artifact_from_evidence(
                    series_id=series_id,
                    evidence=row,
                    synthesis=synthesized_by_id.get(row["character_id"]),
                    reasoning_runtime=self.reasoning_runtime,
                )
                for row in batch
            ]
            for item in self.store.upsert_stable_character_states(states=batch_states):
                persisted_by_id[item.character_id] = item
        ordered = [persisted_by_id[row["character_id"]] for row in evidence_rows if row["character_id"] in persisted_by_id]
        return {"stable_character_states": [item.model_dump() for item in ordered], "request_metadata_rows": request_metadata_rows}

    def _synthesize_stable_states(self, *, batch: list[dict[str, Any]]) -> StableCharacterStatesPayload:
        prompt = _build_stable_state_prompt(batch=batch)
        payload = self.reasoning_runtime.generate_json(prompt, strict=True, max_tokens=3200)
        if payload.get("error"):
            raise RuntimeError(f"Stable character state synthesis failed: {payload.get('error')}")
        return StableCharacterStatesPayload.model_validate(payload)

    def _synthesize_stable_states_with_fallback(self, *, batch: list[dict[str, Any]]) -> list[StableCharacterStatesPayload]:
        try:
            return [self._synthesize_stable_states(batch=batch)]
        except RuntimeError as exc:
            if not _should_retry_split_synthesis_error(exc):
                raise
            try:
                left, right = _split_evidence_batch_for_retry(batch)
            except RuntimeError:
                return [StableCharacterStatesPayload()]
            return [*self._synthesize_stable_states_with_fallback(batch=left), *self._synthesize_stable_states_with_fallback(batch=right)]


class WorldStateAgent:
    def __init__(self, *, store: CharacterWorldModelingStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(
        self,
        *,
        series_id: str,
        scenes: list[SceneArtifact],
        entities: list[EntityArtifact],
        events: list[EventArtifact],
        relationships: list[RelationshipArtifact],
    ) -> dict[str, Any]:
        scene_map = {scene.scene_id: scene for scene in scenes}
        existing_by_id = {item.entity_id: item for item in self.store.list_world_states(series_id=series_id)} if _resume_stage_enabled("world_state_synthesis") else {}
        evidence_rows = [
            _build_world_state_evidence(
                entity=entity,
                scene_map=scene_map,
                events=events,
                relationships=relationships,
            )
            for entity in entities
            if entity.entity_id not in existing_by_id
        ]
        request_metadata_rows: list[dict[str, Any]] = []
        synthesized_by_id: dict[str, WorldStateSynthesis] = {}
        persisted_by_id: dict[str, WorldStateArtifact] = dict(existing_by_id)
        if not existing_by_id:
            self.store.delete_world_states(series_id=series_id)
        jobs = [{"job_index": index, "batch": batch} for index, batch in enumerate(_batched(evidence_rows, ENTITY_BATCH_SIZE))]

        def run_job(job: dict[str, Any]) -> dict[str, Any]:
            runtime = _clone_reasoning_runtime(self.reasoning_runtime)
            started_at = time.perf_counter()
            payloads = self._synthesize_world_states_with_fallback(batch=list(job["batch"]), reasoning_runtime=runtime)
            return {
                "job_index": int(job["job_index"]),
                "batch": list(job["batch"]),
                "payloads": payloads,
                "metadata": _request_metadata_with_job_stats(runtime, started_at=started_at, batch_size=len(job["batch"])),
            }

        for result in _run_ordered_parallel_jobs(jobs, run_job):
            request_metadata_rows.append(dict(result.get("metadata") or {}))
            batch = list(result.get("batch") or [])
            batch_by_id = {str(row.get("entity_id") or ""): row for row in batch}
            for payload in list(result.get("payloads") or []):
                for item in payload.world_states:
                    synthesized_by_id[item.entity_id] = item
            batch_artifacts = [
                _world_state_artifact_from_evidence(
                    series_id=series_id,
                    evidence=row,
                    synthesis=synthesized_by_id.get(row["entity_id"]),
                    reasoning_runtime=self.reasoning_runtime,
                )
                for row in batch
            ]
            for item in self.store.upsert_world_states(world_states=batch_artifacts):
                persisted_by_id[item.entity_id] = item
            synthesized_by_id = {key: value for key, value in synthesized_by_id.items() if key not in batch_by_id}
        ordered = [persisted_by_id[item.entity_id] for item in entities if item.entity_id in persisted_by_id]
        return {"world_states": [item.model_dump() for item in ordered], "request_metadata_rows": request_metadata_rows}

    def _synthesize_world_states(
        self,
        *,
        batch: list[dict[str, Any]],
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> WorldStatesPayload:
        runtime = reasoning_runtime or self.reasoning_runtime
        prompt = _build_world_state_prompt(batch=batch)
        payload = runtime.generate_json(prompt, strict=True, max_tokens=3600)
        if payload.get("error"):
            raise RuntimeError(f"World state synthesis failed: {payload.get('error')}")
        return WorldStatesPayload.model_validate(payload)

    def _synthesize_world_states_with_fallback(
        self,
        *,
        batch: list[dict[str, Any]],
        reasoning_runtime: ReasoningRuntimeClient | None = None,
    ) -> list[WorldStatesPayload]:
        runtime = reasoning_runtime or self.reasoning_runtime
        try:
            return [self._synthesize_world_states(batch=batch, reasoning_runtime=runtime)]
        except RuntimeError as exc:
            if not _should_retry_split_synthesis_error(exc):
                raise
            try:
                left, right = _split_evidence_batch_for_retry(batch)
            except RuntimeError:
                return [WorldStatesPayload()]
            return [
                *self._synthesize_world_states_with_fallback(batch=left, reasoning_runtime=runtime),
                *self._synthesize_world_states_with_fallback(batch=right, reasoning_runtime=runtime),
            ]


def build_character_world_modeling_graph(
    *,
    profile_agent: CharacterProfileAgent,
    stable_state_agent: StableStateAgent,
    world_state_agent: WorldStateAgent,
    checkpointer: BaseCheckpointSaver | None = None,
):
    def profiles_node(state: CharacterWorldModelingState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = profile_agent.run(
            series_id=str(state.get("series_id") or ""),
            books=[BookArtifact.model_validate(item) for item in list(state.get("books") or [])],
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
            events=[EventArtifact.model_validate(item) for item in list(state.get("events") or [])],
            relationships=[RelationshipArtifact.model_validate(item) for item in list(state.get("relationships") or [])],
            timeline=[TimelineArtifact.model_validate(item) for item in list(state.get("timeline") or [])],
        )
        return {
            "character_profiles": list(payload["character_profiles"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="character_profile_synthesis",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "profile_count": len(payload["character_profiles"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "batch_size": CHARACTER_BATCH_SIZE,
                    "parallelism": 1,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    def stable_states_node(state: CharacterWorldModelingState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = stable_state_agent.run(
            series_id=str(state.get("series_id") or ""),
            character_profiles=[CharacterProfileArtifact.model_validate(item) for item in list(state.get("character_profiles") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
            events=[EventArtifact.model_validate(item) for item in list(state.get("events") or [])],
            relationships=[RelationshipArtifact.model_validate(item) for item in list(state.get("relationships") or [])],
            timeline=[TimelineArtifact.model_validate(item) for item in list(state.get("timeline") or [])],
        )
        return {
            "stable_character_states": list(payload["stable_character_states"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="stable_state_synthesis",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "stable_state_count": len(payload["stable_character_states"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "batch_size": CHARACTER_BATCH_SIZE,
                    "parallelism": 1,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    def world_states_node(state: CharacterWorldModelingState) -> dict[str, Any]:
        started_at = time.perf_counter()
        if _resume_stage_enabled("world_state_synthesis"):
            existing_world_states = world_state_agent.store.list_world_states(series_id=str(state.get("series_id") or ""))
            requested_entity_count = len(list(state.get("entities") or []))
            if requested_entity_count > 0 and len(existing_world_states) >= requested_entity_count:
                return {
                    "world_states": [item.model_dump() for item in existing_world_states],
                    "run_metadata": _append_stage_metadata(
                        state.get("run_metadata"),
                        stage_name="world_state_synthesis",
                        elapsed_seconds=time.perf_counter() - started_at,
                        extra={
                            "world_state_count": len(existing_world_states),
                            "resumed": True,
                            "reasoning_calls": 0,
                            "batch_size": ENTITY_BATCH_SIZE,
                            "parallelism": CWM_PARALLELISM,
                            "job_latency_seconds": {"count": 0},
                        },
                    ),
                }
        payload = world_state_agent.run(
            series_id=str(state.get("series_id") or ""),
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            entities=[EntityArtifact.model_validate(item) for item in list(state.get("entities") or [])],
            events=[EventArtifact.model_validate(item) for item in list(state.get("events") or [])],
            relationships=[RelationshipArtifact.model_validate(item) for item in list(state.get("relationships") or [])],
        )
        return {
            "world_states": list(payload["world_states"]),
            "run_metadata": _append_stage_metadata(
                state.get("run_metadata"),
                stage_name="world_state_synthesis",
                elapsed_seconds=time.perf_counter() - started_at,
                extra={
                    "world_state_count": len(payload["world_states"]),
                    "reasoning_calls": len(payload.get("request_metadata_rows") or []),
                    "batch_size": ENTITY_BATCH_SIZE,
                    "parallelism": CWM_PARALLELISM,
                    "job_latency_seconds": _job_latency_summary(payload.get("request_metadata_rows") or []),
                },
            ),
        }

    builder = StateGraph(CharacterWorldModelingState)
    builder.add_node("profiles", profiles_node)
    builder.add_node("stable_states", stable_states_node)
    builder.add_node("world_states", world_states_node)
    builder.add_edge(START, "profiles")
    builder.add_edge("profiles", "stable_states")
    builder.add_edge("stable_states", "world_states")
    builder.add_edge("world_states", END)
    return builder.compile(checkpointer=checkpointer)


class CharacterWorldModelingRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        reasoning_runtime: ReasoningRuntimeClient,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
    ) -> None:
        self.persistence = persistence
        self.persistence.initialize()
        self.store = CharacterWorldModelingStore(persistence)
        self.profile_agent = CharacterProfileAgent(store=self.store, reasoning_runtime=reasoning_runtime)
        self.stable_state_agent = StableStateAgent(store=self.store, reasoning_runtime=reasoning_runtime)
        self.world_state_agent = WorldStateAgent(store=self.store, reasoning_runtime=reasoning_runtime)
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_character_world_modeling_graph(
            profile_agent=self.profile_agent,
            stable_state_agent=self.stable_state_agent,
            world_state_agent=self.world_state_agent,
            checkpointer=self.checkpointer,
        )

    def invoke(self, *, series_id: str, thread_id: str = "character-world-modeling") -> CharacterWorldModelingResult:
        context = self.store.load_series_context(series_id=series_id)
        identity_bundle = context.get("identity_bundle")
        if identity_bundle is None:
            raise ValueError(f"CharacterWorldModelingRuntime requires a persisted identity bundle for series '{series_id}'.")
        if not list(context.get("events") or []) and not list(context.get("entities") or []):
            raise ValueError(f"CharacterWorldModelingRuntime requires persisted canon extraction outputs for series '{series_id}'.")
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "books": [item.model_dump() for item in list(context.get("books") or [])],
                "scenes": [item.model_dump() for item in list(context.get("scenes") or [])],
                "identity_bundle": identity_bundle.model_dump(),
                "events": [item.model_dump() for item in list(context.get("events") or [])],
                "entities": [item.model_dump() for item in list(context.get("entities") or [])],
                "relationships": [item.model_dump() for item in list(context.get("relationships") or [])],
                "timeline": [item.model_dump() for item in list(context.get("timeline") or [])],
            },
            config={"configurable": {"thread_id": str(thread_id or "character-world-modeling")}},
        )
        return CharacterWorldModelingResult(
            series_id=series_id,
            character_profiles=[
                CharacterProfileArtifact.model_validate(item) for item in list(state.get("character_profiles") or [])
            ],
            stable_character_states=[
                StableCharacterStateArtifact.model_validate(item) for item in list(state.get("stable_character_states") or [])
            ],
            world_states=[WorldStateArtifact.model_validate(item) for item in list(state.get("world_states") or [])],
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
    raise ValueError("CharacterWorldModelingRuntime requires a durable checkpointer or an initialized persistence engine.")


def _clone_reasoning_runtime(reasoning_runtime: ReasoningRuntimeClient) -> ReasoningRuntimeClient:
    clone = getattr(reasoning_runtime, "clone", None)
    if callable(clone):
        return clone()
    return reasoning_runtime


def _run_ordered_parallel_jobs(jobs: list[dict[str, Any]], worker) -> list[dict[str, Any]]:
    if not jobs:
        return []
    workers = min(CWM_PARALLELISM, len(jobs))
    if workers <= 1:
        return [worker(job) for job in jobs]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="character-world-modeling") as executor:
        future_to_job = {executor.submit(contextvars.copy_context().run, worker, job): job for job in jobs}
        for future in as_completed(future_to_job):
            results.append(future.result())
    return sorted(results, key=lambda item: int(item.get("job_index") or 0))


def _request_metadata_with_job_stats(reasoning_runtime: ReasoningRuntimeClient, *, started_at: float, batch_size: int) -> dict[str, Any]:
    metadata = dict(reasoning_runtime.last_request_metadata() or {})
    metadata["job_elapsed_seconds"] = round(max(0.0, time.perf_counter() - started_at), 4)
    metadata["batch_size"] = int(batch_size)
    metadata["parallelism"] = CWM_PARALLELISM
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
    return stage_name in CWM_RESUME_STAGES or "all" in CWM_RESUME_STAGES


def _build_character_evidence(
    *,
    character: CanonicalCharacter,
    scene_map: dict[str, SceneArtifact],
    events: list[EventArtifact],
    relationships: list[RelationshipArtifact],
    timeline: list[TimelineArtifact],
) -> dict[str, Any]:
    event_roles = {item.event_id: _character_event_role(item, character=character, scene_map=scene_map) for item in events}
    primary_event_roles = {"actor", "speaker", "narrator_actor"}
    character_events = [
        item
        for item in events
        if character.character_id in (item.participant_refs or []) and event_roles.get(item.event_id) in primary_event_roles
    ][:MAX_EVENT_EVIDENCE]
    contextual_events = [
        item
        for item in events
        if character.character_id in (item.participant_refs or [])
        and event_roles.get(item.event_id) not in primary_event_roles
    ][:MAX_EVENT_EVIDENCE]
    character_timeline = [
        item
        for item in timeline
        if character.character_id in (item.participant_refs or [])
        and event_roles.get(str(item.event_id or item.timeline_id), "implicit_participant") in primary_event_roles
    ][:MAX_EVENT_EVIDENCE]
    character_relationships = [
        item for item in relationships if item.source_ref == character.character_id or item.target_ref == character.character_id
    ][:MAX_RELATIONSHIP_EVIDENCE]
    relevant_scene_ids = _unique_strings(
        [*list(character.scene_ids or [])]
        + [item.scene_id for item in character_events if item.scene_id]
        + [scene_id for item in character_relationships for scene_id in list(item.scene_ids or [])]
    )
    relevant_scenes = [scene_map[scene_id] for scene_id in relevant_scene_ids if scene_id in scene_map][:MAX_SCENE_EVIDENCE]
    latest_summary = ""
    if character_timeline:
        latest_summary = character_timeline[-1].summary or character_timeline[-1].title
    elif character_events:
        latest_summary = character_events[-1].summary or character_events[-1].title
    return {
        "character_id": character.character_id,
        "canonical_name": character.display_name,
        "aliases": list(character.aliases or []),
        "mention_count": int(character.mention_count or 0),
        "chapter_indices": sorted({int(value) for value in list(character.chapter_indices or [])}),
        "scene_ids": relevant_scene_ids,
        "important_event_ids": [item.event_id for item in character_events],
        "event_evidence": [
            {
                "event_id": item.event_id,
                "title": item.title,
                "summary": item.summary,
                "event_type": item.event_type,
                "participant_refs": list(item.participant_refs or []),
                "character_event_role": event_roles.get(item.event_id, "implicit_participant"),
            }
            for item in character_events
        ],
        "contextual_event_evidence": [
            {
                "event_id": item.event_id,
                "title": item.title,
                "summary": item.summary,
                "event_type": item.event_type,
                "participant_refs": list(item.participant_refs or []),
                "character_event_role": event_roles.get(item.event_id, "mentioned_only"),
            }
            for item in contextual_events
        ],
        "relationship_evidence": [
            {
                "relationship_id": item.relationship_id,
                "source_ref": item.source_ref,
                "target_ref": item.target_ref,
                "relationship_type": item.relationship_type,
                "description": item.description,
            }
            for item in character_relationships
        ],
        "timeline_evidence": [
            {"timeline_id": item.timeline_id, "title": item.title, "summary": item.summary, "event_type": item.event_type}
            for item in character_timeline
        ],
        "scene_evidence": [
            {
                "scene_id": scene.scene_id,
                "chapter_index": scene.chapter_index,
                "scene_index": scene.scene_index,
                "summary": scene.summary,
                "excerpt": _excerpt(scene.text),
                "narrative_grounding": _scene_narrative_grounding(scene),
            }
            for scene in relevant_scenes
        ],
        "first_seen_summary": relevant_scenes[0].summary or _excerpt(relevant_scenes[0].text) if relevant_scenes else "",
        "latest_state_summary": latest_summary,
        "book_ids": sorted({scene.book_id for scene in relevant_scenes}),
    }


def _build_stable_state_evidence(
    *,
    profile: CharacterProfileArtifact,
    identity_bundle: CanonicalIdentityBundle,
    events: list[EventArtifact],
    relationships: list[RelationshipArtifact],
    timeline: list[TimelineArtifact],
) -> dict[str, Any]:
    character = _character_for_profile(profile, identity_bundle)
    event_roles = {item.event_id: _character_event_role(item, character=character, scene_map={}) for item in events} if character else {}
    primary_event_roles = {"actor", "speaker", "narrator_actor"}
    event_rows = [
        item
        for item in events
        if profile.character_id in (item.participant_refs or []) and event_roles.get(item.event_id) in primary_event_roles
    ][:MAX_EVENT_EVIDENCE]
    contextual_event_rows = [
        item
        for item in events
        if profile.character_id in (item.participant_refs or []) and event_roles.get(item.event_id) not in primary_event_roles
    ][:MAX_EVENT_EVIDENCE]
    relationship_rows = [
        item for item in relationships if item.source_ref == profile.character_id or item.target_ref == profile.character_id
    ][:MAX_RELATIONSHIP_EVIDENCE]
    timeline_rows = [item for item in timeline if profile.character_id in (item.participant_refs or [])][:MAX_EVENT_EVIDENCE]
    return {
        "character_id": profile.character_id,
        "canonical_name": profile.canonical_name,
        "aliases": list(profile.aliases or []),
        "overview": profile.overview,
        "role_or_archetype": profile.role_or_archetype,
        "traits": list(profile.traits or []),
        "motivations": list(profile.motivations or []),
        "loyalties": list(profile.loyalties or []),
        "tensions": list(profile.tensions or []),
        "notable_relationships": list(profile.notable_relationships or []),
        "event_evidence": [
            {
                "event_id": item.event_id,
                "title": item.title,
                "summary": item.summary,
                "participant_refs": list(item.participant_refs or []),
                "character_event_role": event_roles.get(item.event_id, "implicit_participant"),
            }
            for item in event_rows
        ],
        "contextual_event_evidence": [
            {
                "event_id": item.event_id,
                "title": item.title,
                "summary": item.summary,
                "participant_refs": list(item.participant_refs or []),
                "character_event_role": event_roles.get(item.event_id, "mentioned_only"),
            }
            for item in contextual_event_rows
        ],
        "relationship_evidence": [
            {
                "relationship_id": item.relationship_id,
                "type": item.relationship_type,
                "description": item.description,
                "scene_ids": list(item.scene_ids or []),
            }
            for item in relationship_rows
        ],
        "timeline_evidence": [{"timeline_id": item.timeline_id, "title": item.title, "summary": item.summary} for item in timeline_rows],
        "supporting_event_ids": [item.event_id for item in event_rows],
        "supporting_scene_ids": _unique_strings(
            [item.scene_id for item in event_rows]
            + [scene_id for item in relationship_rows for scene_id in list(item.scene_ids or [])]
        ),
    }


def _build_world_state_evidence(
    *,
    entity: EntityArtifact,
    scene_map: dict[str, SceneArtifact],
    events: list[EventArtifact],
    relationships: list[RelationshipArtifact],
) -> dict[str, Any]:
    entity_events = [item for item in events if entity.entity_id in (item.entity_refs or [])][:MAX_EVENT_EVIDENCE]
    entity_relationships = [
        item for item in relationships if item.source_ref == entity.entity_id or item.target_ref == entity.entity_id
    ][:MAX_RELATIONSHIP_EVIDENCE]
    relevant_scene_ids = _unique_strings(
        list(entity.mention_scene_ids or [])
        + [item.scene_id for item in entity_events if item.scene_id]
        + [scene_id for item in entity_relationships for scene_id in list(item.scene_ids or [])]
    )
    relevant_scenes = [scene_map[scene_id] for scene_id in relevant_scene_ids if scene_id in scene_map][:MAX_SCENE_EVIDENCE]
    return {
        "entity_id": entity.entity_id,
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "description": entity.description,
        "aliases": list(entity.aliases or []),
        "book_ids": sorted(set(entity.book_ids or [])),
        "scene_ids": relevant_scene_ids,
        "event_evidence": [
            {"event_id": item.event_id, "title": item.title, "summary": item.summary, "event_type": item.event_type}
            for item in entity_events
        ],
        "relationship_evidence": [
            {"relationship_id": item.relationship_id, "type": item.relationship_type, "description": item.description}
            for item in entity_relationships
        ],
        "scene_evidence": [
            {
                "scene_id": scene.scene_id,
                "chapter_index": scene.chapter_index,
                "scene_index": scene.scene_index,
                "summary": scene.summary,
                "excerpt": _excerpt(scene.text),
                "narrative_grounding": _scene_narrative_grounding(scene),
            }
            for scene in relevant_scenes
        ],
        "supporting_event_ids": [item.event_id for item in entity_events],
    }


def _profile_artifact_from_evidence(
    *,
    series_id: str,
    evidence: dict[str, Any],
    synthesis: CharacterProfileSynthesis | None,
    reasoning_runtime: ReasoningRuntimeClient,
) -> CharacterProfileArtifact:
    item = synthesis or CharacterProfileSynthesis(character_id=str(evidence.get("character_id") or ""))
    canonical_name = str(evidence.get("canonical_name") or "").strip()
    has_primary_support = _profile_has_primary_support(evidence)
    grounded_first_seen = _grounded_profile_summary(
        _clean_text(item.first_seen_summary) if has_primary_support else "",
        canonical_name=canonical_name,
        evidence=evidence,
    )
    grounded_latest_state = _grounded_profile_summary(
        _clean_text(item.latest_state_summary) if has_primary_support else "",
        canonical_name=canonical_name,
        evidence=evidence,
    )
    return CharacterProfileArtifact(
        profile_id=f"character-profile-{_slug(evidence.get('character_id') or canonical_name)}",
        series_id=series_id,
        character_id=str(evidence.get("character_id") or ""),
        canonical_name=canonical_name,
        aliases=list(evidence.get("aliases") or []),
        book_ids=list(evidence.get("book_ids") or []),
        chapter_indices=[int(value) for value in list(evidence.get("chapter_indices") or [])],
        scene_ids=list(evidence.get("scene_ids") or []),
        overview=_grounded_overview_or_fallback(
            _clean_text(item.overview) if has_primary_support else "",
            canonical_name=canonical_name,
            evidence=evidence,
        ),
        role_or_archetype=_clean_text(item.role_or_archetype) if has_primary_support else "",
        traits=_limit_unique_strings(item.traits, 8) if has_primary_support else [],
        motivations=_limit_unique_strings(item.motivations, 6) if has_primary_support else [],
        loyalties=_limit_unique_strings(item.loyalties, 6) if has_primary_support else [],
        tensions=_limit_unique_strings(item.tensions, 6) if has_primary_support else [],
        notable_relationships=_sanitize_notable_relationships(
            _limit_unique_strings(item.notable_relationships, 8) if has_primary_support else [],
            canonical_name=canonical_name,
            evidence=evidence,
        ),
        visual_cues=_limit_unique_strings(item.visual_cues, 8) if has_primary_support else [],
        first_seen_summary=(
            grounded_first_seen
            or _first_scene_sentence_with_name(evidence, canonical_name)
            or (_clean_text(str(evidence.get("first_seen_summary") or "")) if has_primary_support and _text_mentions_name(str(evidence.get("first_seen_summary") or ""), canonical_name) else "")
        ),
        latest_state_summary=(
            grounded_latest_state
            or (
                _clean_text(str(evidence.get("latest_state_summary") or ""))
                if has_primary_support and _text_mentions_name(str(evidence.get("latest_state_summary") or ""), canonical_name)
                else ""
            )
        ),
        important_event_ids=list(evidence.get("important_event_ids") or []),
        metadata={
            "reasoning_provider": reasoning_runtime.provider_name(),
            "reasoning_model": reasoning_runtime.resolved_model_name(),
            "mention_count": int(evidence.get("mention_count") or 0),
        },
    )


def _stable_state_artifact_from_evidence(
    *,
    series_id: str,
    evidence: dict[str, Any],
    synthesis: StableCharacterStateSynthesis | None,
    reasoning_runtime: ReasoningRuntimeClient,
) -> StableCharacterStateArtifact:
    item = synthesis or StableCharacterStateSynthesis(character_id=str(evidence.get("character_id") or ""))
    has_primary_support = _profile_has_primary_support(evidence)
    stable_attributes = (
        _sanitize_stable_attributes(_normalize_stable_attributes(item.stable_attributes), evidence=evidence)
        if has_primary_support
        else {}
    )
    return StableCharacterStateArtifact(
        stable_state_id=f"stable-character-state-{_slug(evidence.get('character_id') or evidence.get('canonical_name') or '')}",
        series_id=series_id,
        character_id=str(evidence.get("character_id") or ""),
        canonical_name=str(evidence.get("canonical_name") or ""),
        stable_attributes=stable_attributes,
        summary=(_clean_text(item.summary) if has_primary_support else "") or _fallback_stable_state_summary(evidence, stable_attributes),
        supporting_event_ids=list(evidence.get("supporting_event_ids") or []),
        supporting_scene_ids=list(evidence.get("supporting_scene_ids") or []),
        metadata={
            "reasoning_provider": reasoning_runtime.provider_name(),
            "reasoning_model": reasoning_runtime.resolved_model_name(),
        },
    )


def _world_state_artifact_from_evidence(
    *,
    series_id: str,
    evidence: dict[str, Any],
    synthesis: WorldStateSynthesis | None,
    reasoning_runtime: ReasoningRuntimeClient,
) -> WorldStateArtifact:
    item = synthesis or WorldStateSynthesis(entity_id=str(evidence.get("entity_id") or ""))
    stable_facts = _sanitize_world_stable_facts(_normalize_fact_map(item.stable_facts), evidence=evidence)
    return WorldStateArtifact(
        world_state_id=f"world-state-{_slug(evidence.get('entity_id') or evidence.get('canonical_name') or '')}",
        series_id=series_id,
        entity_id=str(evidence.get("entity_id") or ""),
        canonical_name=str(evidence.get("canonical_name") or ""),
        entity_type=str(evidence.get("entity_type") or ""),
        description=_clean_text(str(evidence.get("description") or "")),
        book_ids=list(evidence.get("book_ids") or []),
        scene_ids=list(evidence.get("scene_ids") or []),
        stable_facts=stable_facts,
        active_conditions=_sanitize_world_conditions(_limit_unique_strings(item.active_conditions, 8), evidence=evidence),
        current_state_summary=_clean_text(item.current_state_summary) or _fallback_world_state_summary(evidence),
        story_relevance=_clean_text(item.story_relevance),
        supporting_event_ids=list(evidence.get("supporting_event_ids") or []),
        metadata={
            "reasoning_provider": reasoning_runtime.provider_name(),
            "reasoning_model": reasoning_runtime.resolved_model_name(),
        },
    )


def _build_character_profile_prompt(*, batch: list[dict[str, Any]]) -> str:
    return (
        "You synthesize durable canonical character profiles from grounded book-analysis evidence.\n"
        "Return JSON only with top-level key \"profiles\".\n"
        "Rules:\n"
        "- Output exactly one profile per requested character_id.\n"
        "- Use only grounded evidence.\n"
        "- Treat event_evidence as primary evidence for this character; contextual_event_evidence is background only and must not drive overview, traits, motivations, stable facts, or latest state.\n"
        "- Respect narrative_grounding in scene_evidence: first-person narrator actions belong to narrator_name only when narrator_character_id is present.\n"
        "- Do not assign narrator/addressee actions to a named character without grounding evidence.\n"
        "- Separate actor/agent, recipient, observer, addressee, and mentioned-only roles; do not rewrite an event done to/about a character as an action by that character.\n"
        "- Possessive object phrases such as \"X's seal\" are object provenance, not evidence that X acted, used the object, or has a relationship in that event unless direct evidence says so.\n"
        "- Do not invent powers, history, or appearance details.\n"
        "- Keep every list concise.\n"
        "- If something is not grounded, leave it empty.\n"
        "Each profile object must contain: character_id, overview, role_or_archetype, traits, motivations, loyalties, tensions, notable_relationships, visual_cues, first_seen_summary, latest_state_summary.\n"
        f"Evidence batch:\n{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )


def _compact_character_prompt_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Bound model-facing evidence without changing persisted canon artifacts."""
    compacted = dict(evidence)
    compacted["aliases"] = [
        _bounded_prompt_text(value, max_chars=120)
        for value in list(evidence.get("aliases") or [])[:MAX_PROMPT_ALIASES]
    ]
    for key in ("scene_ids", "important_event_ids", "supporting_event_ids", "supporting_scene_ids"):
        if key in compacted:
            compacted[key] = list(compacted.get(key) or [])[:MAX_PROMPT_REFERENCE_IDS]
    if "chapter_indices" in compacted:
        values = list(compacted.get("chapter_indices") or [])
        compacted["chapter_indices"] = values[:8] + values[-8:] if len(values) > 16 else values

    for key in (
        "overview",
        "role_or_archetype",
        "first_seen_summary",
        "latest_state_summary",
    ):
        if key in compacted:
            compacted[key] = _bounded_prompt_text(compacted.get(key))
    for key in (
        "traits",
        "motivations",
        "loyalties",
        "tensions",
        "notable_relationships",
    ):
        if key in compacted:
            compacted[key] = [
                _bounded_prompt_text(value, max_chars=180)
                for value in list(compacted.get(key) or [])[:8]
            ]

    evidence_limits = {
        "event_evidence": 5,
        "contextual_event_evidence": 2,
        "relationship_evidence": 4,
        "timeline_evidence": 3,
        "scene_evidence": 2,
    }
    for key, row_limit in evidence_limits.items():
        rows = []
        for item in list(compacted.get(key) or [])[:row_limit]:
            row = dict(item)
            for text_key in ("title", "summary", "description", "excerpt", "narrative_grounding"):
                if text_key in row:
                    row[text_key] = _bounded_prompt_text(row.get(text_key))
            if "participant_refs" in row:
                row["participant_refs"] = list(row.get("participant_refs") or [])[:MAX_PROMPT_REFERENCE_IDS]
            if "scene_ids" in row:
                row["scene_ids"] = list(row.get("scene_ids") or [])[:MAX_PROMPT_REFERENCE_IDS]
            rows.append(row)
        compacted[key] = rows
    return compacted


def _bounded_prompt_text(value: Any, *, max_chars: int = MAX_PROMPT_TEXT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _prompt_batched(
    values: list[dict[str, Any]],
    *,
    max_rows: int,
    max_chars: int,
    prompt_builder: Any,
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for value in values:
        candidate = [*current, value]
        if current and (len(candidate) > max_rows or len(prompt_builder(batch=candidate)) > max_chars):
            batches.append(current)
            current = [value]
        else:
            current = candidate
        if len(prompt_builder(batch=current)) > max_chars:
            raise RuntimeError(
                f"Character evidence for {value.get('character_id') or '<unknown>'} exceeds "
                f"the {max_chars}-character prompt budget after compaction"
            )
    if current:
        batches.append(current)
    return batches


def _build_stable_state_prompt(*, batch: list[dict[str, Any]]) -> str:
    return (
        "You extract only durable stable character-state facts from grounded canon evidence.\n"
        "Return JSON only with top-level key \"stable_states\".\n"
        "Rules:\n"
        "- Output exactly one object per requested character_id.\n"
        "- Include only durable facts that are likely to remain true across scenes.\n"
        "- Treat event_evidence as primary evidence for this character; contextual_event_evidence is background only and must not become a stable fact.\n"
        "- Respect narrative_grounding from upstream evidence when interpreting first-person or second-person references.\n"
        "- Preserve event roles: recipient, observer, addressee, or mentioned-only evidence must not become a stable action, allegiance, ownership, or relationship.\n"
        "- Possessive object provenance such as \"X's seal\" is not a stable character fact for X unless direct evidence says X acted or owned the object in the current story context.\n"
        "- Exclude temporary emotions, outfits, injuries, and scene-specific actions.\n"
        "- stable_attributes must be a flat object of short string values.\n"
        "- Preferred keys: role, title, affiliation, allegiance, residence, court, family_role, power_status, species, profession, bond, relationship_status.\n"
        "- If no durable fact is grounded, return an empty stable_attributes object.\n"
        "Each object must contain: character_id, stable_attributes, summary.\n"
        f"Evidence batch:\n{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )


def _build_world_state_prompt(*, batch: list[dict[str, Any]]) -> str:
    return (
        "You synthesize grounded world-state summaries for non-character canon entities.\n"
        "Return JSON only with top-level key \"world_states\".\n"
        "Rules:\n"
        "- Output exactly one object per requested entity_id.\n"
        "- Use only grounded evidence.\n"
        "- stable_facts must be a flat object of durable facts.\n"
        "- active_conditions should list important current conditions if grounded.\n"
        "- current_state_summary should describe the latest grounded known state.\n"
        "- story_relevance should be a short grounded explanation.\n"
        "- If evidence is sparse, keep fields empty rather than inventing details.\n"
        "Each object must contain: entity_id, stable_facts, active_conditions, current_state_summary, story_relevance.\n"
        f"Evidence batch:\n{json.dumps(batch, ensure_ascii=False, indent=2)}"
    )


def _append_stage_metadata(
    current: dict[str, Any] | None,
    *,
    stage_name: str,
    elapsed_seconds: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(current or {})
    stage_order = list(payload.get("stage_order") or [])
    stage_order.append(stage_name)
    timings = dict(payload.get("timings_seconds") or {})
    timings[stage_name] = round(float(elapsed_seconds), 4)
    metrics = dict(payload.get("stage_metrics") or {})
    metrics[stage_name] = dict(extra or {})
    payload["stage_order"] = stage_order
    payload["timings_seconds"] = timings
    payload["stage_metrics"] = metrics
    return payload


def _batched(values: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        return [values]
    return [values[index: index + size] for index in range(0, len(values), size)]


def _grounded_character_ids(
    *, events: list[EventArtifact], relationships: list[RelationshipArtifact]
) -> set[str]:
    references = {
        str(reference or "").strip()
        for event in events
        for reference in event.participant_refs
        if str(reference or "").strip().startswith("char-")
    }
    references.update(
        str(reference or "").strip()
        for relationship in relationships
        for reference in (relationship.source_ref, relationship.target_ref)
        if str(reference or "").strip().startswith("char-")
    )
    return references


def _split_evidence_batch_for_retry(batch: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(batch) <= 1:
        raise RuntimeError("empty_response")
    midpoint = max(1, len(batch) // 2)
    return batch[:midpoint], batch[midpoint:]


def _should_retry_split_synthesis_error(exc: RuntimeError) -> bool:
    message = str(exc)
    return "parse_failed" in message or "empty_response" in message or "max_retries_exceeded" in message


def _excerpt(text: str, *, max_chars: int = 320) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _scene_narrative_grounding(scene: SceneArtifact) -> dict[str, Any]:
    raw = scene.metadata.get("narrative_grounding") if isinstance(scene.metadata, dict) else None
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _character_for_profile(
    profile: CharacterProfileArtifact,
    identity_bundle: CanonicalIdentityBundle,
) -> CanonicalCharacter | None:
    for character in identity_bundle.characters:
        if character.character_id == profile.character_id:
            return character
    return None


def _character_event_role(
    event: EventArtifact | TimelineArtifact,
    *,
    character: CanonicalCharacter,
    scene_map: dict[str, SceneArtifact],
) -> str:
    if character.character_id not in list(event.participant_refs or []):
        return "absent"
    text = f"{event.title or ''}\n{event.summary or ''}".strip()
    scene = scene_map.get(str(event.scene_id or ""))
    grounding = _scene_narrative_grounding(scene) if scene is not None else {}
    if grounding.get("narrator_character_id") == character.character_id and _contains_first_person_reference(text):
        return "narrator_actor"
    names = _character_surface_names(character)
    if not text:
        return "implicit_participant"
    if _only_possessive_name_matches(text, names):
        return "mentioned_only"
    if _matches_primary_actor(text, names):
        return "actor"
    if _matches_speech_actor(text, names):
        return "speaker"
    if _matches_direct_recipient(text, names):
        return "recipient"
    if any(_has_non_possessive_name_match(text, name) for name in names):
        return "mentioned_only"
    return "implicit_participant"


def _character_surface_names(character: CanonicalCharacter) -> list[str]:
    return _unique_strings([character.display_name, *list(character.aliases or [])])


def _contains_first_person_reference(text: str) -> bool:
    return bool(re.search(r"\b(?:I|me|my|mine|myself|we|us|our|ours)\b", text or "", flags=re.IGNORECASE))


def _only_possessive_name_matches(text: str, names: list[str]) -> bool:
    matched = False
    for name in names:
        pattern = _name_pattern(name)
        if pattern is None:
            continue
        for match in pattern.finditer(text or ""):
            matched = True
            suffix = str(text or "")[match.end(): match.end() + 6].lstrip()
            if not _is_possessive_suffix(suffix):
                return False
    return matched


def _matches_primary_actor(text: str, names: list[str]) -> bool:
    actor_verbs = (
        "act|acts|acted|ask|asks|asked|answer|answers|answered|arrive|arrives|arrived|call|calls|called|"
        "climb|climbs|climbed|confront|confronts|confronted|craft|crafts|crafted|demand|demands|demanded|"
        "drag|drags|dragged|enter|enters|entered|fight|fights|fought|give|gives|gave|go|goes|went|"
        "grab|grabs|grabbed|greet|greets|greeted|insist|insists|insisted|join|joins|joined|kiss|kisses|kissed|"
        "meet|meets|met|open|opens|opened|promise|promises|promised|propose|proposes|proposed|read|reads|"
        "resolve|resolves|resolved|say|says|said|send|sends|sent|show|shows|showed|slam|slams|slammed|"
        "speak|speaks|spoke|stand|stands|stood|strike|strikes|struck|suggest|suggests|suggested|tell|tells|told|"
        "threaten|threatens|threatened|visit|visits|visited|vow|vows|vowed|write|writes|wrote"
    )
    for name in names:
        cleaned = _clean_text(name)
        if not cleaned:
            continue
        pattern = re.compile(rf"\b{re.escape(cleaned)}\b", flags=re.IGNORECASE)
        for match in pattern.finditer(text or ""):
            if _name_match_is_contextual_object(text or "", match):
                continue
            suffix = str(text or "")[match.end(): match.end() + 90]
            prefix = str(text or "")[: match.start()]
            if not prefix.strip() and re.search(rf"^[^\n.?!]{{0,80}}\b(?:{actor_verbs})\b", suffix, flags=re.IGNORECASE):
                return True
            if re.search(rf"^[^\n.?!]{{0,80}}\b(?:{actor_verbs})\b", suffix, flags=re.IGNORECASE):
                return True
    return False


def _name_match_is_contextual_object(text: str, match: re.Match[str]) -> bool:
    prefix = text[max(0, match.start() - 40): match.start()]
    return bool(re.search(r"\b(?:involvement|relationship|romance|history|connection|association)\s+with\s+$", prefix, flags=re.IGNORECASE))


def _matches_speech_actor(text: str, names: list[str]) -> bool:
    for name in names:
        cleaned = _clean_text(name)
        if not cleaned:
            continue
        pattern = re.compile(rf"\b{re.escape(cleaned)}\b", flags=re.IGNORECASE)
        for match in pattern.finditer(text or ""):
            if _name_match_is_contextual_object(text or "", match):
                continue
            suffix = str(text or "")[match.end(): match.end() + 90]
            if re.search(
                r"^[^\n.?!]{0,80}\b(?:says|said|speaks|spoke|tells|told|asks|asked|answers|answered|declares|declared)\b",
                suffix,
                flags=re.IGNORECASE,
            ):
                return True
    return False


def _matches_direct_recipient(text: str, names: list[str]) -> bool:
    for name in names:
        cleaned = _clean_text(name)
        if not cleaned:
            continue
        if re.search(rf"\b(?:involvement|relationship|romance|history)\s+with\s+{re.escape(cleaned)}\b", text or "", flags=re.IGNORECASE):
            continue
        if re.search(
            rf"\b(?:to|for|about|toward|towards|with)\s+{re.escape(cleaned)}\b|\b(?:inform|notify|tell|warn)\s+{re.escape(cleaned)}\b",
            text or "",
            flags=re.IGNORECASE,
        ):
            return True
    return False


def _has_non_possessive_name_match(text: str, name: str) -> bool:
    pattern = _name_pattern(name)
    if pattern is None:
        return False
    for match in pattern.finditer(text or ""):
        suffix = str(text or "")[match.end(): match.end() + 6].lstrip()
        if not _is_possessive_suffix(suffix):
            return True
    return False


def _name_pattern(name: str) -> re.Pattern[str] | None:
    cleaned = _clean_text(name)
    if not cleaned:
        return None
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", flags=re.IGNORECASE)


def _is_possessive_suffix(value: str) -> bool:
    return value.startswith("'s") or value.startswith("\u2019s") or value.startswith("\u00e2\u20ac\u2122s")


def _limit_unique_strings(values: list[str], limit: int) -> list[str]:
    return _unique_strings(values)[: max(0, int(limit))]


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    results: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                text = _relationshipish_dict_to_text(item)
            else:
                text = _clean_text(item)
            if text:
                results.append(text)
    return results


def _coerce_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return "; ".join(_coerce_string_list(value))
    if isinstance(value, dict):
        return _clean_text(
            value.get("summary")
            or value.get("description")
            or value.get("value")
            or value.get("label")
            or value.get("name")
            or json.dumps(value, ensure_ascii=False)
        )
    return _clean_text(value)


def _coerce_flat_string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    results: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _clean_text(raw_key)
        if not key:
            continue
        if isinstance(raw_value, dict):
            text = _coerce_string(raw_value)
        elif isinstance(raw_value, list):
            text = _coerce_string(raw_value)
        else:
            text = _clean_text(raw_value)
        if text:
            results[key] = text
    return results


def _relationshipish_dict_to_text(item: dict[str, Any]) -> str:
    target_name = _clean_text(item.get("target_name") or item.get("target") or "")
    target_id = _clean_text(item.get("target_id") or "")
    relation_type = _clean_text(item.get("type") or item.get("relationship_type") or item.get("relationship") or "")
    summary = _clean_text(item.get("summary") or item.get("description") or item.get("evidence") or "")
    if relation_type and target_name:
        return f"{relation_type} with {target_name}" + (f": {summary}" if summary else "")
    if relation_type and target_id:
        return f"{relation_type} with {target_id}" + (f": {summary}" if summary else "")
    if target_name and summary:
        return f"{target_name}: {summary}"
    if summary:
        return summary
    if target_name:
        return target_name
    if target_id:
        return target_id
    return _clean_text(item.get("label") or item.get("name") or item.get("value") or json.dumps(item, ensure_ascii=False))


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(cleaned)
    return results


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _content_tokens(value: str) -> set[str]:
    stopwords = {"the", "and", "for", "with", "from", "that", "this", "into", "onto", "are", "was", "were", "has", "have"}
    return {
        _stem_token(token)
        for token in re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold()).split()
        if len(token) > 2 and token not in stopwords
    }


def _stem_token(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _normalize_stable_attributes(payload: dict[str, str] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in dict(payload or {}).items():
        key = re.sub(r"[^a-z0-9_]+", "_", str(raw_key or "").strip().lower()).strip("_")
        value = _clean_text(raw_value)
        if not key or key not in STABLE_ATTRIBUTE_KEYS or not value:
            continue
        normalized[key] = value
    return normalized


def _normalize_fact_map(payload: dict[str, str] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in dict(payload or {}).items():
        key = re.sub(r"[^a-z0-9_]+", "_", str(raw_key or "").strip().lower()).strip("_")
        value = _clean_text(raw_value)
        if not key or not value:
            continue
        normalized[key] = value
    return normalized


def _sanitize_world_stable_facts(stable_facts: dict[str, str], *, evidence: dict[str, Any]) -> dict[str, str]:
    entity_type = _clean_text(str(evidence.get("entity_type") or "")).casefold()
    canonical_name = _clean_text(str(evidence.get("canonical_name") or "")).casefold()
    description = _clean_text(str(evidence.get("description") or "")).casefold()
    results: dict[str, str] = {}
    for key, value in dict(stable_facts or {}).items():
        normalized_key = _clean_text(key).casefold()
        normalized_value = _clean_text(value)
        folded_value = normalized_value.casefold()
        if normalized_key in {"type", "entity_type", "canonical_name", "name", "label", "alias", "aliases", "synonym", "synonyms"}:
            continue
        if normalized_key in {"description", "summary"} and folded_value == description:
            continue
        if folded_value in {entity_type, canonical_name, description}:
            continue
        if folded_value in {"true", "false", "yes", "no", "unknown", "not specified"}:
            continue
        if folded_value in {"object", "artifact", "location", "concept", "creature", "organization"}:
            continue
        if normalized_value and _world_fact_supported_by_evidence(normalized_value, evidence):
            results[key] = normalized_value
    return results


def _world_fact_supported_by_evidence(value: str, evidence: dict[str, Any]) -> bool:
    claim_tokens = _content_tokens(value)
    if not claim_tokens:
        return True
    evidence_text = " ".join(
        [
            str(evidence.get("canonical_name") or ""),
            str(evidence.get("description") or ""),
            str(evidence.get("overview") or ""),
            str(evidence.get("role_or_archetype") or ""),
            " ".join(str(value or "") for value in list(evidence.get("traits") or [])),
            " ".join(str(value or "") for value in list(evidence.get("motivations") or [])),
            " ".join(str(value or "") for value in list(evidence.get("loyalties") or [])),
            " ".join(str(value or "") for value in list(evidence.get("tensions") or [])),
            " ".join(str(value or "") for value in list(evidence.get("notable_relationships") or [])),
            *[
                f"{row.get('title') or ''} {row.get('summary') or ''}"
                for row in list(evidence.get("event_evidence") or []) + list(evidence.get("relationship_evidence") or [])
                if isinstance(row, dict)
            ],
            *[
                f"{row.get('summary') or ''} {row.get('excerpt') or ''}"
                for row in list(evidence.get("scene_evidence") or [])
                if isinstance(row, dict)
            ],
        ]
    )
    evidence_tokens = _content_tokens(evidence_text)
    return len(claim_tokens.intersection(evidence_tokens)) >= min(2, len(claim_tokens))


def _sanitize_stable_attributes(values: dict[str, str], *, evidence: dict[str, Any]) -> dict[str, str]:
    results: dict[str, str] = {}
    for key, value in dict(values or {}).items():
        if _world_fact_supported_by_evidence(value, evidence):
            results[key] = value
    return results


def _sanitize_world_conditions(values: list[str], *, evidence: dict[str, Any]) -> list[str]:
    generic_conditions = {"object", "artifact", "location", "concept", "creature", "organization", "unknown", "not specified"}
    return [
        value
        for value in values
        if _clean_text(value).casefold() not in generic_conditions and _world_fact_supported_by_evidence(value, evidence)
    ]


def _sanitize_notable_relationships(relationships: list[str], *, canonical_name: str, evidence: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for relationship in relationships:
        value = _clean_text(relationship)
        if not value:
            continue
        if _is_self_relationship_text(value, canonical_name=canonical_name, evidence=evidence):
            continue
        if _is_unsupported_possessive_object_action(value, canonical_name=canonical_name, evidence=evidence):
            continue
        if _is_non_relationship_action_or_reference(value):
            continue
        if not _has_relationship_claim_support(value, canonical_name=canonical_name):
            continue
        results.append(value)
    return results


def _has_relationship_claim_support(value: str, *, canonical_name: str) -> bool:
    if _text_mentions_name(value, canonical_name):
        return True
    if re.search(r"\bchar-[a-z0-9-]+\b", value, flags=re.IGNORECASE):
        return True
    return bool(
        re.search(
            r"\b(?:sibling|sister|brother|family|ally|friend|friendship|romantic|marriage|spouse|protective|antagonistic|companion|manipulation|conflict)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def _is_self_relationship_text(value: str, *, canonical_name: str, evidence: dict[str, Any]) -> bool:
    canonical_ref = str(evidence.get("character_id") or "") if isinstance(evidence, dict) else ""
    if not canonical_ref and canonical_name:
        canonical_ref = f"char-{re.sub(r'[^a-z0-9]+', '-', canonical_name.casefold()).strip('-')}"
    return bool(canonical_ref and re.search(rf"\b(?:self|ally|friendship|romantic|antagonistic) with {re.escape(canonical_ref)}\b", value, flags=re.IGNORECASE))


def _is_unsupported_possessive_object_action(value: str, *, canonical_name: str, evidence: dict[str, Any]) -> bool:
    if not canonical_name:
        return False
    possessive_match = re.search(r"\b([A-Z][A-Za-z0-9_-]+)(?:'s|\u2019s|\u00e2\u20ac\u2122s)\b", value)
    if not possessive_match:
        return False
    owner = possessive_match.group(1)
    if owner.casefold() == canonical_name.casefold():
        return False
    actor_pattern = (
        rf"\b{re.escape(canonical_name)}\b[^.?!]{{0,120}}"
        rf"\b(?:use|uses|used|using|seal|seals|sealed|sealing)\b[^.?!]{{0,120}}"
        rf"\b{re.escape(owner)}(?:'s|\u2019s|\u00e2\u20ac\u2122s)\b"
    )
    evidence_actor_pattern = (
        rf"\b{re.escape(canonical_name)}\b[^.?!]{{0,120}}"
        rf"\b(?:use|uses|used|using|seal|seals|sealed|sealing|send|sends|sent|write|writes|wrote)\b[^.?!]{{0,120}}"
        rf"\b{re.escape(owner)}(?:'s|\u2019s|\u00e2\u20ac\u2122s)\b"
    )
    claim_names_actor = re.search(actor_pattern, value, flags=re.IGNORECASE) or re.match(
        rf"^\s*(?:{re.escape(canonical_name)}\s+)?(?:use|uses|used|using)\b",
        value,
        flags=re.IGNORECASE,
    )
    if not claim_names_actor:
        return False
    evidence_rows = list(evidence.get("event_evidence") or []) + list(evidence.get("timeline_evidence") or [])
    for row in evidence_rows:
        for text in (str(row.get("title") or ""), str(row.get("summary") or "")):
            if re.search(actor_pattern, text, flags=re.IGNORECASE) or re.search(evidence_actor_pattern, text, flags=re.IGNORECASE):
                return False
    return True


def _is_non_relationship_action_or_reference(value: str) -> bool:
    folded = value.casefold()
    if re.search(r"\bartifact_usage\s+with\s+entity-[a-z0-9-]+\b", folded):
        return True
    if re.search(r"\b(?:associated with|uses?|serves?|served|requested by|referenced by)\b", folded):
        return True
    if re.search(r"\b(?:seal|wax|liquid|decanter|note|paper|object|artifact)\b", folded) and not re.search(
        r"\b(?:romantic|marriage|sibling|sister|brother|family|ally|friend|friendship|companion|protective|antagonistic|manipulation)\b",
        folded,
    ):
        return True
    return False


def _fallback_profile_overview(evidence: dict[str, Any]) -> str:
    event_evidence = list(evidence.get("event_evidence") or [])
    if event_evidence:
        first = dict(event_evidence[0] or {})
        text = _clean_text(first.get("summary") or first.get("title") or "")
        canonical_name = _clean_text(str(evidence.get("canonical_name") or ""))
        if _text_mentions_name(text, canonical_name):
            return text
    canonical_name = _clean_text(str(evidence.get("canonical_name") or ""))
    grounded_sentence = _first_scene_sentence_with_name(evidence, canonical_name)
    if grounded_sentence:
        return grounded_sentence
    if canonical_name:
        return f"{canonical_name} appears in the source, but current canon evidence has no primary grounded actions for this character."
    return _clean_text(str(evidence.get("first_seen_summary") or ""))


def _grounded_overview_or_fallback(value: str, *, canonical_name: str, evidence: dict[str, Any]) -> str:
    cleaned = _clean_text(value)
    if cleaned and _text_mentions_name(cleaned, canonical_name):
        return cleaned
    return _fallback_profile_overview(evidence)


def _fallback_stable_state_summary(evidence: dict[str, Any], stable_attributes: dict[str, str]) -> str:
    if stable_attributes:
        return ", ".join(f"{key}: {value}" for key, value in stable_attributes.items())
    canonical_name = _clean_text(str(evidence.get("canonical_name") or ""))
    if canonical_name and not _profile_has_primary_support(evidence):
        return f"No durable character-state facts are grounded for {canonical_name}."
    return _clean_text(str(evidence.get("role_or_archetype") or evidence.get("overview") or ""))


def _profile_has_primary_support(evidence: dict[str, Any]) -> bool:
    if list(evidence.get("event_evidence") or []):
        return True
    relationship_rows = list(evidence.get("relationship_evidence") or [])
    contextual_relationship_types = {"reference", "curiosity", "location_association"}
    return any(str(row.get("relationship_type") or row.get("type") or "") not in contextual_relationship_types for row in relationship_rows)


def _grounded_profile_summary(
    value: str,
    *,
    canonical_name: str,
    evidence: dict[str, Any],
    allow_relationship_partner: bool = False,
) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    if _text_mentions_name(cleaned, canonical_name):
        return cleaned
    if allow_relationship_partner and _summary_mentions_supported_partner(cleaned, evidence):
        return cleaned
    return ""


def _text_mentions_name(text: str, canonical_name: str) -> bool:
    for variant in _name_variants(canonical_name):
        pattern = _name_pattern(variant)
        if pattern and pattern.search(text or ""):
            return True
    return False


def _name_variants(canonical_name: str) -> list[str]:
    cleaned = _clean_text(canonical_name)
    if not cleaned:
        return []
    variants = [cleaned]
    without_title = re.sub(r"^(?:prince|princess|king|queen|lord|lady|sir|madam)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    if without_title and without_title.casefold() != cleaned.casefold():
        variants.append(without_title)
    return _unique_strings(variants)


def _summary_mentions_supported_partner(text: str, evidence: dict[str, Any]) -> bool:
    relationship_refs: set[str] = set()
    character_id = str(evidence.get("character_id") or "")
    for row in list(evidence.get("relationship_evidence") or []):
        source = str(row.get("source_ref") or "")
        target = str(row.get("target_ref") or "")
        if source == character_id and target.startswith("char-"):
            relationship_refs.add(_character_ref_display_name(target))
        if target == character_id and source.startswith("char-"):
            relationship_refs.add(_character_ref_display_name(source))
    return any(_text_mentions_name(text, name) for name in relationship_refs)


def _character_ref_display_name(ref: str) -> str:
    value = str(ref or "")
    if value.startswith("char-"):
        value = value[5:]
    return value.replace("-", " ").strip()


def _first_scene_sentence_with_name(evidence: dict[str, Any], canonical_name: str) -> str:
    if not canonical_name:
        return ""
    pattern = _name_pattern(canonical_name)
    if pattern is None:
        return ""
    for row in list(evidence.get("scene_evidence") or []):
        text = _clean_text(str(row.get("excerpt") or row.get("summary") or ""))
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if pattern.search(sentence):
                return _clean_text(sentence)
    return ""


def _fallback_world_state_summary(evidence: dict[str, Any]) -> str:
    event_rows = list(evidence.get("event_evidence") or [])
    if event_rows:
        first = dict(event_rows[-1] or {})
        return _clean_text(first.get("summary") or first.get("title") or "")
    return _clean_text(str(evidence.get("description") or ""))


def _slug(value: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:8]
