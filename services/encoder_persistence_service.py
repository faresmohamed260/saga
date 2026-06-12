"""Headless encoder pipeline for persistent book ingestion."""

from __future__ import annotations

import logging
import time
import json
import os
import threading
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from analysis.scene_analysis_orchestrator import SceneAnalysisOrchestrator
from analysis.scene_analyzer import SceneAnalyzer
from analysis.scene_extractor import SceneExtractor
from analysis.visual_state_analyzer import VisualStateAnalyzer
from analysis.microtasks.identity_semantic_reviewer import IdentitySemanticReviewer
from analysis.microtasks.scene_semantic_reviewer import SceneSemanticReviewer
from analysis.microtasks.semantic_evidence_refiner import SemanticEvidenceRefiner
from core.pipeline_contract import (
    apply_identity_updates,
    build_canon_snapshot,
    build_entity_registry,
    build_event_ledger,
    build_export_contract_payload,
    build_formal_character_profiles,
    build_scene_context,
    build_state_result,
    build_story_index_summary,
    build_timeline,
    build_character_timelines,
    normalize_character_timelines,
    rebuild_resolved_scene_analyses,
)
from core.builders.relationship_profile_builder import RelationshipProfileBuilder
from core.stable_character_state import StableCharacterStateBuilder
from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionService
from redesign_lab.identity.identity_provider import resolve_identity_provider_input
from services.series_processor import SeriesProcessor
from services.web_entity_hint_service import WebEntityHintService
from timeline.causal_graph_service import CausalGraphService


class RateLimitGuardError(RuntimeError):
    """Raised when provider rate limits exhaust retries during a book encode."""


class SceneFailurePolicyError(RuntimeError):
    """Raised when scene failure policy blocks the encoder from continuing."""

    def __init__(self, message: str, *, contract: Dict[str, Any] | None = None, failure_report: Dict[str, Any] | None = None):
        super().__init__(message)
        self.contract = contract or {}
        self.failure_report = failure_report or {}


