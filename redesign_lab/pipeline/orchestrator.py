"""End-to-end redesign orchestration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from redesign_lab.pipeline.adapters import load_acotar_chapters, load_json_config, now_utc
from redesign_lab.pipeline.chapter_batching import ChapterBatcher
from redesign_lab.pipeline.decoder_run import DecoderRunStage
from redesign_lab.pipeline.graph_ingest import GraphIngestStage
from redesign_lab.pipeline.identity_inventory import IdentityInventoryUpdater, empty_identity_inventory, inventory_to_identity_result
from redesign_lab.pipeline.incremental_identity_roster import IncrementalIdentityRoster
from redesign_lab.pipeline.narrative_extraction import NarrativeExtractionStage
from redesign_lab.pipeline.retrieval_build import RetrievalBuildStage
from redesign_lab.pipeline.stable_state import StableStateStage


class RedesignOrchestrator:
    """Run the redesign pipeline without touching current production defaults."""

    def __init__(self, *, output_root: str | Path = "redesign_lab/outputs") -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def run_dry(
        self,
        *,
        llm_mode: str = "general_compute",
        model_override: str = "deepseek-v3.1",
        identity_provider_mode: str = "redesign_inventory",
        identity_json_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        self._announce("== Redesign Lab Dry Run ==")
        corpus = load_acotar_chapters(llm_mode="gpt_oss")
        chapters = corpus["chapters"][:4]
        base_series_id = corpus["series_id"]
        batches = ChapterBatcher(target_scene_words=0).build_batches(
            chapters,
            series_id=base_series_id,
            series_title=corpus["series_title"],
        )
        extractor = NarrativeExtractionStage(llm_mode=llm_mode, model_override=model_override, analysis_mode="structured")
        inventory = empty_identity_inventory(base_series_id)
        updater = IdentityInventoryUpdater()
        scene_analyses = []
        roster = IncrementalIdentityRoster.build_from_books(
            series_id=base_series_id,
            books=corpus["books"],
            max_chapters_by_book={1: 4},
            cleanup_llm_mode="gpt_oss",
            cleanup_model_override="",
            lookahead_chapters=2,
        )
        for index, batch in enumerate(batches[:2], start=1):
            self._progress("dry-extraction", index, len(batches[:2]), f"batch {index}/{len(batches[:2])} book {batch['book_index']} chapters {batch['chapter_indices']}")
            snapshot = roster.snapshot_for_batch(
                book_index=int(batch["book_index"]),
                chapter_indices=batch["chapter_indices"],
            )
            result = extractor.analyze_batch(
                batch,
                alias_map=snapshot["alias_map"],
                rejected_identities=snapshot["rejected_identities"],
                scene_context=snapshot["scene_context"],
            )
            roster.apply_extraction_feedback(batch=batch, extraction=result)
            inventory = updater.update(inventory, result)
            scene_analyses.append(self._extraction_to_scene(result))
        inventory = roster.merge_into_inventory(inventory)
        identity_result = self._build_identity_result(
            inventory=inventory,
            identity_provider_mode=identity_provider_mode,
            identity_json_path=identity_json_path,
        )
        stable_states = StableStateStage().build(scene_analyses, identity_result)
        output = {
            "series_id": base_series_id,
            "batch_count": len(batches[:2]),
            "scene_analysis_count": len(scene_analyses),
            "stable_state_count": len(stable_states),
            "identity_result": identity_result,
            "stable_character_states": stable_states,
            "completed_at_utc": now_utc(),
        }
        dry_dir = self.output_root / "dry_run"
        dry_dir.mkdir(parents=True, exist_ok=True)
        (dry_dir / "dry_run_report.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        self._announce("Dry run completed.")
        return output

    def run_end_to_end(
        self,
        *,
        user_prompt: str,
        generation_controls: Dict[str, Any] | None = None,
        identity_provider_mode: str = "redesign_inventory",
        identity_json_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        self._announce("== Redesign Lab End-to-End Run ==")
        self._announce("Loading ACOTAR corpus and benchmark-selected assignments...")
        corpus = load_acotar_chapters(llm_mode="gpt_oss")
        assignments = load_json_config("subtask_assignments.json")["assignments"]
        candidate_config = load_json_config("candidates.json")
        start = time.perf_counter()

        batches = ChapterBatcher(target_scene_words=0).build_batches(
            corpus["chapters"],
            series_id=corpus["series_id"],
            series_title=corpus["series_title"],
        )
        extraction_spec = next(
            item for item in candidate_config["narrative_extraction"]
            if item["candidate_id"] == assignments["narrative_extraction"]["candidate_id"]
        )
        extractor = NarrativeExtractionStage(
            llm_mode=extraction_spec["mode"],
            model_override=extraction_spec.get("model_override", ""),
            analysis_mode=extraction_spec.get("analysis_mode", "structured"),
        )
        inventory = empty_identity_inventory(corpus["series_id"])
        updater = IdentityInventoryUpdater()
        scene_analyses: List[Dict[str, Any]] = []
        max_chapters_by_book: Dict[int, int] = {}
        for chapter in corpus["chapters"]:
            book_index = int(chapter.get("book_index") or 1)
            chapter_index = int(chapter.get("chapter_index") or 1)
            max_chapters_by_book[book_index] = max(max_chapters_by_book.get(book_index, 0), chapter_index + 2)
        roster = IncrementalIdentityRoster.build_from_books(
            series_id=corpus["series_id"],
            books=corpus["books"],
            max_chapters_by_book=max_chapters_by_book,
            cleanup_llm_mode="gpt_oss",
            cleanup_model_override="",
            lookahead_chapters=2,
        )
        total_batches = len(batches)
        self._announce(f"Processing {total_batches} redesign chapter batches sequentially...")
        for index, batch in enumerate(batches, start=1):
            self._progress("encoder", index, total_batches, f"book {batch['book_index']} chapters {batch['chapter_indices']}")
            snapshot = roster.snapshot_for_batch(
                book_index=int(batch["book_index"]),
                chapter_indices=batch["chapter_indices"],
            )
            result = extractor.analyze_batch(
                batch,
                alias_map=snapshot["alias_map"],
                rejected_identities=snapshot["rejected_identities"],
                scene_context=snapshot["scene_context"],
            )
            roster.apply_extraction_feedback(batch=batch, extraction=result)
            inventory = updater.update(inventory, result)
            scene_analyses.append(self._extraction_to_scene(result))
        self._announce("Building redesign identity consolidation and stable state...")
        inventory = roster.merge_into_inventory(inventory)
        identity_result = self._build_identity_result(
            inventory=inventory,
            identity_provider_mode=identity_provider_mode,
            identity_json_path=identity_json_path,
        )
        stable_states = StableStateStage().build(scene_analyses, identity_result)
        graph_stage = GraphIngestStage()
        self._announce("Persisting redesign graph namespace into Neo4j...")
        ingest_payload = graph_stage.ingest(
            base_series_id=corpus["series_id"],
            series_title=corpus["series_title"],
            prepared_books=corpus["books"],
            configuration={
                "analysis_model": extraction_spec["mode"],
                "analysis_mode": extraction_spec.get("analysis_mode", "structured"),
                "identity_strategy": "redesign_inventory",
                "target_scene_words": 0,
                "redesign_track": True,
            },
            scene_analyses=scene_analyses,
            identity_result=identity_result,
            stable_character_states=stable_states,
            causal_graph_result={"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}},
            runtime={
                "elapsed_seconds": round(time.perf_counter() - start, 2),
                "redesign_completed_at_utc": now_utc(),
            },
        )
        retrieval_packet = RetrievalBuildStage().build(series_id=ingest_payload["series_id"])
        self._announce(f"Retrieval packet built with {len(retrieval_packet.get('character_states') or [])} character packets.")
        decoder_dir = self.output_root / "end_to_end" / "decoder"
        decoder_dir.mkdir(parents=True, exist_ok=True)
        decoder_stage = DecoderRunStage(
            blueprint_spec=next(item for item in candidate_config["decoder_blueprint"] if item["candidate_id"] == assignments["decoder_blueprint"]["candidate_id"]),
            outline_spec=next(item for item in candidate_config["decoder_outline"] if item["candidate_id"] == assignments["decoder_outline"]["candidate_id"]),
            prose_spec=next(item for item in candidate_config["decoder_prose"] if item["candidate_id"] == assignments["decoder_prose"]["candidate_id"]),
        )
        self._announce("Running redesign decoder with split blueprint/outline/prose routing...")
        sequel_path = decoder_stage.run(
            series_id=ingest_payload["series_id"],
            user_prompt=user_prompt,
            output_dir=decoder_dir,
            generation_controls=generation_controls or {},
        )
        elapsed = round(time.perf_counter() - start, 2)
        report = {
            "series_id": ingest_payload["series_id"],
            "batch_count": len(batches),
            "scene_analysis_count": len(scene_analyses),
            "stable_state_count": len(stable_states),
            "retrieval_character_count": len(retrieval_packet.get("character_states") or []),
            "sequel_output_dir": str(sequel_path),
            "elapsed_seconds": elapsed,
            "completed_at_utc": now_utc(),
        }
        report_path = self.output_root / "end_to_end" / "run_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._announce("Redesign end-to-end run completed.")
        return report

    def _extraction_to_scene(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "book_index": extraction["book_index"],
            "chapter_index": extraction["chapter_indices"][0] if extraction["chapter_indices"] else 1,
            "scene_index": 1,
            "length": len((extraction.get("text") or "").split()),
            "text": extraction.get("text", ""),
            "scene_summary": extraction.get("scene_summary", ""),
            "events": extraction.get("events", []),
            "entities_present": extraction.get("entities_present", []),
            "entity_descriptions": extraction.get("entity_descriptions", []),
            "state_changes": extraction.get("state_changes", []),
            "relationship_changes": extraction.get("relationship_changes", []),
            "location": extraction.get("location", {}),
            "time_signals": extraction.get("time_signals", []),
            "canonical_characters": extraction.get("canonical_characters", []),
            "character_mentions": extraction.get("character_mentions", []),
            "alias_updates": extraction.get("alias_updates", []),
            "rejected_identity_candidates": extraction.get("rejected_identity_candidates", []),
        }

    def _progress(self, stage: str, index: int, total: int, label: str) -> None:
        filled = max(1, int((index / max(total, 1)) * 28))
        bar = "#" * filled + "-" * max(0, 28 - filled)
        self._announce(f"[{stage}] [{bar}] {index}/{total} {label}")

    def _announce(self, message: str) -> None:
        print(message, flush=True)

    def _build_identity_result(
        self,
        *,
        inventory: Dict[str, Any],
        identity_provider_mode: str,
        identity_json_path: str | Path | None,
    ) -> Dict[str, Any]:
        mode = str(identity_provider_mode or "redesign_inventory").strip().lower()
        if mode == "booknlp_clean":
            if not identity_json_path:
                raise ValueError("identity_json_path is required when identity_provider_mode='booknlp_clean'.")
            from redesign_lab.identity.identity_provider import BookNLPCleanIdentityProvider

            provider = BookNLPCleanIdentityProvider.from_path(identity_json_path)
            return provider.build_identity_result_compat()
        consolidated = IdentityConsolidator().consolidate(inventory)
        return {
            **inventory_to_identity_result(inventory),
            "alias_map": consolidated["alias_map"],
            "rejected_non_characters": consolidated["rejected_non_characters"],
        }
