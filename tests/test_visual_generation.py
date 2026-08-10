from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter
from unittest.mock import Mock, patch

from packages.canon_extraction.contracts import EntityArtifact
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.contracts import CharacterProfileArtifact, WorldStateArtifact
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.narrative_generation.contracts import GeneratedStoryArtifact, SceneProseArtifact
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client
from packages.visual_generation import VisualGenerationRuntime
from packages.visual_generation.contracts import (
    CharacterVisualBaselineArtifact,
    CharacterSceneStateArtifact,
    SceneVisualPlanArtifact,
    VisualPromptArtifact,
)
from packages.visual_generation.pipeline import (
    CharacterPlanPayload,
    VisualPlanningPayload,
    _build_baselines,
    _build_category_planning_prompt,
    _blocking_hard_violations,
    _refs_matching_structured_cast,
    _scene_cast_names,
    _scene_visible_character_refs,
)
from packages.visual_generation.prompt_policy import compile_prompt
from packages.visual_generation.quality import evaluate_image_technical_quality
from packages.visual_generation.vision import ReasoningVisionSemanticEvaluator


class StubPlanningRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, *args, **kwargs):
        del args, kwargs
        self.calls += 1
        return {
            "characters": [{
                "character_id": "char-jude",
                "appearance": "young woman with angular features",
                "body": "athletic build",
                "face": "sharp cheekbones",
                "hair": "dark brown hair",
                "clothing": "weathered dark traveling clothes",
                "distinguishing_features": ["scarred left hand"],
                "immutable_traits": ["dark brown hair"],
            }],
            "character_scene_states": [{
                "source_scene_id": "scene-1",
                "character_id": "char-jude",
                "expression": "watchful",
                "pose": "standing at the threshold",
                "clothing_state": "rain dampened",
                "physical_condition": "tired",
                "action": "holding the silver key",
            }],
            "entities": [
                {"entity_id": "entity-palace", "visual_description": "weathered hilltop palace crowded with revelers", "materials": ["stone"], "colors": ["gray"], "scale": "large"},
                {"entity_id": "entity-griffin", "visual_description": "lion-bodied eagle-winged creature", "materials": ["feathers"], "colors": ["gold"]},
                {"entity_id": "entity-key", "visual_description": "ornate silver key", "materials": ["silver"], "colors": ["silver"], "scale": "handheld"},
            ],
            "scenes": [{
                "source_scene_id": "scene-1",
                "composition": "Jude centered at the palace threshold while char-archivist kneels beside the gate",
                "environment": "rain-soaked hilltop palace",
                "lighting": "cold dawn",
                "mood": "tense",
                "camera": "medium-wide eye-level frame",
                "action": "a griffin watches as Jude raises the key",
            }],
        }

    def last_request_metadata(self):
        return {"provider": "stub", "resolved_model": "visual-planner", "status": "ok"}


class ListEntityPlanningRuntime(StubPlanningRuntime):
    def generate_json(self, prompt: str, **kwargs):
        payload = super().generate_json(prompt, **kwargs)
        if "key entities only" in prompt:
            return payload["entities"]
        if "key scenes only" in prompt:
            return payload["scenes"]
        return payload


