from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.production_orchestration.contracts import ArtifactReference, OrchestrationExecutionLimits, OrchestrationRequest, StageOutcomeArtifact
from packages.production_orchestration.packaging import PackageChapter, PackageSourceBundle, VersionedDeliverablePackager, build_epub
from packages.production_orchestration.bindings import (
    ActiveStageBinding,
    ActiveStageInspector,
    _blueprint_matches_requested_structure,
)
from packages.production_orchestration.pipeline import ProductionOrchestrationRuntime
from packages.production_orchestration.policy import STAGE_ORDER, resolve_stage_plan
from packages.production_orchestration.service import _run_scoped_service
from packages.analysis_foundation import AnalysisFoundationService
from packages.audiobook_generation import AudiobookGenerationService
from packages.canon_extraction import CanonExtractionService
from packages.character_world_modeling import CharacterWorldModelingService
from packages.generation_planning import GenerationPlanningService
from packages.narrative_generation import NarrativeGenerationService, NarrativeSupportService
from packages.visual_generation import VisualGenerationService


class FakeStage:
    def __init__(self, stage: str, *, inspect_accepted: bool = False, fail_calls: set[int] | None = None, revision: int = 1) -> None:
        self.stage = stage
        self.inspect_accepted = inspect_accepted
        self.fail_calls = set(fail_calls or set())
        self.inspect_calls = 0
        self.execute_calls = 0
        self.revision = revision
        self.inspection_contexts: list[set[str]] = []
        self.execution_contexts: list[set[str]] = []

    def inspect(self, *, request, outcomes):
        del request
        self.inspection_contexts.append(set(outcomes))
        self.inspect_calls += 1
        if self.inspect_accepted:
            return _accepted(self.stage)
        return None

    def execute(self, *, request, outcomes):
        del request
        self.execution_contexts.append(set(outcomes))
        self.execute_calls += 1
        if self.execute_calls in self.fail_calls:
            raise RuntimeError(f"{self.stage} failed")
        self.inspect_accepted = True
        return _accepted(self.stage)

    def lineage_output(self, *, request, outcomes, outcome):
        del request, outcomes, outcome
        return {"stage": self.stage, "revision": self.revision}


def test_scoped_stage_service_closes_persistence_on_success_and_failure():
    class Persistence:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class Service:
        def __init__(self, error=None):
            self.persistence = Persistence()
            self.error = error

        def run(self, request):
            if self.error:
                raise self.error
            return request

        def close(self):
            self.persistence.close()

    successful = Service()
    failing = Service(RuntimeError("failed"))

    assert _run_scoped_service(successful, "request") == "request"
    with pytest.raises(RuntimeError, match="failed"):
        _run_scoped_service(failing, "request")

    assert successful.persistence.closed is True
    assert failing.persistence.closed is True


@pytest.mark.parametrize(
    "service_type",
    [
        AnalysisFoundationService,
        CanonExtractionService,
        CharacterWorldModelingService,
        GenerationPlanningService,
        NarrativeGenerationService,
        NarrativeSupportService,
        VisualGenerationService,
        AudiobookGenerationService,
    ],
)
def test_active_stage_services_expose_persistence_lifecycle(service_type):
    persistence = type("Persistence", (), {"closed": False, "close": lambda self: setattr(self, "closed", True)})()
    service = service_type.__new__(service_type)
    service.persistence = persistence

    service.close()

    assert persistence.closed is True


def test_visual_attempt_budget_is_independent_and_bounded():
    limits = OrchestrationExecutionLimits(max_visual_attempts=4)

    assert limits.max_visual_attempts == 4
    with pytest.raises(ValueError):
        OrchestrationExecutionLimits(max_visual_attempts=7)


