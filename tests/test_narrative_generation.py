from __future__ import annotations

from pathlib import Path

from packages.generation_planning.contracts import ChapterOutlineItem, GenerationBlueprintArtifact, ScenePlanItem
from packages.generation_planning.store import GenerationPlanningStore
from packages.narrative_generation import NarrativeGenerationRuntime, evaluate_narrative_generation
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


class StubNarrativeReasoningRuntime:
    def __init__(self, *, include_sparse: bool = False) -> None:
        self.include_sparse = include_sparse
        self._last = {}
        self.calls = 0
        self.prompts: list[str] = []

    def provider_name(self) -> str:
        return "mistral"

    def resolved_model_name(self) -> str:
        return "mistral-large-2512"

    def generate_json(self, prompt: str, strict: bool = False, validator=None, max_tokens: int = 4096, response_format=None, tools=None, tool_choice=None):
        self.prompts.append(prompt)
        del strict, validator, max_tokens, response_format, tools, tool_choice
        self.calls += 1
        self._last = {"provider": "mistral", "resolved_model": self.resolved_model_name(), "status": "ok"}
        if self.include_sparse:
            return {"title": "Sparse", "prose": "Too short."}
        return {
            "title": f"Generated Scene {self.calls}",
            "prose": (
                "Fares paused beside the silver notebook, letting its pale cover catch the hallway light. "
                "Kareem waited without rushing him, patient enough to make the silence useful. The old meeting "
                "still mattered, not because it trapped them, but because it gave their next choice a shape. "
                "Fares opened the notebook and named the risk aloud. Kareem answered carefully, keeping their "
                "collaboration steady while the object between them became a promise to continue without breaking "
                "what they already knew."
            ),
        }

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class FailingNarrativeReasoningRuntime(StubNarrativeReasoningRuntime):
    def generate_json(self, *args, **kwargs):
        self.calls += 1
        self._last = {"provider": "mistral", "resolved_model": self.resolved_model_name(), "status": "error"}
        return {"error": "max_retries_exceeded"}


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="narrative-generation-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'narrative_generation.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="narrative-generation-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _seed_blueprint(client, *, series_id: str = "series-1") -> GenerationBlueprintArtifact:
    blueprint = GenerationBlueprintArtifact(
        blueprint_id="blueprint-1",
        series_id=series_id,
        intent_id="intent-1",
        grounding_id="grounding-1",
        title="A Grounded Sequel Plan",
        premise="Plan a canon-grounded sequel.",
        continuation_plan="Continue from known facts.",
        divergence_plan="No unsupported divergence.",
        chapter_outline=[
            ChapterOutlineItem(
                chapter_index=1,
                title="The Notebook Reopens",
                goal="Use the notebook as a grounded inciting object.",
                canon_refs=["event-meeting"],
                character_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-silver-notebook"],
            )
        ],
        scene_plan=[
            ScenePlanItem(
                scene_id="planned-scene-1-1",
                chapter_index=1,
                scene_index=1,
                summary="Fares and Kareem revisit the silver notebook.",
                purpose="Anchor the continuation in known character and object continuity.",
                canon_refs=["event-meeting"],
                character_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-silver-notebook"],
                visual_requirements=["Show the hallway, notebook, and both collaborators."],
                audio_requirements=["Use calm collaborative dialogue pacing."],
            ),
            ScenePlanItem(
                scene_id="planned-scene-1-2",
                chapter_index=1,
                scene_index=2,
                summary="They decide what the notebook requires next.",
                purpose="Move the premise forward without breaking continuity.",
                canon_refs=["event-meeting"],
                character_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-silver-notebook"],
                visual_requirements=["Show the notebook as the central object."],
                audio_requirements=["Use quiet resolve in dialogue."],
            ),
        ],
        canon_refs=["event-meeting"],
        character_refs=["char-fares", "char-kareem"],
        entity_refs=["entity-silver-notebook"],
    )
    GenerationPlanningStore(client).upsert_blueprint(series_id=series_id, blueprint=blueprint)
    return blueprint


def test_narrative_generation_persists_story_and_passes_quality(tmp_path: Path):
    client = _persistence(tmp_path)
    blueprint = _seed_blueprint(client)
    result = NarrativeGenerationRuntime(
        persistence=client,
        reasoning_runtime=StubNarrativeReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", blueprint_id=blueprint.blueprint_id, story_id="story-1")

    assert len(result.scene_prose) == 2
    assert len(result.story.chapters) == 1
    assert len(result.story.chapters[0].scene_prose_ids) == 2
    assert all(scene_id.startswith("scene-prose-") for scene_id in result.story.chapters[0].scene_prose_ids)
    assert client.stories.list_stories(series_id="series-1", limit=10)[0]["story_id"] == "story-1"
    metrics = evaluate_narrative_generation(result, blueprint=blueprint)
    assert metrics.pass_quality_gate is True


def test_narrative_generation_carries_role_identity_context_between_scenes(tmp_path: Path):
    client = _persistence(tmp_path)
    blueprint = _seed_blueprint(client)
    blueprint.premise = "A court archivist discovers an oath."
    GenerationPlanningStore(client).upsert_blueprint(series_id="series-1", blueprint=blueprint)
    reasoning = StubNarrativeReasoningRuntime()

    NarrativeGenerationRuntime(
        persistence=client,
        reasoning_runtime=reasoning,
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", blueprint_id=blueprint.blueprint_id, story_id="story-role-context")

    assert "distinct new story participant" in reasoning.prompts[0]
    assert '"prior_generated_scenes": []' in reasoning.prompts[0]
    assert "Generated Scene 1" in reasoning.prompts[1]
    assert "Preserve role identity and character identity" in reasoning.prompts[1]


def test_narrative_generation_repairs_sparse_provider_output(tmp_path: Path):
    client = _persistence(tmp_path)
    blueprint = _seed_blueprint(client)
    result = NarrativeGenerationRuntime(
        persistence=client,
        reasoning_runtime=StubNarrativeReasoningRuntime(include_sparse=True),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", blueprint_id=blueprint.blueprint_id, story_id="story-1")

    assert all(len(scene.prose.split()) >= 80 for scene in result.scene_prose)
    assert all(check.passed for check in result.story.continuity_checks)


def test_narrative_generation_fallback_remains_usable(tmp_path: Path):
    client = _persistence(tmp_path)
    blueprint = _seed_blueprint(client)
    result = NarrativeGenerationRuntime(
        persistence=client,
        reasoning_runtime=FailingNarrativeReasoningRuntime(),
        allow_in_memory_checkpointer=True,
    ).invoke(series_id="series-1", blueprint_id=blueprint.blueprint_id, story_id="story-1")

    assert len(result.story.chapters[0].prose.split()) >= 80
    assert result.run_metadata["stage_metrics"]["narrative_generation"]["fallback_count"] == 2