class RepairingPlanningRuntime(StubPlanningRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.character_calls = 0

    def generate_json(self, prompt: str, **kwargs):
        payload = super().generate_json(prompt, **kwargs)
        if "keys characters and character_scene_states" in prompt:
            self.character_calls += 1
            if self.character_calls == 1:
                return {"characters": [], "character_scene_states": []}
        return payload


class StubImageProvider:
    def __init__(self, *, black_first: bool = False) -> None:
        self.black_first = black_first
        self.calls: list[dict] = []

    def render(self, **kwargs):
        self.calls.append(dict(kwargs))
        black = self.black_first and len(self.calls) == 1
        return {
            "response": {"image_bytes": _png(
                black=black,
                width=int(kwargs.get("width") or 512),
                height=int(kwargs.get("height") or 512),
            )},
            "token_name": "modal-account-1",
        }


class StubSemanticEvaluator:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.calls = 0

    def evaluate(self, **kwargs):
        del kwargs
        self.calls += 1
        if self.accepted:
            return {
                "prompt_alignment_score": 0.93,
                "subject_consistency_score": 0.88,
                "composition_score": 0.84,
                "photorealism_score": 0.81,
                "defect_score": 0.08,
                "issues": [],
                "request_metadata": {
                    "provider": "mistral",
                    "resolved_model": "mistral-small-2603",
                    "status": "ok",
                },
            }
        return {
            "prompt_alignment_score": 0.25,
            "subject_consistency_score": 0.2,
            "composition_score": 0.4,
            "photorealism_score": 0.3,
            "defect_score": 0.8,
            "issues": ["prompt mismatch"],
        }


class ContradictorySemanticEvaluator(StubSemanticEvaluator):
    def evaluate(self, **kwargs):
        result = super().evaluate(**kwargs)
        result["issues"] = ["Human figure violates the no-people constraint"]
        return result


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="visual-generation-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'visual.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _seed(client, *, accepted: bool = True) -> None:
    series_id = "series-1"
    narrative = NarrativeGenerationStore(client)
    narrative.upsert_story(GeneratedStoryArtifact(
        story_id="story-1",
        series_id=series_id,
        blueprint_id="blueprint-1",
        title="The Silver Threshold",
        premise="Jude returns to a guarded palace.",
        character_refs=["char-jude"],
        entity_refs=["entity-palace", "entity-griffin", "entity-key"],
        metadata={"semantic_support": {"accepted": accepted, "status": "accepted" if accepted else "rejected"}},
    ))
    narrative.replace_scene_prose(series_id=series_id, story_id="story-1", scenes=[SceneProseArtifact(
        scene_prose_id="scene-prose-1",
        series_id=series_id,
        story_id="story-1",
        blueprint_id="blueprint-1",
        source_scene_id="scene-1",
        chapter_index=1,
        scene_index=1,
        title="At the Threshold",
        prose="Jude reaches the palace at dawn while the griffin guards the gate and the silver key warms in her hand.",
        character_refs=["char-jude"],
        entity_refs=["entity-palace", "entity-griffin", "entity-key"],
    )])
    CharacterWorldModelingStore(client).replace_character_profiles(series_id=series_id, profiles=[CharacterProfileArtifact(
        profile_id="profile-jude",
        series_id=series_id,
        character_id="char-jude",
        canonical_name="Jude",
        overview="A mortal warrior in Faerie.",
        visual_cues=["dark hair", "scarred hand"],
    )])
    entities = [
        EntityArtifact(entity_id="entity-palace", series_id=series_id, canonical_name="Hill Palace", entity_type="location", description="A stone palace."),
        EntityArtifact(entity_id="entity-griffin", series_id=series_id, canonical_name="Gate Griffin", entity_type="creature", description="A winged guardian."),
        EntityArtifact(entity_id="entity-key", series_id=series_id, canonical_name="Silver Key", entity_type="artifact", description="An ornate key."),
    ]
    CanonExtractionStore(client).replace_entities(series_id=series_id, entities=entities)
    CharacterWorldModelingStore(client).replace_world_states(series_id=series_id, world_states=[
        WorldStateArtifact(world_state_id=f"world-{item.entity_id}", series_id=series_id, entity_id=item.entity_id, canonical_name=item.canonical_name, entity_type=item.entity_type, description=item.description)
        for item in entities
    ])


def _png(*, black: bool, width: int = 512, height: int = 512) -> bytes:
    image = Image.new("RGB", (width, height), (0, 0, 0))
    if not black:
        pixels = image.load()
        for y in range(height):
            for x in range(width):
                pixels[x, y] = (
                    (x * 3 + y) % 256,
                    (x + y * 5) % 256,
                    ((x + y) * 7) % 256,
                )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _runtime(client, image_provider, semantic_evaluator, seeds):
    iterator = iter(seeds)
    return VisualGenerationRuntime(
        persistence=client,
        reasoning_runtime=StubPlanningRuntime(),
        image_provider=image_provider,
        semantic_evaluator=semantic_evaluator,
        allow_in_memory_checkpointer=True,
        seed_factory=lambda: next(iterator),
    )


def test_technical_quality_accepts_valid_highly_compressed_png():
    image_bytes = _png(black=False)

    result = evaluate_image_technical_quality(image_bytes, expected_width=512, expected_height=512)

    assert result["passed"] is True
    assert result["issues"] == []


def test_technical_quality_rejects_soft_focus_image():
    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)
    for offset in range(0, 512, 16):
        draw.line((offset, 0, 511 - offset, 511), fill="black", width=4)
    image = image.filter(ImageFilter.GaussianBlur(radius=10))
    output = io.BytesIO()
    image.save(output, format="PNG")

    result = evaluate_image_technical_quality(
        output.getvalue(), expected_width=512, expected_height=512, target_type="creature"
    )

    assert result["passed"] is False
    assert "soft_or_blurred_image" in result["issues"]


