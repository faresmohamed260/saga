"""Active-architecture stage inspection, execution, and packaging bindings."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.audiobook_generation.store import AudiobookGenerationStore
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.generation_planning.store import GenerationPlanningStore
from packages.narrative_generation.contracts import (
    GeneratedStoryArtifact,
    NarrativeGenerationResult,
    NarrativeSupportDecisionArtifact,
)
from packages.narrative_generation.quality import require_narrative_generation_acceptance, require_narrative_semantic_acceptance
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.production_orchestration.contracts import ArtifactReference, OrchestrationRequest, StageName, StageOutcomeArtifact
from packages.production_orchestration.packaging import DeliverableSink, DeliverableSource, PackageChapter, PackageSourceBundle
from packages.visual_generation.contracts import VisualGenerationDecisionArtifact
from packages.visual_generation.store import VisualGenerationStore


class ActiveStageBinding:
    def __init__(
        self,
        *,
        inspector: Callable[[OrchestrationRequest, dict[str, StageOutcomeArtifact]], StageOutcomeArtifact | None],
        executor: Callable[[OrchestrationRequest, dict[str, StageOutcomeArtifact]], Any],
        output_builder: Callable[[OrchestrationRequest, dict[str, StageOutcomeArtifact], StageOutcomeArtifact], Any] | None = None,
    ) -> None:
        self.inspector = inspector
        self.executor = executor
        self.output_builder = output_builder

    def inspect(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        return self.inspector(request, outcomes)

    def execute(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact:
        self.executor(request, outcomes)
        inspected = self.inspector(request, outcomes)
        if inspected is None:
            raise RuntimeError("Stage execution completed without a persisted outcome artifact.")
        return inspected.model_copy(update={"reused": False})

    def lineage_output(
        self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact], outcome: StageOutcomeArtifact,
    ) -> Any:
        if self.output_builder is None:
            return outcome.model_dump()
        return self.output_builder(request, outcomes, outcome)


class ActiveStageInspector:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.analysis = AnalysisFoundationStore(persistence)
        self.canon = CanonExtractionStore(persistence)
        self.character_world = CharacterWorldModelingStore(persistence)
        self.planning = GenerationPlanningStore(persistence)
        self.narrative = NarrativeGenerationStore(persistence)
        self.visual = VisualGenerationStore(persistence)
        self.audiobook = AudiobookGenerationStore(persistence)

    def analysis_foundation(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        del outcomes
        books = self.analysis.list_books(series_id=request.series_id)
        scenes = [scene for book in books for scene in self.analysis.list_scenes(book_id=book.book_id)]
        identity = self.analysis.load_identity_bundle(series_id=request.series_id)
        if not books or not scenes or identity is None:
            return None
        return _accepted("analysis_foundation", {"book_ids": [item.book_id for item in books]}, {"book_count": len(books), "scene_count": len(scenes), "identity_count": len(identity.characters)})

    def canon_extraction(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        del outcomes
        events = self.canon.list_events(series_id=request.series_id)
        entities = self.canon.list_entities(series_id=request.series_id)
        timeline = self.canon.list_timeline(series_id=request.series_id)
        if not events or not timeline:
            return None
        return _accepted("canon_extraction", {}, {"event_count": len(events), "entity_count": len(entities), "timeline_count": len(timeline)})

    def character_world_modeling(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        del outcomes
        profiles = self.character_world.list_character_profiles(series_id=request.series_id)
        world = self.character_world.list_world_states(series_id=request.series_id)
        source_entities = self.canon.list_entities(series_id=request.series_id)
        if not profiles or (source_entities and not world):
            return None
        return _accepted(
            "character_world_modeling",
            {},
            {
                "character_profile_count": len(profiles),
                "source_entity_count": len(source_entities),
                "world_state_count": len(world),
            },
        )

    def generation_planning(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        del outcomes
        blueprints = self.planning.list_blueprints(series_id=request.series_id)
        blueprint_id = request.blueprint_id
        if not blueprint_id and request.story_id:
            try:
                blueprint_id = self.narrative.load_story(series_id=request.series_id, story_id=request.story_id).blueprint_id
            except FileNotFoundError:
                blueprint_id = ""
        if blueprint_id:
            blueprints = [item for item in blueprints if item.blueprint_id == blueprint_id]
        elif request.premise:
            intents = self.planning.list_intents(series_id=request.series_id)
            matching_intent_ids = {
                item.intent_id for item in intents
                if item.premise == request.premise
                and item.target_audience == request.target_audience
                and item.tone == request.tone
                and item.desired_chapter_count == request.desired_chapter_count
            }
            blueprints = [item for item in blueprints if item.intent_id in matching_intent_ids]
        if not blueprints:
            return None
        blueprint = blueprints[0]
        return _accepted("generation_planning", {"blueprint_id": blueprint.blueprint_id}, {"chapter_count": len(blueprint.chapter_outline), "scene_count": len(blueprint.scene_plan)})

    def narrative_generation(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        story_id = _story_id(request, outcomes)
        if not story_id:
            planning = outcomes.get("generation_planning")
            blueprint_id = str((planning.output_context if planning else {}).get("blueprint_id") or request.blueprint_id)
            candidates = self.persistence.stories.list_stories(series_id=request.series_id, limit=1000)
            story = next(
                (
                    GeneratedStoryArtifact.model_validate(dict(item.get("payload") or {}))
                    for item in candidates
                    if str(dict(item.get("payload") or {}).get("blueprint_id") or "") == blueprint_id
                ),
                None,
            )
            story_id = story.story_id if story else ""
        if not story_id:
            return None
        try:
            story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
        except FileNotFoundError:
            return None
        if not story.chapters:
            return None
        try:
            quality = _require_story_quality(self.narrative, series_id=request.series_id, story=story)
        except ValueError:
            return None
        return _accepted(
            "narrative_generation",
            {"story_id": story.story_id, "blueprint_id": story.blueprint_id},
            {
                "chapter_count": len(story.chapters),
                "word_count": sum(len(item.prose.split()) for item in story.chapters),
                "quality_passed": quality.pass_quality_gate,
            },
        )

    def narrative_support(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        story_id = _story_id(request, outcomes)
        if not story_id:
            return None
        try:
            story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
            _require_story_quality(self.narrative, series_id=request.series_id, story=story)
        except (FileNotFoundError, ValueError):
            return None
        rows = self.persistence.library.list_records(
            record_type="narrative_support_decision",
            series_id=request.series_id,
            scene_id=story_id,
            limit=10,
        )
        decision = next(
            (
                NarrativeSupportDecisionArtifact.model_validate(dict(row.get("payload") or {}))
                for row in reversed(rows)
            ),
            None,
        )
        if decision is None:
            return None
        metrics = {
            "factual_support_rate": decision.factual_support_rate,
            "unsupported_invention_rate": decision.unsupported_invention_rate,
            "contradiction_rate": decision.contradiction_rate,
            "provider_success_rate": decision.provider_success_rate,
            "status": decision.status,
        }
        if not decision.accepted:
            return StageOutcomeArtifact(
                stage="narrative_support",
                status="rejected",
                accepted=False,
                output_context={"story_id": story.story_id, "support_decision_id": decision.decision_id},
                metrics=metrics,
                reasons=list(decision.reasons),
            )
        try:
            require_narrative_semantic_acceptance(story)
        except ValueError:
            return None
        return _accepted("narrative_support", {"story_id": story.story_id}, metrics)

    def visual_generation(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        story_id = _story_id(request, outcomes)
        rows = self.persistence.library.list_records(record_type="visual_generation_decision", series_id=request.series_id, scene_id=story_id, limit=100)
        decisions = [VisualGenerationDecisionArtifact.model_validate(dict(row.get("payload") or {})) for row in rows]
        decision = decisions[-1] if decisions else None
        if decision is None:
            return None
        audits = self.visual.list_audits(series_id=request.series_id, story_id=story_id)
        metrics = {"accepted_render_count": len([item for item in audits if item.accepted])}
        if not decision.accepted:
            return StageOutcomeArtifact(
                stage="visual_generation",
                status="rejected",
                accepted=False,
                output_context={"story_id": story_id, "visual_decision_id": decision.decision_id},
                metrics=metrics,
                reasons=list(decision.reasons),
            )
        return _accepted("visual_generation", {"story_id": story_id, "visual_decision_id": decision.decision_id}, metrics)

    def audiobook_generation(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        story_id = _story_id(request, outcomes)
        run = self._accepted_audiobook_run(request, story_id)
        if run is None:
            return None
        run_id = str(run.get("run_id") or "")
        decisions = self.audiobook.list_decisions(series_id=request.series_id, story_id=story_id, run_id=run_id)
        decision = next((item for item in decisions if item.accepted), None)
        manifests = self.audiobook.list_manifests(series_id=request.series_id, story_id=story_id, run_id=run_id)
        if decision is None or not manifests:
            return None
        manifest = manifests[0]
        return _accepted("audiobook_generation", {"story_id": story_id, "audiobook_run_id": run_id}, {"duration_seconds": manifest.duration_seconds, "chapter_count": len(manifest.chapter_audio_ids)})

    def _accepted_audiobook_run(self, request: OrchestrationRequest, story_id: str) -> dict[str, Any] | None:
        rows = self.persistence.audiobooks.list_runs(series_id=request.series_id, limit=1000)
        matches = [row for row in rows if str(dict(row.get("payload") or {}).get("story_id") or "") == story_id and str(row.get("status") or "") == "completed"]
        if request.audiobook_run_id:
            matches = [row for row in matches if str(row.get("run_id") or "") == request.audiobook_run_id]
        return matches[0] if matches else None

    def lineage_output(
        self, stage: StageName, request: OrchestrationRequest,
        outcomes: dict[str, StageOutcomeArtifact], outcome: StageOutcomeArtifact,
    ) -> dict[str, Any]:
        if stage == "analysis_foundation":
            books = self.analysis.list_books(series_id=request.series_id)
            identity = self.analysis.load_identity_bundle(series_id=request.series_id)
            return {
                "books": _model_payloads(books),
                "chapters": _model_payloads([chapter for book in books for chapter in self.analysis.list_chapters(book_id=book.book_id)]),
                "scenes": _model_payloads([scene for book in books for scene in self.analysis.list_scenes(book_id=book.book_id)]),
                "identity": identity.model_dump() if identity else None,
            }
        if stage == "canon_extraction":
            return {
                "events": _model_payloads(self.canon.list_events(series_id=request.series_id)),
                "entities": _model_payloads(self.canon.list_entities(series_id=request.series_id)),
                "relationships": _model_payloads(self.canon.list_relationships(series_id=request.series_id)),
                "timeline": _model_payloads(self.canon.list_timeline(series_id=request.series_id)),
            }
        if stage == "character_world_modeling":
            return {
                "character_profiles": _model_payloads(self.character_world.list_character_profiles(series_id=request.series_id)),
                "stable_character_states": _model_payloads(self.character_world.list_stable_character_states(series_id=request.series_id)),
                "world_states": _model_payloads(self.character_world.list_world_states(series_id=request.series_id)),
            }
        if stage == "generation_planning":
            blueprint_id = str(outcome.output_context.get("blueprint_id") or request.blueprint_id)
            items = self.planning.list_blueprints(series_id=request.series_id)
            return {"blueprints": _model_payloads([item for item in items if not blueprint_id or item.blueprint_id == blueprint_id])}
        story_id = _story_id(request, {**outcomes, stage: outcome})
        if stage == "narrative_generation":
            story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
            scenes = self.narrative.list_scene_prose(series_id=request.series_id, story_id=story_id)
            return {
                "story_id": story.story_id,
                "blueprint_id": story.blueprint_id,
                "chapters": [
                    {
                        "chapter_index": item.chapter_index,
                        "scene_prose_ids": item.scene_prose_ids,
                        "canon_refs": item.canon_refs,
                        "character_refs": item.character_refs,
                        "entity_refs": item.entity_refs,
                    }
                    for item in story.chapters
                ],
                "scenes": [
                    {
                        "scene_prose_id": item.scene_prose_id,
                        "source_scene_id": item.source_scene_id,
                        "chapter_index": item.chapter_index,
                        "scene_index": item.scene_index,
                        "canon_refs": item.canon_refs,
                        "character_refs": item.character_refs,
                        "entity_refs": item.entity_refs,
                    }
                    for item in scenes
                ],
            }
        if stage == "narrative_support":
            story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
            decisions = self.persistence.library.list_records(
                record_type="narrative_support_decision",
                series_id=request.series_id,
                scene_id=story_id,
                limit=100,
            )
            return {
                "story": story.model_dump(),
                "scenes": _model_payloads(self.narrative.list_scene_prose(series_id=request.series_id, story_id=story_id)),
                "support_decisions": [dict(item.get("payload") or {}) for item in decisions],
            }
        if stage == "visual_generation":
            decisions = self.persistence.library.list_records(
                record_type="visual_generation_decision", series_id=request.series_id, scene_id=story_id, limit=100,
            )
            return {
                "prompts": _model_payloads(self.visual.list_prompts(series_id=request.series_id, story_id=story_id)),
                "renders": _model_payloads(self.visual.list_renders(series_id=request.series_id, story_id=story_id)),
                "audits": _model_payloads(self.visual.list_audits(series_id=request.series_id, story_id=story_id)),
                "decisions": [dict(item.get("payload") or {}) for item in decisions],
            }
        if stage == "audiobook_generation":
            run_id = str(outcome.output_context.get("audiobook_run_id") or request.audiobook_run_id)
            return {
                "segments": _model_payloads(self.audiobook.list_segments(series_id=request.series_id, story_id=story_id, run_id=run_id)),
                "syntheses": _model_payloads(self.audiobook.list_syntheses(series_id=request.series_id, story_id=story_id, run_id=run_id)),
                "audits": _model_payloads(self.audiobook.list_audits(series_id=request.series_id, story_id=story_id, run_id=run_id)),
                "chapters": _model_payloads(self.audiobook.list_chapters(series_id=request.series_id, story_id=story_id, run_id=run_id)),
                "manifests": _model_payloads(self.audiobook.list_manifests(series_id=request.series_id, story_id=story_id, run_id=run_id)),
                "decisions": _model_payloads(self.audiobook.list_decisions(series_id=request.series_id, story_id=story_id, run_id=run_id)),
            }
        return outcome.model_dump()


class ActiveDeliverableSource(DeliverableSource):
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence
        self.narrative = NarrativeGenerationStore(persistence)
        self.visual = VisualGenerationStore(persistence)
        self.audiobook = AudiobookGenerationStore(persistence)

    def collect(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> PackageSourceBundle:
        story_id = _story_id(request, outcomes)
        story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
        _require_story_quality(self.narrative, series_id=request.series_id, story=story)
        require_narrative_semantic_acceptance(story)
        refs: list[ArtifactReference] = []
        if request.include_visuals:
            accepted = {item.render_id for item in self.visual.list_audits(series_id=request.series_id, story_id=story_id) if item.accepted}
            for render in self.visual.list_renders(series_id=request.series_id, story_id=story_id):
                if render.render_id in accepted and render.bucket_name and render.object_path:
                    refs.append(ArtifactReference(
                        artifact_id=render.render_id, role=f"visual:{render.target_type}", media_type="image/png",
                        bucket_name=render.bucket_name, object_path=render.object_path, byte_length=render.byte_length,
                        sha256=render.image_sha256, source_stage="visual_generation",
                        metadata={"target_ref": render.target_ref, "seed": render.seed},
                    ))
        if request.include_audiobook:
            run_id = str((outcomes.get("audiobook_generation") or StageOutcomeArtifact(stage="audiobook_generation", status="rejected")).output_context.get("audiobook_run_id") or request.audiobook_run_id)
            manifests = self.audiobook.list_manifests(series_id=request.series_id, story_id=story_id, run_id=run_id)
            if not manifests:
                raise ValueError(f"Accepted audiobook manifest for story '{story_id}' was not found.")
            audio = manifests[0]
            refs.append(ArtifactReference(
                artifact_id=audio.manifest_id, role="audiobook", media_type="audio/wav", bucket_name=audio.bucket_name,
                object_path=audio.object_path, byte_length=audio.byte_length, source_stage="audiobook_generation",
                metadata={"duration_seconds": audio.duration_seconds, "sample_rate": audio.sample_rate, "run_id": audio.run_id},
            ))
        refs.extend(self._runtime_reports(request, story_id))
        return PackageSourceBundle(
            story_id=story.story_id,
            title=story.title,
            chapters=[PackageChapter(chapter_index=item.chapter_index, title=item.title or f"Chapter {item.chapter_index}", prose=item.prose) for item in story.chapters],
            artifact_refs=refs,
            provenance={
                "series_id": request.series_id,
                "story_id": story.story_id,
                "blueprint_id": story.blueprint_id,
                "canon_refs": list(story.canon_refs),
                "character_refs": list(story.character_refs),
                "entity_refs": list(story.entity_refs),
                "stage_decisions": {name: item.status for name, item in outcomes.items()},
            },
        )

    def _runtime_reports(self, request: OrchestrationRequest, story_id: str) -> list[ArtifactReference]:
        rows = self.persistence.library.list_records(record_type="artifact", limit=10000)
        latest_by_provider: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
        for row in rows:
            payload = dict(row.get("payload") or {})
            if payload.get("artifact_type") != "runtime_report" or payload.get("series_id") != request.series_id or payload.get("story_id") != story_id:
                continue
            provider = str(payload.get("provider_name") or "runtime")
            created_at = int(payload.get("created_at") or 0)
            if provider not in latest_by_provider or created_at > latest_by_provider[provider][0]:
                latest_by_provider[provider] = (created_at, row, payload)
        refs = []
        for provider, (_, row, payload) in sorted(latest_by_provider.items()):
            refs.append(ArtifactReference(
                artifact_id=str(row.get("record_id") or ""), role="runtime_report", media_type=str(payload.get("content_type") or "application/json"),
                bucket_name=str(payload.get("bucket_name") or ""), object_path=str(payload.get("object_path") or ""),
                byte_length=int(payload.get("size_bytes") or 0), source_stage=provider,
            ))
        return refs


class PersistenceDeliverableSink(DeliverableSink):
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence

    def store_epub(self, *, request: OrchestrationRequest, filename: str, data: bytes) -> ArtifactReference:
        stored = self.persistence.artifacts.store_bytes(
            artifact_type="story_export", data=data, filename=filename, content_type="application/epub+zip",
            series_id=request.series_id, story_id=request.story_id, run_id=request.run_id,
            provider_name="production_orchestration", metadata={"kind": "epub", "version": 1},
        )
        return _stored_ref(stored, role="generated_epub", source_stage="artifact_packaging", sha256=hashlib.sha256(data).hexdigest())

    def store_manifest(self, *, request: OrchestrationRequest, filename: str, payload: dict) -> ArtifactReference:
        stored = self.persistence.artifacts.store_json(
            artifact_type="story_export", payload=payload, filename=filename,
            series_id=request.series_id, story_id=request.story_id, run_id=request.run_id,
            provider_name="production_orchestration", metadata={"kind": "deliverable_manifest", "version": 1},
        )
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return _stored_ref(stored, role="deliverable_manifest", source_stage="artifact_packaging", sha256=digest)


def _accepted(stage: StageName, context: dict[str, Any], metrics: dict[str, Any]) -> StageOutcomeArtifact:
    now = int(time.time())
    return StageOutcomeArtifact(stage=stage, status="accepted", accepted=True, started_at=now, completed_at=now, output_context=context, metrics=metrics)


def _require_story_quality(store: NarrativeGenerationStore, *, series_id: str, story: GeneratedStoryArtifact):
    context = store.load_series_context(series_id=series_id, blueprint_id=story.blueprint_id)
    blueprint = context.get("blueprint")
    if blueprint is None:
        raise ValueError(f"Blueprint '{story.blueprint_id}' was not found for story '{story.story_id}'.")
    scenes = store.list_scene_prose(series_id=series_id, story_id=story.story_id)
    return require_narrative_generation_acceptance(
        NarrativeGenerationResult(series_id=series_id, story=story, scene_prose=scenes), blueprint=blueprint,
    )


def _story_id(request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> str:
    for stage in ("narrative_support", "narrative_generation"):
        if stage in outcomes and outcomes[stage].output_context.get("story_id"):
            return str(outcomes[stage].output_context["story_id"])
    return request.story_id


def _stored_ref(stored: dict[str, Any], *, role: str, source_stage: str, sha256: str) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=str(stored.get("record_id") or _stable_id(stored.get("bucket_name"), stored.get("object_path"))),
        role=role, media_type=str(stored.get("content_type") or "application/octet-stream"),
        bucket_name=str(stored.get("bucket_name") or ""), object_path=str(stored.get("object_path") or ""),
        byte_length=int(stored.get("bytes_written") or 0), sha256=sha256, source_stage=source_stage,
    )


def _stable_id(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(item or "") for item in parts).encode("utf-8")).hexdigest()[:24]


def _model_payloads(items: list[Any]) -> list[dict[str, Any]]:
    payloads = [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in items]
    return sorted(payloads, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
