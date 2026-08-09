"""LangGraph workflow for retrieval-grounded generated-prose support auditing."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from packages.agent_runtime import SqlCheckpointSaver
from packages.generation_planning.contracts import GenerationBlueprintArtifact
from packages.narrative_generation.contracts import (
    ClaimSupportArtifact,
    GeneratedStoryArtifact,
    NarrativeSupportDecisionArtifact,
    NarrativeSupportResult,
    RevisionRecordArtifact,
    SceneProseArtifact,
    SceneSupportAuditArtifact,
    SupportEvidenceArtifact,
)
from packages.narrative_generation.quality import evaluate_chapter_continuity
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime import ReasoningRuntimeClient
from packages.retrieval_runtime import DocumentRetrievalTool
from packages.retrieval_runtime.contracts import RetrievalIndexRef


logger = logging.getLogger(__name__)


class NarrativeSupportState(TypedDict, total=False):
    series_id: str
    story_id: str
    blueprint: dict[str, Any]
    story: dict[str, Any]
    scene_prose: list[dict[str, Any]]
    context: dict[str, Any]
    evidence_documents: list[dict[str, Any]]
    index_ref: dict[str, Any]
    audits: list[dict[str, Any]]
    revisions: list[dict[str, Any]]
    revised_scene_ids: list[str]
    reevaluation_scene_ids: list[str]
    evaluation_round: int
    decision: dict[str, Any]
    run_metadata: dict[str, Any]


class ClaimEvaluationPayload(BaseModel):
    claim: str = Field(max_length=500)
    claim_type: str = "canon_fact"
    classification: str = "unsupported"
    severity: str = "medium"
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(default="", max_length=300)
    confidence: float = 0.0
    temporal_scope: str = ""
    plan_alignment: str = ""


class SceneEvaluationPayload(BaseModel):
    claims: list[ClaimEvaluationPayload] = Field(default_factory=list, max_length=16)
    summary: str = Field(default="", max_length=500)


class SceneRevisionPayload(BaseModel):
    title: str = ""
    prose: str = ""


class CanonEvidenceIndexAgent:
    def __init__(self, *, retrieval_runtime: DocumentRetrievalTool) -> None:
        self.retrieval_runtime = retrieval_runtime

    def run(self, state: NarrativeSupportState) -> dict[str, Any]:
        started = time.perf_counter()
        documents = _build_evidence_documents(
            dict(state.get("context") or {}),
            blueprint=GenerationBlueprintArtifact.model_validate(state["blueprint"]),
        )
        if not documents:
            raise ValueError("Narrative semantic support requires persisted source/canon evidence.")
        indexed = self.retrieval_runtime.ensure_document_index(
            series_id=state["series_id"],
            scope_key="narrative-semantic-support",
            documents=documents,
        )
        logger.info("semantic_support evidence_index complete documents=%d", len(documents))
        index_ref = RetrievalIndexRef(
            index_id=str(indexed.get("index_id") or ""),
            series_id=state["series_id"],
            scope_key="narrative-semantic-support",
            fingerprint=str(indexed.get("fingerprint") or ""),
            namespace=str(indexed.get("namespace") or ""),
        )
        metadata = _stage_metadata(
            state,
            "evidence_index",
            started,
            document_count=len(documents),
            index_id=index_ref.index_id,
        )
        return {"evidence_documents": documents, "index_ref": index_ref.model_dump(), "run_metadata": metadata}


class SemanticSupportAgent:
    def __init__(
        self,
        *,
        retrieval_runtime: DocumentRetrievalTool,
        reasoning_runtime: ReasoningRuntimeClient,
        minimum_factual_support_rate: float,
        maximum_unsupported_invention_rate: float,
    ) -> None:
        self.retrieval_runtime = retrieval_runtime
        self.reasoning_runtime = reasoning_runtime
        self.minimum_factual_support_rate = minimum_factual_support_rate
        self.maximum_unsupported_invention_rate = maximum_unsupported_invention_rate

    def run(self, state: NarrativeSupportState) -> dict[str, Any]:
        started = time.perf_counter()
        evaluation_round = int(state.get("evaluation_round") or 1)
        revised_ids = set(state.get("reevaluation_scene_ids") or state.get("revised_scene_ids") or [])
        previous = [SceneSupportAuditArtifact.model_validate(item) for item in list(state.get("audits") or [])]
        scenes = [SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])]
        if evaluation_round > 1:
            scenes = [item for item in scenes if item.source_scene_id in revised_ids]
        document_map = {str(item.get("document_id") or ""): item for item in list(state.get("evidence_documents") or [])}
        new_audits = [
            self._evaluate_scene(
                state=state,
                scene=scene,
                document_map=document_map,
                evaluation_round=evaluation_round,
            )
            for scene in scenes
        ]
        logger.info(
            "semantic_support evaluation round=%d complete scenes=%d accepted=%d",
            evaluation_round,
            len(scenes),
            len([item for item in new_audits if item.status == "accepted"]),
        )
        if evaluation_round > 1:
            audited_ids = {item.source_scene_id for item in new_audits}
            new_audits = [item for item in previous if item.source_scene_id not in audited_ids] + new_audits
        new_audits.sort(key=lambda item: item.source_scene_id)
        provider_successes = len([item for item in new_audits if (item.metadata or {}).get("reasoning_status") == "ok"])
        metadata = _stage_metadata(
            state,
            f"semantic_evaluation_round_{evaluation_round}",
            started,
            scene_count=len(scenes),
            accepted_count=len([item for item in new_audits if item.status == "accepted"]),
            provider_success_count=provider_successes,
        )
        return {"audits": [item.model_dump() for item in new_audits], "run_metadata": metadata}

    def _evaluate_scene(
        self,
        *,
        state: NarrativeSupportState,
        scene: SceneProseArtifact,
        document_map: dict[str, dict[str, Any]],
        evaluation_round: int,
    ) -> SceneSupportAuditArtifact:
        logger.info("semantic_support evaluating scene=%s round=%d", scene.source_scene_id, evaluation_round)
        blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
        plan = next((item for item in blueprint.scene_plan if item.scene_id == scene.source_scene_id), None)
        query = " ".join(
            value
            for value in [scene.title, scene.purpose, getattr(plan, "summary", ""), scene.prose]
            if str(value or "").strip()
        )
        results = self.retrieval_runtime.query_documents(
            index_ref=state["index_ref"],
            query_text=query,
            top_k=8,
            character_bias=list(scene.character_refs),
        )
        evidence = _evidence_from_results(results, document_map=document_map)
        prompt = _build_support_prompt(scene=scene, plan=plan, evidence=evidence)
        response = self.reasoning_runtime.generate_json(
            prompt,
            strict=True,
            max_tokens=2600,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "narrative_scene_support_evaluation",
                    "schema": SceneEvaluationPayload.model_json_schema(),
                },
            },
        )
        request_metadata = dict(self.reasoning_runtime.last_request_metadata() or {})
        request_ok = request_metadata.get("status") == "ok" and isinstance(response, dict) and not response.get("error")
        try:
            payload = SceneEvaluationPayload.model_validate(response) if request_ok else SceneEvaluationPayload()
        except Exception as exc:
            request_ok = False
            request_metadata["status"] = "error"
            request_metadata["error_code"] = f"support_payload_validation_failed:{type(exc).__name__}"
            payload = SceneEvaluationPayload()
        claims = _normalize_claims(
            payload.claims,
            scene=scene,
            plan=plan,
            evidence=evidence,
            request_ok=request_ok,
        )
        factual_support_rate, unsupported_rate, contradiction_rate = _weighted_support_metrics(claims)
        accepted = (
            request_ok
            and bool(evidence)
            and bool(claims)
            and contradiction_rate == 0.0
            and factual_support_rate >= self.minimum_factual_support_rate
            and unsupported_rate <= self.maximum_unsupported_invention_rate
        )
        status = "accepted" if accepted else ("revision_required" if evaluation_round == 1 else "rejected")
        issues = _support_issues(
            claims=claims,
            request_ok=request_ok,
            has_evidence=bool(evidence),
            minimum_support=self.minimum_factual_support_rate,
            factual_support_rate=factual_support_rate,
        )
        return SceneSupportAuditArtifact(
            audit_id=_stable_id("narrative-support-audit", state["story_id"], scene.source_scene_id, evaluation_round),
            series_id=state["series_id"],
            story_id=state["story_id"],
            source_scene_id=scene.source_scene_id,
            scene_prose_id=scene.scene_prose_id,
            evaluation_round=evaluation_round,
            claims=claims,
            evidence=evidence,
            factual_support_rate=factual_support_rate,
            unsupported_invention_rate=unsupported_rate,
            contradiction_rate=contradiction_rate,
            status=status,
            issues=issues,
            metadata={
                "agent": "SemanticSupportAgent",
                "reasoning_status": "ok" if request_ok else "error",
                "reasoning_provider": request_metadata.get("provider"),
                "reasoning_model": request_metadata.get("resolved_model"),
                "request_metadata": request_metadata,
                "evaluation_summary": payload.summary,
            },
        )


class SupportRevisionAgent:
    def __init__(self, *, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.reasoning_runtime = reasoning_runtime

    def run(self, state: NarrativeSupportState) -> dict[str, Any]:
        started = time.perf_counter()
        audits = [SceneSupportAuditArtifact.model_validate(item) for item in list(state.get("audits") or [])]
        audit_map = {item.source_scene_id: item for item in audits if item.status == "revision_required"}
        scenes = [SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])]
        revisions: list[RevisionRecordArtifact] = []
        revised_ids: list[str] = []
        reevaluation_ids = list(audit_map)
        for scene in scenes:
            audit = audit_map.get(scene.source_scene_id)
            if audit is None:
                continue
            blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
            plan = next((item for item in blueprint.scene_plan if item.scene_id == scene.source_scene_id), None)
            response = self.reasoning_runtime.generate_json(
                _build_revision_prompt(scene=scene, plan=plan, audit=audit), strict=True, max_tokens=1600,
            )
            metadata = dict(self.reasoning_runtime.last_request_metadata() or {})
            if metadata.get("status") != "ok" or not isinstance(response, dict) or response.get("error"):
                continue
            try:
                revised = SceneRevisionPayload.model_validate(response)
            except Exception:
                continue
            if len(revised.prose.split()) < 60 or revised.prose.strip() == scene.prose.strip():
                continue
            before = scene.prose
            scene.title = revised.title or scene.title
            scene.prose = revised.prose.strip()
            scene.metadata = {**dict(scene.metadata or {}), "semantic_support_revision": metadata}
            revised_ids.append(scene.source_scene_id)
            revisions.append(
                RevisionRecordArtifact(
                    revision_id=_stable_id("semantic-support-revision", state["story_id"], scene.source_scene_id),
                    series_id=state["series_id"],
                    story_id=state["story_id"],
                    blueprint_id=scene.blueprint_id,
                    chapter_index=scene.chapter_index,
                    source_artifact_id=scene.scene_prose_id,
                    reason="Semantic support repair",
                    before_excerpt=before[:500],
                    after_excerpt=scene.prose[:500],
                    issues_addressed=list(audit.issues),
                    metadata={"agent": "SupportRevisionAgent", "request_metadata": metadata},
                )
            )
        metadata = _stage_metadata(
            state,
            "semantic_revision",
            started,
            requested_count=len(audit_map),
            revised_count=len(revised_ids),
        )
        logger.info("semantic_support revision complete requested=%d revised=%d", len(audit_map), len(revised_ids))
        return {
            "scene_prose": [item.model_dump() for item in scenes],
            "revisions": [item.model_dump() for item in revisions],
            "revised_scene_ids": revised_ids,
            "reevaluation_scene_ids": reevaluation_ids,
            "evaluation_round": 2,
            "run_metadata": metadata,
        }


class SupportDecisionAgent:
    def __init__(self, *, store: NarrativeGenerationStore) -> None:
        self.store = store

    def run(self, state: NarrativeSupportState) -> dict[str, Any]:
        started = time.perf_counter()
        audits = [SceneSupportAuditArtifact.model_validate(item) for item in list(state.get("audits") or [])]
        scenes = [SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])]
        support_revisions = [RevisionRecordArtifact.model_validate(item) for item in list(state.get("revisions") or [])]
        story = GeneratedStoryArtifact.model_validate(state["story"])
        revised_ids = list(state.get("revised_scene_ids") or [])
        rejected_ids = [item.source_scene_id for item in audits if item.status != "accepted"]
        provider_successes = len([item for item in audits if (item.metadata or {}).get("reasoning_status") == "ok"])
        all_claims = [claim for audit in audits for claim in audit.claims]
        factual_support_rate, unsupported_rate, contradiction_rate = _weighted_support_metrics(all_claims)
        accepted = bool(audits) and not rejected_ids and provider_successes == len(audits)
        reasons = []
        if rejected_ids:
            reasons.append(f"{len(rejected_ids)} scene(s) failed semantic support after revision.")
        if provider_successes != len(audits):
            reasons.append("One or more semantic evaluations did not complete through the live reasoning provider.")
        decision = NarrativeSupportDecisionArtifact(
            decision_id=_stable_id("narrative-support-decision", state["story_id"]),
            series_id=state["series_id"],
            story_id=state["story_id"],
            accepted=accepted,
            status="accepted" if accepted else "rejected",
            scene_count=len(audits),
            accepted_scene_count=len([item for item in audits if item.status == "accepted"]),
            factual_support_rate=factual_support_rate,
            unsupported_invention_rate=unsupported_rate,
            contradiction_rate=contradiction_rate,
            provider_success_rate=_ratio(provider_successes, len(audits)),
            revised_scene_ids=revised_ids,
            rejected_scene_ids=rejected_ids,
            reasons=reasons,
            metadata={"agent": "SupportDecisionAgent", "evaluation_rounds": int(state.get("evaluation_round") or 1)},
        )
        persisted_scenes = self.store.replace_scene_prose(series_id=state["series_id"], story_id=state["story_id"], scenes=scenes)
        story = _rebuild_story(story=story, scenes=persisted_scenes, support_revisions=support_revisions, decision=decision)
        blueprint = GenerationBlueprintArtifact.model_validate(state["blueprint"])
        story.continuity_checks = [
            evaluate_chapter_continuity(blueprint=blueprint, chapter=chapter) for chapter in story.chapters
        ]
        if any(not item.passed for item in story.continuity_checks):
            decision.accepted = False
            decision.status = "rejected"
            decision.reasons.append("Generated story failed continuity validation after semantic support revision.")
            story.metadata["semantic_support"].update(status="rejected", accepted=False)
        persisted_chapters = self.store.replace_chapter_drafts(
            series_id=state["series_id"], story_id=state["story_id"], chapters=story.chapters
        )
        story.chapters = persisted_chapters
        story.continuity_checks = self.store.replace_continuity_checks(
            series_id=state["series_id"], story_id=state["story_id"], checks=story.continuity_checks
        )
        persisted_revisions = self.store.replace_revisions(
            series_id=state["series_id"], story_id=state["story_id"], revisions=story.revisions
        )
        story.revisions = persisted_revisions
        persisted_story = self.store.upsert_story(story)
        persisted_audits = self.store.replace_support_audits(
            series_id=state["series_id"], story_id=state["story_id"], audits=audits
        )
        persisted_decision = self.store.upsert_support_decision(decision)
        metadata = _stage_metadata(state, "support_decision", started, accepted=accepted, rejected_scene_count=len(rejected_ids))
        metadata["stage_order"] = [
            "evidence_index",
            "semantic_evaluation_round_1",
            *(["semantic_revision", "semantic_evaluation_round_2"] if int(state.get("evaluation_round") or 1) > 1 else []),
            "support_decision",
        ]
        logger.info("semantic_support decision story=%s status=%s", state["story_id"], decision.status)
        return {
            "story": persisted_story.model_dump(),
            "scene_prose": [item.model_dump() for item in persisted_scenes],
            "audits": [item.model_dump() for item in persisted_audits],
            "revisions": [item.model_dump() for item in support_revisions],
            "decision": persisted_decision.model_dump(),
            "run_metadata": metadata,
        }


class NarrativeSupportRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        retrieval_runtime: DocumentRetrievalTool,
        reasoning_runtime: ReasoningRuntimeClient,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
        minimum_factual_support_rate: float = 0.85,
        maximum_unsupported_invention_rate: float = 0.10,
    ) -> None:
        self.persistence = persistence
        self.store = NarrativeGenerationStore(persistence)
        self.retrieval_runtime = retrieval_runtime
        self.reasoning_runtime = reasoning_runtime
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_narrative_support_graph(
            store=self.store,
            retrieval_runtime=retrieval_runtime,
            reasoning_runtime=reasoning_runtime,
            checkpointer=self.checkpointer,
            minimum_factual_support_rate=minimum_factual_support_rate,
            maximum_unsupported_invention_rate=maximum_unsupported_invention_rate,
        )

    def invoke(
        self,
        *,
        series_id: str,
        story_id: str,
        thread_id: str = "narrative-support",
    ) -> NarrativeSupportResult:
        story = self.store.load_story(series_id=series_id, story_id=story_id)
        scenes = self.store.list_scene_prose(series_id=series_id, story_id=story_id)
        context = self.store.load_series_context(series_id=series_id, blueprint_id=story.blueprint_id)
        blueprint = context.get("blueprint")
        if blueprint is None:
            raise ValueError(f"Narrative support requires blueprint '{story.blueprint_id}'.")
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "story_id": story_id,
                "blueprint": blueprint.model_dump(),
                "story": story.model_dump(),
                "scene_prose": [item.model_dump() for item in scenes],
                "context": _serialize_context(context),
                "evaluation_round": 1,
                "run_metadata": {},
            },
            config={"configurable": {"thread_id": str(thread_id or "narrative-support")}},
        )
        return NarrativeSupportResult(
            series_id=series_id,
            story=GeneratedStoryArtifact.model_validate(state["story"]),
            scene_prose=[SceneProseArtifact.model_validate(item) for item in list(state.get("scene_prose") or [])],
            audits=[SceneSupportAuditArtifact.model_validate(item) for item in list(state.get("audits") or [])],
            revisions=[RevisionRecordArtifact.model_validate(item) for item in list(state.get("revisions") or [])],
            decision=NarrativeSupportDecisionArtifact.model_validate(state["decision"]),
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def build_narrative_support_graph(
    *,
    store: NarrativeGenerationStore,
    retrieval_runtime: DocumentRetrievalTool,
    reasoning_runtime: ReasoningRuntimeClient,
    checkpointer: BaseCheckpointSaver | None = None,
    minimum_factual_support_rate: float = 0.85,
    maximum_unsupported_invention_rate: float = 0.10,
):
    graph = StateGraph(NarrativeSupportState)
    graph.add_node("evidence_index", CanonEvidenceIndexAgent(retrieval_runtime=retrieval_runtime).run)
    graph.add_node(
        "semantic_evaluation",
        SemanticSupportAgent(
            retrieval_runtime=retrieval_runtime,
            reasoning_runtime=reasoning_runtime,
            minimum_factual_support_rate=minimum_factual_support_rate,
            maximum_unsupported_invention_rate=maximum_unsupported_invention_rate,
        ).run,
    )
    graph.add_node("semantic_revision", SupportRevisionAgent(reasoning_runtime=reasoning_runtime).run)
    graph.add_node("support_decision", SupportDecisionAgent(store=store).run)
    graph.add_edge(START, "evidence_index")
    graph.add_edge("evidence_index", "semantic_evaluation")
    graph.add_conditional_edges(
        "semantic_evaluation",
        _route_after_evaluation,
        {"revise": "semantic_revision", "decide": "support_decision"},
    )
    graph.add_edge("semantic_revision", "semantic_evaluation")
    graph.add_edge("support_decision", END)
    return graph.compile(checkpointer=checkpointer)


def _route_after_evaluation(state: NarrativeSupportState) -> str:
    if int(state.get("evaluation_round") or 1) > 1:
        return "decide"
    audits = [SceneSupportAuditArtifact.model_validate(item) for item in list(state.get("audits") or [])]
    return "revise" if any(item.status == "revision_required" for item in audits) else "decide"


def _build_evidence_documents(
    context: dict[str, Any],
    *,
    blueprint: GenerationBlueprintArtifact,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    canon_refs = set(blueprint.canon_refs)
    character_refs = set(blueprint.character_refs)
    entity_refs = set(blueprint.entity_refs)
    for chapter in blueprint.chapter_outline:
        canon_refs.update(chapter.canon_refs)
        character_refs.update(chapter.character_refs)
        entity_refs.update(chapter.entity_refs)
    for scene in blueprint.scene_plan:
        canon_refs.update(scene.canon_refs)
        character_refs.update(scene.character_refs)
        entity_refs.update(scene.entity_refs)
    for scene in list(context.get("source_scenes") or []):
        row = _as_dict(scene)
        scene_id = str(row.get("scene_id") or "")
        text = str(row.get("text") or row.get("summary") or "").strip()
        for index, chunk in enumerate(_chunk_text(text), start=1):
            documents.append(
                {
                    "document_id": f"source-scene:{scene_id}:chunk-{index}",
                    "text": chunk,
                    "summary": str(row.get("summary") or ""),
                    "source_type": "source_scene",
                    "metadata": {
                        "scene_id": scene_id,
                        "book_id": row.get("book_id"),
                        "chapter_index": row.get("chapter_index"),
                        "characters": list((row.get("metadata") or {}).get("character_names") or []),
                        "authority": "primary_source",
                    },
                }
            )
    for event in list(context.get("events") or []):
        row = _as_dict(event)
        if canon_refs or character_refs or entity_refs:
            is_relevant = str(row.get("event_id") or "") in canon_refs or bool(set(row.get("entity_refs") or []) & entity_refs)
            if not canon_refs and not entity_refs:
                is_relevant = bool(set(row.get("participant_refs") or []) & character_refs)
            if not is_relevant:
                continue
        documents.append(
            {
                "document_id": f"canon-event:{row.get('event_id')}",
                "text": f"{row.get('title') or ''}. {row.get('summary') or ''}".strip(),
                "summary": str(row.get("summary") or ""),
                "source_type": "canon_event",
                "metadata": {
                    "event_id": row.get("event_id"),
                    "scene_id": row.get("scene_id"),
                    "characters": list(row.get("participant_refs") or []),
                    "entity_refs": list(row.get("entity_refs") or []),
                    "authority": "derived_canon",
                },
            }
        )
    for profile in list(context.get("character_profiles") or []):
        row = _as_dict(profile)
        if character_refs and str(row.get("character_id") or "") not in character_refs:
            continue
        text = " ".join(
            str(value or "")
            for value in [
                row.get("canonical_name"), row.get("overview"), row.get("role_or_archetype"),
                " ".join(row.get("traits") or []), " ".join(row.get("motivations") or []),
                row.get("latest_state_summary"),
            ]
        )
        documents.append(
            {
                "document_id": f"character-profile:{row.get('character_id')}",
                "text": text,
                "summary": str(row.get("overview") or ""),
                "source_type": "character_profile",
                "metadata": {
                    "character_id": row.get("character_id"),
                    "characters": [row.get("canonical_name")] if row.get("canonical_name") else [],
                    "authority": "derived_canon",
                },
            }
        )
    for stable in list(context.get("stable_character_states") or []):
        row = _as_dict(stable)
        if character_refs and str(row.get("character_id") or "") not in character_refs:
            continue
        documents.append(
            {
                "document_id": f"stable-character-state:{row.get('character_id')}",
                "text": " ".join(
                    str(value or "")
                    for value in [
                        row.get("canonical_name"),
                        row.get("summary"),
                        " ".join(f"{key}: {value}" for key, value in dict(row.get("stable_attributes") or {}).items()),
                    ]
                ),
                "summary": str(row.get("summary") or ""),
                "source_type": "stable_character_state",
                "metadata": {
                    "character_id": row.get("character_id"),
                    "characters": [row.get("canonical_name")] if row.get("canonical_name") else [],
                    "authority": "derived_canon",
                },
            }
        )
    relevant_refs = character_refs | entity_refs
    for relationship in list(context.get("relationships") or []):
        row = _as_dict(relationship)
        if relevant_refs:
            endpoints = {str(row.get("source_ref") or ""), str(row.get("target_ref") or "")}
            if str(row.get("relationship_id") or "") not in canon_refs and not endpoints.issubset(relevant_refs):
                continue
        documents.append(
            {
                "document_id": f"canon-relationship:{row.get('relationship_id')}",
                "text": f"{row.get('source_ref') or ''} {row.get('relationship_type') or ''} {row.get('target_ref') or ''}. {row.get('description') or ''}".strip(),
                "summary": str(row.get("description") or ""),
                "source_type": "canon_relationship",
                "metadata": {
                    "relationship_id": row.get("relationship_id"),
                    "source_ref": row.get("source_ref"),
                    "target_ref": row.get("target_ref"),
                    "authority": "derived_canon",
                },
            }
        )
    for world in list(context.get("world_states") or []):
        row = _as_dict(world)
        if entity_refs and str(row.get("entity_id") or "") not in entity_refs:
            continue
        facts = " ".join(f"{key}: {value}" for key, value in dict(row.get("stable_facts") or {}).items())
        documents.append(
            {
                "document_id": f"world-state:{row.get('entity_id')}",
                "text": " ".join(str(value or "") for value in [row.get("canonical_name"), row.get("description"), facts, row.get("current_state_summary")]),
                "summary": str(row.get("current_state_summary") or row.get("description") or ""),
                "source_type": "world_state",
                "metadata": {"entity_id": row.get("entity_id"), "authority": "derived_canon"},
            }
        )
    return [item for item in documents if str(item.get("document_id") or "") and str(item.get("text") or "").strip()]


def _evidence_from_results(results: list[Any], *, document_map: dict[str, dict[str, Any]]) -> list[SupportEvidenceArtifact]:
    evidence: list[SupportEvidenceArtifact] = []
    for position, raw in enumerate(results, start=1):
        row = _as_dict(raw)
        document_id = str(row.get("document_id") or "")
        source = document_map.get(document_id, {})
        excerpt = re.sub(r"\s+", " ", str(source.get("text") or row.get("excerpt") or row.get("summary") or "")).strip()[:1200]
        metadata = _as_dict(row.get("metadata") or source.get("metadata") or {})
        evidence.append(
            SupportEvidenceArtifact(
                evidence_id=f"evidence-{position}",
                document_id=document_id,
                source_type=str(row.get("source_type") or source.get("source_type") or ""),
                excerpt=excerpt,
                score=float(row.get("score") or 0.0),
                metadata=metadata,
            )
        )
    return evidence


def _build_support_prompt(*, scene: SceneProseArtifact, plan: Any, evidence: list[SupportEvidenceArtifact]) -> str:
    evidence_payload = [item.model_dump() for item in evidence]
    return (
        "You audit generated continuation prose against retrieved source-book canon evidence.\n"
        "Extract claims ONLY from GENERATED_SCENE.prose, then classify each claim.\n"
        "PLANNED_SCENE is authoritative generation intent, not source-book canon. Never extract a claim merely because it appears in the plan.\n"
        "For each extracted claim set temporal_scope=generated_present when it describes an event, action, dialogue, location, or state created in this scene; otherwise use prior_canon when it asserts pre-existing history, motive, identity, relationship, ability, rule, or durable state.\n"
        "For generated_present claims set plan_alignment=aligned when entailed by PLANNED_SCENE, otherwise not_aligned. Prior-canon claims use not_applicable.\n"
        "A non-contradictory generated_present claim is story_local creative_expansion, including consequential events explicitly authorized by PLANNED_SCENE. The plan can never make a prior_canon claim supported.\n"
        "Claims must be atomic. Split prior canon facts from present generated actions or locations.\n"
        "Return at most 16 material claims. Prioritize every prior-canon claim and consequential generated-present claim; group minor set dressing when needed.\n"
        "Classifications:\n"
        "- supported: a canon_fact directly stated or safely entailed by cited evidence.\n"
        "- creative_expansion: a story_local action, dialogue, sensation, or emotion invented for this new scene that neither asserts prior canon nor conflicts with it.\n"
        "- unsupported: a canon_fact about prior history, identity, relationship, ability, rule, possession, location, or state that lacks evidence.\n"
        "- contradiction: a canon_fact that conflicts with evidence.\n"
        "Do not demand source evidence for ordinary new-scene actions. Do not call contradictions creative expansion.\n"
        "Food, drink, weather, lighting, clothing, gestures, dialogue, and props that exist only in the generated present scene are story_local creative expansion, even when they occur at a canon location.\n"
        "Treat those details as canon_fact only when the prose asserts they existed previously, are permanent, are customary, or define established history/world rules.\n"
        "Keep each extracted claim faithful to the generated sentence; do not generalize a one-scene detail into a permanent statement about a place or character.\n"
        "A character appearing with someone elsewhere does not support their presence, behavior, or emotional state at a new time or location. Do not use likelihood as entailment.\n"
        "Prior ownership or possession does not prove that a character carries the object at a later event; current possession is story-local unless the prose frames it as established continuity.\n"
        "Assign severity: high for identity, death/life status, major history, world rules, powers, or direct contradictions; medium for relationships, ownership, durable state, or consequential location facts; low for atmospheric description, furniture, hearths, food, drink, weather, lighting, clothing, and other set dressing.\n"
        "Non-contradictory low-severity set dressing should normally be story_local creative_expansion, not unsupported canon.\n"
        "Use only evidence_id values present below. A supported claim must cite at least one evidence_id.\n"
        "Return JSON only: {\"claims\":[{\"claim\":str,\"claim_type\":\"canon_fact|story_local\","
        "\"classification\":\"supported|creative_expansion|unsupported|contradiction\",\"evidence_ids\":[str],"
        "\"severity\":\"low|medium|high\",\"temporal_scope\":\"prior_canon|generated_present\","
        "\"plan_alignment\":\"aligned|not_aligned|not_applicable\",\"rationale\":str,\"confidence\":0..1}],\"summary\":str}.\n"
        f"PLANNED_SCENE: {json.dumps(_as_dict(plan), ensure_ascii=False)}\n"
        f"GENERATED_SCENE: {json.dumps({'title': scene.title, 'prose': scene.prose, 'canon_refs': scene.canon_refs, 'character_refs': scene.character_refs, 'entity_refs': scene.entity_refs}, ensure_ascii=False)}\n"
        f"RETRIEVED_EVIDENCE: {json.dumps(evidence_payload, ensure_ascii=False)}"
    )


def _build_revision_prompt(*, scene: SceneProseArtifact, plan: Any, audit: SceneSupportAuditArtifact) -> str:
    problematic = [item.model_dump() for item in audit.claims if item.classification in {"unsupported", "contradiction"}]
    return (
        "Revise generated continuation prose so every listed unsupported or contradictory canon claim is removed or corrected.\n"
        "Preserve supported canon, scene purpose, style, and permissible creative expansion. Do not invent replacement canon facts.\n"
        "Preserve present-scene events authorized by PLANNED_SCENE. Remove or reframe only the unsupported prior-canon assertion, motive, history, or contradiction identified in PROBLEMS.\n"
        "Return JSON only: {\"title\":str,\"prose\":str}.\n"
        f"SCENE: {json.dumps({'title': scene.title, 'prose': scene.prose, 'purpose': scene.purpose}, ensure_ascii=False)}\n"
        f"PLANNED_SCENE: {json.dumps(_as_dict(plan), ensure_ascii=False)}\n"
        f"PROBLEMS: {json.dumps(problematic, ensure_ascii=False)}\n"
        f"EVIDENCE: {json.dumps([item.model_dump() for item in audit.evidence], ensure_ascii=False)}"
    )


def _normalize_claims(
    rows: list[ClaimEvaluationPayload],
    *,
    scene: SceneProseArtifact,
    plan: Any,
    evidence: list[SupportEvidenceArtifact],
    request_ok: bool,
) -> list[ClaimSupportArtifact]:
    allowed_evidence = {item.evidence_id for item in evidence}
    if not request_ok:
        return [
            ClaimSupportArtifact(
                claim_id=_stable_id("claim", scene.scene_prose_id, "provider-error"),
                claim="Semantic support evaluation did not complete.",
                claim_type="canon_fact",
                classification="unsupported",
                severity="high",
                rationale="The quality gate fails closed when the reasoning provider does not return a valid audit.",
                confidence=1.0,
                temporal_scope="prior_canon",
                plan_alignment="not_applicable",
            )
        ]
    normalized: list[ClaimSupportArtifact] = []
    for index, row in enumerate(rows, start=1):
        claim = str(row.claim or "").strip()
        if not claim:
            continue
        claim_type = str(row.claim_type or "canon_fact").strip().lower()
        classification = str(row.classification or "unsupported").strip().lower()
        severity = str(row.severity or "medium").strip().lower()
        temporal_scope = str(
            row.temporal_scope or ("generated_present" if claim_type == "story_local" else "prior_canon")
        ).strip().lower()
        plan_alignment = str(
            row.plan_alignment or ("not_aligned" if temporal_scope == "generated_present" else "not_applicable")
        ).strip().lower()
        if claim_type not in {"canon_fact", "story_local"}:
            claim_type = "canon_fact"
        if classification not in {"supported", "creative_expansion", "unsupported", "contradiction"}:
            classification = "unsupported"
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        if temporal_scope not in {"prior_canon", "generated_present"}:
            temporal_scope = "prior_canon"
        if plan_alignment not in {"aligned", "not_aligned", "not_applicable"}:
            plan_alignment = "not_applicable"
        cited = [item for item in row.evidence_ids if item in allowed_evidence]
        if temporal_scope == "generated_present" and classification != "contradiction":
            claim_type = "story_local"
            classification = "creative_expansion"
            cited = []
            if plan is None:
                plan_alignment = "not_applicable"
        elif temporal_scope == "prior_canon":
            claim_type = "canon_fact"
            plan_alignment = "not_applicable"
        if classification == "supported" and not cited:
            classification = "unsupported"
        if claim_type == "story_local" and classification == "supported":
            classification = "creative_expansion"
            cited = []
        if claim_type == "canon_fact" and classification == "creative_expansion":
            classification = "unsupported"
        normalized.append(
            ClaimSupportArtifact(
                claim_id=_stable_id("claim", scene.scene_prose_id, index, claim),
                claim=claim,
                claim_type=claim_type,
                classification=classification,
                severity=severity,
                evidence_ids=cited,
                rationale=str(row.rationale or "").strip(),
                confidence=max(0.0, min(1.0, float(row.confidence or 0.0))),
                temporal_scope=temporal_scope,
                plan_alignment=plan_alignment,
            )
        )
    return normalized


def _support_issues(
    *,
    claims: list[ClaimSupportArtifact],
    request_ok: bool,
    has_evidence: bool,
    minimum_support: float,
    factual_support_rate: float,
) -> list[str]:
    issues: list[str] = []
    if not request_ok:
        issues.append("Semantic evaluation provider failed or returned an invalid payload.")
    if not has_evidence:
        issues.append("No canon evidence was retrieved for this scene.")
    if not claims:
        issues.append("Semantic evaluation returned no claims.")
    for claim in claims:
        if claim.classification == "unsupported" and claim.severity in {"medium", "high"}:
            issues.append(f"Unsupported canon claim: {claim.claim}")
        elif claim.classification == "contradiction":
            issues.append(f"Canon contradiction: {claim.claim}")
    if factual_support_rate < minimum_support:
        issues.append(f"Factual support rate {factual_support_rate:.4f} is below {minimum_support:.4f}.")
    return issues


def _weighted_support_metrics(claims: list[ClaimSupportArtifact]) -> tuple[float, float, float]:
    factual = [item for item in claims if item.claim_type == "canon_fact"]
    if not factual:
        return 1.0, 0.0, 0.0
    weights = {"low": 0.1, "medium": 0.5, "high": 1.0}
    total = sum(weights[item.severity] for item in factual)
    unsupported = sum(weights[item.severity] for item in factual if item.classification == "unsupported")
    contradictions = sum(weights[item.severity] for item in factual if item.classification == "contradiction")
    supported = max(0.0, total - unsupported - contradictions)
    return _ratio(supported, total), _ratio(unsupported, total), _ratio(contradictions, total)


def _rebuild_story(
    *,
    story: GeneratedStoryArtifact,
    scenes: list[SceneProseArtifact],
    support_revisions: list[RevisionRecordArtifact],
    decision: NarrativeSupportDecisionArtifact,
) -> GeneratedStoryArtifact:
    by_id = {item.scene_prose_id: item for item in scenes}
    for chapter in story.chapters:
        chapter_scenes = [by_id[item] for item in chapter.scene_prose_ids if item in by_id]
        chapter.prose = "\n\n".join(item.prose.strip() for item in chapter_scenes if item.prose.strip())
    existing = {item.revision_id: item for item in story.revisions}
    existing.update({item.revision_id: item for item in support_revisions})
    story.revisions = list(existing.values())
    story.metadata = {
        **dict(story.metadata or {}),
        "semantic_support": {
            "decision_id": decision.decision_id,
            "status": decision.status,
            "accepted": decision.accepted,
            "factual_support_rate": decision.factual_support_rate,
            "unsupported_invention_rate": decision.unsupported_invention_rate,
            "contradiction_rate": decision.contradiction_rate,
        },
    }
    return story


def _serialize_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        key: [_as_dict(item) for item in value] if isinstance(value, list) else _as_dict(value)
        for key, value in context.items()
        if key != "blueprint"
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _chunk_text(text: str, *, max_chars: int = 1800, overlap: int = 220) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        if end < len(cleaned):
            boundary = cleaned.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _stage_metadata(state: NarrativeSupportState, stage: str, started: float, **metrics: Any) -> dict[str, Any]:
    metadata = dict(state.get("run_metadata") or {})
    stage_metrics = dict(metadata.get("stage_metrics") or {})
    stage_metrics[stage] = {"elapsed_seconds": round(time.perf_counter() - started, 4), **metrics}
    metadata["stage_metrics"] = stage_metrics
    return metadata


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
    raise ValueError("NarrativeSupportRuntime requires a durable checkpointer or initialized persistence engine.")


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 1.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)