def test_technical_quality_rejects_central_scene_collage_seam():
    image = Image.new("RGB", (512, 512))
    pixels = image.load()
    for y in range(512):
        for x in range(512):
            pixels[x, y] = (
                ((x * 5) % 256, (y * 7) % 256, ((x + y) * 11) % 256)
                if y < 256
                else ((x * 13) % 256, (y * 3) % 256, 255)
            )
    output = io.BytesIO()
    image.save(output, format="PNG")

    result = evaluate_image_technical_quality(
        output.getvalue(), expected_width=512, expected_height=512, target_type="scene"
    )

    assert result["passed"] is False
    assert "central_horizontal_seam_or_collage" in result["issues"]


def test_scene_prompt_enforces_unique_whole_image_cast_cardinality():
    positive, negative, mode = compile_prompt(
        target_type="scene",
        body="Azriel opens the scroll while Elain watches and Cassian stands by the fire.",
        scene_character_names=["Azriel", "Elain", "Cassian", "Azriel"],
    )

    assert "EXACTLY 3 PEOPLE TOTAL" in positive
    assert "Azriel, Elain, Cassian" in positive
    assert "Show each named person exactly once" in positive
    assert "background people" in negative
    assert "one frozen instant" in positive
    assert "split screen" in negative
    assert mode == "entity_generation"


def test_scene_cast_excludes_characters_that_are_only_offscreen_references():
    plan = SceneVisualPlanArtifact(
        plan_id="plan-1", series_id="series-1", story_id="story-1",
        source_scene_id="scene-1", character_refs=["char-present", "char-mentioned"],
    )
    states = [
        CharacterSceneStateArtifact(
            state_id="state-present", series_id="series-1", story_id="story-1",
            source_scene_id="scene-1", character_id="char-present", action="opens the ledger",
        ),
        CharacterSceneStateArtifact(
            state_id="state-mentioned", series_id="series-1", story_id="story-1",
            source_scene_id="scene-1", character_id="char-mentioned",
            action="implied reference as the absent High King",
        ),
    ]

    assert _scene_visible_character_refs(plan, states) == ["char-present"]


def test_scene_cast_prefers_explicit_story_local_character_ids():
    plan = SceneVisualPlanArtifact(
        plan_id="plan-1",
        series_id="series-1",
        story_id="story-1",
        source_scene_id="scene-1",
        character_refs=["char-taryn"],
        composition="foreground: type: character; id: archivist-elara-vey; pose: reading",
    )
    baselines = {
        "char-taryn": CharacterVisualBaselineArtifact(
            baseline_id="baseline-1",
            series_id="series-1",
            story_id="story-1",
            character_id="char-taryn",
            canonical_name="Taryn",
            consistency_key="taryn-key",
        )
    }

    assert _scene_cast_names(plan, baselines, ["char-taryn"]) == ["Archivist Elara Vey"]


def test_scene_cast_uses_structured_visible_character_names_as_authority():
    plan = SceneVisualPlanArtifact(
        plan_id="plan-1",
        series_id="series-1",
        story_id="story-1",
        source_scene_id="scene-1",
        character_refs=["char-taryn"],
        visible_character_names=["Elara Vey"],
    )

    assert _scene_cast_names(plan, {}, ["char-taryn"]) == ["Elara Vey"]

    positive, _, _ = compile_prompt(
        target_type="scene", body="Elara reads the oath.", scene_character_names=["Elara Vey"]
    )
    assert "EXACTLY 1 PERSON TOTAL" in positive


def test_character_baseline_preserves_grounded_female_identity_when_planner_is_neutral():
    profile = CharacterProfileArtifact(
        profile_id="profile-jude",
        series_id="series-1",
        character_id="char-jude",
        canonical_name="Jude",
        overview="Jude is Taryn's mortal twin sister and she protects her family.",
    )
    payload = VisualPlanningPayload(characters=[CharacterPlanPayload(
        character_id="char-jude", appearance="neutral presentation", body="average build"
    )])

    baseline = _build_baselines(
        {"series_id": "series-1", "story_id": "story-1"}, payload, [profile]
    )[0]

    assert "female" in baseline.appearance
    assert "female" in baseline.immutable_traits
    assert baseline.clothing == "plain practical pre-industrial tunic, fitted trousers, and simple boots"
    assert baseline.metadata["grounded_identity_cue"] == "female"


