from __future__ import annotations

from pathlib import Path

from packages.analysis_foundation.contracts import BookArtifact, SceneArtifact
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.generation_planning.contracts import ChapterOutlineItem, GenerationBlueprintArtifact, ScenePlanItem
from packages.generation_planning.store import GenerationPlanningStore
from packages.narrative_generation import (
    ChapterDraftArtifact,
    GeneratedStoryArtifact,
    NarrativeSupportRuntime,
    SceneProseArtifact,
    require_narrative_semantic_acceptance,
)
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.narrative_generation.support_pipeline import _bounded_support_response
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.retrieval_runtime import RetrievalProfile, RetrievalRuntimeConfig, create_retrieval_client


class StubSupportReasoningRuntime:
    def __init__(self, evaluations: list[dict], *, revision_prose: str = "") -> None:
        self.evaluations = list(evaluations)
        self.revision_prose = revision_prose
        self._last = {}
        self.last_kwargs = {}
        self.evaluation_calls = 0
        self.revision_calls = 0
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        self.last_kwargs = dict(kwargs)
        self._last = {"provider": "test-live", "resolved_model": "support-model", "status": "ok"}
        if prompt.startswith("Revise generated"):
            self.revision_calls += 1
            return {"title": "Revised scene", "prose": self.revision_prose}
        self.evaluation_calls += 1
        return self.evaluations.pop(0)

    def last_request_metadata(self) -> dict:
        return dict(self._last)


class FailingSupportReasoningRuntime(StubSupportReasoningRuntime):
    def __init__(self) -> None:
        super().__init__([])

    def generate_json(self, prompt: str, **kwargs):
        del prompt, kwargs
        self._last = {"provider": "test-live", "resolved_model": "support-model", "status": "error"}
        return {"error": "provider_failed"}


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="narrative-support-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'narrative_support.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="narrative-support-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _retrieval(client):
    profile = RetrievalProfile(name="narrative-support-test")

    def embedder(texts: list[str]) -> list[list[float]]:
        return [
            [
                float(len(text.split())),
                float(text.lower().count("notebook")),
                float(text.lower().count("fares")),
            ]
            for text in texts
        ]

    return create_retrieval_client(
        config=RetrievalRuntimeConfig(profile=profile),
        profile=profile,
        embedder=embedder,
        persistence_client=client,
    )


def _seed_story(client) -> tuple[str, str]:
    series_id = "series-support"
    story_id = "story-support"
    book_id = "book-support"
    analysis = AnalysisFoundationStore(client)
    analysis.upsert_book(
        BookArtifact(
            book_id=book_id,
            series_id=series_id,
            title="The Silver Notebook",
            book_index=1,
            chapter_count=1,
            word_count=120,
        )
    )
    analysis.upsert_scene(
        SceneArtifact(
            scene_id="source-scene-1",
            book_id=book_id,
            chapter_index=1,
            scene_index=1,
            summary="Fares and Kareem discover a silver notebook.",
            text=(
                "Fares found the silver notebook in the quiet hallway and showed it to Kareem. "
                "They agreed to keep the notebook safe because its earlier entries recorded their meeting."
            ),
            word_count=29,
        )
    )
    blueprint = GenerationBlueprintArtifact(
        blueprint_id="blueprint-support",
        series_id=series_id,
        intent_id="intent-support",
        grounding_id="grounding-support",
        title="The Notebook Reopens",
        premise="Continue the notebook story without changing established canon.",
        divergence_plan="Introduce Mira as a new archivist for this generated story.",
        chapter_outline=[
            ChapterOutlineItem(
                chapter_index=1,
                title="The Promise",
                goal="Continue from the notebook discovery.",
                character_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-notebook"],
            )
        ],
        scene_plan=[
            ScenePlanItem(
                scene_id="planned-scene-1",
                chapter_index=1,
                scene_index=1,
                summary="Fares and Kareem decide how to protect the notebook.",
                purpose="Create a new decision grounded in the discovery.",
                character_refs=["char-fares", "char-kareem"],
                entity_refs=["entity-notebook"],
            )
        ],
        character_refs=["char-fares", "char-kareem"],
        entity_refs=["entity-notebook"],
    )
    GenerationPlanningStore(client).upsert_blueprint(series_id=series_id, blueprint=blueprint)
    scene = SceneProseArtifact(
        scene_prose_id="scene-prose-support",
        series_id=series_id,
        story_id=story_id,
        blueprint_id=blueprint.blueprint_id,
        source_scene_id="planned-scene-1",
        chapter_index=1,
        scene_index=1,
        title="A New Promise",
        prose=(
            "Fares remembered finding the silver notebook in the hallway and showing it to Kareem. "
            "Now they sat beside the window and quietly chose a new hiding place. The afternoon rain "
            "softened the room while Kareem wrapped the notebook in plain cloth. Fares checked the door, "
            "then wrote a fresh promise on the final page. Neither of them spoke loudly; this new decision "
            "belonged to the present, shaped by what they already knew and by the trust they chose to keep."
        ),
        purpose="Create a new decision grounded in the discovery.",
        character_refs=["char-fares", "char-kareem"],
        entity_refs=["entity-notebook"],
    )
    chapter = ChapterDraftArtifact(
        chapter_draft_id="chapter-draft-support",
        series_id=series_id,
        story_id=story_id,
        blueprint_id=blueprint.blueprint_id,
        chapter_index=1,
        title="The Promise",
        prose=scene.prose,
        scene_prose_ids=[scene.scene_prose_id],
        character_refs=scene.character_refs,
        entity_refs=scene.entity_refs,
    )
    store = NarrativeGenerationStore(client)
    store.replace_scene_prose(series_id=series_id, story_id=story_id, scenes=[scene])
    store.replace_chapter_drafts(series_id=series_id, story_id=story_id, chapters=[chapter])
    store.upsert_story(
        GeneratedStoryArtifact(
            story_id=story_id,
            series_id=series_id,
            blueprint_id=blueprint.blueprint_id,
            title=blueprint.title,
            premise=blueprint.premise,
            chapters=[chapter],
            character_refs=scene.character_refs,
            entity_refs=scene.entity_refs,
        )
    )
    return series_id, story_id


