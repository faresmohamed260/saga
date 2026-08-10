"""Persisted-contract evaluator for raw-book-to-deliverable qualification."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import wave
import zipfile
from array import array
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.audiobook_generation.store import AudiobookGenerationStore
from packages.canon_extraction.store import CanonExtractionStore
from packages.character_world_modeling.store import CharacterWorldModelingStore
from packages.character_world_modeling.quality import character_world_shape_complete
from packages.generation_planning.store import GenerationPlanningStore
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.production_orchestration import OrchestrationResult
from packages.observability_runtime import UsageGovernanceRuntime
from packages.production_orchestration.contracts import ArtifactReference
from packages.qualification_runtime.contracts import ProductionQualificationReport, QualificationCheck, QualificationThresholds
from packages.visual_generation.store import VisualGenerationStore


REQUIRED_STAGES = (
    "analysis_foundation", "canon_extraction", "character_world_modeling", "generation_planning",
    "narrative_generation", "narrative_support", "visual_generation", "audiobook_generation", "artifact_packaging",
)


class ProductionQualificationEvaluator:
    def __init__(self, *, persistence, thresholds: QualificationThresholds | None = None) -> None:
        self.persistence = persistence
        self.thresholds = thresholds or QualificationThresholds()
        self.analysis = AnalysisFoundationStore(persistence)
        self.canon = CanonExtractionStore(persistence)
        self.character_world = CharacterWorldModelingStore(persistence)
        self.planning = GenerationPlanningStore(persistence)
        self.narrative = NarrativeGenerationStore(persistence)
        self.visual = VisualGenerationStore(persistence)
        self.audiobook = AudiobookGenerationStore(persistence)

    def evaluate(self, *, result: OrchestrationResult, source_path: str, expected_source_sha256: str, expected_release_id: str = "") -> ProductionQualificationReport:
        request = result.request
        checks: list[QualificationCheck] = []
        outcomes = {item.stage: item for item in result.outcomes}
        self._check(checks, "orchestration.accepted", "orchestration", result.decision.accepted, result.decision.status, "accepted")
        self._check(checks, "stages.complete", "orchestration", set(REQUIRED_STAGES).issubset(outcomes), sorted(outcomes), list(REQUIRED_STAGES))
        fresh = {stage: str(dict((outcomes.get(stage).metadata if outcomes.get(stage) else {}) or {}).get("lineage", {}).get("execution_mode") or "") for stage in REQUIRED_STAGES}
        self._check(checks, "stages.fresh", "lineage", all(mode == "executed" for mode in fresh.values()), fresh, "all stages executed")
        total_seconds = sum(float(item.elapsed_seconds or 0.0) for item in result.outcomes)
        self._check(checks, "latency.total", "operations", total_seconds <= self.thresholds.max_run_seconds, total_seconds, self.thresholds.max_run_seconds)
        source = Path(source_path).resolve()
        actual_digest = _sha256(source.read_bytes())
        self._check(checks, "source.digest", "freshness", actual_digest == expected_source_sha256, actual_digest, expected_source_sha256)
        self._check(checks, "release.provenance", "release", not expected_release_id or request.metadata.get("release_id") == expected_release_id, request.metadata.get("release_id", ""), expected_release_id)

        books = self.analysis.list_books(series_id=request.series_id)
        chapters = [chapter for book in books for chapter in self.analysis.list_chapters(book_id=book.book_id)]
        scenes = [scene for book in books for scene in self.analysis.list_scenes(book_id=book.book_id)]
        identity = self.analysis.load_identity_bundle(series_id=request.series_id)
        self._check(checks, "analysis.shape", "analysis", len(books) == 1 and bool(chapters) and bool(scenes), {"books": len(books), "chapters": len(chapters), "scenes": len(scenes)}, "one book and non-empty chapters/scenes")
        self._check(checks, "identity.provider", "identity", bool(identity) and identity.provider_name == "modal_xcore_litbank", identity.provider_name if identity else "", "modal_xcore_litbank")
        characters = list(identity.characters if identity else [])
        self._check(checks, "identity.characters", "identity", len(characters) >= self.thresholds.min_identity_characters, len(characters), self.thresholds.min_identity_characters)
        corpus = _normalize(" ".join(chapter.content for chapter in chapters))
        supported = [character for character in characters if any(_normalize(name) in corpus for name in [character.display_name, *character.proper_mentions] if len(_normalize(name)) > 1)]
        evidence_rate = len(supported) / max(1, len(characters))
        self._check(checks, "identity.evidence_rate", "identity", evidence_rate >= self.thresholds.min_identity_evidence_rate, round(evidence_rate, 4), self.thresholds.min_identity_evidence_rate)

        events = self.canon.list_events(series_id=request.series_id)
        entities = self.canon.list_entities(series_id=request.series_id)
        timeline = self.canon.list_timeline(series_id=request.series_id)
        event_ids, scene_ids = {item.event_id for item in events}, {item.scene_id for item in scenes}
        references_valid = all(item.event_id in event_ids and item.scene_id in scene_ids for item in timeline) and all(item.scene_id in scene_ids for item in events)
        self._check(checks, "canon.shape", "canon", bool(events) and bool(timeline), {"events": len(events), "entities": len(entities), "timeline": len(timeline)}, "non-empty events and timeline")
        self._check(checks, "canon.references", "canon", references_valid, references_valid, True)

        profiles = self.character_world.list_character_profiles(series_id=request.series_id)
        states = self.character_world.list_stable_character_states(series_id=request.series_id)
        world = self.character_world.list_world_states(series_id=request.series_id)
        character_ids = {item.character_id for item in characters}
        self._check(
            checks,
            "world.shape",
            "world",
            character_world_shape_complete(
                profiles=profiles,
                stable_states=states,
                world_states=world,
                source_entities=entities,
            ),
            {"profiles": len(profiles), "states": len(states), "source_entities": len(entities), "world": len(world)},
            "stable state per profile and world state per extracted entity",
        )
        self._check(checks, "world.references", "world", all(item.character_id in character_ids for item in profiles), len([item for item in profiles if item.character_id not in character_ids]), 0)

        blueprint_id = str((outcomes.get("generation_planning").output_context if outcomes.get("generation_planning") else {}).get("blueprint_id") or "")
        blueprints = [item for item in self.planning.list_blueprints(series_id=request.series_id) if item.blueprint_id == blueprint_id]
        blueprint = blueprints[0] if blueprints else None
        self._check(checks, "planning.blueprint", "generation", bool(blueprint and blueprint.chapter_outline and blueprint.scene_plan), {"blueprint_id": blueprint_id, "chapters": len(blueprint.chapter_outline) if blueprint else 0, "scenes": len(blueprint.scene_plan) if blueprint else 0}, "non-empty grounded blueprint")

        story_id = str((outcomes.get("narrative_generation").output_context if outcomes.get("narrative_generation") else {}).get("story_id") or "")
        story = self.narrative.load_story(series_id=request.series_id, story_id=story_id)
        story_words = sum(len(item.prose.split()) for item in story.chapters)
        continuity_passed = bool(story.continuity_checks) and all(item.passed for item in story.continuity_checks)
        self._check(checks, "narrative.content", "narrative", bool(story.chapters) and story_words >= self.thresholds.min_story_words, {"chapters": len(story.chapters), "words": story_words}, self.thresholds.min_story_words)
        self._check(checks, "narrative.continuity", "narrative", continuity_passed, [item.issues for item in story.continuity_checks], "all continuity checks pass")
        support = dict(story.metadata.get("semantic_support") or {})
        support_rate = float(support.get("factual_support_rate") or 0.0)
        contradiction_rate = float(support.get("contradiction_rate") or 0.0)
        self._check(checks, "narrative.support", "narrative", support_rate >= self.thresholds.min_factual_support_rate and contradiction_rate <= self.thresholds.max_contradiction_rate, {"support_rate": support_rate, "contradiction_rate": contradiction_rate}, {"min_support": self.thresholds.min_factual_support_rate, "max_contradiction": self.thresholds.max_contradiction_rate})

        prompts = self.visual.list_prompts(series_id=request.series_id, story_id=story_id)
        renders = self.visual.list_renders(series_id=request.series_id, story_id=story_id)
        audits = self.visual.list_audits(series_id=request.series_id, story_id=story_id)
        accepted_audits = [item for item in audits if item.accepted]
        requested_types = set(request.execution_limits.visual_include_types)
        accepted_types = {item.target_type for item in accepted_audits}
        scene_prose = self.narrative.list_scene_prose(series_id=request.series_id, story_id=story_id)
        applicable_types = applicable_visual_types(scene_prose=scene_prose, entities=entities)
        scores = [min(item.prompt_alignment_score, item.subject_consistency_score, item.composition_score) for item in accepted_audits]
        defects = [item.defect_score for item in accepted_audits]
        self._check(
            checks, "visual.coverage", "visual",
            bool(prompts) and applicable_types.issubset(accepted_types),
            {"allowed": sorted(requested_types), "applicable": sorted(applicable_types), "accepted": sorted(accepted_types)},
            "all story-applicable types accepted",
        )
        omitted_types = requested_types - applicable_types
        self._check(
            checks, "visual.inapplicable_types", "visual", not omitted_types,
            sorted(omitted_types), [], critical=False,
            detail="Allowed types without grounded story targets were intentionally not rendered.",
        )
        self._check(checks, "visual.semantic_scores", "visual", bool(scores) and min(scores) >= self.thresholds.min_visual_score and max(defects) <= self.thresholds.max_visual_defect_score, {"min_score": min(scores) if scores else 0.0, "max_defect": max(defects) if defects else 1.0}, {"min_score": self.thresholds.min_visual_score, "max_defect": self.thresholds.max_visual_defect_score})

        audio_run_id = str((outcomes.get("audiobook_generation").output_context if outcomes.get("audiobook_generation") else {}).get("audiobook_run_id") or "")
        audio_audits = self.audiobook.list_audits(series_id=request.series_id, story_id=story_id, run_id=audio_run_id)
        accepted_audio = [item for item in audio_audits if item.accepted]
        self._check(checks, "audio.transcription", "audio", bool(accepted_audio) and max(item.word_error_rate for item in accepted_audio) <= self.thresholds.max_audio_word_error_rate and min(item.word_match_rate for item in accepted_audio) >= self.thresholds.min_audio_word_match_rate, {"accepted": len(accepted_audio), "max_wer": max((item.word_error_rate for item in accepted_audio), default=1.0), "min_match": min((item.word_match_rate for item in accepted_audio), default=0.0)}, {"max_wer": self.thresholds.max_audio_word_error_rate, "min_match": self.thresholds.min_audio_word_match_rate})

        manifest = result.manifest
        self._check(checks, "package.manifest", "packaging", bool(manifest and manifest.status == "accepted"), manifest.status if manifest else "missing", "accepted")
        artifact_metrics = self._artifact_checks(checks, list(manifest.artifacts if manifest else []))
        queue_items = [item for item in self.persistence.execution_queue.list(limit=10000) if item.get("run_id") == request.run_id]
        queue_events = self.persistence.execution_queue.list_events(run_id=request.run_id, limit=10000)
        self._check(checks, "queue.terminal", "operations", len(queue_items) == 1 and queue_items[0].get("status") == "succeeded", [item.get("status") for item in queue_items], "one succeeded queue item")
        serialized = json.dumps({"result": result.model_dump(), "checks": [item.model_dump() for item in checks]}, sort_keys=True, default=str)
        exposed = [name for name in _secret_names() if os.getenv(name) and os.getenv(name) in serialized]
        self._check(checks, "security.secrets", "security", not exposed, exposed, [])
        observation_rows = self.persistence.observability.list(run_id=request.run_id, limit=10000)
        usage_summary = UsageGovernanceRuntime(store=self.persistence.usage).summary(run_id=request.run_id)
        provider_names = _provider_visibility_names(observation_rows, usage_summary)
        self._check(checks, "operations.provider_visibility", "operations", bool(provider_names), provider_names, "provider telemetry")
        self._check(
            checks, "operations.usage_visibility", "operations", usage_summary["charge_count"] > 0,
            usage_summary, "at least one attributed provider charge",
        )
        self._check(
            checks, "operations.cost_visibility", "operations",
            usage_summary["charge_count"] > 0
            and usage_summary["unpriced_charge_count"] == 0
            and usage_summary["reconciled"],
            {"charge_count": usage_summary["charge_count"], "priced_charge_count": usage_summary["priced_charge_count"],
             "unpriced_charge_count": usage_summary["unpriced_charge_count"],
             "reconciled_charge_count": usage_summary["reconciled_charge_count"], "cost_usd": usage_summary["cost_usd"]},
            "all provider charges priced and reconciled with settlement evidence",
        )
        accepted = not any(item.critical and item.status == "failed" for item in checks)
        metrics = {
            "stage_seconds": {item.stage: item.elapsed_seconds for item in result.outcomes}, "total_stage_seconds": total_seconds,
            "queue_event_count": len(queue_events), "identity_evidence_rate": evidence_rate, "story_words": story_words,
            "visual_render_count": len(renders), "accepted_visual_count": len(accepted_audits), "accepted_audio_segment_count": len(accepted_audio),
            "usage": usage_summary,
            **artifact_metrics,
        }
        return ProductionQualificationReport(
            report_id=f"qualification-{request.run_id}", run_id=request.run_id, series_id=request.series_id,
            source_path=str(source), source_sha256=actual_digest, release_id=str(request.metadata.get("release_id") or ""),
            accepted=accepted, checks=checks, metrics=metrics,
        )

    def persist(self, report: ProductionQualificationReport) -> ProductionQualificationReport:
        stored = self.persistence.artifacts.store_json(
            artifact_type="runtime_report", filename=f"{report.run_id}-production-qualification.json",
            payload=report.model_dump(), provider_name="qualification_runtime", report_kind="production_qualification",
            series_id=report.series_id, run_id=report.run_id, metadata={"accepted": report.accepted, "release_id": report.release_id},
        )
        return report.model_copy(update={"artifact_reference": stored})

    def _artifact_checks(self, checks: list[QualificationCheck], refs: list[ArtifactReference]) -> dict[str, Any]:
        roles = {item.role for item in refs}
        self._check(checks, "artifacts.roles", "artifacts", "generated_epub" in roles and "audiobook" in roles and any(role.startswith("visual:") for role in roles), sorted(roles), "EPUB, audiobook, and visual artifacts")
        verified = 0
        for ref in refs:
            if not ref.bucket_name or not ref.object_path:
                continue
            data = self.persistence.objects.download_bytes(ref.bucket_name, ref.object_path)
            digest_ok = not ref.sha256 or _sha256(data) == ref.sha256
            length_ok = not ref.byte_length or len(data) == ref.byte_length
            self._check(checks, f"artifact.integrity.{ref.artifact_id}", "artifacts", digest_ok and length_ok, {"bytes": len(data), "sha256": _sha256(data)}, {"bytes": ref.byte_length, "sha256": ref.sha256})
            if ref.role.startswith("visual:"):
                quality = image_quality(data)
                passed = quality["width"] >= self.thresholds.min_image_dimension and quality["height"] >= self.thresholds.min_image_dimension and quality["luma_mean"] >= self.thresholds.min_image_luma_mean and quality["luma_stddev"] >= self.thresholds.min_image_luma_stddev
                self._check(checks, f"artifact.image.{ref.artifact_id}", "visual", passed, quality, self.thresholds.model_dump(include={"min_image_dimension", "min_image_luma_mean", "min_image_luma_stddev"}))
            elif ref.role == "audiobook":
                quality = audio_quality(data)
                self._check(checks, f"artifact.audio.{ref.artifact_id}", "audio", quality["duration_seconds"] >= self.thresholds.min_audio_duration_seconds and quality["rms"] >= self.thresholds.min_audio_rms, quality, {"min_duration": self.thresholds.min_audio_duration_seconds, "min_rms": self.thresholds.min_audio_rms})
            elif ref.role == "generated_epub":
                quality = epub_quality(data)
                self._check(checks, f"artifact.epub.{ref.artifact_id}", "packaging", quality["valid"] and quality["chapter_count"] > 0, quality, "valid EPUB with chapters")
            verified += 1
        return {"artifact_count": len(refs), "verified_artifact_count": verified}

    @staticmethod
    def _check(checks: list[QualificationCheck], check_id: str, category: str, passed: bool, observed: Any, expected: Any, *, critical: bool = True, detail: str = "") -> None:
        checks.append(QualificationCheck(check_id=check_id, category=category, status="passed" if passed else ("failed" if critical else "warning"), critical=critical, observed=observed, expected=expected, detail=detail))


def image_quality(data: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        luma = image.convert("L")
        stats = ImageStat.Stat(luma)
        return {"format": image.format, "width": image.width, "height": image.height, "luma_mean": round(float(stats.mean[0]), 4), "luma_stddev": round(float(stats.stddev[0]), 4)}


def _provider_visibility_names(
    observation_rows: list[dict[str, Any]], usage_summary: dict[str, Any]
) -> list[str]:
    observed = {
        str(row.get("name") or "")
        for row in observation_rows
        if str(row.get("name") or "").startswith("provider.")
    }
    attributed = {
        f"provider.{provider}"
        for provider in list(usage_summary.get("providers") or [])
        if str(provider or "").strip()
    }
    return sorted(observed | attributed)


def audio_quality(data: bytes) -> dict[str, Any]:
    with wave.open(io.BytesIO(data), "rb") as stream:
        frames = stream.readframes(stream.getnframes())
        width, channels, rate, count = stream.getsampwidth(), stream.getnchannels(), stream.getframerate(), stream.getnframes()
    if width != 2:
        return {"duration_seconds": count / max(1, rate), "sample_rate": rate, "channels": channels, "sample_width": width, "rms": 0.0}
    samples = array("h")
    samples.frombytes(frames)
    rms = math.sqrt(sum((item / 32768.0) ** 2 for item in samples) / max(1, len(samples)))
    return {"duration_seconds": round(count / max(1, rate), 4), "sample_rate": rate, "channels": channels, "sample_width": width, "rms": round(rms, 6)}


def epub_quality(data: bytes) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            bad = archive.testzip()
            names = archive.namelist()
            mimetype = archive.read("mimetype").decode("ascii")
            chapters = [name for name in names if re.fullmatch(r"OEBPS/chapter-\d+\.xhtml", name)]
            return {"valid": bad is None and mimetype == "application/epub+zip" and "META-INF/container.xml" in names and "OEBPS/content.opf" in names, "chapter_count": len(chapters), "bad_member": bad or ""}
    except (KeyError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return {"valid": False, "chapter_count": 0, "error": type(exc).__name__}


def applicable_visual_types(*, scene_prose: list[Any], entities: list[Any]) -> set[str]:
    result: set[str] = set()
    if scene_prose:
        result.add("scene")
    character_refs = {ref for scene in scene_prose for ref in list(getattr(scene, "character_refs", []) or [])}
    entity_refs = {ref for scene in scene_prose for ref in list(getattr(scene, "entity_refs", []) or [])}
    if character_refs:
        result.add("character")
    for entity in entities:
        if getattr(entity, "entity_id", "") not in entity_refs:
            continue
        target_type = _entity_visual_type(getattr(entity, "entity_type", ""))
        if target_type:
            result.add(target_type)
    return result


def _entity_visual_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if any(token in normalized for token in ("location", "place", "building", "room", "estate", "court", "forest", "city", "land", "kingdom", "island")):
        return "location"
    if any(token in normalized for token in ("creature", "animal", "beast", "monster", "horse", "bird", "serpent")):
        return "creature"
    if any(token in normalized for token in ("object", "artifact", "weapon", "item", "book", "letter", "crown", "knife", "sword", "bridle", "ring")):
        return "object"
    return ""


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _secret_names() -> tuple[str, ...]:
    return tuple(name for name in os.environ if any(token in name.upper() for token in ("TOKEN", "PASSWORD", "SECRET", "API_KEY", "SERVICE_ROLE")))