def test_scene_planning_excludes_people_only_named_in_documents():
    story = GeneratedStoryArtifact(
        story_id="story-1", series_id="series-1", blueprint_id="blueprint-1"
    )
    scene = SceneProseArtifact(
        scene_prose_id="prose-1", series_id="series-1", story_id="story-1",
        blueprint_id="blueprint-1", source_scene_id="scene-1", chapter_index=1,
        scene_index=1, prose="Elara reads signatures belonging to Taryn and Locke."
    )

    prompt = _build_category_planning_prompt(
        category="scenes", story=story, scenes=[scene], profiles=[], entities=[], world_states=[]
    )

    assert "named in a signature or document" in prompt
    assert "physical body is visibly present" in prompt


def test_structured_scene_cast_removes_off_camera_character_reference_text():
    plan = SceneVisualPlanArtifact(
        plan_id="plan-1", series_id="series-1", story_id="story-1",
        source_scene_id="scene-1", character_refs=["char-taryn", "char-locke"],
        visible_character_names=["Elara"],
    )
    baselines = {
        ref: CharacterVisualBaselineArtifact(
            baseline_id=f"baseline-{ref}", series_id="series-1", story_id="story-1",
            character_id=ref, canonical_name=name,
        )
        for ref, name in (("char-taryn", "Taryn"), ("char-locke", "Locke"))
    }

    assert _refs_matching_structured_cast(
        plan, baselines, ["char-taryn", "char-locke"], ["Elara"]
    ) == []


def test_semantic_hard_violations_always_block_even_when_scores_conflict():
    violations = ["Character name mismatch", "Scene type violation"]

    assert _blocking_hard_violations(
        violations,
        scores={"prompt_alignment_score": 0.85, "defect_score": 0.15},
    ) == violations
    assert _blocking_hard_violations(
        violations,
        scores={"prompt_alignment_score": 0.4, "defect_score": 0.6},
    ) == violations


def test_vision_evaluator_does_not_require_written_character_names():
    class CapturingRuntime:
        prompt = ""

        def generate_vision_json(self, *, prompt, image_bytes):
            self.prompt = prompt
            assert image_bytes
            return {
                "prompt_alignment_score": 0.9,
                "subject_consistency_score": 0.9,
                "composition_score": 0.9,
                "photorealism_score": 0.9,
                "defect_score": 0.1,
                "issues": [],
                "hard_constraint_violations": [],
            }

        def last_request_metadata(self):
            return {"provider": "test"}

    runtime = CapturingRuntime()
    evaluator = ReasoningVisionSemanticEvaluator(runtime)
    evaluator.evaluate(
        image_bytes=_png(black=False),
        prompt=VisualPromptArtifact(
            prompt_id="prompt-1", series_id="series-1", story_id="story-1",
            target_type="scene", target_ref="scene-1", workflow_mode="entity_generation",
            positive_prompt="Show exactly two people: Apollo and Evangeline.", negative_prompt="text, watermark",
        ),
    )

    assert "must never appear as written labels" in runtime.prompt
    assert "count visible human figures" in runtime.prompt
    assert "omitted minor expression" in runtime.prompt


def test_vision_evaluator_rejects_mismatched_tiled_hard_cast():
    class CountingRuntime:
        calls = 0

        def generate_vision_json(self, *, prompt, image_bytes):
            self.calls += 1
            if self.calls == 1:
                return {
                    "prompt_alignment_score": 0.9,
                    "subject_consistency_score": 0.9,
                    "composition_score": 0.9,
                    "photorealism_score": 0.9,
                    "defect_score": 0.1,
                    "issues": [],
                    "hard_constraint_violations": [],
                }
            return {
                "visible_head_center_count": 1 if self.calls in {2, 3} else 0,
                "detections": [],
                "uncertain_count": 0,
            }

        def last_request_metadata(self):
            return {"provider": "test"}

    evaluator = ReasoningVisionSemanticEvaluator(CountingRuntime())
    result = evaluator.evaluate(
        image_bytes=_png(black=False),
        prompt=VisualPromptArtifact(
            prompt_id="prompt-1", series_id="series-1", story_id="story-1",
            target_type="scene", target_ref="scene-1", workflow_mode="entity_generation",
            positive_prompt="Show exactly one person.", negative_prompt="extra people",
            metadata={"expected_visible_human_count": 1},
        ),
    )

    assert result["cast_audit"]["observed_visible_human_count"] == 2
    assert result["cast_audit"]["passed"] is False
    assert result["prompt_alignment_score"] == 0.4
    assert result["defect_score"] == 0.6
    assert result["hard_constraint_violations"]