def _evaluation(classification: str, *, claim_type: str = "canon_fact") -> dict:
    return {
        "claims": [
            {
                "claim": "Fares found the silver notebook and showed it to Kareem.",
                "claim_type": claim_type,
                "classification": classification,
                "evidence_ids": ["evidence-1"] if classification == "supported" else [],
                "rationale": "Compared against the source scene.",
                "confidence": 0.98,
            },
            {
                "claim": "They choose a new hiding place in this continuation scene.",
                "claim_type": "story_local",
                "classification": "creative_expansion",
                "evidence_ids": [],
                "rationale": "This is permissible new-scene action.",
                "confidence": 0.95,
            },
        ],
        "summary": "Scene evaluated.",
    }


def _runtime(client, reasoning):
    return NarrativeSupportRuntime(
        persistence=client,
        retrieval_runtime=_retrieval(client),
        reasoning_runtime=reasoning,
        allow_in_memory_checkpointer=True,
    )


def test_semantic_support_accepts_supported_canon_and_creative_expansion(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    reasoning = StubSupportReasoningRuntime([_evaluation("supported")])
    result = _runtime(client, reasoning).invoke(
        series_id=series_id, story_id=story_id, thread_id="accepted"
    )

    assert result.decision.accepted is True
    assert result.decision.factual_support_rate == 1.0
    assert result.decision.unsupported_invention_rate == 0.0
    assert result.audits[0].status == "accepted"
    assert {item.classification for item in result.audits[0].claims} == {"supported", "creative_expansion"}
    require_narrative_semantic_acceptance(result.story)
    schema = reasoning.last_kwargs["response_format"]["json_schema"]["schema"]
    assert reasoning.last_kwargs["max_tokens"] == 2600
    assert schema["properties"]["claims"]["maxItems"] == 16


def test_semantic_support_allows_low_severity_noncontradictory_set_dressing(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    evaluation = _evaluation("supported")
    evaluation["claims"][0]["severity"] = "high"
    evaluation["claims"].append(
        {
            "claim": "The room has a hearth.",
            "claim_type": "canon_fact",
            "classification": "unsupported",
            "severity": "low",
            "evidence_ids": [],
            "rationale": "Minor set dressing is not present in source evidence.",
            "confidence": 0.8,
        }
    )
    result = _runtime(client, StubSupportReasoningRuntime([evaluation])).invoke(
        series_id=series_id, story_id=story_id, thread_id="set-dressing"
    )

    assert result.decision.accepted is True
    assert result.decision.unsupported_invention_rate <= 0.1
    assert result.audits[0].status == "accepted"


def test_semantic_support_uses_temporal_scope_for_plan_authorized_present_events(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    evaluation = _evaluation("supported")
    evaluation["claims"].append(
        {
            "claim": "Fares and Kareem choose a new hiding place.",
            "claim_type": "canon_fact",
            "classification": "unsupported",
            "severity": "medium",
            "temporal_scope": "generated_present",
            "plan_alignment": "aligned",
            "evidence_ids": [],
            "rationale": "This is the planned action occurring now, not prior history.",
            "confidence": 0.99,
        }
    )
    result = _runtime(client, StubSupportReasoningRuntime([evaluation])).invoke(
        series_id=series_id, story_id=story_id, thread_id="temporal-scope"
    )

    claim = next(item for item in result.audits[0].claims if item.claim.startswith("Fares and Kareem"))
    assert result.decision.accepted is True
    assert claim.claim_type == "story_local"
    assert claim.classification == "creative_expansion"
    assert claim.temporal_scope == "generated_present"
    assert claim.plan_alignment == "aligned"


def test_semantic_support_allows_blueprint_aligned_generated_story_innovation(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    evaluation = _evaluation("supported")
    evaluation["claims"].append(
        {
            "claim": "Mira is a new archivist in this generated story.",
            "claim_type": "canon_fact",
            "classification": "unsupported",
            "severity": "medium",
            "temporal_scope": "generated_story",
            "plan_alignment": "aligned",
            "evidence_ids": [],
            "rationale": "The blueprint explicitly introduces Mira as a new participant.",
            "confidence": 0.99,
        }
    )
    reasoning = StubSupportReasoningRuntime([evaluation])
    result = _runtime(client, reasoning).invoke(
        series_id=series_id, story_id=story_id, thread_id="generated-story-innovation"
    )

    claim = next(item for item in result.audits[0].claims if item.claim.startswith("Mira"))
    assert result.decision.accepted is True
    assert claim.claim_type == "story_local"
    assert claim.classification == "creative_expansion"
    assert claim.temporal_scope == "generated_story"
    assert "Introduce Mira as a new archivist" in reasoning.prompts[0]


def test_semantic_support_revises_then_rechecks_unsupported_claims(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    revised_prose = (
        "Fares remembered finding the silver notebook in the hallway and showing it to Kareem. "
        "He placed it on the table while rain moved softly over the window. Kareem suggested a new hiding "
        "place, and Fares considered the idea without claiming anything more about the notebook's history. "
        "They wrapped it in plain cloth, checked the quiet room, and made a present-day promise to protect it. "
        "Their choice grew from the discovery they both remembered and from no other invented fact. "
        "Before leaving, they checked the knot once more and agreed to meet there again after sunset."
    )
    reasoning = StubSupportReasoningRuntime(
        [_evaluation("unsupported"), _evaluation("supported")],
        revision_prose=revised_prose,
    )
    result = _runtime(client, reasoning).invoke(series_id=series_id, story_id=story_id, thread_id="revised")

    assert result.decision.accepted is True
    assert result.decision.revised_scene_ids == ["planned-scene-1"]
    assert result.audits[0].evaluation_round == 2
    assert result.audits[0].status == "accepted"
    assert len(result.revisions) == 1
    assert result.story.chapters[0].prose == revised_prose


def test_semantic_support_rejects_unresolved_contradiction(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    reasoning = StubSupportReasoningRuntime(
        [_evaluation("contradiction"), _evaluation("contradiction")],
        revision_prose=("A revised but still contradictory scene. " * 20).strip(),
    )
    result = _runtime(client, reasoning).invoke(series_id=series_id, story_id=story_id, thread_id="rejected")

    assert result.decision.accepted is False
    assert result.decision.contradiction_rate == 1.0
    assert result.audits[0].status == "rejected"
    assert result.decision.rejected_scene_ids == ["planned-scene-1"]


def test_semantic_support_fails_closed_when_provider_fails(tmp_path: Path):
    client = _persistence(tmp_path)
    series_id, story_id = _seed_story(client)
    result = _runtime(client, FailingSupportReasoningRuntime()).invoke(
        series_id=series_id, story_id=story_id, thread_id="provider-failure"
    )

    assert result.decision.accepted is False
    assert result.decision.provider_success_rate == 0.0
    assert result.audits[0].status == "rejected"
    assert any("provider" in reason.lower() for reason in result.decision.reasons)
    try:
        require_narrative_semantic_acceptance(result.story)
    except ValueError as exc:
        assert "has not passed" in str(exc)
    else:
        raise AssertionError("Rejected narrative should not pass the downstream semantic-support guard.")


def test_bounded_support_response_retains_late_risky_claims():
    claims = [
        {
            "claim": f"Creative detail {index}",
            "claim_type": "story_local",
            "classification": "creative_expansion",
        }
        for index in range(20)
    ]
    risky = {
        "claim": "Unsupported prior-canon assertion",
        "claim_type": "canon_fact",
        "classification": "unsupported",
    }
    response, metadata = _bounded_support_response({"claims": [*claims, risky], "summary": "audit"})

    assert len(response["claims"]) == 16
    assert risky in response["claims"]
    assert metadata == {
        "status": "bounded",
        "original_claim_count": 21,
        "risky_claim_count": 1,
        "retained_claim_count": 16,
    }


def test_bounded_support_response_fails_closed_on_risky_overflow():
    claims = [
        {
            "claim": f"Risky claim {index}",
            "claim_type": "canon_fact",
            "classification": "unsupported",
        }
        for index in range(17)
    ]
    response, metadata = _bounded_support_response({"claims": claims})

    assert len(response["claims"]) == 17
    assert metadata["status"] == "rejected_risky_overflow"
    assert metadata["risky_claim_count"] == 17


def test_bounded_support_response_is_noop_within_schema_limit():
    response = {"claims": [{"claim": "A"}]}

    normalized, metadata = _bounded_support_response(response)

    assert normalized is response
    assert metadata == {}