def test_character_world_stage_accepts_empty_world_when_canon_has_no_entities():
    profile = type("Profile", (), {"character_id": "char-one"})()
    inspector = ActiveStageInspector.__new__(ActiveStageInspector)
    inspector.character_world = type(
        "CharacterWorld",
        (),
        {
            "list_character_profiles": lambda self, series_id: [profile],
            "list_stable_character_states": lambda self, series_id: [profile],
            "list_world_states": lambda self, series_id: [],
        },
    )()
    inspector.canon = type("Canon", (), {"list_entities": lambda self, series_id: []})()
    request = OrchestrationRequest(run_id="run-1", series_id="series-1", project_id="project-1")

    outcome = inspector.character_world_modeling(request, {})

    assert outcome is not None
    assert outcome.metrics["source_entity_count"] == 0
    assert outcome.metrics["world_state_count"] == 0


def test_blueprint_reuse_requires_exact_requested_structure():
    valid = SimpleNamespace(
        chapter_outline=[SimpleNamespace(chapter_index=1)],
        scene_plan=[
            SimpleNamespace(chapter_index=1, scene_index=1),
            SimpleNamespace(chapter_index=1, scene_index=2),
        ],
    )
    duplicate_chapter = SimpleNamespace(
        chapter_outline=[SimpleNamespace(chapter_index=1), SimpleNamespace(chapter_index=1)],
        scene_plan=valid.scene_plan,
    )

    assert _blueprint_matches_requested_structure(valid, desired_chapter_count=1) is True
    assert _blueprint_matches_requested_structure(duplicate_chapter, desired_chapter_count=1) is False


class FakeSource:
    def collect(self, *, request, outcomes):
        del outcomes
        return PackageSourceBundle(
            story_id=request.story_id or "story-1",
            title="The Packaged Story",
            chapters=[PackageChapter(chapter_index=1, title="One", prose="A first paragraph.\n\nA second paragraph.")],
            artifact_refs=[ArtifactReference(
                artifact_id="image-1", role="visual:scene", media_type="image/png",
                bucket_name="images", object_path="accepted/image-1.png", byte_length=1234,
                source_stage="visual_generation",
            )],
            provenance={"source": "test"},
        )


class FakeSink:
    def __init__(self) -> None:
        self.epubs: list[bytes] = []
        self.manifests: list[dict] = []

    def store_epub(self, *, request, filename, data):
        del request, filename
        self.epubs.append(data)
        return ArtifactReference(artifact_id="epub-1", role="generated_epub", media_type="application/epub+zip", bucket_name="stories", object_path="exports/story.epub", byte_length=len(data))

    def store_manifest(self, *, request, filename, payload):
        del request, filename
        self.manifests.append(payload)
        return ArtifactReference(artifact_id="manifest-1", role="deliverable_manifest", media_type="application/json", bucket_name="stories", object_path="exports/manifest.json")


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="production-orchestration-test", provider="supabase", mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'orchestration.sqlite3'}", local_storage_root_dir=str(tmp_path / "storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _bindings(**overrides):
    result = {stage: FakeStage(stage) for stage in STAGE_ORDER if stage != "artifact_packaging"}
    result.update(overrides)
    return result


def _runtime(tmp_path: Path, bindings, sink, *, client=None, version_overrides=None):
    client = client or _persistence(tmp_path)
    runtime = ProductionOrchestrationRuntime(
        persistence=client,
        stages=bindings,
        packager=VersionedDeliverablePackager(source=FakeSource(), sink=sink),
        allow_in_memory_checkpointer=True,
        lineage_version_overrides=version_overrides,
    )
    return client, runtime


def _request(run_id="run-1", **kwargs):
    payload = {
        "run_id": run_id, "series_id": "series-1", "project_id": "project-1", "story_id": "story-1",
        "selected_stages": ["artifact_packaging"], "include_visuals": False, "include_audiobook": False,
    }
    payload.update(kwargs)
    return OrchestrationRequest.model_validate(payload)


def _accepted(stage):
    return StageOutcomeArtifact(stage=stage, status="accepted", accepted=True, output_context={"story_id": "story-1"} if stage in {"narrative_generation", "narrative_support"} else {})