def test_full_graph_routes_all_types_and_persists_images(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    provider = StubImageProvider()
    result = _runtime(client, provider, StubSemanticEvaluator(), range(100, 120)).invoke(
        series_id="series-1", story_id="story-1", thread_id="accepted-run",
    )

    assert result.decision.accepted is True
    assert {item.target_type for item in result.prompts} == {"character", "location", "creature", "object", "scene"}
    assert {call["workflow_mode"] for call in provider.calls if call["workflow_mode"] == "character_sheet"} == {"character_sheet"}
    assert len([call for call in provider.calls if call["workflow_mode"] == "entity_generation"]) == 4
    assert len({item.seed for item in result.renders}) == len(result.renders) == 5
    assert all(item.object_path and client.objects.download_bytes(item.bucket_name, item.object_path) for item in result.renders)
    location_prompt = next(item for item in result.prompts if item.target_type == "location")
    assert "crowded with revelers" not in location_prompt.positive_prompt
    assert "Unoccupied static environment reference" in location_prompt.positive_prompt
    scene_prompt = next(item for item in result.prompts if item.target_type == "scene")
    assert "EXACTLY 2 PEOPLE TOTAL" in scene_prompt.positive_prompt
    assert "Jude" in scene_prompt.positive_prompt
    assert "Archivist" in scene_prompt.positive_prompt
    assert (scene_prompt.width, scene_prompt.height) == (768, 512)
    assert scene_prompt.metadata["policy_version"] == "visual-prompt-policy-v5"
    assert scene_prompt.metadata["expected_visible_human_count"] == 2
    assert location_prompt.metadata["expected_visible_human_count"] == 0
    assert all(
        item.metadata["semantic_request"]["resolved_model"] == "mistral-small-2603"
        for item in result.audits
    )


def test_black_image_retries_with_a_new_seed(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    provider = StubImageProvider(black_first=True)
    result = _runtime(client, provider, StubSemanticEvaluator(), [123, 456]).invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="black-retry",
        include_types=["character"],
        max_attempts=2,
    )

    assert result.decision.accepted is True
    assert [item.seed for item in result.renders] == [123, 456]
    assert [item.status for item in result.renders] == ["technical_rejection", "rendered"]
    assert result.audits[0].status == "retry_required"
    assert result.audits[-1].status == "accepted"


def test_semantic_rejection_is_bounded_and_fails_closed(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    result = _runtime(client, StubImageProvider(), StubSemanticEvaluator(accepted=False), [10, 11]).invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="semantic-rejection",
        include_types=["object"],
        max_attempts=2,
    )

    assert result.decision.accepted is False
    assert len(result.renders) == 2
    assert result.audits[-1].status == "rejected"


def test_reaudit_reuses_persisted_images_without_rendering(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    provider = StubImageProvider()
    runtime = _runtime(client, provider, StubSemanticEvaluator(accepted=False), [10])
    first = runtime.invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="reaudit-source",
        include_types=["object"],
        max_attempts=1,
    )
    assert first.decision.accepted is False

    runtime.semantic_evaluator = StubSemanticEvaluator(accepted=True)
    second = runtime.reaudit(series_id="series-1", story_id="story-1", max_attempts=1)

    assert second.decision.accepted is True
    assert len(provider.calls) == 1
    assert second.renders[0].render_id == first.renders[0].render_id


def test_retry_existing_renders_only_rejected_targets_with_new_seed(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    provider = StubImageProvider()
    seeds = iter([10, 11])
    runtime = VisualGenerationRuntime(
        persistence=client,
        reasoning_runtime=StubPlanningRuntime(),
        image_provider=provider,
        semantic_evaluator=StubSemanticEvaluator(accepted=False),
        allow_in_memory_checkpointer=True,
        seed_factory=lambda: next(seeds),
    )
    first = runtime.invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="retry-source",
        include_types=["character"],
        max_attempts=1,
    )
    assert first.decision.accepted is False

    runtime.semantic_evaluator = StubSemanticEvaluator(accepted=True)
    second = runtime.retry_rejected(series_id="series-1", story_id="story-1", max_attempts=2)

    assert second.decision.accepted is True
    assert [item.seed for item in second.renders] == [10, 11]
    assert len(provider.calls) == 2


def test_category_planner_accepts_top_level_entity_and_scene_lists(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    provider = StubImageProvider()
    runtime = VisualGenerationRuntime(
        persistence=client,
        reasoning_runtime=ListEntityPlanningRuntime(),
        image_provider=provider,
        semantic_evaluator=StubSemanticEvaluator(),
        allow_in_memory_checkpointer=True,
        seed_factory=lambda: 42,
    )
    result = runtime.invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="list-shape",
        include_types=["location"],
        max_attempts=1,
    )
    assert result.decision.accepted is True


def test_category_planner_repairs_missing_character_records_once(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    planner = RepairingPlanningRuntime()
    runtime = VisualGenerationRuntime(
        persistence=client,
        reasoning_runtime=planner,
        image_provider=StubImageProvider(),
        semantic_evaluator=StubSemanticEvaluator(),
        allow_in_memory_checkpointer=True,
        seed_factory=lambda: 43,
    )
    result = runtime.invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="repair-shape",
        include_types=["character"],
        max_attempts=1,
    )
    assert result.decision.accepted is True
    assert planner.character_calls == 2


def test_unaccepted_story_is_blocked_before_planning_or_render(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, accepted=False)
    provider = StubImageProvider()
    runtime = _runtime(client, provider, StubSemanticEvaluator(), [1])

    with pytest.raises(ValueError, match="has not passed narrative semantic support"):
        runtime.invoke(series_id="series-1", story_id="story-1", thread_id="blocked")
    assert provider.calls == []


def test_explicit_semantic_constraint_violation_overrides_high_scores(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    result = _runtime(client, StubImageProvider(), ContradictorySemanticEvaluator(), [1]).invoke(
        series_id="series-1",
        story_id="story-1",
        thread_id="hard-violation",
        include_types=["creature"],
        max_attempts=1,
    )
    assert result.decision.accepted is False
    assert result.audits[0].status == "rejected"


def test_vision_inference_uses_reasoning_runtime_ollama_transport():
    profile = ReasoningProfile(name="vision", mode="gpt_oss", model_override="gemma3:4b", prefer_local_ollama=True)
    client = create_reasoning_client(
        profile_name="vision",
        profile=profile,
        config=ReasoningRuntimeConfig(
            profiles={"vision": profile},
            ollama_local_url="http://localhost:11434/api/generate",
        ),
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": '{"prompt_alignment_score": 0.9}'}

    with patch("packages.reasoning_runtime.client.requests.post", return_value=response) as post:
        result = client.generate_vision_json(prompt="Evaluate", image_bytes=b"png-bytes")

    assert result["prompt_alignment_score"] == 0.9
    assert post.call_args.args[0] == "http://localhost:11434/api/generate"
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "gemma3:4b"
    assert payload["images"]
    assert client.last_request_metadata()["status"] == "ok"


def test_planner_contract_normalizes_nested_provider_descriptions():
    payload = VisualPlanningPayload.model_validate({
        "characters": [{
            "character_id": "char-jude",
            "appearance": {"skin_tone": "pale", "eyes": "brown"},
            "body": {"build": "athletic"},
            "face": {},
            "hair": {"color": "dark brown"},
            "clothing": {"typical": "traveling clothes"},
            "distinguishing_features": "scarred hand",
        }],
        "entities": [{
            "entity_id": "entity-key",
            "visual_description": {"shape": "ornate", "finish": "tarnished"},
            "materials": "silver",
        }],
        "scenes": [{
            "source_scene_id": "scene-1",
            "composition": {"framing": "medium shot", "focus": "the key"},
            "environment": {"location": "palace gate"},
        }],
    })

    assert payload.characters[0].appearance == "skin tone: pale; eyes: brown"
    assert payload.characters[0].distinguishing_features == ["scarred hand"]
    assert payload.entities[0].materials == ["silver"]
    assert payload.scenes[0].composition == "framing: medium shot; focus: the key"


def test_mistral_vision_uses_reasoning_runtime_client():
    profile = ReasoningProfile(name="vision", mode="mistral", model_override="mistral-small-2603")
    client = create_reasoning_client(
        profile_name="vision",
        profile=profile,
        config=ReasoningRuntimeConfig(profiles={"vision": profile}, mistral_api_key="secret"),
    )
    response = Mock()
    response.choices = [Mock(message=Mock(content='{"defect_score": 0.1}'))]
    mistral = Mock()
    mistral.chat.complete.return_value = response
    client._mistral_client = mistral

    result = client.generate_vision_json(prompt="Evaluate", image_bytes=b"png-bytes")

    assert result["defect_score"] == 0.1
    call = mistral.chat.complete.call_args.kwargs
    assert call["model"] == "mistral-small-2603"
    assert call["messages"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
