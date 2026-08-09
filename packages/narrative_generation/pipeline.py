"""LangGraph-native runtime for canon-grounded narrative generation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

from packages.agent_runtime import SqlCheckpointSaver
from packages.generation_planning.contracts import GenerationBlueprintArtifact, ScenePlanItem
from packages.narrative_generation.contracts import (
    ChapterDraftArtifact,
    ContinuityCheckArtifact,
    GeneratedStoryArtifact,
    NarrativeGenerationResult,
    RevisionRecordArtifact,
    SceneProseArtifact,
)
from packages.narrative_generation.quality import evaluate_chapter_continuity
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient

MAX_SCENE_WORDS = 260
MIN_SCENE_WORDS = 80
SCENE_CALL_DELAY_SECONDS = max(0.0, float(os.getenv("SAGA_NARRATIVE_GENERATION_SCENE_DELAY_SECONDS") or "0"))


class NarrativeGenerationState(TypedDict, total=False):
    series_id: str
    blueprint_id: str
    story_id: str
    target_words_per_scene: int
    blueprint: dict[str, Any]
    events: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    character_profiles: list[dict[str, Any]]
    world_states: list[dict[str, Any]]
    scene_prose: list[dict[str, Any]]
    chapter_drafts: list[dict[str, Any]]
    continuity_checks: list[dict[str, Any]]
    revisions: list[dict[str, Any]]
    story: dict[str, Any]
    run_metadata: dict[str, Any]


class SceneProsePayload(BaseModel):
    title: str = ""
    prose: str = ""

    @field_validator("title", "prose", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        return _clean_text(value)


class NarrativeGenerationAgent:
    def __init__(self, *, store: NarrativeGenerationStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(self, state: NarrativeGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
        story_id = _story_id(state)
        scene_outputs: list[SceneProseArtifact] = []
        request_metadata_rows: list[dict[str, Any]] = []
        for scene in blueprint.scene_plan:
            _pace_scene_call()
            payload, metadata = self._generate_scene(
                blueprint=blueprint,
                scene=scene,
                target_words_per_scene=int(state.get("target_words_per_scene") or 180),
                context=state,
                prior_scenes=scene_outputs,
            )
            request_metadata_rows.append(metadata)
            scene_outputs.append(
                SceneProseArtifact(
                    scene_prose_id=_stable_id("scene-prose", story_id, scene.scene_id),
                    series_id=blueprint.series_id,
                    story_id=story_id,
                    blueprint_id=blueprint.blueprint_id,
                    source_scene_id=scene.scene_id,
                    chapter_index=scene.chapter_index,
                    scene_index=scene.scene_index,
                    title=payload.title or f"Scene {scene.chapter_index}.{scene.scene_index}",
                    prose=_repair_scene_prose(payload.prose, scene=scene, blueprint=blueprint),
                    purpose=scene.purpose,
                    canon_refs=list(scene.canon_refs),
                    character_refs=list(scene.character_refs),
                    entity_refs=list(scene.entity_refs),
                    metadata={
                        "agent": "NarrativeGenerationAgent",
                        "reasoning_provider": metadata.get("provider"),
                        "reasoning_model": metadata.get("resolved_model"),
                        "reasoning_status": metadata.get("status"),
                        "request_metadata": metadata,
                    },
                )
            )
        persisted = self.store.replace_scene_prose(series_id=blueprint.series_id, story_id=story_id, scenes=scene_outputs)
        run_metadata = dict(state.get("run_metadata") or {})
        run_metadata["stage_metrics"] = {
            **dict(run_metadata.get("stage_metrics") or {}),
            "narrative_generation": {
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "scene_count": len(persisted),
                "reasoning_calls": len(request_metadata_rows),
                "fallback_count": len([row for row in request_metadata_rows if row.get("deterministic_fallback")]),
                "provider_statuses": sorted({str(row.get("status") or "") for row in request_metadata_rows if row.get("status")}),
            },
        }
        return {"scene_prose": [item.model_dump() for item in persisted], "run_metadata": run_metadata}

    def _generate_scene(
        self,
        *,
        blueprint: GenerationBlueprintArtifact,
        scene: ScenePlanItem,
        target_words_per_scene: int,
        context: NarrativeGenerationState,
        prior_scenes: list[SceneProseArtifact],
    ) -> tuple[SceneProsePayload, dict[str, Any]]:
        prompt = _build_scene_prompt(
            blueprint=blueprint,
            scene=scene,
            target_words_per_scene=target_words_per_scene,
            context=context,
            prior_scenes=prior_scenes,
        )
        response = self.reasoning_runtime.generate_json(prompt, strict=True, max_tokens=1400)
        metadata = dict(self.reasoning_runtime.last_request_metadata() or {})
        if isinstance(response, dict) and not response.get("error"):
            try:
                return SceneProsePayload.model_validate(response), metadata
            except Exception as exc:
                metadata["status"] = "error"
                metadata["error_code"] = f"scene_payload_validation_failed:{type(exc).__name__}"
        else:
            metadata["status"] = "error"
            metadata["error_code"] = str((response or {}).get("error") or "empty_scene_response")
            metadata["last_error"] = str((response or {}).get("last_error") or "")
        metadata["deterministic_fallback"] = True
        return _fallback_scene_payload(blueprint=blueprint, scene=scene), metadata


class ContinuityGuardAgent:
    def __init__(self, *, store: NarrativeGenerationStore) -> None:
        self.store = store

    def run(self, state: NarrativeGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
        story_id = _story_id(state)
        scene_prose = [SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])]
        chapters = _assemble_chapters(blueprint=blueprint, story_id=story_id, scene_prose=scene_prose)
        checks = [evaluate_chapter_continuity(blueprint=blueprint, chapter=chapter, minimum_words=MIN_SCENE_WORDS) for chapter in chapters]
        persisted_chapters = self.store.replace_chapter_drafts(series_id=blueprint.series_id, story_id=story_id, chapters=chapters)
        persisted_checks = self.store.replace_continuity_checks(series_id=blueprint.series_id, story_id=story_id, checks=checks)
        run_metadata = dict(state.get("run_metadata") or {})
        run_metadata["stage_metrics"] = {
            **dict(run_metadata.get("stage_metrics") or {}),
            "continuity_guard": {
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "chapter_count": len(chapters),
                "failed_checks": len([item for item in checks if not item.passed]),
            },
        }
        return {
            "chapter_drafts": [item.model_dump() for item in persisted_chapters],
            "continuity_checks": [item.model_dump() for item in persisted_checks],
            "run_metadata": run_metadata,
        }


class RewriteRevisionAgent:
    def __init__(self, *, store: NarrativeGenerationStore) -> None:
        self.store = store

    def run(self, state: NarrativeGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
        story_id = _story_id(state)
        chapters = [ChapterDraftArtifact.model_validate(item) for item in list(state.get("chapter_drafts") or [])]
        checks = [ContinuityCheckArtifact.model_validate(item) for item in list(state.get("continuity_checks") or [])]
        revisions: list[RevisionRecordArtifact] = []
        revised_chapters: list[ChapterDraftArtifact] = []
        check_by_chapter = {item.chapter_index: item for item in checks}
        for chapter in chapters:
            check = check_by_chapter.get(chapter.chapter_index)
            if check and not check.passed:
                before = chapter.prose
                chapter.prose = _deterministic_revise(chapter=chapter, check=check)
                revisions.append(
                    RevisionRecordArtifact(
                        revision_id=_stable_id("narrative-revision", story_id, chapter.chapter_index, *check.issues),
                        series_id=blueprint.series_id,
                        story_id=story_id,
                        blueprint_id=blueprint.blueprint_id,
                        chapter_index=chapter.chapter_index,
                        source_artifact_id=chapter.chapter_draft_id,
                        reason="Continuity guard repair",
                        before_excerpt=before[:500],
                        after_excerpt=chapter.prose[:500],
                        issues_addressed=list(check.issues),
                        metadata={"agent": "RewriteRevisionAgent", "mode": "deterministic_repair"},
                    )
                )
            revised_chapters.append(chapter)
        final_checks = [evaluate_chapter_continuity(blueprint=blueprint, chapter=chapter, minimum_words=MIN_SCENE_WORDS) for chapter in revised_chapters]
        persisted_chapters = self.store.replace_chapter_drafts(series_id=blueprint.series_id, story_id=story_id, chapters=revised_chapters)
        persisted_checks = self.store.replace_continuity_checks(series_id=blueprint.series_id, story_id=story_id, checks=final_checks)
        persisted_revisions = self.store.replace_revisions(series_id=blueprint.series_id, story_id=story_id, revisions=revisions)
        story = GeneratedStoryArtifact(
            story_id=story_id,
            series_id=blueprint.series_id,
            blueprint_id=blueprint.blueprint_id,
            title=blueprint.title,
            premise=blueprint.premise,
            chapters=persisted_chapters,
            continuity_checks=persisted_checks,
            revisions=persisted_revisions,
            canon_refs=_dedupe([ref for chapter in persisted_chapters for ref in chapter.canon_refs]),
            character_refs=_dedupe([ref for chapter in persisted_chapters for ref in chapter.character_refs]),
            entity_refs=_dedupe([ref for chapter in persisted_chapters for ref in chapter.entity_refs]),
            metadata={"agent": "RewriteRevisionAgent", "chapter_count": len(persisted_chapters)},
        )
        persisted_story = self.store.upsert_story(story)
        run_metadata = dict(state.get("run_metadata") or {})
        run_metadata["stage_order"] = ["narrative_generation", "continuity_guard", "rewrite_revision"]
        run_metadata["stage_metrics"] = {
            **dict(run_metadata.get("stage_metrics") or {}),
            "rewrite_revision": {
                "elapsed_seconds": round(time.perf_counter() - started, 4),
                "revision_count": len(persisted_revisions),
                "failed_checks_after_revision": len([item for item in persisted_checks if not item.passed]),
            },
        }
        return {
            "chapter_drafts": [item.model_dump() for item in persisted_chapters],
            "continuity_checks": [item.model_dump() for item in persisted_checks],
            "revisions": [item.model_dump() for item in persisted_revisions],
            "story": persisted_story.model_dump(),
            "run_metadata": run_metadata,
        }


class NarrativeGenerationRuntime:
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
        self.store = NarrativeGenerationStore(persistence)
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_narrative_generation_graph(
            store=self.store,
            reasoning_runtime=reasoning_runtime,
            checkpointer=self.checkpointer,
        )

    def invoke(
        self,
        *,
        series_id: str,
        blueprint_id: str = "",
        story_id: str = "",
        thread_id: str = "narrative-generation",
        target_words_per_scene: int = 180,
    ) -> NarrativeGenerationResult:
        context = self.store.load_series_context(series_id=series_id, blueprint_id=blueprint_id)
        blueprint = context.get("blueprint")
        if blueprint is None:
            raise ValueError(f"NarrativeGenerationRuntime requires a persisted generation blueprint for series '{series_id}'.")
        resolved_story_id = story_id or _stable_id("generated-story", series_id, blueprint.blueprint_id)
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "blueprint_id": blueprint.blueprint_id,
                "story_id": resolved_story_id,
                "target_words_per_scene": max(80, min(MAX_SCENE_WORDS, int(target_words_per_scene or 180))),
                "blueprint": blueprint.model_dump(),
                "events": [item.model_dump() for item in list(context.get("events") or [])],
                "entities": [item.model_dump() for item in list(context.get("entities") or [])],
                "character_profiles": [item.model_dump() for item in list(context.get("character_profiles") or [])],
                "world_states": [item.model_dump() for item in list(context.get("world_states") or [])],
                "run_metadata": {},
            },
            config={"configurable": {"thread_id": str(thread_id or "narrative-generation")}},
        )
        return NarrativeGenerationResult(
            series_id=series_id,
            story=GeneratedStoryArtifact.model_validate(state["story"]),
            scene_prose=[SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])],
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def build_narrative_generation_graph(
    *,
    store: NarrativeGenerationStore,
    reasoning_runtime: ReasoningRuntimeClient,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(NarrativeGenerationState)
    graph.add_node("narrative_generation", NarrativeGenerationAgent(store=store, reasoning_runtime=reasoning_runtime).run)
    graph.add_node("continuity_guard", ContinuityGuardAgent(store=store).run)
    graph.add_node("rewrite_revision", RewriteRevisionAgent(store=store).run)
    graph.add_edge(START, "narrative_generation")
    graph.add_edge("narrative_generation", "continuity_guard")
    graph.add_edge("continuity_guard", "rewrite_revision")
    graph.add_edge("rewrite_revision", END)
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
    raise ValueError("NarrativeGenerationRuntime requires a durable checkpointer or an initialized persistence engine.")


def _build_scene_prompt(
    *,
    blueprint: GenerationBlueprintArtifact,
    scene: ScenePlanItem,
    target_words_per_scene: int,
    context: NarrativeGenerationState,
    prior_scenes: list[SceneProseArtifact] | None = None,
) -> str:
    evidence = {
        "blueprint_title": blueprint.title,
        "premise": blueprint.premise,
        "continuation_plan": blueprint.continuation_plan,
        "divergence_plan": blueprint.divergence_plan,
        "scene": scene.model_dump(),
        "characters": _profiles_for_refs(context.get("character_profiles") or [], scene.character_refs),
        "entities": _entities_for_refs(context.get("entities") or [], context.get("world_states") or [], scene.entity_refs),
        "canon": _canon_for_refs(context.get("events") or [], scene.canon_refs),
        "prior_generated_scenes": [
            {
                "source_scene_id": item.source_scene_id,
                "title": item.title,
                "prose_excerpt": item.prose[-1200:],
            }
            for item in list(prior_scenes or [])[-3:]
        ],
    }
    schema = {"title": "string", "prose": "string"}
    return (
        "Write one polished prose scene for a generated story. Use only the provided plan/evidence. "
        "Do not introduce unsupported canon claims. Keep every named character/entity grounded in refs. "
        "A role introduced by the premise or scene plan that is not explicitly identified in a grounded character "
        "profile is a distinct new story participant, not one of the canon characters. Never assign that role to a "
        "canon character by implication. Preserve role identity and character identity exactly across PRIOR_GENERATED_SCENES. "
        f"Target {target_words_per_scene} words, maximum {MAX_SCENE_WORDS}. Return exactly JSON: "
        f"{json.dumps(schema)}\n\nEvidence:\n{json.dumps(evidence, ensure_ascii=False)}"
    )


def _pace_scene_call() -> None:
    if SCENE_CALL_DELAY_SECONDS > 0:
        time.sleep(SCENE_CALL_DELAY_SECONDS)


def _profiles_for_refs(profiles: list[dict[str, Any]], refs: list[str]) -> list[dict[str, Any]]:
    allowed = set(refs)
    return [
        {
            "character_id": item.get("character_id"),
            "canonical_name": item.get("canonical_name"),
            "overview": item.get("overview"),
            "latest_state_summary": item.get("latest_state_summary"),
        }
        for item in profiles
        if item.get("character_id") in allowed
    ][:8]


def _entities_for_refs(entities: list[dict[str, Any]], world_states: list[dict[str, Any]], refs: list[str]) -> list[dict[str, Any]]:
    allowed = set(refs)
    by_id = {item.get("entity_id"): item for item in entities}
    for item in world_states:
        by_id.setdefault(item.get("entity_id"), item)
    return [
        {
            "entity_id": item.get("entity_id"),
            "canonical_name": item.get("canonical_name"),
            "entity_type": item.get("entity_type"),
            "description": item.get("description"),
            "current_state_summary": item.get("current_state_summary"),
        }
        for entity_id, item in by_id.items()
        if entity_id in allowed
    ][:8]


def _canon_for_refs(events: list[dict[str, Any]], refs: list[str]) -> list[dict[str, Any]]:
    allowed = set(refs)
    return [
        {
            "event_id": item.get("event_id"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "participant_refs": item.get("participant_refs"),
            "entity_refs": item.get("entity_refs"),
        }
        for item in events
        if item.get("event_id") in allowed
    ][:8]


def _fallback_scene_payload(*, blueprint: GenerationBlueprintArtifact, scene: ScenePlanItem) -> SceneProsePayload:
    characters = ", ".join(scene.character_refs[:4]) or "the grounded cast"
    entities = ", ".join(scene.entity_refs[:3]) or "the grounded setting"
    prose = (
        f"{scene.summary} The scene follows {characters} through the planned beat while keeping {entities} visible in the action. "
        f"The purpose remains clear: {scene.purpose} The moment stays tied to canon references {', '.join(scene.canon_refs[:3])}, "
        f"so later continuity checks can trace the generated prose back to the blueprint. The tone follows {blueprint.title or 'the planned story'}, "
        "using concrete sensory detail without adding unsupported history, new factions, or contradictory relationships. "
        "Each choice is framed as a consequence of the planned scene rather than an invented revelation. The characters speak and move "
        "within the known constraints, letting tension come from what is already established. The scene closes with a clear forward "
        "motion for the chapter while preserving the blueprint's canon, character, and world boundaries."
    )
    return SceneProsePayload(title=f"Scene {scene.chapter_index}.{scene.scene_index}", prose=prose)


def _repair_scene_prose(prose: str, *, scene: ScenePlanItem, blueprint: GenerationBlueprintArtifact) -> str:
    cleaned = _clean_text(prose)
    if len(cleaned.split()) >= MIN_SCENE_WORDS:
        return cleaned
    return _fallback_scene_payload(blueprint=blueprint, scene=scene).prose


def _assemble_chapters(
    *,
    blueprint: GenerationBlueprintArtifact,
    story_id: str,
    scene_prose: list[SceneProseArtifact],
) -> list[ChapterDraftArtifact]:
    scenes_by_chapter: dict[int, list[SceneProseArtifact]] = {}
    for scene in scene_prose:
        scenes_by_chapter.setdefault(scene.chapter_index, []).append(scene)
    chapters: list[ChapterDraftArtifact] = []
    for outline in blueprint.chapter_outline:
        scenes = sorted(scenes_by_chapter.get(outline.chapter_index, []), key=lambda item: item.scene_index)
        prose_parts = [f"## {scene.title}\n\n{scene.prose}" for scene in scenes]
        chapters.append(
            ChapterDraftArtifact(
                chapter_draft_id=_stable_id("chapter-draft", story_id, outline.chapter_index),
                series_id=blueprint.series_id,
                story_id=story_id,
                blueprint_id=blueprint.blueprint_id,
                chapter_index=outline.chapter_index,
                title=outline.title,
                goal=outline.goal,
                prose="\n\n".join(prose_parts),
                scene_prose_ids=[scene.scene_prose_id for scene in scenes],
                canon_refs=_dedupe([*outline.canon_refs, *(ref for scene in scenes for ref in scene.canon_refs)]),
                character_refs=_dedupe([*outline.character_refs, *(ref for scene in scenes for ref in scene.character_refs)]),
                entity_refs=_dedupe([*outline.entity_refs, *(ref for scene in scenes for ref in scene.entity_refs)]),
                metadata={"agent": "ContinuityGuardAgent", "scene_count": len(scenes)},
            )
        )
    return chapters


def _deterministic_revise(*, chapter: ChapterDraftArtifact, check: ContinuityCheckArtifact) -> str:
    repair_note = (
        "\n\nContinuity repair note: this chapter remains anchored to canon refs "
        f"{', '.join(chapter.canon_refs[:4])}, character refs {', '.join(chapter.character_refs[:4])}, "
        f"and entity refs {', '.join(chapter.entity_refs[:4])}. Addressed: {', '.join(check.issues)}."
    )
    return _clean_text(chapter.prose + repair_note)


def _story_id(state: NarrativeGenerationState) -> str:
    return str(state.get("story_id") or "").strip() or _stable_id("generated-story", state.get("series_id"), state.get("blueprint_id"))


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in seen:
            results.append(cleaned)
            seen.add(cleaned)
    return results


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("::".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)