def test_active_stage_binding_propagates_a_persisted_quality_rejection():
    rejected = StageOutcomeArtifact(
        stage="narrative_support",
        status="rejected",
        accepted=False,
        reasons=["Live semantic evaluation did not pass."],
    )
    binding = ActiveStageBinding(
        inspector=lambda request, outcomes: rejected,
        executor=lambda request, outcomes: None,
    )

    outcome = binding.execute(request=_request(), outcomes={})

    assert outcome.status == "rejected"
    assert outcome.reasons == ["Live semantic evaluation did not pass."]


def test_dependency_plan_is_ordered_and_optional_media_is_explicit():
    request = _request()
    assert resolve_stage_plan(request) == list(STAGE_ORDER[:6]) + ["artifact_packaging"]
    with_media = request.model_copy(update={
        "include_visuals": True,
        "include_audiobook": True,
        "selected_stages": ["visual_generation", "audiobook_generation", "artifact_packaging"],
    })
    assert resolve_stage_plan(with_media) == list(STAGE_ORDER)


def test_graph_executes_dependencies_then_packages_and_persists_lineage(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    client, runtime = _runtime(tmp_path, bindings, sink)
    result = runtime.invoke(_request(), thread_id="thread-1")

    assert result.decision.accepted is True
    assert result.manifest is not None
    assert [item.stage for item in result.outcomes] == list(STAGE_ORDER[:6]) + ["artifact_packaging"]
    assert all(bindings[stage].execute_calls == 1 for stage in STAGE_ORDER[:6])
    assert len(sink.epubs) == 1
    assert len(sink.manifests) == 2
    assert sink.manifests[-1] == result.manifest.model_dump()
    job = client.jobs.get_job("run-1")
    assert job["status"] == "accepted"
    assert len(job["logs"]) == 8


def test_unversioned_inspected_artifacts_are_executed_fail_closed(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings(**{stage: FakeStage(stage, inspect_accepted=True) for stage in STAGE_ORDER[:6]})
    client, runtime = _runtime(tmp_path, bindings, sink)
    result = runtime.invoke(_request(), thread_id="thread-reuse")

    assert result.decision.accepted is True
    assert all(not item.reused for item in result.outcomes)
    assert all(bindings[stage].execute_calls == 1 for stage in STAGE_ORDER[:6])


def test_failure_stops_downstream_and_resume_reuses_accepted_stages(tmp_path: Path):
    sink = FakeSink()
    canon = FakeStage("canon_extraction", fail_calls={1})
    bindings = _bindings(canon_extraction=canon)
    _, runtime = _runtime(tmp_path, bindings, sink)
    first = runtime.invoke(_request(max_attempts=1), thread_id="thread-fail")
    assert first.decision.accepted is False
    assert first.decision.failed_stage == "canon_extraction"
    assert bindings["character_world_modeling"].execute_calls == 0

    resumed = runtime.invoke(_request(max_attempts=2), thread_id="thread-resume")
    assert resumed.decision.accepted is True
    assert bindings["analysis_foundation"].execute_calls == 1
    assert canon.execute_calls == 2
    assert bindings["character_world_modeling"].execute_calls == 1


def test_completed_run_is_idempotent_and_does_not_repackage(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    client, runtime = _runtime(tmp_path, bindings, sink)
    first = runtime.invoke(_request(), thread_id="thread-first")
    second = runtime.invoke(_request(), thread_id="thread-second")
    assert len(sink.epubs) == 1
    assert len(sink.manifests) == 2
    assert second.manifest == first.manifest
    assert second.decision.accepted is True
    assert all(bindings[stage].execute_calls == 1 for stage in STAGE_ORDER[:6])
    history = client.lineage.list(run_id="run-1")
    assert len(history) == 7
    assert all(item["execution_mode"] == "executed" for item in history)
    assert all(dict(item["payload"]).get("output_artifact_version") for item in history)


def test_changed_planning_input_invalidates_only_planning_and_downstream(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    client, runtime = _runtime(tmp_path, bindings, sink)
    runtime.invoke(_request(premise="A difficult peace."), thread_id="thread-original")
    changed = runtime.invoke(_request(premise="A broken peace."), thread_id="thread-changed")

    assert changed.decision.accepted is True
    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[:3]] == [1, 1, 1]
    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[3:6]] == [2, 2, 2]
    history = client.lineage.list(run_id="run-1")
    assert len([item for item in history if item["stage"] == "generation_planning"]) == 2
    assert len([item for item in history if item["stage"] == "analysis_foundation"]) == 1
    assert len(sink.epubs) == 2
    assert "generation_planning" not in bindings["generation_planning"].execution_contexts[-1]
    assert "narrative_generation" not in bindings["narrative_generation"].inspection_contexts[-1]
    assert "narrative_support" not in bindings["narrative_generation"].inspection_contexts[-1]


def test_prompt_version_change_invalidates_stage_and_transitive_dependents(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    client, first_runtime = _runtime(tmp_path, bindings, sink)
    first_runtime.invoke(_request(), thread_id="thread-v1")
    _, second_runtime = _runtime(
        tmp_path, bindings, sink, client=client,
        version_overrides={"narrative_generation": {"prompt": "prompt-v2"}},
    )
    second_runtime.invoke(_request(), thread_id="thread-v2")

    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[:4]] == [1, 1, 1, 1]
    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[4:6]] == [2, 2]
    assert len(sink.epubs) == 2


def test_mutated_persisted_output_invalidates_stage_and_downstream(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    _, runtime = _runtime(tmp_path, bindings, sink)
    runtime.invoke(_request(), thread_id="thread-output-v1")
    bindings["character_world_modeling"].revision = 2
    runtime.invoke(_request(), thread_id="thread-output-v2")

    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[:2]] == [1, 1]
    assert [bindings[stage].execute_calls for stage in STAGE_ORDER[2:6]] == [2, 2, 2, 2]


def test_run_identity_cannot_be_rebound_to_another_story(tmp_path: Path):
    sink = FakeSink()
    _, runtime = _runtime(tmp_path, _bindings(), sink)
    runtime.invoke(_request(), thread_id="thread-story-1")
    with pytest.raises(ValueError, match="cannot change story_id"):
        runtime.invoke(_request(story_id="story-2"), thread_id="thread-story-2")


def test_epub_is_valid_zip_with_uncompressed_mimetype_and_escaped_content():
    bundle = PackageSourceBundle(
        story_id="story-1", title="A & B", chapters=[PackageChapter(chapter_index=1, title="One < Two", prose="Jude & Cardan")],
    )
    data = build_epub(bundle)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/epub+zip"
        chapter = archive.read("OEBPS/chapter-001.xhtml").decode()
        assert "One &lt; Two" in chapter
        assert "Jude &amp; Cardan" in chapter


def test_cancellation_stops_at_next_unresolved_stage_and_preserves_accepted_work(tmp_path: Path):
    sink = FakeSink()
    bindings = _bindings()
    client = _persistence(tmp_path)
    checks = {"count": 0}

    def cancellation_checker(run_id):
        del run_id
        checks["count"] += 1
        return checks["count"] >= 2

    runtime = ProductionOrchestrationRuntime(
        persistence=client, stages=bindings,
        packager=VersionedDeliverablePackager(source=FakeSource(), sink=sink),
        allow_in_memory_checkpointer=True, cancellation_checker=cancellation_checker,
    )
    result = runtime.invoke(_request(run_id="run-cancelled"), thread_id="thread-cancelled")
    assert result.decision.status == "cancelled"
    assert result.decision.completed_stages == ["analysis_foundation"]
    assert result.decision.failed_stage == "canon_extraction"
    assert bindings["analysis_foundation"].execute_calls == 1
    assert bindings["canon_extraction"].execute_calls == 0


def test_execution_limits_are_typed_and_bounded():
    payload = _request().model_dump()
    payload["execution_limits"] = {
            "target_words_per_scene": 120,
            "visual_include_types": ["object"],
            "max_visual_renders_per_type": 1,
            "audiobook_max_chapters": 1,
            "audiobook_max_segment_chars": 800,
    }
    validated = OrchestrationRequest.model_validate(payload)
    assert validated.execution_limits.max_visual_renders_per_type == 1
    assert validated.execution_limits.audiobook_max_chapters == 1