class EncoderPersistenceService:
    """Encode books into a durable SAGA contract and optionally persist to Neo4j."""

    ENCODER_VERSION = "encoder-persistence-v2"
    SCENE_FALLBACK_TARGETS = [2400, 1800, 1400, 1100, 900, 700, 500, 350, 250]
    DEFAULT_IDENTITY_PROVIDER = "booknlp_clean"
    PROVIDER_MODE_SINGLE = "single_provider"
    PROVIDER_MODE_ROTATING = "same_provider_rotating"
    PROVIDER_MODE_FALLBACK = "cross_provider_fallback"

    def __init__(
        self,
        *,
        analysis_model: str = "gpt_oss",
        identity_model: str = "gpt_oss",
        identity_provider: str = DEFAULT_IDENTITY_PROVIDER,
        identity_json_path: str | None = None,
        analysis_provider_mode: str = "single_provider",
        analysis_mode: str = "structured",
        target_scene_words: int = 0,
        max_chapters: int = 0,
        scene_failure_policy: str = "fail_fast",
        max_failed_scenes_absolute: int = 3,
        max_failed_scene_ratio: float = 0.10,
        min_nonempty_scene_ratio: float = 0.80,
        series_id: str | None = None,
        series_title: str | None = None,
        book_index_base: int = 1,
        identity_web_hints_enabled: bool = True,
    ) -> None:
        self.analysis_model = analysis_model
        self.identity_model = identity_model
        self.identity_provider = str(identity_provider or self.DEFAULT_IDENTITY_PROVIDER).strip().lower()
        if self.identity_provider != "booknlp_clean":
            raise ValueError(
                f"Unsupported identity provider: {self.identity_provider}. "
                "The legacy/custom identity resolver has been removed."
            )
        self.identity_json_path = str(identity_json_path or "").strip()
        requested_provider_mode = str(analysis_provider_mode or self.PROVIDER_MODE_SINGLE).strip().lower()
        if requested_provider_mode == "comparison_mode":
            requested_provider_mode = self.PROVIDER_MODE_FALLBACK
        self.analysis_provider_mode = requested_provider_mode
        self.analysis_mode = analysis_mode
        self.target_scene_words = target_scene_words
        self.max_chapters = max(0, int(max_chapters or 0))
        self.scene_failure_policy = str(scene_failure_policy or "fail_fast").strip().lower()
        self.max_failed_scenes_absolute = max(0, int(max_failed_scenes_absolute))
        self.max_failed_scene_ratio = max(0.0, float(max_failed_scene_ratio))
        self.min_nonempty_scene_ratio = max(0.0, min(1.0, float(min_nonempty_scene_ratio)))
        self.series_id = (series_id or "").strip()
        self.series_title = (series_title or "").strip()
        self.book_index_base = max(1, int(book_index_base))
        self.identity_web_hints_enabled = bool(identity_web_hints_enabled)
        self.stable_state_builder = StableCharacterStateBuilder()
        self.web_entity_hint_service = WebEntityHintService()

    def encode_books(
        self,
        book_inputs: List[Dict[str, Any]],
        *,
        progress_callback: Callable[[str, Dict[str, Any]], None] | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        started_at = time.perf_counter()
        prepared_books = self._prepare_book_inputs(book_inputs)
        series_id, series_title = self._series_context(prepared_books)
        checkpoint = self._load_checkpoint(checkpoint_path, prepared_books[0], series_id, series_title) if checkpoint_path and prepared_books else None

        if checkpoint:
            chapters = checkpoint["chapters"]
            identity_result = checkpoint["identity_result"]
            planned_scenes = checkpoint["planned_scenes"]
            scene_analyses = checkpoint["scene_analyses"]
            total_scenes = len(planned_scenes)
            resume_scene_count = len(scene_analyses)
            rebuilt = self._rebuild_story_state(scene_analyses, identity_result)
            resolved_scene_analyses = rebuilt["resolved_scene_analyses"]
            entity_registry = rebuilt["entity_registry"]
            state_result = rebuilt["state_result"]
            timeline = rebuilt["timeline"]
            event_ledger = rebuilt["event_ledger"]
            character_timelines = rebuilt["character_timelines"]
            character_profiles = rebuilt["character_profiles"]
            canon_snapshot = rebuilt["canon_snapshot"]
            stable_character_states = rebuilt["stable_character_states"]
            story_index_summary = rebuilt["story_index_summary"]
            visual_prompt_sets = rebuilt["visual_prompt_sets"]
            causal_graph_result: Dict[str, Any] = checkpoint.get("causal_graph_result") or self._empty_causal_graph_result()
            failed_scenes: List[Dict[str, Any]] = checkpoint.get("failed_scenes") or []
            self._emit(progress_callback, "resume", {
                "status": f"Resuming from scene {resume_scene_count + 1}/{total_scenes}",
                "completed_scenes": resume_scene_count,
                "total_scenes": total_scenes,
                "book": prepared_books[0]["title"],
            })
        else:
            self._emit(progress_callback, "chapters", {"status": "Loading chapters"})
            chapters = self._build_chapters(prepared_books)

            self._emit(progress_callback, "identity", {"status": "Loading BookNLP clean identity provider"})
            identity_result = self._run_identity_resolution(prepared_books, progress_callback=progress_callback)

            scene_analyses = []
            resolved_scene_analyses = []
            entity_registry = []
            state_result = {"transitions": [], "latest_state": []}
            timeline = []
            event_ledger = []
            character_timelines = []
            character_profiles = []
            canon_snapshot = []
            stable_character_states = []
            story_index_summary = {"document_count": 0}
            visual_prompt_sets = self._build_visual_prompt_sets(resolved_scene_analyses)
            causal_graph_result = self._empty_causal_graph_result()
            failed_scenes: List[Dict[str, Any]] = []

            planned_scenes = SceneExtractor.from_target_words(self.target_scene_words).extract_many(
                chapters,
                allow_cross_chapter=True,
            )
            total_scenes = len(planned_scenes)
            resume_scene_count = 0
            self._save_checkpoint(
                checkpoint_path,
                prepared_books[0],
                series_id,
                series_title,
                chapters,
                identity_result,
                planned_scenes,
                scene_analyses,
                phase="scene",
                total_scenes=total_scenes,
                causal_graph_result=causal_graph_result,
                failed_scenes=failed_scenes,
            )

        for scene_position, planned_scene in enumerate(planned_scenes[resume_scene_count:], start=resume_scene_count + 1):
            self._emit(progress_callback, "scene", {
                "status": f"Processing scene {scene_position}/{total_scenes}",
                "scene_position": scene_position,
                "total_scenes": total_scenes,
                "book_index": planned_scene.get("book_index"),
                "chapter_index": planned_scene.get("chapter_index"),
                "scene_index": planned_scene.get("scene_index"),
            })
            analyzed_scenes, attempted_targets = self._analyze_scene_with_heartbeat(
                planned_scene,
                identity_result=identity_result,
                state_result=state_result,
                resolved_scene_analyses=resolved_scene_analyses,
                progress_callback=progress_callback,
                scene_position=scene_position,
                total_scenes=total_scenes,
            )
            for scene_analysis in analyzed_scenes:
                failure_record = self._scene_failure_record(scene_analysis)
                if failure_record:
                    failed_scenes.append(failure_record)
                    if self.scene_failure_policy == "fail_fast":
                        quality = self._scene_quality_metrics(scene_analyses, failed_scenes, total_scenes)
                        contract = self._build_contract(
                            prepared_books=prepared_books,
                            series_id=series_id,
                            series_title=series_title,
                            chapters=chapters,
                            scene_analyses=scene_analyses,
                            resolved_scene_analyses=resolved_scene_analyses,
                            entity_registry=entity_registry,
                            state_result=state_result,
                            canon_snapshot=canon_snapshot,
                            timeline=timeline,
                            event_ledger=event_ledger,
                            character_timelines=character_timelines,
                            character_profiles=character_profiles,
                            stable_character_states=stable_character_states,
                            identity_result=identity_result,
                            causal_graph_result=causal_graph_result,
                            story_index_summary=story_index_summary,
                            visual_prompt_sets=visual_prompt_sets,
                            elapsed_seconds=round(time.perf_counter() - started_at, 2),
                            run_status="failed",
                            scene_analysis_quality=quality,
                            failed_scenes=failed_scenes,
                            artifacts_invalid=True,
                        )
                        raise SceneFailurePolicyError(
                            f"Scene analysis halted by {self.scene_failure_policy} at book {scene_analysis.get('book_index')} "
                            f"chapter {scene_analysis.get('chapter_index')} scene {scene_analysis.get('scene_index')}: "
                            f"{failure_record.get('error_category') or failure_record.get('error')}",
                            contract=contract,
                            failure_report=self._build_scene_failure_report(contract),
                        )
                    if self.scene_failure_policy == "skip_failed":
                        continue
                scene_analysis["fallback_targets"] = attempted_targets
                apply_identity_updates(scene_analysis, identity_result)
                scene_analyses.append(scene_analysis)
                resolved_scene_analyses = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
                entity_registry = build_entity_registry(resolved_scene_analyses)
                state_result = build_state_result(resolved_scene_analyses)
                timeline = build_timeline(resolved_scene_analyses)
                event_ledger = build_event_ledger(resolved_scene_analyses, timeline, causal_graph_result)
                character_timelines = build_character_timelines(timeline)
                character_timelines = normalize_character_timelines(character_timelines, identity_result)
                character_profiles = build_formal_character_profiles(
                    character_timelines,
                    entity_registry,
                    state_result,
                    identity_result,
                    resolved_scene_analyses,
                )
                canon_snapshot = build_canon_snapshot(
                    state_result,
                    (scene_analysis["book_index"], scene_analysis["chapter_index"], scene_analysis["scene_index"]),
                )
                stable_character_states = self.stable_state_builder.build(
                    character_profiles=character_profiles,
                    identity_result=identity_result,
                    canon_snapshot=canon_snapshot,
                    state_result=state_result,
                )
                story_index_summary = build_story_index_summary(
                    resolved_scene_analyses,
                    timeline,
                    event_ledger,
                    character_timelines,
                    character_profiles,
                    entity_registry,
                    canon_snapshot,
                    state_result,
                    identity_result,
                    causal_graph_result,
                )
                visual_prompt_sets = self._build_visual_prompt_sets(resolved_scene_analyses)
                self._save_checkpoint(
                    checkpoint_path,
                    prepared_books[0],
                    series_id,
                    series_title,
                    chapters,
                    identity_result,
                    planned_scenes,
                    scene_analyses,
                    phase="scene",
                    total_scenes=total_scenes,
                    causal_graph_result=causal_graph_result,
                    failed_scenes=failed_scenes,
                )

        self._emit(progress_callback, "causal_graph", {"status": "Building causal graph"})
        self._save_checkpoint(
            checkpoint_path,
            prepared_books[0],
            series_id,
            series_title,
            chapters,
            identity_result,
            planned_scenes,
            scene_analyses,
            phase="causal_graph",
            total_scenes=total_scenes,
            causal_graph_result=causal_graph_result,
            failed_scenes=failed_scenes,
        )
        causal_graph_result = CausalGraphService(
            llm_client=LLMClient(mode=self.analysis_model, max_retries=2, base_delay=0.0, timeout=120),
            batch_size=20,
        ).build(timeline, resolved_scene_analyses)
        if self._is_rate_limit_error((causal_graph_result.get("graph") or {})):
            raise RateLimitGuardError("Rate limit exhausted while building the causal graph.")

        event_ledger = build_event_ledger(resolved_scene_analyses, timeline, causal_graph_result)
        character_profiles = build_formal_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            resolved_scene_analyses,
        )
        stable_character_states = self.stable_state_builder.build(
            character_profiles=character_profiles,
            identity_result=identity_result,
            canon_snapshot=canon_snapshot,
            state_result=state_result,
        )
        story_index_summary = build_story_index_summary(
            resolved_scene_analyses,
            timeline,
            event_ledger,
            character_timelines,
            character_profiles,
            entity_registry,
            canon_snapshot,
            state_result,
            identity_result,
            causal_graph_result,
        )
        visual_prompt_sets = self._build_visual_prompt_sets(resolved_scene_analyses)

        elapsed_seconds = round(time.perf_counter() - started_at, 2)
        quality = self._scene_quality_metrics(scene_analyses, failed_scenes, total_scenes)
        artifacts_invalid = self._scene_quality_failed(quality)
        run_status = self._run_status_from_policy(quality, failed_scenes)
        contract = self._build_contract(
            prepared_books=prepared_books,
            series_id=series_id,
            series_title=series_title,
            chapters=chapters,
            scene_analyses=scene_analyses,
            resolved_scene_analyses=resolved_scene_analyses,
            entity_registry=entity_registry,
            state_result=state_result,
            canon_snapshot=canon_snapshot,
            timeline=timeline,
            event_ledger=event_ledger,
            character_timelines=character_timelines,
            character_profiles=character_profiles,
            stable_character_states=stable_character_states,
            identity_result=identity_result,
            causal_graph_result=causal_graph_result,
            story_index_summary=story_index_summary,
            visual_prompt_sets=visual_prompt_sets,
            elapsed_seconds=elapsed_seconds,
            run_status=run_status,
            scene_analysis_quality=quality,
            failed_scenes=failed_scenes,
            artifacts_invalid=artifacts_invalid,
        )
        if run_status == "failed":
            raise SceneFailurePolicyError(
                "Book contract marked failed due to scene-analysis quality thresholds.",
                contract=contract,
                failure_report=self._build_scene_failure_report(contract),
            )
        return contract

    def encode_and_persist(
        self,
        book_inputs: List[Dict[str, Any]],
        *,
        neo4j_service: Neo4jIngestionService,
        progress_callback: Callable[[str, Dict[str, Any]], None] | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        contract = self.encode_books(book_inputs, progress_callback=progress_callback, checkpoint_path=checkpoint_path)
        ingest_result = neo4j_service.ingest_contract(contract)
        self._clear_checkpoint(checkpoint_path)
        return {"contract": contract, "ingest_result": ingest_result}

    def _series_context(self, prepared_books: List[Dict[str, Any]]) -> tuple[str, str]:
        series_title = self.series_title or (prepared_books[0]["title"] if prepared_books else "Standalone Series")
        series_id = self.series_id or self._slugify(series_title)
        return series_id, series_title

    def _prepare_book_inputs(self, book_inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for offset, book in enumerate(book_inputs):
            source_path = Path(book["path"])
            stat = source_path.stat()
            prepared.append({
                **book,
                "path": str(source_path),
                "title": book.get("title") or source_path.name,
                "type": book.get("type") or source_path.suffix.lstrip(".").lower(),
                "book_index": self.book_index_base + offset,
                "source_hash_sha256": self._sha256_file(source_path),
                "source_size_bytes": stat.st_size,
                "source_mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            })
        return prepared

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _slugify(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "standalone-series"

    def _build_chapters(self, book_inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processor = SeriesProcessor(
            llm_client=LLMClient(mode=self.analysis_model, max_retries=1, base_delay=0.0)
        )
        chapters = processor.process(book_inputs)
        if self.max_chapters:
            chapters = chapters[: self.max_chapters]
        if self.book_index_base == 1:
            return chapters
        adjusted = []
        for chapter in chapters:
            adjusted.append({
                **chapter,
                "book_index": int(chapter.get("book_index", 1)) + self.book_index_base - 1,
            })
        return adjusted

    def _run_identity_resolution(
        self,
        book_inputs: List[Dict[str, Any]],
        *,
        progress_callback: Callable[[str, Dict[str, Any]], None] | None = None,
    ) -> Dict[str, Any]:
        provider = resolve_identity_provider_input(
            provider_mode="booknlp_clean",
            input_json=self.identity_json_path or None,
            book_inputs=book_inputs,
        )
        try:
            return provider.build_identity_result_compat(book_inputs=book_inputs)
        except TypeError:
            return provider.build_identity_result_compat()

    def _analyze_scene_with_fallback(
        self,
        scene: Dict[str, Any],
        *,
        identity_result: Dict[str, Any],
        state_result: Dict[str, Any],
        resolved_scene_analyses: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        current_target = self.target_scene_words
        attempted_targets: List[int] = []
        client_policy = self._analysis_client_policy()
        analysis_llm = LLMClient(
            mode=self.analysis_model,
            max_retries=2,
            base_delay=0.0,
            timeout=120,
            allow_account_rotation=client_policy["allow_account_rotation"],
            allow_cross_provider_fallback=client_policy["allow_cross_provider_fallback"],
        )
        visual_llm = LLMClient(
            mode=self.analysis_model,
            max_retries=2,
            base_delay=0.0,
            timeout=120,
            allow_account_rotation=client_policy["allow_account_rotation"],
            allow_cross_provider_fallback=client_policy["allow_cross_provider_fallback"],
        )
        orchestrator = SceneAnalysisOrchestrator(
            analysis_model=self.analysis_model,
            identity_model=self.identity_model,
            identity_pass_enabled=False,
            semantic_evidence_refiner=SemanticEvidenceRefiner(enabled=False),
            identity_semantic_reviewer=IdentitySemanticReviewer(enabled=False),
            scene_semantic_reviewer=SceneSemanticReviewer(enabled=False),
            scene_analyzer=SceneAnalyzer(llm_client=analysis_llm),
            visual_analyzer=VisualStateAnalyzer(llm_client=visual_llm),
        )
        working_scenes = [scene]
        while current_target is not None:
            attempted_targets.append(current_target)
            analyzed: List[Dict[str, Any]] = []
            overflow_triggered = False
            for current_scene in working_scenes:
                scene_context = build_scene_context(
                    current_scene.get("text", ""),
                    resolved_scene_analyses,
                    state_result,
                    identity_result,
                )
                result = orchestrator.analyze_scene(
                    current_scene,
                    alias_map=identity_result.get("alias_map") or {},
                    rejected_identities=identity_result.get("rejected_non_characters") or [],
                    scene_context=scene_context,
                    analysis_mode=self.analysis_mode,
                )
                self._stamp_scene_provider_metadata(result)
                self._enforce_provider_consistency(result)
                if self._is_overflow_error(result):
                    overflow_triggered = True
                    break
                analyzed.append(result)
            if not overflow_triggered:
                return analyzed, attempted_targets
            next_target = self._next_smaller_scene_target(current_target)
            if next_target is None or next_target == current_target:
                fallback_error = dict(scene)
                fallback_error["error"] = "Scene analysis overflowed and could not be split further."
                self._stamp_scene_provider_metadata(fallback_error, llm_client=analysis_llm)
                return [fallback_error], attempted_targets
            current_target = next_target
            splitter = SceneExtractor.from_target_words(current_target)
            working_scenes = splitter.extract(scene)
        overflow = dict(scene, error="Scene analysis overflowed.")
        self._stamp_scene_provider_metadata(overflow, llm_client=analysis_llm)
        return [overflow], attempted_targets

    def _analyze_scene_with_heartbeat(
        self,
        scene: Dict[str, Any],
        *,
        identity_result: Dict[str, Any],
        state_result: Dict[str, Any],
        resolved_scene_analyses: List[Dict[str, Any]],
        progress_callback: Callable[[str, Dict[str, Any]], None] | None,
        scene_position: int,
        total_scenes: int,
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        should_heartbeat = self.analysis_model == LLMClient.MODE_GENERAL_COMPUTE or self.identity_model == LLMClient.MODE_GENERAL_COMPUTE
        if not should_heartbeat or progress_callback is None:
            return self._analyze_scene_with_fallback(
                scene,
                identity_result=identity_result,
                state_result=state_result,
                resolved_scene_analyses=resolved_scene_analyses,
            )

        stop_event = threading.Event()
        started_at = time.perf_counter()

        def _heartbeat() -> None:
            while not stop_event.wait(20):
                elapsed = int(time.perf_counter() - started_at)
                self._emit(progress_callback, "scene_wait", {
                    "status": (
                        f"Waiting on General Compute for scene {scene_position}/{total_scenes} "
                        f"(book {scene.get('book_index')} ch {scene.get('chapter_index')} "
                        f"scene {scene.get('scene_index')}, {elapsed}s elapsed)"
                    ),
                    "scene_position": scene_position,
                    "total_scenes": total_scenes,
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                    "elapsed_seconds": elapsed,
                })

        thread = threading.Thread(target=_heartbeat, daemon=True)
        thread.start()
        try:
            return self._analyze_scene_with_fallback(
                scene,
                identity_result=identity_result,
                state_result=state_result,
                resolved_scene_analyses=resolved_scene_analyses,
            )
        finally:
            stop_event.set()
            thread.join(timeout=1.0)

    def _next_smaller_scene_target(self, target_words: int) -> int | None:
        if target_words == 0:
            return self.SCENE_FALLBACK_TARGETS[0]
        for candidate in self.SCENE_FALLBACK_TARGETS:
            if candidate < target_words:
                return candidate
        return None

    def _is_overflow_error(self, result: Dict[str, Any]) -> bool:
        error_blob = " ".join([str(result.get("error", "")), str(result.get("last_error", ""))]).lower()
        return any(keyword in error_blob for keyword in ["context", "token", "overflow", "length", "too long", "prompt"])

    def _is_rate_limit_error(self, result: Dict[str, Any]) -> bool:
        error_blob = " ".join([str(result.get("error", "")), str(result.get("last_error", ""))]).lower()
        return any(keyword in error_blob for keyword in ["rate_limited_exhausted", "429 rate_limited", "rate limit"])

    def _analysis_client_policy(self) -> Dict[str, Any]:
        mode = self.analysis_provider_mode
        if mode == self.PROVIDER_MODE_ROTATING:
            return {
                "allow_account_rotation": True,
                "allow_cross_provider_fallback": False,
                "canonical_consistency_status": "same_provider_rotating",
            }
        if mode == self.PROVIDER_MODE_FALLBACK:
            return {
                "allow_account_rotation": True,
                "allow_cross_provider_fallback": True,
                "canonical_consistency_status": "mixed_provider_experimental",
            }
        return {
            "allow_account_rotation": False,
            "allow_cross_provider_fallback": False,
            "canonical_consistency_status": "strict_single_account",
        }

    def _stamp_scene_provider_metadata(self, scene_analysis: Dict[str, Any], *, llm_client: LLMClient | None = None) -> None:
        client = llm_client or LLMClient(
            mode=self.analysis_model,
            allow_account_rotation=self._analysis_client_policy()["allow_account_rotation"],
            allow_cross_provider_fallback=self._analysis_client_policy()["allow_cross_provider_fallback"],
        )
        request_meta = client.last_request_metadata()
        scene_analysis.setdefault("provider", client.provider_name())
        scene_analysis.setdefault("provider_family", request_meta.get("provider_family") or client.provider_name())
        scene_analysis.setdefault("model", client.resolved_model_name())
        scene_analysis.setdefault("resolved_model", request_meta.get("resolved_model") or client.resolved_model_name())
        scene_analysis.setdefault("provider_account_alias", request_meta.get("provider_account_alias") or client.current_account_alias())
        scene_analysis.setdefault("rotation_used", bool(request_meta.get("rotation_used")))
        scene_analysis.setdefault("rotation_attempt_count", int(request_meta.get("rotation_attempt_count") or 0))
        scene_analysis.setdefault("fallback_used", bool(request_meta.get("fallback_used")))
        scene_analysis.setdefault("provider_mode", self.analysis_provider_mode)

    def _enforce_provider_consistency(self, scene_analysis: Dict[str, Any]) -> None:
        expected_provider = self._analysis_provider_name()
        expected_model = self._analysis_model_name()
        actual_provider = str(scene_analysis.get("provider_family") or scene_analysis.get("provider") or "").strip()
        actual_model = str(scene_analysis.get("resolved_model") or scene_analysis.get("model") or "").strip()
        if self.analysis_provider_mode == self.PROVIDER_MODE_ROTATING:
            if bool(scene_analysis.get("fallback_used")):
                raise SceneFailurePolicyError(
                    "same_provider_rotating attempted cross-provider fallback, which is not canonical.",
                    contract={},
                    failure_report={},
                )
            if actual_provider and actual_provider != expected_provider:
                raise SceneFailurePolicyError(
                    f"same_provider_rotating detected provider drift: expected {expected_provider}, got {actual_provider}.",
                    contract={},
                    failure_report={},
                )
            if actual_model and actual_model != expected_model:
                raise SceneFailurePolicyError(
                    f"same_provider_rotating detected model drift: expected {expected_model}, got {actual_model}.",
                    contract={},
                    failure_report={},
                )

    def _emit(
        self,
        callback: Callable[[str, Dict[str, Any]], None] | None,
        phase: str,
        payload: Dict[str, Any],
    ) -> None:
        if callback:
            callback(phase, payload)

    def _empty_causal_graph_result(self) -> Dict[str, Any]:
        return {
            "graph": {
                "events": [],
                "critical_path": [],
                "flexible_events": [],
                "causal_chains": [],
                "divergence_points": [],
            },
            "metrics": {},
        }

    def _scene_failure_record(self, scene_analysis: Dict[str, Any]) -> Dict[str, Any] | None:
        error = str(scene_analysis.get("error") or "").strip()
        last_error = str(scene_analysis.get("last_error") or "").strip()
        category = str(scene_analysis.get("error_category") or LLMClient.classify_error(error, last_error)).strip()
        if not error and not category:
            return None
        return {
            "book_index": scene_analysis.get("book_index"),
            "chapter_index": scene_analysis.get("chapter_index"),
            "scene_index": scene_analysis.get("scene_index"),
            "provider": scene_analysis.get("provider") or self._analysis_provider_name(),
            "provider_family": scene_analysis.get("provider_family") or scene_analysis.get("provider") or self._analysis_provider_name(),
            "model": scene_analysis.get("model") or self._analysis_model_name(),
            "resolved_model": scene_analysis.get("resolved_model") or scene_analysis.get("model") or self._analysis_model_name(),
            "provider_account_alias": scene_analysis.get("provider_account_alias") or "",
            "rotation_used": bool(scene_analysis.get("rotation_used")),
            "rotation_attempt_count": int(scene_analysis.get("rotation_attempt_count") or 0),
            "fallback_used": bool(scene_analysis.get("fallback_used")),
            "provider_mode": scene_analysis.get("provider_mode") or self.analysis_provider_mode,
            "attempt_count": int(scene_analysis.get("attempt_count") or 0),
            "final_status": scene_analysis.get("final_status") or "failed",
            "error": error,
            "error_category": category,
            "last_error": last_error,
        }

    def _scene_quality_metrics(self, scene_analyses: List[Dict[str, Any]], failed_scenes: List[Dict[str, Any]], total_scenes: int) -> Dict[str, Any]:
        successful = [scene for scene in scene_analyses if not str(scene.get("error") or "").strip()]
        failed = list(failed_scenes or [])
        dominant_error = ""
        if failed:
            counts: Dict[str, int] = {}
            for item in failed:
                key = str(item.get("error_category") or item.get("error") or "unknown").strip()
                counts[key] = counts.get(key, 0) + 1
            dominant_error = max(counts.items(), key=lambda row: row[1])[0]
        total = max(int(total_scenes or 0), len(successful) + len(failed))
        nonempty_events = sum(1 for scene in successful if scene.get("events"))
        nonempty_summary = sum(1 for scene in successful if str(scene.get("scene_summary") or "").strip())
        nonempty_entities = sum(1 for scene in successful if scene.get("entities_present"))
        nonempty_state = sum(1 for scene in successful if scene.get("state_changes"))
        nonempty_relationships = sum(1 for scene in successful if scene.get("relationship_changes"))
        nonempty_scene_count = sum(
            1 for scene in successful
            if scene.get("events") or scene.get("entities_present") or scene.get("state_changes") or scene.get("relationship_changes") or str(scene.get("scene_summary") or "").strip()
        )
        return {
            "total_scenes": total,
            "successful_scenes": len(successful),
            "failed_scenes": len(failed),
            "failure_ratio": round((len(failed) / total), 4) if total else 0.0,
            "dominant_error": dominant_error,
            "nonempty_events_scene_count": nonempty_events,
            "nonempty_summary_scene_count": nonempty_summary,
            "nonempty_entities_scene_count": nonempty_entities,
            "nonempty_state_changes_scene_count": nonempty_state,
            "nonempty_relationship_changes_scene_count": nonempty_relationships,
            "nonempty_scene_ratio": round((nonempty_scene_count / total), 4) if total else 0.0,
            "invalid_due_to_scene_failure": False,
        }

    def _scene_quality_failed(self, quality: Dict[str, Any]) -> bool:
        total = int(quality.get("total_scenes") or 0)
        failed = int(quality.get("failed_scenes") or 0)
        failure_ratio = float(quality.get("failure_ratio") or 0.0)
        nonempty_scene_ratio = float(quality.get("nonempty_scene_ratio") or 0.0)
        return (
            failed > self.max_failed_scenes_absolute
            or failure_ratio > self.max_failed_scene_ratio
            or (total > 0 and nonempty_scene_ratio < self.min_nonempty_scene_ratio)
        )

    def _run_status_from_policy(self, quality: Dict[str, Any], failed_scenes: List[Dict[str, Any]]) -> str:
        if self._scene_quality_failed(quality):
            return "failed"
        if failed_scenes:
            return "partial"
        return "success"

    def _analysis_provider_name(self) -> str:
        policy = self._analysis_client_policy()
        return LLMClient(mode=self.analysis_model, allow_account_rotation=policy["allow_account_rotation"], allow_cross_provider_fallback=policy["allow_cross_provider_fallback"]).provider_name()

    def _analysis_model_name(self) -> str:
        policy = self._analysis_client_policy()
        return LLMClient(mode=self.analysis_model, allow_account_rotation=policy["allow_account_rotation"], allow_cross_provider_fallback=policy["allow_cross_provider_fallback"]).resolved_model_name()

    def _analysis_provider_config_hash(self) -> str:
        policy = self._analysis_client_policy()
        return LLMClient(mode=self.analysis_model, allow_account_rotation=policy["allow_account_rotation"], allow_cross_provider_fallback=policy["allow_cross_provider_fallback"]).provider_config_hash()

    def _artifact_validity(self, invalid_due_to_scene_failure: bool) -> Dict[str, Dict[str, Any]]:
        status = "invalid_due_to_scene_failure" if invalid_due_to_scene_failure else "ready"
        return {
            key: {"status": status if key != "causal_graph_result" else "not_required_for_mvp", "invalid_due_to_scene_failure": bool(invalid_due_to_scene_failure and key != "causal_graph_result")}
            for key in [
                "entity_registry",
                "timeline",
                "event_ledger",
                "character_profiles",
                "stable_character_states",
                "story_index_summary",
                "causal_graph_result",
            ]
        }

    def _build_contract(
        self,
        *,
        prepared_books: List[Dict[str, Any]],
        series_id: str,
        series_title: str,
        chapters: List[Dict[str, Any]],
        scene_analyses: List[Dict[str, Any]],
        resolved_scene_analyses: List[Dict[str, Any]],
        entity_registry: List[Dict[str, Any]],
        state_result: Dict[str, Any],
        canon_snapshot: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        event_ledger: List[Dict[str, Any]],
        character_timelines: List[Dict[str, Any]],
        character_profiles: List[Dict[str, Any]],
        stable_character_states: List[Dict[str, Any]],
        identity_result: Dict[str, Any],
        causal_graph_result: Dict[str, Any],
        story_index_summary: Dict[str, Any],
        visual_prompt_sets: Dict[str, Any],
        elapsed_seconds: float,
        run_status: str,
        scene_analysis_quality: Dict[str, Any],
        failed_scenes: List[Dict[str, Any]],
        artifacts_invalid: bool,
    ) -> Dict[str, Any]:
        scene_analysis_quality = dict(scene_analysis_quality or {})
        scene_analysis_quality["invalid_due_to_scene_failure"] = artifacts_invalid
        provider_policy = self._analysis_client_policy()
        account_aliases = sorted({
            str(scene.get("provider_account_alias") or "").strip()
            for scene in (scene_analyses or [])
            if str(scene.get("provider_account_alias") or "").strip()
        })
        pipeline_status = "Pipeline completed."
        if run_status == "partial":
            pipeline_status = "Pipeline completed partially with scene-analysis failures."
        elif run_status == "failed":
            pipeline_status = "Pipeline failed due to scene-analysis failures."
        contract = build_export_contract_payload(
            app_name="S.A.G.A.",
            pipeline_status=pipeline_status,
            configuration={
                "analysis_provider_mode": self.analysis_provider_mode,
                "analysis_provider": self._analysis_provider_name(),
                "provider_family": self._analysis_provider_name(),
                "analysis_model": self.analysis_model,
                "analysis_model_resolved": self._analysis_model_name(),
                "resolved_model": self._analysis_model_name(),
                "account_rotation_allowed": provider_policy["allow_account_rotation"],
                "cross_provider_fallback_allowed": provider_policy["allow_cross_provider_fallback"],
                "canonical_consistency_status": provider_policy["canonical_consistency_status"],
                "identity_model": self.identity_model,
                "identity_strategy": "booknlp_clean",
                "identity_provider": self.identity_provider,
                "identity_json_path": self.identity_json_path,
                "analysis_mode": self.analysis_mode,
                "target_scene_words": self.target_scene_words,
                "max_chapters": self.max_chapters,
                "scene_failure_policy": self.scene_failure_policy,
                "max_failed_scenes_absolute": self.max_failed_scenes_absolute,
                "max_failed_scene_ratio": self.max_failed_scene_ratio,
                "min_nonempty_scene_ratio": self.min_nonempty_scene_ratio,
                "encoder_version": self.ENCODER_VERSION,
            },
            inputs={
                "books": prepared_books,
                "series": {
                    "series_id": series_id,
                    "series_title": series_title,
                    "book_index_base": self.book_index_base,
                },
            },
            outputs={
                "chapters": chapters,
                "scene_analyses": scene_analyses,
                "resolved_scene_analyses": resolved_scene_analyses,
                "entity_registry": entity_registry,
                "state_result": state_result,
                "canon_snapshot": canon_snapshot,
                "timeline": timeline,
                "event_ledger": event_ledger,
                "character_timelines": character_timelines,
                "character_profiles": character_profiles,
                "relationship_profiles": RelationshipProfileBuilder().build(scene_analyses=resolved_scene_analyses),
                "stable_character_states": stable_character_states,
                "identity_result": identity_result,
                "causal_graph_result": causal_graph_result,
                "sequel_artifacts": {"context": {}, "blueprint": {}},
                "story_index_summary": {
                    **(story_index_summary or {}),
                    "invalid_due_to_scene_failure": artifacts_invalid,
                },
                "visual_prompt_sets": visual_prompt_sets or self._build_visual_prompt_sets(resolved_scene_analyses),
                "artifact_validity": self._artifact_validity(artifacts_invalid),
                "failed_scenes": failed_scenes,
            },
            runtime={
                "elapsed_seconds": elapsed_seconds,
                "encoded_at_utc": datetime.now(timezone.utc).isoformat(),
                "encoder_version": self.ENCODER_VERSION,
                "run_status": run_status,
                "analysis_provider_mode": self.analysis_provider_mode,
                "analysis_provider": self._analysis_provider_name(),
                "analysis_model": self._analysis_model_name(),
                "provider_family": self._analysis_provider_name(),
                "resolved_model": self._analysis_model_name(),
                "account_rotation_allowed": provider_policy["allow_account_rotation"],
                "cross_provider_fallback_allowed": provider_policy["allow_cross_provider_fallback"],
                "canonical_consistency_status": provider_policy["canonical_consistency_status"],
                "unique_account_aliases_used_count": len(account_aliases),
                "unique_account_aliases_used": account_aliases,
                "provider_config_hash": self._analysis_provider_config_hash(),
                "prompt_version": "scene_analyzer_v1",
                "temperature": 0.0,
                "last_scene_seconds": float(scene_analyses[-1].get("analysis_duration_seconds") or 0.0) if scene_analyses else 0.0,
                "avg_scene_seconds": round(elapsed_seconds / max(len(scene_analyses), 1), 2) if scene_analyses else 0.0,
                "processed_scene_count": len(scene_analyses),
                "estimated_total_scenes": scene_analysis_quality.get("total_scenes", 0),
                "scene_analysis_quality": scene_analysis_quality,
            },
        )
        contract["run_status"] = run_status
        return contract

    def _build_scene_failure_report(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        runtime = (contract.get("runtime") or {})
        quality = runtime.get("scene_analysis_quality") or {}
        outputs = (contract.get("outputs") or {})
        failed = outputs.get("failed_scenes") or []
        return {
            "run_status": contract.get("run_status") or runtime.get("run_status") or "failed",
            "provider": runtime.get("analysis_provider") or "",
            "model": runtime.get("analysis_model") or "",
            "analysis_provider_mode": runtime.get("analysis_provider_mode") or self.analysis_provider_mode,
            "scene_failure_policy": self.scene_failure_policy,
            "total_scenes": quality.get("total_scenes", 0),
            "successful_scenes": quality.get("successful_scenes", 0),
            "failed_scenes": quality.get("failed_scenes", 0),
            "failure_ratio": quality.get("failure_ratio", 0.0),
            "dominant_error": quality.get("dominant_error", ""),
            "first_failed_scene_ids": [
                f"b{row.get('book_index')}_c{row.get('chapter_index')}_s{row.get('scene_index')}"
                for row in failed[:10]
            ],
            "last_error_samples": [row.get("last_error", "") for row in failed[:10]],
            "downstream_artifacts_invalidated": bool(quality.get("invalid_due_to_scene_failure")),
            "recommended_resume_command": "python saga_tools.py retry-failed-scenes --contract <failed_contract> --analysis-provider <same_provider> --analysis-model <same_model>",
        }

    def _rebuild_story_state(self, scene_analyses: List[Dict[str, Any]], identity_result: Dict[str, Any]) -> Dict[str, Any]:
        resolved_scene_analyses: List[Dict[str, Any]] = []
        entity_registry: List[Dict[str, Any]] = []
        state_result: Dict[str, Any] = {"transitions": [], "latest_state": []}
        timeline: List[Dict[str, Any]] = []
        event_ledger: List[Dict[str, Any]] = []
        character_timelines: List[Dict[str, Any]] = []
        character_profiles: List[Dict[str, Any]] = []
        canon_snapshot: List[Dict[str, Any]] = []
        stable_character_states: List[Dict[str, Any]] = []
        story_index_summary: Dict[str, Any] = {"document_count": 0}
        causal_graph_result = self._empty_causal_graph_result()

        for position, scene_analysis in enumerate(scene_analyses, start=1):
            resolved_scene_analyses = rebuild_resolved_scene_analyses(scene_analyses[:position], identity_result)
            entity_registry = build_entity_registry(resolved_scene_analyses)
            state_result = build_state_result(resolved_scene_analyses)
            timeline = build_timeline(resolved_scene_analyses)
            event_ledger = build_event_ledger(resolved_scene_analyses, timeline, causal_graph_result)
            character_timelines = build_character_timelines(timeline)
            character_timelines = normalize_character_timelines(character_timelines, identity_result)
            character_profiles = build_formal_character_profiles(
                character_timelines,
                entity_registry,
                state_result,
                identity_result,
                resolved_scene_analyses,
            )
            canon_snapshot = build_canon_snapshot(
                state_result,
                (scene_analysis["book_index"], scene_analysis["chapter_index"], scene_analysis["scene_index"]),
            )
            stable_character_states = self.stable_state_builder.build(
                character_profiles=character_profiles,
                identity_result=identity_result,
                canon_snapshot=canon_snapshot,
                state_result=state_result,
            )
            story_index_summary = build_story_index_summary(
                resolved_scene_analyses,
                timeline,
                event_ledger,
                character_timelines,
                character_profiles,
                entity_registry,
                canon_snapshot,
                state_result,
                identity_result,
                causal_graph_result,
            )
        return {
            "resolved_scene_analyses": resolved_scene_analyses,
            "entity_registry": entity_registry,
            "state_result": state_result,
            "timeline": timeline,
            "event_ledger": event_ledger,
            "character_timelines": character_timelines,
            "character_profiles": character_profiles,
            "canon_snapshot": canon_snapshot,
            "stable_character_states": stable_character_states,
            "story_index_summary": story_index_summary,
            "visual_prompt_sets": self._build_visual_prompt_sets(resolved_scene_analyses),
        }

    def _build_visual_prompt_sets(self, scene_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        sets: Dict[str, Any] = {
            "initial_characters": [],
            "character_changes": [],
            "objects_creatures": [],
            "locations": [],
            "scene_compositions": [],
            "diagnostics": {
                "source": "visual_state_analyzer",
                "source_scene_count": len(scene_analyses or []),
                "missing_visual_evidence": [],
                "rejected_visual_claims": [],
            },
        }
        seen: Dict[str, set[tuple[str, str, str]]] = {
            "initial_characters": set(),
            "character_changes": set(),
            "objects_creatures": set(),
            "locations": set(),
            "scene_compositions": set(),
        }

        def provenance(scene: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
            }

        def prompt_specificity(row: Dict[str, Any], prompt: str) -> int:
            details = row.get("persistent_visual_profile") or {}
            score = sum(1 for value in details.values() if value not in ("", [], {}, None))
            score += min(4, len(str(prompt or "").split()) // 10)
            return score

        best_initial_by_name: Dict[str, Dict[str, Any]] = {}

        def add_prompt(bucket: str, scene: Dict[str, Any], row: Dict[str, Any], prompt_type: str) -> None:
            prompt = str(
                row.get("persistent_visual_prompt")
                or row.get("image_prompt")
                or row.get("image_edit_prompt")
                or row.get("scene_prompt")
                or ""
            ).strip()
            if not prompt:
                return
            entity_name = str(row.get("entity_name") or row.get("beat_title") or "").strip()
            key = (entity_name.lower(), prompt_type, prompt.lower())
            payload = {
                **provenance(scene),
                "prompt_type": prompt_type,
                "entity_name": entity_name,
                "entity_type": row.get("entity_type") or ("character" if bucket in {"initial_characters", "character_changes"} else ""),
                "positive_prompt": prompt,
                "image_edit_prompt": str(row.get("image_edit_prompt") or "").strip(),
                "source_evidence": str(row.get("source_evidence") or "").strip(),
                "confidence": str(row.get("confidence") or "medium").strip(),
                "details": {
                    key: value
                    for key, value in row.items()
                    if key not in {"image_prompt", "image_edit_prompt", "scene_prompt", "source_evidence"}
                    and value not in (None, "", [], {})
                },
            }
            if bucket == "initial_characters":
                name_key = entity_name.lower()
                existing = best_initial_by_name.get(name_key)
                if existing is None or prompt_specificity(row, prompt) > prompt_specificity(existing.get("details") or {}, existing.get("positive_prompt") or ""):
                    best_initial_by_name[name_key] = payload
                return
            if key in seen[bucket]:
                return
            seen[bucket].add(key)
            sets[bucket].append(payload)

        for scene in scene_analyses or []:
            visual = scene.get("visual_analysis") or {}
            if not isinstance(visual, dict):
                continue
            for row in visual.get("characters") or []:
                if not isinstance(row, dict):
                    continue
                bucket = "initial_characters" if row.get("visual_role") == "initial_character_description" else "character_changes"
                add_prompt(bucket, scene, row, str(row.get("visual_role") or "character_change"))
            for row in (visual.get("objects") or []) + (visual.get("creatures") or []):
                if isinstance(row, dict):
                    add_prompt("objects_creatures", scene, row, str(row.get("entity_type") or "object"))
            for row in visual.get("locations") or []:
                if isinstance(row, dict):
                    add_prompt("locations", scene, row, "location")
            for row in visual.get("scene_compositions") or []:
                if isinstance(row, dict):
                    add_prompt("scene_compositions", scene, row, "scene_composition")
            diagnostics = visual.get("diagnostics") or {}
            if isinstance(diagnostics, dict):
                sets["diagnostics"]["missing_visual_evidence"].extend(diagnostics.get("missing_visual_evidence") or [])
                sets["diagnostics"]["rejected_visual_claims"].extend(diagnostics.get("rejected_visual_claims") or [])

        for bucket in ["initial_characters", "character_changes", "objects_creatures", "locations", "scene_compositions"]:
            sets[bucket] = sets[bucket][:500]
        if best_initial_by_name:
            sets["initial_characters"] = sorted(
                best_initial_by_name.values(),
                key=lambda item: ((item.get("entity_name") or "").lower(), int(item.get("book_index") or 0), int(item.get("chapter_index") or 0)),
            )[:500]
        for diag_key in ["missing_visual_evidence", "rejected_visual_claims"]:
            values = []
            seen_diag = set()
            for value in sets["diagnostics"][diag_key]:
                cleaned = str(value or "").strip()
                if not cleaned or cleaned.lower() in seen_diag:
                    continue
                seen_diag.add(cleaned.lower())
                values.append(cleaned)
            sets["diagnostics"][diag_key] = values[:200]
        sets["diagnostics"].update(
            {
                "initial_character_prompt_count": len(sets["initial_characters"]),
                "character_change_prompt_count": len(sets["character_changes"]),
                "object_creature_prompt_count": len(sets["objects_creatures"]),
                "location_prompt_count": len(sets["locations"]),
                "scene_composition_prompt_count": len(sets["scene_compositions"]),
            }
        )
        return sets

    def _save_checkpoint(
        self,
        checkpoint_path: str | Path | None,
        prepared_book: Dict[str, Any],
        series_id: str,
        series_title: str,
        chapters: List[Dict[str, Any]],
        identity_result: Dict[str, Any],
        planned_scenes: List[Dict[str, Any]],
        scene_analyses: List[Dict[str, Any]],
        *,
        phase: str,
        total_scenes: int,
        causal_graph_result: Dict[str, Any],
        failed_scenes: List[Dict[str, Any]] | None = None,
    ) -> None:
        if not checkpoint_path:
            return
        target = Path(checkpoint_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "series_id": series_id,
            "series_title": series_title,
            "book": prepared_book,
            "configuration": {
                "analysis_model": self.analysis_model,
                "identity_model": self.identity_model,
                "identity_strategy": "booknlp_clean",
                "identity_provider": self.identity_provider,
                "identity_json_path": self.identity_json_path,
                "analysis_provider_mode": self.analysis_provider_mode,
                "analysis_mode": self.analysis_mode,
                "scene_failure_policy": self.scene_failure_policy,
                "target_scene_words": self.target_scene_words,
                "max_chapters": self.max_chapters,
                "encoder_version": self.ENCODER_VERSION,
            },
            "chapters": chapters,
            "identity_result": identity_result,
            "planned_scenes": planned_scenes,
            "scene_analyses": scene_analyses,
            "failed_scenes": failed_scenes or [],
            "phase": phase,
            "total_scenes": total_scenes,
            "causal_graph_result": causal_graph_result,
            "checkpointed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        temp_target = target.with_name(f"{target.name}.tmp")
        try:
            serialized = json.dumps(payload, ensure_ascii=True, indent=2, default=str)
            with temp_target.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
            os.replace(temp_target, target)
        except Exception:
            logging.exception("Checkpoint write failed at %s; continuing without aborting encode.", target)
            try:
                if temp_target.exists():
                    temp_target.unlink()
            except Exception:
                logging.warning("Failed to clean up temporary checkpoint file at %s", temp_target)

    def _load_checkpoint(
        self,
        checkpoint_path: str | Path | None,
        prepared_book: Dict[str, Any],
        series_id: str,
        series_title: str,
    ) -> Dict[str, Any] | None:
        if not checkpoint_path:
            return None
        target = Path(checkpoint_path)
        if not target.exists():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            logging.warning("Ignoring unreadable checkpoint at %s", target)
            return None
        checkpoint_book = payload.get("book") or {}
        config = payload.get("configuration") or {}
        if (
            payload.get("series_id") != series_id
            or checkpoint_book.get("book_index") != prepared_book.get("book_index")
            or checkpoint_book.get("title") != prepared_book.get("title")
            or checkpoint_book.get("source_hash_sha256") != prepared_book.get("source_hash_sha256")
            or config.get("analysis_model") != self.analysis_model
            or config.get("identity_model") != self.identity_model
            or config.get("identity_strategy") not in {"", "booknlp_clean"}
            or config.get("identity_provider", self.DEFAULT_IDENTITY_PROVIDER) != self.identity_provider
            or str(config.get("identity_json_path") or "") != self.identity_json_path
            or config.get("analysis_provider_mode", "single_provider") != self.analysis_provider_mode
            or config.get("analysis_mode") != self.analysis_mode
            or config.get("scene_failure_policy", "fail_fast") != self.scene_failure_policy
            or config.get("target_scene_words") != self.target_scene_words
            or config.get("max_chapters", 0) != self.max_chapters
            or config.get("encoder_version") != self.ENCODER_VERSION
        ):
            return None
        return payload

    def _clear_checkpoint(self, checkpoint_path: str | Path | None) -> None:
        if not checkpoint_path:
            return
        target = Path(checkpoint_path)
        if target.exists():
            target.unlink()
