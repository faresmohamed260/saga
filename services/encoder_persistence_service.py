"""Headless encoder pipeline for persistent book ingestion."""

from __future__ import annotations

import logging
import time
import json
import os
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from analysis.scene_analysis_orchestrator import SceneAnalysisOrchestrator
from analysis.scene_extractor import SceneExtractor
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
from entities.deterministic_identity_resolver import DeterministicIdentityResolver
from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionService
from services.series_processor import SeriesProcessor
from timeline.causal_graph_service import CausalGraphService


class RateLimitGuardError(RuntimeError):
    """Raised when provider rate limits exhaust retries during a book encode."""


class EncoderPersistenceService:
    """Encode books into a durable SAGA contract and optionally persist to Neo4j."""

    ENCODER_VERSION = "encoder-persistence-v2"
    SCENE_FALLBACK_TARGETS = [2400, 1800, 1400, 1100, 900, 700, 500, 350, 250]

    def __init__(
        self,
        *,
        analysis_model: str = "gpt_oss",
        identity_model: str = "gpt_oss",
        analysis_mode: str = "structured",
        target_scene_words: int = 0,
        series_id: str | None = None,
        series_title: str | None = None,
        book_index_base: int = 1,
    ) -> None:
        self.analysis_model = analysis_model
        self.identity_model = identity_model
        self.analysis_mode = analysis_mode
        self.target_scene_words = target_scene_words
        self.series_id = (series_id or "").strip()
        self.series_title = (series_title or "").strip()
        self.book_index_base = max(1, int(book_index_base))

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
            story_index_summary = rebuilt["story_index_summary"]
            causal_graph_result: Dict[str, Any] = checkpoint.get("causal_graph_result") or self._empty_causal_graph_result()
            self._emit(progress_callback, "resume", {
                "status": f"Resuming from scene {resume_scene_count + 1}/{total_scenes}",
                "completed_scenes": resume_scene_count,
                "total_scenes": total_scenes,
                "book": prepared_books[0]["title"],
            })
        else:
            self._emit(progress_callback, "chapters", {"status": "Loading chapters"})
            chapters = self._build_chapters(prepared_books)

            self._emit(progress_callback, "identity", {"status": "Resolving identities"})
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
            story_index_summary = {"document_count": 0}
            causal_graph_result = self._empty_causal_graph_result()

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
            analyzed_scenes, attempted_targets = self._analyze_scene_with_fallback(
                planned_scene,
                identity_result=identity_result,
                state_result=state_result,
                resolved_scene_analyses=resolved_scene_analyses,
            )
            for scene_analysis in analyzed_scenes:
                if self._is_rate_limit_error(scene_analysis):
                    raise RateLimitGuardError(
                        f"Rate limit exhausted while processing scene {scene_analysis.get('scene_index')} "
                        f"of chapter {scene_analysis.get('chapter_index')} (book {scene_analysis.get('book_index')})."
                    )
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

        elapsed_seconds = round(time.perf_counter() - started_at, 2)
        contract = build_export_contract_payload(
            app_name="S.A.G.A.",
            pipeline_status="Pipeline completed." if not (causal_graph_result.get("graph") or {}).get("error") else f"Pipeline completed with causal-graph issue: {(causal_graph_result.get('graph') or {}).get('error')}",
            configuration={
                "analysis_model": self.analysis_model,
                "identity_model": self.identity_model,
                "analysis_mode": self.analysis_mode,
                "target_scene_words": self.target_scene_words,
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
                "identity_result": identity_result,
                "causal_graph_result": causal_graph_result,
                "sequel_artifacts": {"context": {}, "blueprint": {}},
                "story_index_summary": story_index_summary,
            },
            runtime={
                "elapsed_seconds": elapsed_seconds,
                "encoded_at_utc": datetime.now(timezone.utc).isoformat(),
                "encoder_version": self.ENCODER_VERSION,
                "last_scene_seconds": float(scene_analyses[-1].get("analysis_duration_seconds") or 0.0) if scene_analyses else 0.0,
                "avg_scene_seconds": round(elapsed_seconds / max(len(scene_analyses), 1), 2) if scene_analyses else 0.0,
                "processed_scene_count": len(scene_analyses),
                "estimated_total_scenes": total_scenes,
            },
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
        resolver = DeterministicIdentityResolver()
        for book in book_inputs:
            book_path = Path(book["path"])
            if not book_path.exists():
                logging.warning("Identity resolver: book not found at %s", book_path)
                continue

            def _cb(chapter_index: int, total_chapters: int, chapter_title: str) -> None:
                self._emit(progress_callback, "identity", {
                    "status": f"Resolving identities: {chapter_title or f'Chapter {chapter_index}'} ({chapter_index}/{total_chapters})",
                    "chapter_index": chapter_index,
                    "total_chapters": total_chapters,
                    "chapter_title": chapter_title,
                    "book": book_path.name,
                })

            resolver.process_epub(book_path, progress_callback=_cb)
        return resolver.build_identity_result()

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
        orchestrator = SceneAnalysisOrchestrator(
            analysis_model=self.analysis_model,
            identity_model=self.identity_model,
            identity_pass_enabled=False,
            semantic_evidence_refiner=SemanticEvidenceRefiner(enabled=False),
            identity_semantic_reviewer=IdentitySemanticReviewer(enabled=False),
            scene_semantic_reviewer=SceneSemanticReviewer(enabled=False),
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
                return [fallback_error], attempted_targets
            current_target = next_target
            splitter = SceneExtractor.from_target_words(current_target)
            working_scenes = splitter.extract(scene)
        return [dict(scene, error="Scene analysis overflowed.")], attempted_targets

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

    def _rebuild_story_state(self, scene_analyses: List[Dict[str, Any]], identity_result: Dict[str, Any]) -> Dict[str, Any]:
        resolved_scene_analyses: List[Dict[str, Any]] = []
        entity_registry: List[Dict[str, Any]] = []
        state_result: Dict[str, Any] = {"transitions": [], "latest_state": []}
        timeline: List[Dict[str, Any]] = []
        event_ledger: List[Dict[str, Any]] = []
        character_timelines: List[Dict[str, Any]] = []
        character_profiles: List[Dict[str, Any]] = []
        canon_snapshot: List[Dict[str, Any]] = []
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
            "story_index_summary": story_index_summary,
        }

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
                "analysis_mode": self.analysis_mode,
                "target_scene_words": self.target_scene_words,
                "encoder_version": self.ENCODER_VERSION,
            },
            "chapters": chapters,
            "identity_result": identity_result,
            "planned_scenes": planned_scenes,
            "scene_analyses": scene_analyses,
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
            or config.get("analysis_mode") != self.analysis_mode
            or config.get("target_scene_words") != self.target_scene_words
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
