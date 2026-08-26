"""LangGraph-native generation planning runtime."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

from packages.agent_runtime import SqlCheckpointSaver
from packages.generation_planning.contracts import (
    CanonGroundingArtifact,
    ChapterOutlineItem,
    GenerationBlueprintArtifact,
    GenerationPlanningResult,
    ScenePlanItem,
    StoryIntentArtifact,
)
from packages.generation_planning.store import GenerationPlanningStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient

MAX_GROUNDING_EVENTS = 12
MAX_GROUNDING_CHARACTERS = 10
MAX_GROUNDING_ENTITIES = 10
MAX_GROUNDING_RELATIONSHIPS = 8


class GenerationPlanningState(TypedDict, total=False):
    series_id: str
    premise: str
    target_audience: str
    tone: str
    continuation_mode: str
    desired_chapter_count: int
    books: list[dict[str, Any]]
    identity_bundle: dict[str, Any]
    events: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    character_profiles: list[dict[str, Any]]
    stable_character_states: list[dict[str, Any]]
    world_states: list[dict[str, Any]]
    intent: dict[str, Any]
    grounding: dict[str, Any]
    blueprint: dict[str, Any]
    run_metadata: dict[str, Any]


class BlueprintSynthesisPayload(BaseModel):
    title: str = ""
    continuation_plan: str = ""
    divergence_plan: str = ""
    chapter_outline: list[ChapterOutlineItem] = Field(default_factory=list)
    scene_plan: list[ScenePlanItem] = Field(default_factory=list)
    visual_requirements: list[str] = Field(default_factory=list)
    audio_requirements: list[str] = Field(default_factory=list)
    canon_refs: list[str] = Field(default_factory=list)
    character_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)

    @field_validator("visual_requirements", "audio_requirements", "canon_refs", "character_refs", "entity_refs", mode="before")
    @classmethod
    def _coerce_string_lists(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)


class StoryIntentAgent:
    def __init__(self, *, store: GenerationPlanningStore) -> None:
        self.store = store

    def run(self, state: GenerationPlanningState) -> dict[str, Any]:
        started = time.perf_counter()
        premise = _clean_text(state.get("premise") or "Create a canon-grounded continuation.")
        constraints = [
            "Use only persisted canon extraction and character/world modeling outputs as source-of-truth.",
            "Do not contradict established character states, relationships, timeline order, or world rules.",
            "Produce reusable planning artifacts for later prose, image, and audio generation agents.",
        ]
        intent = StoryIntentArtifact(
            intent_id=_stable_id(
                "generation-intent", state["series_id"], premise,
                _clean_text(state.get("target_audience") or ""),
                _clean_text(state.get("tone") or ""),
                _clean_text(state.get("continuation_mode") or "canon_continuation"),
                int(state.get("desired_chapter_count") or 3),
            ),
            series_id=state["series_id"],
            premise=premise,
            target_audience=_clean_text(state.get("target_audience") or ""),
            tone=_clean_text(state.get("tone") or ""),
            continuation_mode=_clean_text(state.get("continuation_mode") or "canon_continuation"),
            desired_chapter_count=int(state.get("desired_chapter_count") or 3),
            constraints=constraints,
            metadata={"agent": "StoryIntentAgent", "elapsed_seconds": round(time.perf_counter() - started, 4)},
        )
        persisted = self.store.upsert_intent(series_id=state["series_id"], intent=intent)
        return {"intent": persisted.model_dump()}


class CanonGroundingAgent:
    def __init__(self, *, store: GenerationPlanningStore) -> None:
        self.store = store

    def run(self, state: GenerationPlanningState) -> dict[str, Any]:
        started = time.perf_counter()
        events = list(state.get("events") or [])
        timeline = list(state.get("timeline") or [])
        profiles = list(state.get("character_profiles") or [])
        states = list(state.get("stable_character_states") or [])
        entities = list(state.get("entities") or [])
        world_states = list(state.get("world_states") or [])
        relationships = list(state.get("relationships") or [])

        selected_timeline = sorted(timeline, key=lambda item: int(item.get("sequence_index") or 0))[-MAX_GROUNDING_EVENTS:]
        selected_events = _events_for_timeline(events, selected_timeline)
        selected_profiles = sorted(profiles, key=lambda item: len(item.get("important_event_ids") or []), reverse=True)[:MAX_GROUNDING_CHARACTERS]
        if not selected_profiles:
            identity = dict(state.get("identity_bundle") or {})
            selected_profiles = [
                {
                    "character_id": item.get("character_id"),
                    "canonical_name": item.get("display_name"),
                    "overview": "",
                    "latest_state_summary": "",
                    "important_event_ids": [],
                }
                for item in list(identity.get("characters") or [])[:MAX_GROUNDING_CHARACTERS]
            ]
        selected_world = sorted(world_states, key=lambda item: len(item.get("supporting_event_ids") or []), reverse=True)[:MAX_GROUNDING_ENTITIES]
        selected_entities = _entities_for_world_states(entities, selected_world) or entities[:MAX_GROUNDING_ENTITIES]

        event_ids = _dedupe([str(item.get("event_id") or "") for item in selected_events])
        timeline_ids = _dedupe([str(item.get("timeline_id") or "") for item in selected_timeline])
        character_ids = _dedupe([str(item.get("character_id") or "") for item in selected_profiles])
        entity_ids = _dedupe([str(item.get("entity_id") or "") for item in selected_entities])

        grounding = CanonGroundingArtifact(
            grounding_id=_stable_id("generation-grounding", state["series_id"], *event_ids, *character_ids, *entity_ids),
            series_id=state["series_id"],
            canon_event_ids=event_ids,
            timeline_ids=timeline_ids,
            required_character_ids=character_ids,
            required_entity_ids=entity_ids,
            timeline_constraints=[
                f"{item.get('timeline_id')}: {item.get('title') or item.get('summary')}"
                for item in selected_timeline
                if str(item.get("timeline_id") or "").strip()
            ],
            character_constraints=[
                _join_constraint(
                    item.get("character_id"),
                    item.get("canonical_name"),
                    item.get("overview"),
                    item.get("latest_state_summary"),
                    _state_summary(item.get("character_id"), states),
                )
                for item in selected_profiles
                if str(item.get("character_id") or "").strip()
            ],
            world_constraints=[
                _join_constraint(
                    item.get("entity_id"),
                    item.get("canonical_name"),
                    item.get("description"),
                    item.get("current_state_summary"),
                    item.get("story_relevance"),
                )
                for item in selected_world
                if str(item.get("entity_id") or "").strip()
            ],
            relationship_constraints=[
                f"{item.get('relationship_id')}: {item.get('source_ref')} {item.get('relationship_type')} {item.get('target_ref')}: {item.get('description')}"
                for item in relationships[:MAX_GROUNDING_RELATIONSHIPS]
                if str(item.get("relationship_id") or "").strip()
            ],
            metadata={
                "agent": "CanonGroundingAgent",
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "source_counts": {
                    "events": len(events),
                    "timeline": len(timeline),
                    "character_profiles": len(profiles),
                    "world_states": len(world_states),
                    "relationships": len(relationships),
                },
            },
        )
        persisted = self.store.upsert_grounding(series_id=state["series_id"], grounding=grounding)
        return {"grounding": persisted.model_dump()}


class BlueprintSynthesisAgent:
    def __init__(self, *, store: GenerationPlanningStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(self, state: GenerationPlanningState) -> dict[str, Any]:
        started = time.perf_counter()
        intent = StoryIntentArtifact.model_validate(state["intent"])
        grounding = CanonGroundingArtifact.model_validate(state["grounding"])
        valid_canon_refs = _valid_canon_refs(state)
        valid_character_refs = _valid_character_refs(state)
        valid_entity_refs = _valid_entity_refs(state)
        payload, provider_metadata = self._synthesize_with_fallback(
            intent=intent,
            grounding=grounding,
            valid_canon_refs=valid_canon_refs,
            valid_character_refs=valid_character_refs,
            valid_entity_refs=valid_entity_refs,
        )
        blueprint = _blueprint_from_payload(
            series_id=state["series_id"],
            intent=intent,
            grounding=grounding,
            payload=payload,
            provider_metadata=provider_metadata,
            elapsed_seconds=round(time.perf_counter() - started, 4),
            valid_canon_refs=valid_canon_refs,
            valid_character_refs=valid_character_refs,
            valid_entity_refs=valid_entity_refs,
        )
        persisted = self.store.upsert_blueprint(series_id=state["series_id"], blueprint=blueprint)
        run_metadata = dict(state.get("run_metadata") or {})
        run_metadata["stage_order"] = ["story_intent", "canon_grounding", "blueprint_synthesis"]
        run_metadata["stage_metrics"] = {
            **dict(run_metadata.get("stage_metrics") or {}),
            "blueprint_synthesis": {
                "elapsed_seconds": blueprint.metadata.get("elapsed_seconds"),
                "reasoning_provider": provider_metadata.get("provider"),
                "reasoning_model": provider_metadata.get("resolved_model"),
                "reasoning_status": provider_metadata.get("status"),
                "fallback_used": bool(provider_metadata.get("fallback_used") or provider_metadata.get("deterministic_fallback")),
            },
        }
        return {"blueprint": persisted.model_dump(), "run_metadata": run_metadata}

    def _synthesize_with_fallback(
        self,
        *,
        intent: StoryIntentArtifact,
        grounding: CanonGroundingArtifact,
        valid_canon_refs: set[str],
        valid_character_refs: set[str],
        valid_entity_refs: set[str],
    ) -> tuple[BlueprintSynthesisPayload, dict[str, Any]]:
        prompt = _build_blueprint_prompt(intent=intent, grounding=grounding)
        response = self.reasoning_runtime.generate_json(
            prompt,
            strict=True,
            max_tokens=4200,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generation_blueprint",
                    "schema": BlueprintSynthesisPayload.model_json_schema(),
                    "strict": True,
                },
            },
        )
        metadata = dict(self.reasoning_runtime.last_request_metadata() or {})
        if isinstance(response, dict) and not response.get("error"):
            try:
                return BlueprintSynthesisPayload.model_validate(response), metadata
            except Exception as exc:
                metadata["status"] = "error"
                metadata["error_code"] = f"blueprint_validation_failed:{type(exc).__name__}"
        else:
            metadata["status"] = "error"
            metadata["error_code"] = str((response or {}).get("error") or "empty_blueprint_response")
        metadata["deterministic_fallback"] = True
        return _fallback_blueprint_payload(
            intent=intent,
            grounding=grounding,
            valid_canon_refs=valid_canon_refs,
            valid_character_refs=valid_character_refs,
            valid_entity_refs=valid_entity_refs,
        ), metadata


class GenerationPlanningRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        reasoning_runtime: ReasoningRuntimeClient,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
    ) -> None:
        self.persistence = persistence
        self.reasoning_runtime = reasoning_runtime
        self.store = GenerationPlanningStore(persistence)
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_generation_planning_graph(
            store=self.store,
            reasoning_runtime=reasoning_runtime,
            checkpointer=self.checkpointer,
        )

    def invoke(
        self,
        *,
        series_id: str,
        thread_id: str = "generation-planning",
        premise: str = "",
        target_audience: str = "",
        tone: str = "",
        continuation_mode: str = "canon_continuation",
        desired_chapter_count: int = 3,
    ) -> GenerationPlanningResult:
        context = self.store.load_series_context(series_id=series_id)
        if not list(context.get("events") or []) or not list(context.get("timeline") or []):
            raise ValueError(f"GenerationPlanningRuntime requires persisted canon extraction outputs for series '{series_id}'.")
        if not list(context.get("character_profiles") or []) and not list(context.get("world_states") or []):
            raise ValueError(f"GenerationPlanningRuntime requires persisted character/world modeling outputs for series '{series_id}'.")
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "premise": premise,
                "target_audience": target_audience,
                "tone": tone,
                "continuation_mode": continuation_mode,
                "desired_chapter_count": desired_chapter_count,
                "books": [item.model_dump() for item in list(context.get("books") or [])],
                "identity_bundle": context["identity_bundle"].model_dump() if context.get("identity_bundle") else {},
                "events": [item.model_dump() for item in list(context.get("events") or [])],
                "entities": [item.model_dump() for item in list(context.get("entities") or [])],
                "relationships": [item.model_dump() for item in list(context.get("relationships") or [])],
                "timeline": [item.model_dump() for item in list(context.get("timeline") or [])],
                "character_profiles": [item.model_dump() for item in list(context.get("character_profiles") or [])],
                "stable_character_states": [item.model_dump() for item in list(context.get("stable_character_states") or [])],
                "world_states": [item.model_dump() for item in list(context.get("world_states") or [])],
                "run_metadata": {},
            },
            config={"configurable": {"thread_id": str(thread_id or "generation-planning")}},
        )
        return GenerationPlanningResult(
            series_id=series_id,
            intent=StoryIntentArtifact.model_validate(state["intent"]),
            grounding=CanonGroundingArtifact.model_validate(state["grounding"]),
            blueprint=GenerationBlueprintArtifact.model_validate(state["blueprint"]),
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def build_generation_planning_graph(
    *,
    store: GenerationPlanningStore,
    reasoning_runtime: ReasoningRuntimeClient,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(GenerationPlanningState)
    graph.add_node("story_intent", StoryIntentAgent(store=store).run)
    graph.add_node("canon_grounding", CanonGroundingAgent(store=store).run)
    graph.add_node("blueprint_synthesis", BlueprintSynthesisAgent(store=store, reasoning_runtime=reasoning_runtime).run)
    graph.add_edge(START, "story_intent")
    graph.add_edge("story_intent", "canon_grounding")
    graph.add_edge("canon_grounding", "blueprint_synthesis")
    graph.add_edge("blueprint_synthesis", END)
    return graph.compile(checkpointer=checkpointer)


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
    raise ValueError("GenerationPlanningRuntime requires a durable checkpointer or an initialized persistence engine.")


def _build_blueprint_prompt(*, intent: StoryIntentArtifact, grounding: CanonGroundingArtifact) -> str:
    schema = {
        "title": "string",
        "continuation_plan": "string",
        "divergence_plan": "string",
        "chapter_outline": [
            {"chapter_index": 1, "title": "string", "goal": "string", "canon_refs": [], "character_refs": [], "entity_refs": []}
        ],
        "scene_plan": [
            {
                "scene_id": "planned-scene-1-1",
                "chapter_index": 1,
                "scene_index": 1,
                "summary": "string",
                "purpose": "string",
                "canon_refs": [],
                "character_refs": [],
                "entity_refs": [],
                "visual_requirements": [],
                "audio_requirements": [],
            }
        ],
        "visual_requirements": ["string"],
        "audio_requirements": ["string"],
        "canon_refs": [],
        "character_refs": [],
        "entity_refs": [],
    }
    context = {
        "intent": intent.model_dump(),
        "allowed_canon_refs": grounding.canon_event_ids + grounding.timeline_ids,
        "allowed_character_refs": grounding.required_character_ids,
        "allowed_entity_refs": grounding.required_entity_ids,
        "timeline_constraints": grounding.timeline_constraints,
        "character_constraints": grounding.character_constraints,
        "world_constraints": grounding.world_constraints,
        "relationship_constraints": grounding.relationship_constraints,
    }
    return (
        "You are a reusable generation-planning agent. Build a canon-grounded blueprint for later prose, image, "
        "and audiobook agents. Use only the provided constraints. Do not invent unsupported facts. Every chapter "
        "and scene must cite allowed refs only. Include visual and audio requirements for every scene. "
        "Treat unnamed roles introduced by the requested premise as distinct new story participants. Never map such "
        "a role onto an allowed canon character unless the planning context explicitly states that identity. Preserve "
        "the same role identity across every scene where it appears. "
        "Create exactly the requested chapter count and 2 scenes per chapter. Keep each text field under 35 words. "
        f"Return exactly this JSON shape: {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"Planning context:\n{json.dumps(context, ensure_ascii=False)}"
    )


def _blueprint_from_payload(
    *,
    series_id: str,
    intent: StoryIntentArtifact,
    grounding: CanonGroundingArtifact,
    payload: BlueprintSynthesisPayload,
    provider_metadata: dict[str, Any],
    elapsed_seconds: float,
    valid_canon_refs: set[str],
    valid_character_refs: set[str],
    valid_entity_refs: set[str],
) -> GenerationBlueprintArtifact:
    chapters = [
        ChapterOutlineItem(
            chapter_index=max(1, int(item.chapter_index or 1)),
            title=_clean_text(item.title) or f"Chapter {item.chapter_index}",
            goal=_clean_text(item.goal),
            canon_refs=_sanitize_refs(item.canon_refs, valid_canon_refs),
            character_refs=_sanitize_refs(item.character_refs, valid_character_refs),
            entity_refs=_sanitize_refs(item.entity_refs, valid_entity_refs),
        )
        for item in list(payload.chapter_outline or [])
    ]
    scenes = [
        ScenePlanItem(
            scene_id=_clean_ref(item.scene_id) or f"planned-scene-{item.chapter_index}-{item.scene_index}",
            chapter_index=max(1, int(item.chapter_index or 1)),
            scene_index=max(1, int(item.scene_index or 1)),
            summary=_clean_text(item.summary),
            purpose=_clean_text(item.purpose),
            canon_refs=_sanitize_refs(item.canon_refs, valid_canon_refs),
            character_refs=_sanitize_refs(item.character_refs, valid_character_refs),
            entity_refs=_sanitize_refs(item.entity_refs, valid_entity_refs),
            visual_requirements=_coerce_string_list(item.visual_requirements),
            audio_requirements=_coerce_string_list(item.audio_requirements),
        )
        for item in list(payload.scene_plan or [])
    ]
    payload = BlueprintSynthesisPayload(
        title=payload.title,
        continuation_plan=payload.continuation_plan,
        divergence_plan=payload.divergence_plan,
        chapter_outline=chapters,
        scene_plan=scenes,
        visual_requirements=_coerce_string_list(payload.visual_requirements),
        audio_requirements=_coerce_string_list(payload.audio_requirements),
        canon_refs=_sanitize_refs(payload.canon_refs, valid_canon_refs),
        character_refs=_sanitize_refs(payload.character_refs, valid_character_refs),
        entity_refs=_sanitize_refs(payload.entity_refs, valid_entity_refs),
    )
    payload = _repair_blueprint_completeness(
        intent=intent,
        grounding=grounding,
        payload=payload,
        valid_canon_refs=valid_canon_refs,
        valid_character_refs=valid_character_refs,
        valid_entity_refs=valid_entity_refs,
    )
    return GenerationBlueprintArtifact(
        blueprint_id=_stable_id(
            "generation-blueprint", series_id, intent.intent_id, grounding.grounding_id,
            json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
        series_id=series_id,
        intent_id=intent.intent_id,
        grounding_id=grounding.grounding_id,
        title=_clean_text(payload.title) or "Canon-Grounded Continuation Blueprint",
        premise=intent.premise,
        continuation_plan=_clean_text(payload.continuation_plan),
        divergence_plan=_clean_text(payload.divergence_plan),
        chapter_outline=payload.chapter_outline,
        scene_plan=payload.scene_plan,
        visual_requirements=payload.visual_requirements,
        audio_requirements=payload.audio_requirements,
        canon_refs=payload.canon_refs or _first_refs(valid_canon_refs, 8),
        character_refs=payload.character_refs or _first_refs(valid_character_refs, 8),
        entity_refs=payload.entity_refs or _first_refs(valid_entity_refs, 8),
        metadata={
            "agent": "BlueprintSynthesisAgent",
            "elapsed_seconds": elapsed_seconds,
            "reasoning_provider": provider_metadata.get("provider"),
            "reasoning_model": provider_metadata.get("resolved_model"),
            "reasoning_status": provider_metadata.get("status"),
            "request_metadata": provider_metadata,
        },
    )


def _repair_blueprint_completeness(
    *,
    intent: StoryIntentArtifact,
    grounding: CanonGroundingArtifact,
    payload: BlueprintSynthesisPayload,
    valid_canon_refs: set[str],
    valid_character_refs: set[str],
    valid_entity_refs: set[str],
) -> BlueprintSynthesisPayload:
    chapter_count = max(1, int(intent.desired_chapter_count or 1))
    chapters_by_index: dict[int, ChapterOutlineItem] = {}
    for chapter in list(payload.chapter_outline or []):
        if 1 <= chapter.chapter_index <= chapter_count and chapter.chapter_index not in chapters_by_index:
            chapters_by_index[chapter.chapter_index] = chapter
    base_canon = _priority_refs(grounding.canon_event_ids + grounding.timeline_ids, valid_canon_refs, 6)
    base_characters = _priority_refs(grounding.required_character_ids, valid_character_refs, 6)
    base_entities = _priority_refs(grounding.required_entity_ids, valid_entity_refs, 4)
    for index in range(1, chapter_count + 1):
        if index in chapters_by_index:
            continue
        chapters_by_index[index] = (
            ChapterOutlineItem(
                chapter_index=index,
                title=f"Chapter {index}",
                goal=f"Advance the premise while preserving canon: {intent.premise}",
                canon_refs=base_canon[:3],
                character_refs=base_characters[:3],
                entity_refs=base_entities[:2],
            )
        )
    chapters = [chapters_by_index[index] for index in range(1, chapter_count + 1)]
    repaired_scene_by_key: dict[tuple[int, int], ScenePlanItem] = {}
    for scene in list(payload.scene_plan or []):
        key = (scene.chapter_index, scene.scene_index)
        if 1 <= scene.chapter_index <= chapter_count and scene.scene_index in (1, 2) and key not in repaired_scene_by_key:
            repaired_scene_by_key[key] = scene
    for chapter in chapters:
        for scene_index in (1, 2):
            key = (chapter.chapter_index, scene_index)
            if key in repaired_scene_by_key:
                continue
            repaired_scene_by_key[key] = (
                ScenePlanItem(
                    scene_id=f"planned-scene-{chapter.chapter_index}-{scene_index}",
                    chapter_index=chapter.chapter_index,
                    scene_index=scene_index,
                    summary=f"Scene {scene_index} develops {chapter.goal}",
                    purpose="Translate grounded canon constraints into story movement without introducing unsupported contradictions.",
                    canon_refs=chapter.canon_refs or base_canon[:3],
                    character_refs=chapter.character_refs or base_characters[:3],
                    entity_refs=chapter.entity_refs or base_entities[:2],
                    visual_requirements=["Identify characters, setting, mood, and key non-character entities for image generation."],
                    audio_requirements=["Track speaker/narrator tone, emotional beat, and pacing for audiobook generation."],
                )
            )
    repaired_scenes = list(repaired_scene_by_key.values())
    for scene in repaired_scenes:
        if not scene.visual_requirements:
            scene.visual_requirements = ["Identify characters, setting, mood, and key non-character entities for image generation."]
        if not scene.audio_requirements:
            scene.audio_requirements = ["Track speaker/narrator tone, emotional beat, and pacing for audiobook generation."]
        if not scene.canon_refs:
            scene.canon_refs = base_canon[:3]
        if not scene.character_refs:
            scene.character_refs = base_characters[:3]
    payload.chapter_outline = sorted(chapters, key=lambda item: item.chapter_index)
    payload.scene_plan = sorted(repaired_scenes, key=lambda item: (item.chapter_index, item.scene_index))
    payload.visual_requirements = payload.visual_requirements or ["Produce scene-level image briefs from each scene plan."]
    payload.audio_requirements = payload.audio_requirements or ["Produce scene-level narration and dialogue cues from each scene plan."]
    return payload


def _fallback_blueprint_payload(
    *,
    intent: StoryIntentArtifact,
    grounding: CanonGroundingArtifact,
    valid_canon_refs: set[str],
    valid_character_refs: set[str],
    valid_entity_refs: set[str],
) -> BlueprintSynthesisPayload:
    base_canon = _priority_refs(grounding.canon_event_ids + grounding.timeline_ids, valid_canon_refs, 8)
    base_characters = _priority_refs(grounding.required_character_ids, valid_character_refs, 8)
    base_entities = _priority_refs(grounding.required_entity_ids, valid_entity_refs, 6)
    chapters = []
    scenes = []
    for chapter_index in range(1, max(1, int(intent.desired_chapter_count or 1)) + 1):
        chapters.append(
            ChapterOutlineItem(
                chapter_index=chapter_index,
                title=f"Grounded Continuation {chapter_index}",
                goal=f"Develop '{intent.premise}' using established canon constraints.",
                canon_refs=base_canon[:4],
                character_refs=base_characters[:4],
                entity_refs=base_entities[:3],
            )
        )
        for scene_index in (1, 2):
            scenes.append(
                ScenePlanItem(
                    scene_id=f"planned-scene-{chapter_index}-{scene_index}",
                    chapter_index=chapter_index,
                    scene_index=scene_index,
                    summary=f"A canon-grounded scene for chapter {chapter_index}, beat {scene_index}.",
                    purpose="Maintain continuity while moving the requested premise forward.",
                    canon_refs=base_canon[:4],
                    character_refs=base_characters[:4],
                    entity_refs=base_entities[:3],
                    visual_requirements=["Render the setting, involved characters, and relevant non-character entities."],
                    audio_requirements=["Preserve narrator voice, emotional tone, and dialogue pacing."],
                )
            )
    return BlueprintSynthesisPayload(
        title="Canon-Grounded Continuation Blueprint",
        continuation_plan="Continue from persisted canon and CWM constraints without unsupported contradictions.",
        divergence_plan="No divergence from canon is permitted unless explicitly marked by a later generation agent.",
        chapter_outline=chapters,
        scene_plan=scenes,
        visual_requirements=["Generate character, location, creature, or object briefs from scene requirements."],
        audio_requirements=["Generate narration and dialogue cues from scene requirements."],
        canon_refs=base_canon,
        character_refs=base_characters,
        entity_refs=base_entities,
    )


def _valid_canon_refs(state: GenerationPlanningState) -> set[str]:
    return {
        *{str(item.get("event_id") or "").strip() for item in list(state.get("events") or [])},
        *{str(item.get("timeline_id") or "").strip() for item in list(state.get("timeline") or [])},
    } - {""}


def _valid_character_refs(state: GenerationPlanningState) -> set[str]:
    refs = {str(item.get("character_id") or "").strip() for item in list(state.get("character_profiles") or [])}
    identity = dict(state.get("identity_bundle") or {})
    refs.update(str(item.get("character_id") or "").strip() for item in list(identity.get("characters") or []))
    return refs - {""}


def _valid_entity_refs(state: GenerationPlanningState) -> set[str]:
    refs = {str(item.get("entity_id") or "").strip() for item in list(state.get("entities") or [])}
    refs.update(str(item.get("entity_id") or "").strip() for item in list(state.get("world_states") or []))
    return refs - {""}


def _events_for_timeline(events: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_map = {str(item.get("event_id") or ""): item for item in events}
    results = [event_map.get(str(item.get("event_id") or "")) for item in timeline]
    return [item for item in results if item]


def _entities_for_world_states(entities: list[dict[str, Any]], world_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entity_map = {str(item.get("entity_id") or ""): item for item in entities}
    return [entity_map.get(str(item.get("entity_id") or "")) or item for item in world_states]


def _state_summary(character_id: Any, states: list[dict[str, Any]]) -> str:
    target = str(character_id or "").strip()
    for item in states:
        if str(item.get("character_id") or "").strip() == target:
            return str(item.get("summary") or "")
    return ""


def _join_constraint(*parts: Any) -> str:
    return " | ".join(_clean_text(part) for part in parts if _clean_text(part))


def _sanitize_refs(values: list[str], allowed: set[str]) -> list[str]:
    return [value for value in _dedupe(values) if value in allowed]


def _first_refs(values: set[str], limit: int) -> list[str]:
    return sorted(values)[: max(0, int(limit))]


def _priority_refs(values: list[str], allowed: set[str], limit: int) -> list[str]:
    prioritized = [value for value in _dedupe(values) if value in allowed]
    if len(prioritized) >= limit:
        return prioritized[:limit]
    remaining = [value for value in sorted(allowed) if value not in set(prioritized)]
    return (prioritized + remaining)[: max(0, int(limit))]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = _clean_ref(value)
        if cleaned and cleaned not in seen:
            results.append(cleaned)
            seen.add(cleaned)
    return results


def _clean_ref(value: Any) -> str:
    return re.sub(r"\s+", "-", str(value or "").strip())


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, tuple):
        return [_clean_text(item) for item in value if _clean_text(item)]
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("::".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"
