"""LangGraph-native visual planning, rendering, retry, and quality workflow."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import time
import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

from packages.agent_runtime import SqlCheckpointSaver
from packages.character_world_modeling.contracts import CharacterProfileArtifact, WorldStateArtifact
from packages.canon_extraction.contracts import EntityArtifact
from packages.lineage_runtime import sanitize
from packages.narrative_generation.contracts import GeneratedStoryArtifact, SceneProseArtifact
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient
from packages.visual_generation.contracts import (
    CharacterSceneStateArtifact,
    CharacterVisualBaselineArtifact,
    EntityVisualDossierArtifact,
    ImageRenderProvider,
    SceneVisualPlanArtifact,
    VisualGenerationDecisionArtifact,
    VisualGenerationResult,
    VisualPromptArtifact,
    VisualQualityDecisionArtifact,
    VisualRenderArtifact,
    VisualSemanticEvaluator,
)
from packages.visual_generation.prompt_policy import compile_prompt
from packages.visual_generation.quality import evaluate_image_technical_quality
from packages.visual_generation.store import VisualGenerationStore


logger = logging.getLogger(__name__)


class VisualGenerationState(TypedDict, total=False):
    series_id: str
    story_id: str
    context: dict[str, Any]
    include_types: list[str]
    max_renders_per_type: int
    max_attempts: int
    workflow_versions: dict[str, str]
    character_baselines: list[dict[str, Any]]
    character_scene_states: list[dict[str, Any]]
    entity_dossiers: list[dict[str, Any]]
    scene_plans: list[dict[str, Any]]
    prompts: list[dict[str, Any]]
    renders: list[dict[str, Any]]
    audits: list[dict[str, Any]]
    decision: dict[str, Any]
    run_metadata: dict[str, Any]


class CharacterPlanPayload(BaseModel):
    character_id: str
    appearance: str = ""
    body: str = ""
    face: str = ""
    hair: str = ""
    clothing: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)
    immutable_traits: list[str] = Field(default_factory=list)

    @field_validator("appearance", "body", "face", "hair", "clothing", mode="before")
    @classmethod
    def normalize_descriptions(cls, value: Any) -> str:
        return _description_text(value)

    @field_validator("distinguishing_features", "immutable_traits", mode="before")
    @classmethod
    def normalize_lists(cls, value: Any) -> list[str]:
        return _string_list(value)


class CharacterSceneStatePayload(BaseModel):
    source_scene_id: str
    character_id: str
    expression: str = ""
    pose: str = ""
    clothing_state: str = ""
    physical_condition: str = ""
    action: str = ""

    @field_validator("expression", "pose", "clothing_state", "physical_condition", "action", mode="before")
    @classmethod
    def normalize_descriptions(cls, value: Any) -> str:
        return _description_text(value)


class EntityPlanPayload(BaseModel):
    entity_id: str
    visual_description: str = ""
    materials: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    scale: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)

    @field_validator("visual_description", "scale", mode="before")
    @classmethod
    def normalize_descriptions(cls, value: Any) -> str:
        return _description_text(value)

    @field_validator("materials", "colors", "distinguishing_features", mode="before")
    @classmethod
    def normalize_lists(cls, value: Any) -> list[str]:
        return _string_list(value)


class ScenePlanPayload(BaseModel):
    source_scene_id: str
    composition: str = ""
    environment: str = ""
    lighting: str = ""
    mood: str = ""
    camera: str = ""
    action: str = ""
    visible_character_names: list[str] = Field(default_factory=list)

    @field_validator("composition", "environment", "lighting", "mood", "camera", "action", mode="before")
    @classmethod
    def normalize_descriptions(cls, value: Any) -> str:
        return _description_text(value)

    @field_validator("visible_character_names", mode="before")
    @classmethod
    def normalize_visible_character_names(cls, value: Any) -> list[str]:
        return _string_list(value)


class VisualPlanningPayload(BaseModel):
    characters: list[CharacterPlanPayload] = Field(default_factory=list)
    character_scene_states: list[CharacterSceneStatePayload] = Field(default_factory=list)
    entities: list[EntityPlanPayload] = Field(default_factory=list)
    scenes: list[ScenePlanPayload] = Field(default_factory=list)


class VisualPlanningAgent:
    def __init__(self, *, store: VisualGenerationStore, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.store = store
        self.reasoning_runtime = reasoning_runtime

    def run(self, state: VisualGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        context = dict(state["context"])
        story = GeneratedStoryArtifact.model_validate(context["story"])
        scenes = [SceneProseArtifact.model_validate(item) for item in context.get("scene_prose") or []]
        profiles = [CharacterProfileArtifact.model_validate(item) for item in context.get("character_profiles") or []]
        entities = [EntityArtifact.model_validate(item) for item in context.get("entities") or []]
        world_states = [WorldStateArtifact.model_validate(item) for item in context.get("world_states") or []]
        story_character_refs = {ref for scene in scenes for ref in scene.character_refs}
        story_entity_refs = {ref for scene in scenes for ref in scene.entity_refs}
        profiles = [item for item in profiles if item.character_id in story_character_refs]
        entities = [item for item in entities if item.entity_id in story_entity_refs and _entity_visual_type(item.entity_type)]
        world_states = [item for item in world_states if item.entity_id in story_entity_refs]
        scenes, profiles, entities, world_states = _scope_planning_inputs(
            scenes=scenes,
            profiles=profiles,
            entities=entities,
            world_states=world_states,
            include_types=state.get("include_types") or [],
            max_per_type=int(state.get("max_renders_per_type") or 0),
        )
        character_refs = {item.character_id for item in profiles}
        entity_refs = {item.entity_id for item in entities}
        payload, planning_metadata = self._plan_categories(
            story=story,
            scenes=scenes,
            profiles=profiles,
            entities=entities,
            world_states=world_states,
        )
        baselines = _build_baselines(state, payload, profiles)
        scene_states = _build_character_scene_states(state, payload, baselines, scenes)
        dossiers = _build_entity_dossiers(state, payload, entities, world_states)
        scene_plans = _build_scene_plans(state, payload, scenes)
        returned_character_refs = {item.character_id for item in baselines}
        if character_refs and returned_character_refs != character_refs:
            missing = sorted(character_refs - returned_character_refs)
            raise ValueError(f"Visual planning did not return every referenced character baseline: missing={missing}.")
        expected_scene_states = {
            (scene.source_scene_id, character_id)
            for scene in scenes
            for character_id in scene.character_refs
        }
        returned_scene_states = {(item.source_scene_id, item.character_id) for item in scene_states}
        if not returned_scene_states.issubset(expected_scene_states):
            invalid = sorted(returned_scene_states - expected_scene_states)
            raise ValueError(f"Visual planning returned invalid per-scene character states: {invalid}.")
        if {item.entity_id for item in dossiers} != {item.entity_id for item in entities}:
            raise ValueError("Visual planning did not return every referenced visual entity dossier.")
        if {item.source_scene_id for item in scene_plans} != {item.source_scene_id for item in scenes}:
            raise ValueError("Visual planning did not return every generated scene.")
        baselines = self.store.replace_baselines(series_id=state["series_id"], story_id=state["story_id"], items=baselines)
        scene_states = self.store.replace_scene_states(series_id=state["series_id"], story_id=state["story_id"], items=scene_states)
        dossiers = self.store.replace_dossiers(series_id=state["series_id"], story_id=state["story_id"], items=dossiers)
        scene_plans = self.store.replace_scene_plans(series_id=state["series_id"], story_id=state["story_id"], items=scene_plans)
        metadata = _stage_metadata(
            state, "visual_planning", started,
            character_count=len(baselines), entity_count=len(dossiers), scene_count=len(scene_plans),
            provider=planning_metadata[0].get("provider") if planning_metadata else "",
            model=planning_metadata[0].get("resolved_model") if planning_metadata else "",
            planning_call_count=len(planning_metadata),
            planning_latencies_ms=[item.get("latency_ms") for item in planning_metadata],
        )
        return {
            "character_baselines": [item.model_dump() for item in baselines],
            "character_scene_states": [item.model_dump() for item in scene_states],
            "entity_dossiers": [item.model_dump() for item in dossiers],
            "scene_plans": [item.model_dump() for item in scene_plans],
            "run_metadata": metadata,
        }

    def _plan_categories(
        self,
        *,
        story: GeneratedStoryArtifact,
        scenes: list[SceneProseArtifact],
        profiles: list[CharacterProfileArtifact],
        entities: list[EntityArtifact],
        world_states: list[WorldStateArtifact],
    ) -> tuple[VisualPlanningPayload, list[dict[str, Any]]]:
        categories = {
            "characters": 3500,
            "entities": 2500,
            "scenes": 4000,
        }

        def execute(
            category: str,
            max_tokens: int,
            selected_scenes: list[SceneProseArtifact] | None = None,
            selected_profiles: list[CharacterProfileArtifact] | None = None,
            selected_entities: list[EntityArtifact] | None = None,
            selected_world_states: list[WorldStateArtifact] | None = None,
        ) -> tuple[str, VisualPlanningPayload, dict[str, Any]]:
            client = self.reasoning_runtime.clone() if hasattr(self.reasoning_runtime, "clone") else self.reasoning_runtime
            response = client.generate_json(
                _build_category_planning_prompt(
                    category=category,
                    story=story,
                    scenes=selected_scenes if selected_scenes is not None else scenes,
                    profiles=selected_profiles if selected_profiles is not None else profiles,
                    entities=selected_entities if selected_entities is not None else entities,
                    world_states=selected_world_states if selected_world_states is not None else world_states,
                ),
                strict=True,
                max_tokens=max_tokens,
            )
            metadata = dict(client.last_request_metadata() or {})
            if isinstance(response, list) and category in {"entities", "scenes"}:
                response = {category: response}
            if metadata.get("status") != "ok" or not isinstance(response, dict) or response.get("error"):
                raise RuntimeError(f"Visual {category} planning provider failed: {response!r}")
            return category, VisualPlanningPayload.model_validate(response), metadata

        if hasattr(self.reasoning_runtime, "clone"):
            with ThreadPoolExecutor(max_workers=len(categories), thread_name_prefix="visual-planning") as executor:
                futures = [executor.submit(contextvars.copy_context().run, execute, *item) for item in categories.items()]
                rows = [future.result() for future in futures]
        else:
            rows = [execute(*item) for item in categories.items()]
        by_category = {category: payload for category, payload, _ in rows}
        combined = VisualPlanningPayload(
            characters=by_category["characters"].characters,
            character_scene_states=by_category["characters"].character_scene_states,
            entities=by_category["entities"].entities,
            scenes=by_category["scenes"].scenes,
        )
        metadata = [item for _, _, item in rows]
        repair_jobs: list[tuple[str, int, dict[str, Any]]] = []
        returned_characters = {item.character_id for item in combined.characters}
        character_repair_ids = {item.character_id for item in profiles} - returned_characters
        if character_repair_ids:
            repair_profiles = [item for item in profiles if item.character_id in character_repair_ids]
            repair_scenes = []
            for scene in scenes:
                refs = [ref for ref in scene.character_refs if ref in character_repair_ids]
                if refs:
                    repair_scenes.append(scene.model_copy(update={"character_refs": refs}))
            repair_jobs.append(("characters", 2500, {"selected_profiles": repair_profiles, "selected_scenes": repair_scenes}))
        missing_entity_ids = {item.entity_id for item in entities} - {item.entity_id for item in combined.entities}
        if missing_entity_ids:
            repair_jobs.append(("entities", 1800, {
                "selected_entities": [item for item in entities if item.entity_id in missing_entity_ids],
                "selected_world_states": [item for item in world_states if item.entity_id in missing_entity_ids],
            }))
        missing_scene_ids = {item.source_scene_id for item in scenes} - {item.source_scene_id for item in combined.scenes}
        if missing_scene_ids:
            repair_jobs.append(("scenes", 2200, {"selected_scenes": [item for item in scenes if item.source_scene_id in missing_scene_ids]}))
        if repair_jobs:
            with ThreadPoolExecutor(max_workers=len(repair_jobs), thread_name_prefix="visual-planning-repair") as executor:
                futures = [executor.submit(contextvars.copy_context().run, execute, item[0], item[1], **item[2]) for item in repair_jobs]
                repaired = [future.result() for future in futures]
            metadata.extend(item for _, _, item in repaired)
            for category, payload, _ in repaired:
                if category == "characters":
                    combined.characters = _merge_models(combined.characters, payload.characters, key=lambda item: item.character_id)
                    combined.character_scene_states = _merge_models(
                        combined.character_scene_states,
                        payload.character_scene_states,
                        key=lambda item: (item.source_scene_id, item.character_id),
                    )
                elif category == "entities":
                    combined.entities = _merge_models(combined.entities, payload.entities, key=lambda item: item.entity_id)
                else:
                    combined.scenes = _merge_models(combined.scenes, payload.scenes, key=lambda item: item.source_scene_id)
        return combined, metadata


class VisualPromptAgent:
    def __init__(self, *, store: VisualGenerationStore) -> None:
        self.store = store

    def run(self, state: VisualGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        prompts: list[VisualPromptArtifact] = []
        versions = dict(state.get("workflow_versions") or {})
        baselines = [CharacterVisualBaselineArtifact.model_validate(item) for item in state.get("character_baselines") or []]
        dossiers = [EntityVisualDossierArtifact.model_validate(item) for item in state.get("entity_dossiers") or []]
        scene_plans = [SceneVisualPlanArtifact.model_validate(item) for item in state.get("scene_plans") or []]
        scene_states = [CharacterSceneStateArtifact.model_validate(item) for item in state.get("character_scene_states") or []]
        baseline_map = {item.character_id: item for item in baselines}
        dossier_map = {item.entity_id: item for item in dossiers}
        for item in baselines:
            body = " ".join([item.canonical_name, item.appearance, item.body, item.face, item.hair, item.clothing, *item.distinguishing_features])
            prompts.append(_prompt_artifact(
                state, "character", item.character_id, body, versions=versions,
                consistency_keys=[item.consistency_key], character_clothing=item.clothing,
            ))
        for item in dossiers:
            if item.entity_type == "location":
                body = " ".join([
                    item.canonical_name,
                    "Unoccupied static environment reference; depict geography and architecture only.",
                    "Colors: " + ", ".join(item.colors),
                    item.scale,
                ])
            else:
                body = " ".join([item.canonical_name, item.visual_description, "Materials: " + ", ".join(item.materials), "Colors: " + ", ".join(item.colors), item.scale, *item.distinguishing_features])
            prompts.append(_prompt_artifact(state, item.entity_type, item.entity_id, body, versions=versions, consistency_keys=[item.consistency_key]))
        for item in scene_plans:
            character_text = []
            visible_character_refs = _scene_visible_character_refs(item, scene_states)
            cast_names = _scene_cast_names(item, baseline_map, visible_character_refs)
            visible_character_refs = _refs_matching_structured_cast(
                item, baseline_map, visible_character_refs, cast_names
            )
            consistency_keys: list[str] = []
            for ref in visible_character_refs:
                baseline = baseline_map.get(ref)
                per_scene = next((row for row in scene_states if row.source_scene_id == item.source_scene_id and row.character_id == ref), None)
                if baseline:
                    consistency_keys.append(baseline.consistency_key)
                    character_text.append(_bounded_text(" ".join([
                        baseline.canonical_name,
                        baseline.appearance,
                        baseline.clothing,
                        per_scene.expression if per_scene else "",
                        per_scene.action if per_scene else "",
                    ]), 240))
            entity_text = []
            for ref in item.entity_refs:
                dossier = dossier_map.get(ref)
                if dossier:
                    consistency_keys.append(dossier.consistency_key)
                    entity_text.append(_bounded_text(f"{dossier.canonical_name}: {dossier.visual_description}", 180))
            body = " ".join([
                f"Scene: {_bounded_text(item.title, 120)}.",
                f"Composition: {_bounded_text(item.composition, 300)}.",
                f"Environment: {_bounded_text(item.environment, 240)}.",
                f"Lighting: {_bounded_text(item.lighting, 160)}.",
                f"Mood: {_bounded_text(item.mood, 100)}.",
                f"Frozen action: {_bounded_text(item.action, 300)}.",
                *character_text,
                *entity_text,
            ])
            prompts.append(_prompt_artifact(
                state, "scene", item.source_scene_id, body, versions=versions,
                consistency_keys=consistency_keys, source_scene_id=item.source_scene_id,
                scene_character_names=cast_names,
            ))
        prompts = _select_prompts(prompts, include_types=state.get("include_types") or [], max_per_type=int(state.get("max_renders_per_type") or 0))
        persisted = self.store.replace_prompts(series_id=state["series_id"], story_id=state["story_id"], items=prompts)
        metadata = _stage_metadata(state, "prompt_construction", started, prompt_count=len(persisted), target_types=sorted({item.target_type for item in persisted}))
        return {"prompts": [item.model_dump() for item in persisted], "run_metadata": metadata}


class VisualRenderAgent:
    def __init__(self, *, store: VisualGenerationStore, image_provider: ImageRenderProvider, seed_factory: Callable[[], int]) -> None:
        self.store = store
        self.image_provider = image_provider
        self.seed_factory = seed_factory

    def run(self, state: VisualGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        prompts = [VisualPromptArtifact.model_validate(item) for item in state.get("prompts") or []]
        renders = [VisualRenderArtifact.model_validate(item) for item in state.get("renders") or []]
        audits = [VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []]
        accepted = {item.prompt_id for item in audits if item.accepted}
        max_attempts = int(state.get("max_attempts") or 2)
        rendered_now = 0
        for prompt in prompts:
            attempts = len([item for item in renders if item.prompt_id == prompt.prompt_id])
            if prompt.prompt_id in accepted or attempts >= max_attempts:
                continue
            attempt = attempts + 1
            seed = int(self.seed_factory())
            render_id = _stable_id("visual-render", prompt.prompt_id, attempt, seed)
            call_started = time.perf_counter()
            try:
                raw = self.image_provider.render(
                    prompt=prompt.positive_prompt,
                    negative_prompt=prompt.negative_prompt,
                    seed=seed,
                    steps=prompt.steps,
                    cfg=prompt.cfg,
                    width=prompt.width,
                    height=prompt.height,
                    workflow_mode=prompt.workflow_mode,
                )
                response = dict(raw.get("response") or raw)
                image_bytes = bytes(response.get("image_bytes") or b"")
                technical = evaluate_image_technical_quality(
                    image_bytes,
                    expected_width=prompt.width,
                    expected_height=prompt.height,
                    target_type=prompt.target_type,
                )
                render = VisualRenderArtifact(
                    render_id=render_id, series_id=prompt.series_id, story_id=prompt.story_id,
                    prompt_id=prompt.prompt_id, target_type=prompt.target_type, target_ref=prompt.target_ref,
                    attempt=attempt, seed=seed, status="rendered" if technical.get("passed") else "technical_rejection",
                    byte_length=len(image_bytes), image_sha256=hashlib.sha256(image_bytes).hexdigest() if image_bytes else "",
                    provider_name="modal_comfyui", provider_account=str(raw.get("token_name") or response.get("token_name") or ""),
                    elapsed_seconds=round(time.perf_counter() - call_started, 4), technical_metrics=technical,
                    metadata={"workflow_mode": prompt.workflow_mode, "workflow_version": prompt.workflow_version, "source_scene_id": prompt.source_scene_id, "request_metrics": response.get("request_metrics") or {}},
                )
                if technical.get("passed"):
                    stored = self.store.store_image(render=render, image_bytes=image_bytes)
                    render.bucket_name = str(stored.get("bucket_name") or "")
                    render.object_path = str(stored.get("object_path") or "")
            except Exception as exc:
                render = VisualRenderArtifact(
                    render_id=render_id, series_id=prompt.series_id, story_id=prompt.story_id,
                    prompt_id=prompt.prompt_id, target_type=prompt.target_type, target_ref=prompt.target_ref,
                    attempt=attempt, seed=seed, status="provider_error", provider_name="modal_comfyui",
                    elapsed_seconds=round(time.perf_counter() - call_started, 4), error=f"{type(exc).__name__}: {exc}",
                    metadata={"workflow_mode": prompt.workflow_mode, "workflow_version": prompt.workflow_version, "source_scene_id": prompt.source_scene_id},
                )
            renders.append(render)
            rendered_now += 1
            logger.info("visual_generation render prompt=%s attempt=%d status=%s", prompt.prompt_id, attempt, render.status)
        persisted = self.store.replace_renders(series_id=state["series_id"], story_id=state["story_id"], items=renders)
        metadata = _stage_metadata(state, f"render_round_{_max_attempt(renders)}", started, rendered_count=rendered_now)
        return {"renders": [item.model_dump() for item in persisted], "run_metadata": metadata}


class VisualAuditAgent:
    def __init__(self, *, store: VisualGenerationStore, semantic_evaluator: VisualSemanticEvaluator) -> None:
        self.store = store
        self.semantic_evaluator = semantic_evaluator

    def run(self, state: VisualGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        prompts = {item.prompt_id: item for item in [VisualPromptArtifact.model_validate(row) for row in state.get("prompts") or []]}
        renders = [VisualRenderArtifact.model_validate(row) for row in state.get("renders") or []]
        audits = [VisualQualityDecisionArtifact.model_validate(row) for row in state.get("audits") or []]
        audited_render_ids = {item.render_id for item in audits}
        max_attempts = int(state.get("max_attempts") or 2)
        for render in renders:
            if render.render_id in audited_render_ids:
                continue
            prompt = prompts[render.prompt_id]
            semantic: dict[str, Any] = {}
            image_bytes = b""
            if render.status == "rendered":
                image_bytes = self.store.load_image(render)
                render.technical_metrics = evaluate_image_technical_quality(
                    image_bytes,
                    expected_width=prompt.width,
                    expected_height=prompt.height,
                    target_type=prompt.target_type,
                )
                if not render.technical_metrics.get("passed"):
                    render.status = "technical_rejection"
            issues = list((render.technical_metrics or {}).get("issues") or [])
            technical_passed = render.status == "rendered" and bool((render.technical_metrics or {}).get("passed"))
            if technical_passed:
                try:
                    semantic = self.semantic_evaluator.evaluate(image_bytes=image_bytes, prompt=prompt)
                except Exception as exc:
                    issues.append(f"semantic_evaluator_error:{type(exc).__name__}")
            else:
                issues.append(render.error or render.status)
            scores = {key: _score(semantic.get(key)) for key in ["prompt_alignment_score", "subject_consistency_score", "composition_score", "photorealism_score", "defect_score"]}
            issues.extend(str(item) for item in list(semantic.get("issues") or []) if str(item).strip())
            reported_hard_violations = [
                str(item) for item in list(semantic.get("hard_constraint_violations") or []) if str(item).strip()
            ]
            hard_violations = _blocking_hard_violations(reported_hard_violations, scores=scores)
            issues.extend(reported_hard_violations)
            blocking_issues = [item for item in issues if item not in reported_hard_violations or item in hard_violations]
            accepted = (
                technical_passed and not any(item.startswith("semantic_evaluator_error") for item in issues)
                and not hard_violations
                and not _issues_contain_hard_violation(blocking_issues)
                and scores["prompt_alignment_score"] >= 0.65
                and scores["subject_consistency_score"] >= 0.60
                and scores["composition_score"] >= 0.55
                and scores["photorealism_score"] >= 0.55
                and scores["defect_score"] <= 0.35
            )
            status = "accepted" if accepted else ("retry_required" if render.attempt < max_attempts else "rejected")
            audits.append(
                VisualQualityDecisionArtifact(
                    audit_id=_stable_id("visual-audit", render.render_id), series_id=render.series_id, story_id=render.story_id,
                    prompt_id=render.prompt_id, render_id=render.render_id, target_type=render.target_type, target_ref=render.target_ref,
                    accepted=accepted, status=status, technical_passed=technical_passed, issues=_dedupe(issues),
                    **scores, metadata={
                        "attempt": render.attempt,
                        "semantic_provider": type(self.semantic_evaluator).__name__,
                        "semantic_request": _semantic_request_lineage(semantic),
                        "cast_audit": _cast_audit_lineage(semantic),
                        "character_consistency_audit": _character_consistency_audit_lineage(semantic),
                        "reported_hard_violation_count": len(reported_hard_violations),
                        "blocking_hard_violation_count": len(hard_violations),
                    },
                )
            )
            logger.info("visual_generation audit prompt=%s attempt=%d status=%s", render.prompt_id, render.attempt, status)
        self.store.replace_renders(series_id=state["series_id"], story_id=state["story_id"], items=renders)
        persisted = self.store.replace_audits(series_id=state["series_id"], story_id=state["story_id"], items=audits)
        metadata = _stage_metadata(state, f"audit_round_{_max_attempt(renders)}", started, audited_count=len(persisted))
        return {
            "renders": [item.model_dump() for item in renders],
            "audits": [item.model_dump() for item in persisted],
            "run_metadata": metadata,
        }


class VisualDecisionAgent:
    def __init__(self, *, store: VisualGenerationStore) -> None:
        self.store = store

    def run(self, state: VisualGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        prompts = [VisualPromptArtifact.model_validate(item) for item in state.get("prompts") or []]
        audits = [VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []]
        latest = _latest_audits(audits)
        rejected = [item.prompt_id for item in prompts if not latest.get(item.prompt_id) or not latest[item.prompt_id].accepted]
        accepted = bool(prompts) and not rejected
        decision = self.store.upsert_decision(
            VisualGenerationDecisionArtifact(
                decision_id=_stable_id("visual-generation-decision", state["story_id"]),
                series_id=state["series_id"], story_id=state["story_id"], accepted=accepted,
                status="accepted" if accepted else "rejected", requested_count=len(prompts), accepted_count=len(prompts) - len(rejected),
                rejected_prompt_ids=rejected,
                reasons=[] if accepted else [f"{len(rejected)} visual target(s) failed quality validation."],
                metadata={"agent": "VisualDecisionAgent", "max_attempts": int(state.get("max_attempts") or 2)},
            )
        )
        metadata = _stage_metadata(state, "visual_decision", started, accepted=accepted, rejected_count=len(rejected))
        return {"decision": decision.model_dump(), "run_metadata": metadata}


class VisualGenerationRuntime:
    def __init__(
        self, *, persistence: PersistenceRuntimeClient, reasoning_runtime: ReasoningRuntimeClient,
        image_provider: ImageRenderProvider, semantic_evaluator: VisualSemanticEvaluator,
        checkpointer: BaseCheckpointSaver | None = None, allow_in_memory_checkpointer: bool = False,
        seed_factory: Callable[[], int] | None = None,
    ) -> None:
        self.persistence = persistence
        self.store = VisualGenerationStore(persistence)
        self.reasoning_runtime = reasoning_runtime
        self.image_provider = image_provider
        self.semantic_evaluator = semantic_evaluator
        self.seed_factory = seed_factory or (lambda: secrets.randbelow((1 << 63) - 1) + 1)
        resolved_checkpointer = _resolve_checkpointer(persistence, checkpointer, allow_in_memory_checkpointer)
        self.graph = build_visual_generation_graph(
            store=self.store, reasoning_runtime=reasoning_runtime, image_provider=image_provider,
            semantic_evaluator=semantic_evaluator, checkpointer=resolved_checkpointer,
            seed_factory=self.seed_factory,
        )

    def invoke(
        self, *, series_id: str, story_id: str, thread_id: str = "visual-generation",
        include_types: list[str] | None = None, max_renders_per_type: int = 0, max_attempts: int = 2,
        workflow_versions: dict[str, str] | None = None,
    ) -> VisualGenerationResult:
        context = self.store.load_context(series_id=series_id, story_id=story_id)
        state = self.graph.invoke(
            {
                "series_id": series_id, "story_id": story_id, "context": _serialize_context(context),
                "include_types": list(include_types or []), "max_renders_per_type": max(0, int(max_renders_per_type)),
                "max_attempts": max(1, int(max_attempts)), "workflow_versions": dict(workflow_versions or {}),
                "renders": [], "audits": [], "run_metadata": {},
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        return VisualGenerationResult(
            series_id=series_id, story_id=story_id,
            character_baselines=[CharacterVisualBaselineArtifact.model_validate(item) for item in state.get("character_baselines") or []],
            character_scene_states=[CharacterSceneStateArtifact.model_validate(item) for item in state.get("character_scene_states") or []],
            entity_dossiers=[EntityVisualDossierArtifact.model_validate(item) for item in state.get("entity_dossiers") or []],
            scene_plans=[SceneVisualPlanArtifact.model_validate(item) for item in state.get("scene_plans") or []],
            prompts=[VisualPromptArtifact.model_validate(item) for item in state.get("prompts") or []],
            renders=[VisualRenderArtifact.model_validate(item) for item in state.get("renders") or []],
            audits=[VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []],
            decision=VisualGenerationDecisionArtifact.model_validate(state["decision"]),
            run_metadata=dict(state.get("run_metadata") or {}),
        )

    def reaudit(self, *, series_id: str, story_id: str, max_attempts: int = 1) -> VisualGenerationResult:
        prompts = self.store.list_prompts(series_id=series_id, story_id=story_id)
        renders = self.store.list_renders(series_id=series_id, story_id=story_id)
        if not prompts or not renders:
            raise FileNotFoundError(f"No persisted visual prompts/renders found for story '{story_id}'.")
        self.store.replace_audits(series_id=series_id, story_id=story_id, items=[])
        state: VisualGenerationState = {
            "series_id": series_id,
            "story_id": story_id,
            "prompts": [item.model_dump() for item in prompts],
            "renders": [item.model_dump() for item in renders],
            "audits": [],
            "max_attempts": max(1, int(max_attempts)),
            "run_metadata": {},
        }
        state.update(VisualAuditAgent(store=self.store, semantic_evaluator=self.semantic_evaluator).run(state))
        state.update(VisualDecisionAgent(store=self.store).run(state))
        return VisualGenerationResult(
            series_id=series_id,
            story_id=story_id,
            character_baselines=self.store.list_baselines(series_id=series_id, story_id=story_id),
            character_scene_states=self.store.list_scene_states(series_id=series_id, story_id=story_id),
            entity_dossiers=self.store.list_dossiers(series_id=series_id, story_id=story_id),
            scene_plans=self.store.list_scene_plans(series_id=series_id, story_id=story_id),
            prompts=prompts,
            renders=[VisualRenderArtifact.model_validate(item) for item in state.get("renders") or []],
            audits=[VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []],
            decision=VisualGenerationDecisionArtifact.model_validate(state["decision"]),
            run_metadata=dict(state.get("run_metadata") or {}),
        )

    def retry_rejected(self, *, series_id: str, story_id: str, max_attempts: int = 2) -> VisualGenerationResult:
        prompts = self.store.list_prompts(series_id=series_id, story_id=story_id)
        renders = self.store.list_renders(series_id=series_id, story_id=story_id)
        audits = self.store.list_audits(series_id=series_id, story_id=story_id)
        if not prompts or not renders or not audits:
            raise FileNotFoundError(f"No persisted visual run found for story '{story_id}'.")
        state: VisualGenerationState = {
            "series_id": series_id,
            "story_id": story_id,
            "prompts": [item.model_dump() for item in prompts],
            "renders": [item.model_dump() for item in renders],
            "audits": [item.model_dump() for item in audits],
            "max_attempts": max(1, int(max_attempts)),
            "run_metadata": {},
        }
        render_agent = VisualRenderAgent(store=self.store, image_provider=self.image_provider, seed_factory=self.seed_factory)
        audit_agent = VisualAuditAgent(store=self.store, semantic_evaluator=self.semantic_evaluator)
        while _route_after_audit(state) == "retry":
            state.update(render_agent.run(state))
            state.update(audit_agent.run(state))
        state.update(VisualDecisionAgent(store=self.store).run(state))
        return VisualGenerationResult(
            series_id=series_id,
            story_id=story_id,
            character_baselines=self.store.list_baselines(series_id=series_id, story_id=story_id),
            character_scene_states=self.store.list_scene_states(series_id=series_id, story_id=story_id),
            entity_dossiers=self.store.list_dossiers(series_id=series_id, story_id=story_id),
            scene_plans=self.store.list_scene_plans(series_id=series_id, story_id=story_id),
            prompts=prompts,
            renders=[VisualRenderArtifact.model_validate(item) for item in state.get("renders") or []],
            audits=[VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []],
            decision=VisualGenerationDecisionArtifact.model_validate(state["decision"]),
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def build_visual_generation_graph(
    *, store: VisualGenerationStore, reasoning_runtime: ReasoningRuntimeClient,
    image_provider: ImageRenderProvider, semantic_evaluator: VisualSemanticEvaluator,
    seed_factory: Callable[[], int], checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(VisualGenerationState)
    graph.add_node("visual_planning", VisualPlanningAgent(store=store, reasoning_runtime=reasoning_runtime).run)
    graph.add_node("prompt_construction", VisualPromptAgent(store=store).run)
    graph.add_node("render", VisualRenderAgent(store=store, image_provider=image_provider, seed_factory=seed_factory).run)
    graph.add_node("audit", VisualAuditAgent(store=store, semantic_evaluator=semantic_evaluator).run)
    graph.add_node("decision", VisualDecisionAgent(store=store).run)
    graph.add_edge(START, "visual_planning")
    graph.add_edge("visual_planning", "prompt_construction")
    graph.add_edge("prompt_construction", "render")
    graph.add_edge("render", "audit")
    graph.add_conditional_edges("audit", _route_after_audit, {"retry": "render", "decide": "decision"})
    graph.add_edge("decision", END)
    return graph.compile(checkpointer=checkpointer)


def _route_after_audit(state: VisualGenerationState) -> str:
    prompts = [VisualPromptArtifact.model_validate(item) for item in state.get("prompts") or []]
    renders = [VisualRenderArtifact.model_validate(item) for item in state.get("renders") or []]
    latest = _latest_audits([VisualQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []])
    max_attempts = int(state.get("max_attempts") or 2)
    for prompt in prompts:
        attempts = len([item for item in renders if item.prompt_id == prompt.prompt_id])
        if (not latest.get(prompt.prompt_id) or not latest[prompt.prompt_id].accepted) and attempts < max_attempts:
            return "retry"
    return "decide"


def _build_planning_prompt(*, story: GeneratedStoryArtifact, scenes: list[SceneProseArtifact], profiles: list[CharacterProfileArtifact], entities: list[EntityArtifact], world_states: list[WorldStateArtifact]) -> str:
    return (
        "You are a production visual-development planner. Use only supplied grounded story and canon artifacts. "
        "Create stable character baselines, per-scene states, visualizable entity dossiers, and one composition plan per generated scene. "
        "Do not invent identity, anatomy, clothing, injuries, architecture, powers, or materials as canon. When evidence is absent, use restrained neutral production choices and label them in plain visual language. "
        "Return JSON only with keys characters, character_scene_states, entities, scenes. Preserve every supplied ID exactly. "
        "characters fields: character_id, appearance, body, face, hair, clothing, distinguishing_features, immutable_traits. "
        "character_scene_states fields: source_scene_id, character_id, expression, pose, clothing_state, physical_condition, action. "
        "entities fields: entity_id, visual_description, materials, colors, scale, distinguishing_features. "
        "scenes fields: source_scene_id, composition, environment, lighting, mood, camera, action.\n"
        f"STORY: {json.dumps({'title': story.title, 'premise': story.premise}, ensure_ascii=False)}\n"
        f"CHARACTER_PROFILES: {json.dumps([item.model_dump() for item in profiles], ensure_ascii=False)}\n"
        f"ENTITIES: {json.dumps([item.model_dump() for item in entities], ensure_ascii=False)}\n"
        f"WORLD_STATES: {json.dumps([item.model_dump() for item in world_states], ensure_ascii=False)}\n"
        f"GENERATED_SCENES: {json.dumps([item.model_dump() for item in scenes], ensure_ascii=False)}"
    )


def _build_category_planning_prompt(
    *,
    category: str,
    story: GeneratedStoryArtifact,
    scenes: list[SceneProseArtifact],
    profiles: list[CharacterProfileArtifact],
    entities: list[EntityArtifact],
    world_states: list[WorldStateArtifact],
) -> str:
    category_instructions = {
        "characters": (
            "Return JSON with keys characters and character_scene_states only. Return every supplied character ID and every "
            "scene-character combination that appears in GENERATED_SCENES. Character fields: character_id, appearance, body, "
            "face, hair, clothing, distinguishing_features, immutable_traits. Scene-state fields: source_scene_id, character_id, "
            "expression, pose, clothing_state, physical_condition, action. Preserve each grounded_identity_cue exactly in the "
            "character appearance and immutable_traits; never replace an explicit female or male cue with neutral or unspecified."
        ),
        "entities": (
            "Return JSON with key entities only. Return every supplied entity ID. Fields: entity_id, visual_description, "
            "materials, colors, scale, distinguishing_features. Location dossiers must describe only static geography, architecture, "
            "materials, lighting, and scale; never include occupants, crowds, creatures, actions, ceremonies, or narrative events."
        ),
        "scenes": (
            "Return JSON with key scenes only. Return every supplied source_scene_id. Fields: source_scene_id, composition, "
            "environment, lighting, mood, camera, action, visible_character_names. visible_character_names must list every "
            "person whose physical body is visibly present in that frozen scene and no one else, using exact names from "
            "GENERATED_SCENES. A person who is only mentioned, remembered, quoted, named in a signature or document, heard, "
            "or otherwise off-camera is not visible and must not be listed. Include story-local named people when physically "
            "present even when they have no canonical character ID."
        ),
    }
    if category not in category_instructions:
        raise ValueError(f"Unsupported visual planning category '{category}'.")
    common = (
        "You are a production visual-development planner. Use only supplied grounded artifacts. Preserve every supplied ID exactly. "
        "Do not present invented identity, anatomy, clothing, injuries, architecture, powers, or materials as canon. Use restrained "
        "neutral production choices when evidence is absent. Return JSON only. "
    )
    source_payload: dict[str, Any] = {"story": {"title": story.title, "premise": story.premise}}
    if category == "characters":
        source_payload.update(
            character_profiles=[_profile_visual_source(item) for item in profiles],
            generated_scenes=[item.model_dump() for item in scenes],
        )
    elif category == "entities":
        source_payload.update(
            entities=[item.model_dump() for item in entities],
            world_states=[item.model_dump() for item in world_states],
        )
    else:
        source_payload.update(generated_scenes=[item.model_dump() for item in scenes])
    return common + category_instructions[category] + "\nSOURCE: " + json.dumps(source_payload, ensure_ascii=False)


def _build_baselines(state: VisualGenerationState, payload: VisualPlanningPayload, profiles: list[CharacterProfileArtifact]) -> list[CharacterVisualBaselineArtifact]:
    profile_map = {item.character_id: item for item in profiles}
    results = []
    for row in payload.characters:
        profile = profile_map.get(row.character_id)
        if not profile:
            continue
        identity_cue = _grounded_identity_cue(profile)
        appearance = row.appearance
        clothing = row.clothing
        immutable_traits = _dedupe(row.immutable_traits)
        if identity_cue:
            combined = " ".join([row.appearance, row.body, row.face, *immutable_traits]).casefold()
            if identity_cue not in combined:
                appearance = f"{identity_cue} character; {appearance}".strip("; ")
            immutable_traits = _dedupe([identity_cue, *immutable_traits])
        if _is_unspecified_visual_detail(clothing):
            clothing = "plain practical pre-industrial tunic, fitted trousers, and simple boots"
        results.append(CharacterVisualBaselineArtifact(
            baseline_id=_stable_id("character-visual-baseline", state["story_id"], row.character_id),
            series_id=state["series_id"], story_id=state["story_id"], character_id=row.character_id,
            canonical_name=profile.canonical_name, appearance=appearance, body=row.body, face=row.face,
            hair=row.hair, clothing=clothing, distinguishing_features=_dedupe(row.distinguishing_features),
            immutable_traits=immutable_traits, consistency_key=_stable_id("character-consistency", row.character_id, appearance, row.face, row.hair),
            metadata={"agent": "VisualPlanningAgent", "source_profile_id": profile.profile_id, "grounded_identity_cue": identity_cue},
        ))
    return results


def _build_character_scene_states(state: VisualGenerationState, payload: VisualPlanningPayload, baselines: list[CharacterVisualBaselineArtifact], scenes: list[SceneProseArtifact]) -> list[CharacterSceneStateArtifact]:
    baseline_map = {item.character_id: item for item in baselines}
    valid = {(scene.source_scene_id, ref) for scene in scenes for ref in scene.character_refs}
    return [CharacterSceneStateArtifact(
        state_id=_stable_id("character-scene-state", state["story_id"], row.source_scene_id, row.character_id),
        series_id=state["series_id"], story_id=state["story_id"], source_scene_id=row.source_scene_id,
        character_id=row.character_id, expression=row.expression, pose=row.pose, clothing_state=row.clothing_state,
        physical_condition=row.physical_condition, action=row.action, baseline_id=baseline_map[row.character_id].baseline_id,
        metadata={"agent": "VisualPlanningAgent"},
    ) for row in payload.character_scene_states if (row.source_scene_id, row.character_id) in valid and row.character_id in baseline_map]


def _build_entity_dossiers(state: VisualGenerationState, payload: VisualPlanningPayload, entities: list[EntityArtifact], world_states: list[WorldStateArtifact]) -> list[EntityVisualDossierArtifact]:
    entity_map = {item.entity_id: item for item in entities}
    world_map = {item.entity_id: item for item in world_states}
    results = []
    for row in payload.entities:
        entity = entity_map.get(row.entity_id)
        if not entity:
            continue
        visual_type = _entity_visual_type(entity.entity_type)
        if not visual_type:
            continue
        world = world_map.get(entity.entity_id)
        description = row.visual_description or (world.description if world else "") or entity.description
        results.append(EntityVisualDossierArtifact(
            dossier_id=_stable_id("entity-visual-dossier", state["story_id"], row.entity_id), series_id=state["series_id"], story_id=state["story_id"],
            entity_id=row.entity_id, canonical_name=entity.canonical_name, entity_type=visual_type, visual_description=description,
            materials=_dedupe(row.materials), colors=_dedupe(row.colors), scale=row.scale, distinguishing_features=_dedupe(row.distinguishing_features),
            consistency_key=_stable_id("entity-consistency", row.entity_id, description, *row.distinguishing_features),
            metadata={"agent": "VisualPlanningAgent", "source_entity_type": entity.entity_type},
        ))
    return results


def _build_scene_plans(state: VisualGenerationState, payload: VisualPlanningPayload, scenes: list[SceneProseArtifact]) -> list[SceneVisualPlanArtifact]:
    scene_map = {item.source_scene_id: item for item in scenes}
    results = []
    for row in payload.scenes:
        scene = scene_map.get(row.source_scene_id)
        if not scene:
            continue
        results.append(SceneVisualPlanArtifact(
            plan_id=_stable_id("scene-visual-plan", state["story_id"], row.source_scene_id), series_id=state["series_id"], story_id=state["story_id"],
            source_scene_id=row.source_scene_id, title=scene.title, composition=row.composition, environment=row.environment,
            lighting=row.lighting, mood=row.mood, camera=row.camera, action=row.action,
            visible_character_names=_dedupe(row.visible_character_names),
            character_refs=list(scene.character_refs), entity_refs=list(scene.entity_refs), metadata={"agent": "VisualPlanningAgent"},
        ))
    return results


def _prompt_artifact(
    state: VisualGenerationState,
    target_type: str,
    target_ref: str,
    body: str,
    *,
    versions: dict[str, str],
    consistency_keys: list[str],
    source_scene_id: str = "",
    scene_character_names: list[str] | None = None,
    character_clothing: str = "",
) -> VisualPromptArtifact:
    positive, negative, mode = compile_prompt(
        target_type=target_type,
        body=body,
        scene_character_names=scene_character_names,
    )
    metadata: dict[str, Any] = {"agent": "VisualPromptAgent", "policy_version": "visual-prompt-policy-v5"}
    if target_type == "character":
        clothing = " ".join(str(character_clothing or "").split())
        metadata["expected_character_clothing"] = clothing
        metadata["requires_footwear"] = (
            not bool(re.search(r"\b(?:barefoot|unshod)\b", clothing, flags=re.IGNORECASE))
            and bool(re.search(r"\b(?:boot|shoe|combat|durable|practical|court|travel)\w*\b", clothing, flags=re.IGNORECASE))
        )
    elif target_type == "scene":
        metadata["expected_visible_human_count"] = len(
            [name for name in (scene_character_names or []) if str(name).strip()]
        )
    elif target_type in {"location", "creature", "object"}:
        metadata["expected_visible_human_count"] = 0
    return VisualPromptArtifact(
        prompt_id=_stable_id("visual-prompt", state["story_id"], target_type, target_ref), series_id=state["series_id"], story_id=state["story_id"],
        target_type=target_type, target_ref=target_ref, source_scene_id=source_scene_id, workflow_mode=mode,
        positive_prompt=positive, negative_prompt=negative, workflow_version=str(versions.get(mode) or "unknown"),
        width=768 if target_type == "scene" else 512,
        consistency_keys=_dedupe(consistency_keys), metadata=metadata,
    )


def _profile_visual_source(profile: CharacterProfileArtifact) -> dict[str, Any]:
    payload = profile.model_dump()
    payload["grounded_identity_cue"] = _grounded_identity_cue(profile)
    return payload


def _grounded_identity_cue(profile: CharacterProfileArtifact) -> str:
    evidence = " ".join([
        profile.overview,
        profile.role_or_archetype,
        profile.first_seen_summary,
        profile.latest_state_summary,
    ]).casefold()
    female = bool(re.search(r"\b(?:female|woman|girl|sister|daughter|mother|wife)\b", evidence))
    male = bool(re.search(r"\b(?:male|man|boy|brother|son|father|husband)\b", evidence))
    if female == male:
        return ""
    return "female" if female else "male"


def _is_unspecified_visual_detail(value: str) -> bool:
    normalized = " ".join(str(value or "").casefold().split()).strip(" .;:-")
    return not normalized or normalized in {"unspecified", "not specified", "unknown", "neutral"}


def _refs_matching_structured_cast(
    plan: SceneVisualPlanArtifact,
    baselines: dict[str, CharacterVisualBaselineArtifact],
    refs: list[str],
    cast_names: list[str],
) -> list[str]:
    if not plan.visible_character_names:
        return refs
    cast = {name.casefold() for name in cast_names}
    return [
        ref for ref in refs
        if ref in baselines and baselines[ref].canonical_name.casefold() in cast
    ]


def _select_prompts(prompts: list[VisualPromptArtifact], *, include_types: list[str], max_per_type: int) -> list[VisualPromptArtifact]:
    allowed = {str(item).strip().lower() for item in include_types if str(item).strip()}
    selected = [item for item in prompts if not allowed or item.target_type in allowed]
    if max_per_type <= 0:
        return selected
    counts: dict[str, int] = {}
    limited = []
    for item in selected:
        if counts.get(item.target_type, 0) >= max_per_type:
            continue
        counts[item.target_type] = counts.get(item.target_type, 0) + 1
        limited.append(item)
    return limited


def _scope_planning_inputs(
    *,
    scenes: list[SceneProseArtifact],
    profiles: list[CharacterProfileArtifact],
    entities: list[EntityArtifact],
    world_states: list[WorldStateArtifact],
    include_types: list[str],
    max_per_type: int,
) -> tuple[list[SceneProseArtifact], list[CharacterProfileArtifact], list[EntityArtifact], list[WorldStateArtifact]]:
    if max_per_type <= 0:
        return scenes, profiles, entities, world_states
    allowed = {str(item).strip().lower() for item in include_types if str(item).strip()}
    if not allowed:
        allowed = {"character", "location", "creature", "object", "scene"}
    selected_scenes = scenes[:max_per_type] if "scene" in allowed else []
    character_ids = {ref for scene in selected_scenes for ref in scene.character_refs}
    if "character" in allowed:
        character_ids.update(item.character_id for item in profiles[:max_per_type])
    entity_ids = {ref for scene in selected_scenes for ref in scene.entity_refs}
    for target_type in ("location", "creature", "object"):
        if target_type not in allowed:
            continue
        matches = [item for item in entities if _entity_visual_type(item.entity_type) == target_type]
        entity_ids.update(item.entity_id for item in matches[:max_per_type])
    selected_profiles = [item for item in profiles if item.character_id in character_ids]
    selected_entities = [item for item in entities if item.entity_id in entity_ids]
    selected_world_states = [item for item in world_states if item.entity_id in entity_ids]
    return selected_scenes, selected_profiles, selected_entities, selected_world_states


def _entity_visual_type(value: str) -> str | None:
    normalized = str(value or "").strip().lower()
    if any(token in normalized for token in ("location", "place", "building", "room", "estate", "court", "forest", "city", "land", "kingdom", "island")):
        return "location"
    if any(token in normalized for token in ("creature", "animal", "beast", "monster", "horse", "bird", "serpent")):
        return "creature"
    if any(token in normalized for token in ("object", "artifact", "weapon", "item", "book", "letter", "crown", "knife", "sword", "bridle", "ring")):
        return "object"
    return None


def _scene_cast_names(
    plan: SceneVisualPlanArtifact,
    baselines: dict[str, CharacterVisualBaselineArtifact],
    visible_character_refs: list[str],
) -> list[str]:
    if plan.visible_character_names:
        return _dedupe(plan.visible_character_names)
    plan_text = " ".join([
        plan.composition, plan.environment, plan.lighting, plan.mood, plan.camera, plan.action,
    ])
    local_character_ids = re.findall(
        r"\btype\s*:\s*character\s*;\s*id\s*:\s*([a-z0-9][a-z0-9-]*)",
        plan_text.casefold(),
    )
    if local_character_ids:
        return _dedupe(item.replace("-", " ").title() for item in local_character_ids)
    explicit_refs = re.findall(r"\bchar-[a-z0-9][a-z0-9-]*", plan_text.casefold())
    refs = _dedupe([*visible_character_refs, *explicit_refs])
    names = []
    for ref in refs:
        baseline = baselines.get(ref)
        names.append(baseline.canonical_name if baseline else ref.removeprefix("char-").replace("-", " ").title())
    return _dedupe(names)


def _scene_visible_character_refs(
    plan: SceneVisualPlanArtifact,
    scene_states: list[CharacterSceneStateArtifact],
) -> list[str]:
    states = {
        item.character_id: item
        for item in scene_states
        if item.source_scene_id == plan.source_scene_id
    }
    offscreen_markers = (
        "implied presence",
        "implied reference",
        "off-screen",
        "offscreen",
        "not present",
        "mentioned only",
        "reference only",
    )
    visible: list[str] = []
    for ref in plan.character_refs:
        state = states.get(ref)
        state_text = " ".join([
            state.expression,
            state.pose,
            state.physical_condition,
            state.action,
        ]).casefold() if state else ""
        if state and any(marker in state_text for marker in offscreen_markers):
            continue
        visible.append(ref)
    return _dedupe(visible)


def _latest_audits(audits: list[VisualQualityDecisionArtifact]) -> dict[str, VisualQualityDecisionArtifact]:
    latest: dict[str, VisualQualityDecisionArtifact] = {}
    for item in audits:
        attempt = int((item.metadata or {}).get("attempt") or 0)
        current = latest.get(item.prompt_id)
        if current is None or attempt >= int((current.metadata or {}).get("attempt") or 0):
            latest[item.prompt_id] = item
    return latest


def _serialize_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: [_as_dict(item) for item in value] if isinstance(value, list) else _as_dict(value) for key, value in context.items() if key not in {"book_map"}}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict): return dict(value)
    if hasattr(value, "model_dump"): return value.model_dump()
    return {}


def _resolve_checkpointer(persistence: PersistenceRuntimeClient, checkpointer: BaseCheckpointSaver | None, allow_memory: bool) -> BaseCheckpointSaver:
    if checkpointer is not None: return checkpointer
    if getattr(persistence, "engine", None) is not None: return SqlCheckpointSaver(engine=persistence.engine)
    if allow_memory: return InMemorySaver()
    raise ValueError("VisualGenerationRuntime requires a durable checkpointer or initialized persistence engine.")


def _stage_metadata(state: VisualGenerationState, stage: str, started: float, **metrics: Any) -> dict[str, Any]:
    metadata = dict(state.get("run_metadata") or {}); stages = dict(metadata.get("stage_metrics") or {})
    stages[stage] = {"elapsed_seconds": round(time.perf_counter() - started, 4), **metrics}; metadata["stage_metrics"] = stages
    return metadata


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _score(value: Any) -> float:
    try: return round(max(0.0, min(1.0, float(value))), 4)
    except Exception: return 0.0


def _semantic_request_lineage(semantic: dict[str, Any]) -> dict[str, str]:
    metadata = dict(semantic.get("request_metadata") or {})
    return {
        key: str(metadata[key])
        for key in ("provider", "resolved_model", "status", "account_name")
        if metadata.get(key) not in (None, "")
    }


def _cast_audit_lineage(semantic: dict[str, Any]) -> dict[str, Any]:
    audit = dict(semantic.get("cast_audit") or {})
    if not audit:
        return {}
    return {
        "passed": audit.get("passed") is True,
        "expected_visible_human_count": int(audit.get("expected_visible_human_count") or 0),
        "observed_visible_human_count": int(audit.get("observed_visible_human_count") or 0),
        "uncertain_count": int(audit.get("uncertain_count") or 0),
        "detections": [str(item) for item in list(audit.get("detections") or []) if str(item).strip()],
        "request_metadata": sanitize(dict(audit.get("request_metadata") or {})),
    }


def _character_consistency_audit_lineage(semantic: dict[str, Any]) -> dict[str, Any]:
    audit = dict(semantic.get("character_consistency_audit") or {})
    if not audit:
        return {}
    return {
        key: audit.get(key)
        for key in (
            "passed", "same_clothing_all_views", "same_sleeve_length_all_views",
            "same_footwear_all_views", "all_views_full_body", "required_clothing_match_all_views",
            "visible_skin_tight_bodysuit", "visible_transparent_or_sheer_clothing",
            "visible_barefoot_any_view", "requires_footwear", "evidence",
        )
    }


def _issues_contain_hard_violation(issues: list[str]) -> bool:
    markers = ("violates", "violation", "forbidden", "identity drift", "malformed anatomy")
    return any(any(marker in str(issue).lower() for marker in markers) for issue in issues)


def _blocking_hard_violations(violations: list[str], *, scores: dict[str, float]) -> list[str]:
    del scores
    return violations


def _dedupe(values: list[Any]) -> list[str]:
    seen = set(); results = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text.casefold() not in seen: seen.add(text.casefold()); results.append(text)
    return results


def _description_text(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(
            f"{str(key).replace('_', ' ')}: {_description_text(item)}"
            for key, item in value.items()
            if _description_text(item)
        )
    if isinstance(value, list):
        return ", ".join(_description_text(item) for item in value if _description_text(item))
    return " ".join(str(value or "").split())


def _bounded_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return clipped or text[:limit]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _dedupe(value)
    if isinstance(value, dict):
        return [_description_text(value)]
    text = " ".join(str(value).split())
    return [text] if text else []


def _max_attempt(renders: list[VisualRenderArtifact]) -> int:
    return max([item.attempt for item in renders] or [1])


def _merge_models(existing: list[Any], additions: list[Any], *, key: Callable[[Any], Any]) -> list[Any]:
    merged = {key(item): item for item in existing}
    for item in additions:
        merged[key(item)] = item
    return list(merged.values())
