"""Run redesign-local ACOTAR subtask benchmarks and write provisional assignments."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.general_compute_account_rotator import GeneralComputeAccountRotator
from infrastructure.llm_client import LLMClient
from redesign_lab.benchmarks.common import (
    choose_winner,
    ensure_dir,
    save_case_artifact,
    summarize_task_results,
    timed_call,
    write_json,
)
from redesign_lab.benchmarks.evaluators import (
    blueprint_score,
    chapter_batching_score,
    identity_inventory_score,
    narrative_extraction_score,
    outline_score,
    prose_score,
    retrieval_packet_score,
    stable_state_score,
)
from redesign_lab.pipeline.adapters import load_acotar_chapters, load_json_config, now_utc
from redesign_lab.pipeline.chapter_batching import ChapterBatcher
from redesign_lab.pipeline.decoder_run import DecoderRunStage
from redesign_lab.pipeline.graph_ingest import GraphIngestStage
from redesign_lab.pipeline.identity_consolidation import IdentityConsolidator
from redesign_lab.pipeline.identity_inventory import IdentityInventoryUpdater, empty_identity_inventory, inventory_to_identity_result
from redesign_lab.pipeline.incremental_identity_roster import IncrementalIdentityRoster
from redesign_lab.pipeline.narrative_extraction import NarrativeExtractionStage
from redesign_lab.pipeline.retrieval_build import RetrievalBuildStage
from redesign_lab.pipeline.stable_state import StableStateStage
from services.narrative_generation_service import NarrativeGenerationService


class RedesignBenchmarkSuite:
    """Benchmark real ACOTAR subtasks before assigning redesign winners."""

    def __init__(self, *, output_root: str | Path = "redesign_lab/reports") -> None:
        self.output_root = ensure_dir(output_root)
        self.candidate_config = load_json_config("candidates.json")
        self.case_config = load_json_config("acotar_benchmark_cases.json")
        self._prepared_runtime: Optional[Dict[str, Any]] = None
        self._identity_roster: Optional[IncrementalIdentityRoster] = None
        self.gc_rotator = GeneralComputeAccountRotator()

    def run_all(self) -> Dict[str, Any]:
        self._announce("== Redesign Lab Benchmarks ==")
        self._announce("Loading ACOTAR corpus for redesign benchmarks...")
        chapters_payload = load_acotar_chapters(llm_mode=LLMClient.MODE_GPT_OSS)
        self._stage(1, 8, "Benchmarking chapter batching")
        chapter_batches = self._benchmark_chapter_batching(chapters_payload)
        self._stage(2, 8, "Benchmarking narrative extraction")
        extraction = self._benchmark_narrative_extraction(chapters_payload)
        self._stage(3, 8, "Benchmarking identity inventory update")
        identity_update = self._benchmark_identity_inventory_update(chapters_payload, extraction)
        self._stage(4, 8, "Benchmarking identity consolidation")
        identity = self._benchmark_identity_consolidation(identity_update)
        self._stage(5, 8, "Benchmarking stable state build")
        stable_state = self._benchmark_stable_state_build(identity_update)
        self._stage(6, 8, "Benchmarking retrieval build")
        retrieval = self._benchmark_retrieval_build(chapters_payload, identity_update, stable_state)
        self._stage(7, 8, "Benchmarking decoder blueprint / outline / prose")
        decoder_blueprint = self._benchmark_decoder_blueprint(retrieval)
        decoder_outline = self._benchmark_decoder_outline(retrieval, decoder_blueprint)
        decoder_prose = self._benchmark_decoder_prose(retrieval, decoder_blueprint, decoder_outline)
        self._stage(8, 8, "Writing subtask assignments")
        assignments = self._build_assignments(
            chapter_report=chapter_batches,
            extraction_report=extraction,
            inventory_report=identity_update,
            identity_report=identity,
            stable_state_report=stable_state,
            retrieval_report=retrieval,
            blueprint_report=decoder_blueprint,
            outline_report=decoder_outline,
            prose_report=decoder_prose,
        )
        report = {
            "status": "completed",
            "completed_at_utc": now_utc(),
            "chapter_batching": chapter_batches,
            "narrative_extraction": extraction,
            "identity_inventory_update": identity_update,
            "identity_consolidation": identity,
            "stable_state_build": stable_state,
            "retrieval_build": retrieval,
            "decoder_blueprint": decoder_blueprint,
            "decoder_outline": decoder_outline,
            "decoder_prose": decoder_prose,
            "assignments": assignments,
        }
        write_json(self.output_root / "benchmark_report.json", report)
        write_json(Path("redesign_lab/configs/subtask_assignments.json"), assignments)
        self._announce("Benchmark suite completed.")
        return report

    def _benchmark_chapter_batching(self, chapters_payload: Dict[str, Any]) -> Dict[str, Any]:
        results = []
        total = len(self.candidate_config["chapter_batching"])
        for index, candidate in enumerate(self.candidate_config["chapter_batching"], start=1):
            self._announce(f"  [chapter_batching {index}/{total}] {candidate['candidate_id']}")
            batcher = ChapterBatcher(target_scene_words=int(candidate["target_scene_words"]))
            output, elapsed, error = timed_call(
                batcher.build_batches,
                chapters_payload["chapters"][:8],
                series_id=chapters_payload["series_id"],
                series_title=chapters_payload["series_title"],
            )
            scores = chapter_batching_score(output or [])
            results.append({
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **scores,
            })
            save_case_artifact(
                self.output_root,
                task_name="chapter_batching",
                candidate_id=candidate["candidate_id"],
                case_id="acotar_first8",
                payload={"output": output or [], "elapsed_seconds": elapsed, "error": error, **scores},
            )
        winner = choose_winner(results)
        return {"results": results, "winner": winner, "summary": summarize_task_results(results)}

    def _benchmark_narrative_extraction(self, chapters_payload: Dict[str, Any]) -> Dict[str, Any]:
        cases = self.case_config["narrative_extraction"]
        roster = self._build_incremental_identity_roster(chapters_payload, cases)
        batches = ChapterBatcher(target_scene_words=0).build_batches(
            chapters_payload["chapters"],
            series_id=chapters_payload["series_id"],
            series_title=chapters_payload["series_title"],
        )
        matched_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        for case in cases:
            target_chapters = set(case["chapter_indices"])
            matching_batch = next(
                (
                    batch
                    for batch in batches
                    if int(batch["book_index"]) == int(case["book_index"])
                    and target_chapters.intersection(batch["chapter_indices"])
                ),
                None,
            )
            if matching_batch:
                matched_pairs.append((case, matching_batch))
        results = []
        total = len(self.candidate_config["narrative_extraction"])
        for index, candidate in enumerate(self.candidate_config["narrative_extraction"], start=1):
            self._announce(f"  [narrative_extraction {index}/{total}] {candidate['candidate_id']}")
            if not self._probe_candidate(candidate):
                results.append({
                    "candidate_id": candidate["candidate_id"],
                    "status": "unavailable",
                    "elapsed_seconds": 0.0,
                    "validity_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_failures": 1.0,
                    "error": "probe_failed",
                })
                continue
            stage = NarrativeExtractionStage(
                llm_mode=candidate["mode"],
                model_override=candidate.get("model_override", ""),
                analysis_mode=candidate.get("analysis_mode", "structured"),
            )
            candidate_roster = deepcopy(roster)
            semantic_scores: List[float] = []
            validity_scores: List[float] = []
            structural_failures = 0.0
            elapsed_total = 0.0
            errors: List[str] = []
            for case, batch in matched_pairs:
                snapshot = candidate_roster.snapshot_for_batch(
                    book_index=int(batch["book_index"]),
                    chapter_indices=batch["chapter_indices"],
                )
                output, elapsed, error = timed_call(
                    stage.analyze_batch,
                    batch,
                    alias_map=snapshot["alias_map"],
                    rejected_identities=snapshot["rejected_identities"],
                    scene_context=snapshot["scene_context"],
                )
                elapsed_total += elapsed
                if error:
                    errors.append(error)
                    semantic_scores.append(0.0)
                    validity_scores.append(0.0)
                    structural_failures += 1.0
                    continue
                score = narrative_extraction_score(output or {}, case)
                semantic_scores.append(score["semantic_score"])
                validity_scores.append(score["validity_score"])
                structural_failures += score["structural_failures"]
                candidate_roster.apply_extraction_feedback(batch=batch, extraction=output or {})
                save_case_artifact(
                    self.output_root,
                    task_name="narrative_extraction",
                    candidate_id=candidate["candidate_id"],
                    case_id=case["case_id"],
                    payload={"output": output or {}, "elapsed_seconds": elapsed, "error": error, **score},
                )
            results.append({
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not errors else "partial",
                "elapsed_seconds": round(elapsed_total, 2),
                "validity_score": round(sum(validity_scores) / max(len(validity_scores), 1), 3),
                "semantic_score": round(sum(semantic_scores) / max(len(semantic_scores), 1), 3),
                "structural_failures": round(structural_failures, 3),
                "error": "; ".join(errors),
            })
        winner = choose_winner(results)
        write_json(
            self.output_root / "narrative_extraction" / "identity_roster_seed.json",
            {"entries": roster.entries, "rejected_identities": roster.rejected_identities},
        )
        return {
            "results": results,
            "winner": winner,
            "summary": summarize_task_results(results),
            "identity_roster_seed": {
                "entries": roster.entries,
                "rejected_identities": roster.rejected_identities,
            },
        }

    def _benchmark_identity_inventory_update(self, chapters_payload: Dict[str, Any], extraction_report: Dict[str, Any]) -> Dict[str, Any]:
        prepared = self._prepare_runtime(chapters_payload, extraction_report)
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["identity_inventory"][0]
        results = []
        total = len(self.candidate_config["identity_inventory_update"])
        for index, candidate in enumerate(self.candidate_config["identity_inventory_update"], start=1):
            self._announce(f"  [identity_inventory_update {index}/{total}] {candidate['candidate_id']}")
            score = identity_inventory_score(prepared["identity_inventory_projection"], case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok",
                "elapsed_seconds": prepared["inventory_elapsed_seconds"],
                **score,
                "error": "",
            }
            results.append(payload)
            save_case_artifact(
                self.output_root,
                task_name="identity_inventory_update",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": prepared["identity_inventory_projection"], **payload},
            )
        winner = choose_winner(results)
        return {"results": results, "winner": winner, "summary": summarize_task_results(results), "prepared": prepared}

    def _benchmark_identity_consolidation(self, inventory_report: Dict[str, Any]) -> Dict[str, Any]:
        prepared = inventory_report.get("prepared")
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["identity_inventory"][0]
        inventory = prepared["inventory"]
        results = []
        total = len(self.candidate_config["identity_consolidation"])
        for index, candidate in enumerate(self.candidate_config["identity_consolidation"], start=1):
            self._announce(f"  [identity_consolidation {index}/{total}] {candidate['candidate_id']}")
            consolidator = IdentityConsolidator(use_web_hints=candidate["component"] == "deterministic_web_hints")
            output, elapsed, error = timed_call(consolidator.consolidate, inventory)
            score = identity_inventory_score(output or {}, case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **score,
            }
            results.append(payload)
            save_case_artifact(
                self.output_root,
                task_name="identity_consolidation",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or {}, **payload},
            )
        winner = choose_winner(results)
        return {"results": results, "winner": winner, "summary": summarize_task_results(results)}

    def _benchmark_stable_state_build(self, inventory_report: Dict[str, Any]) -> Dict[str, Any]:
        prepared = inventory_report.get("prepared")
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["stable_state"][0]
        results = []
        total = len(self.candidate_config["stable_state_build"])
        for index, candidate in enumerate(self.candidate_config["stable_state_build"], start=1):
            self._announce(f"  [stable_state_build {index}/{total}] {candidate['candidate_id']}")
            stage = StableStateStage()
            output, elapsed, error = timed_call(stage.build, prepared["scene_analyses"], prepared["identity_result"])
            score = stable_state_score(output or [], case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **score,
            }
            results.append(payload)
            save_case_artifact(
                self.output_root,
                task_name="stable_state_build",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or [], **payload},
            )
        winner = choose_winner(results)
        return {"results": results, "winner": winner, "summary": summarize_task_results(results), "prepared": prepared}

    def _benchmark_retrieval_build(
        self,
        chapters_payload: Dict[str, Any],
        inventory_report: Dict[str, Any],
        stable_state_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        prepared = inventory_report.get("prepared")
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["retrieval_packet"][0]
        stable_states, _elapsed, _error = timed_call(StableStateStage().build, prepared["scene_analyses"], prepared["identity_result"])
        graph_stage = GraphIngestStage(series_suffix="-redesign-benchmark")
        ingest_result, ingest_elapsed, ingest_error = timed_call(
            graph_stage.ingest,
            base_series_id=chapters_payload["series_id"],
            series_title=chapters_payload["series_title"],
            prepared_books=chapters_payload["books"],
            configuration={
                "analysis_model": prepared["extraction_spec"]["mode"],
                "analysis_mode": prepared["extraction_spec"].get("analysis_mode", "structured"),
                "identity_strategy": "redesign_inventory_benchmark",
                "target_scene_words": 0,
                "redesign_track": True,
            },
            scene_analyses=prepared["scene_analyses"],
            identity_result=prepared["identity_result"],
            stable_character_states=stable_states or [],
            causal_graph_result={"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}},
            runtime={"elapsed_seconds": prepared["inventory_elapsed_seconds"], "redesign_completed_at_utc": now_utc()},
        )
        results = []
        total = len(self.candidate_config["retrieval_build"])
        for index, candidate in enumerate(self.candidate_config["retrieval_build"], start=1):
            self._announce(f"  [retrieval_build {index}/{total}] {candidate['candidate_id']}")
            if ingest_error:
                payload = {
                    "candidate_id": candidate["candidate_id"],
                    "status": "error",
                    "elapsed_seconds": round(ingest_elapsed, 2),
                    "validity_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_failures": 1.0,
                    "error": ingest_error,
                }
                results.append(payload)
                continue
            stage = RetrievalBuildStage()
            output, elapsed, error = timed_call(stage.build, series_id=ingest_result["series_id"])
            score = retrieval_packet_score(output or {}, case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": round(ingest_elapsed + elapsed, 2),
                "error": error,
                **score,
            }
            results.append(payload)
            save_case_artifact(
                self.output_root,
                task_name="retrieval_build",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or {}, "series_id": ingest_result["series_id"], **payload},
            )
        winner = choose_winner(results)
        return {
            "results": results,
            "winner": winner,
            "summary": summarize_task_results(results),
            "prepared": {
                **prepared,
                "stable_states": stable_states or [],
                "retrieval_series_id": (ingest_result or {}).get("series_id", ""),
            },
        }

    def _benchmark_decoder_blueprint(self, retrieval_report: Dict[str, Any]) -> Dict[str, Any]:
        prepared = retrieval_report.get("prepared")
        if not prepared or not prepared.get("retrieval_series_id"):
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["decoder_blueprint"][0]
        results = []
        generated = {}
        total = len(self.candidate_config["decoder_blueprint"])
        for index, candidate in enumerate(self.candidate_config["decoder_blueprint"], start=1):
            self._announce(f"  [decoder_blueprint {index}/{total}] {candidate['candidate_id']}")
            if not self._probe_candidate(candidate):
                results.append({
                    "candidate_id": candidate["candidate_id"],
                    "status": "unavailable",
                    "elapsed_seconds": 0.0,
                    "validity_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_failures": 1.0,
                    "error": "probe_failed",
                })
                continue
            llm = LLMClient(mode=candidate["mode"], ollama_model_override=candidate.get("model_override", ""))
            service = NarrativeGenerationService(planner_llm_client=llm, prose_llm_client=llm)
            retrieval_context = service.build_retrieval_context_from_neo4j(series_id=prepared["retrieval_series_id"])
            compiled = service.compile_context(retrieval_context, case["prompt"], generation_controls={"primary_pov_character": "Elain Archeron", "chapter_count": 10})
            output, elapsed, error = timed_call(service.generate_blueprint, compiled)
            score = blueprint_score(output or {}, case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **score,
            }
            results.append(payload)
            if not error and output:
                generated[candidate["candidate_id"]] = {"compiled": compiled, "blueprint": output, "retrieval_context": retrieval_context}
            save_case_artifact(
                self.output_root,
                task_name="decoder_blueprint",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or {}, **payload},
            )
        winner = choose_winner(results)
        return {
            "results": results,
            "winner": winner,
            "summary": summarize_task_results(results),
            "prepared": generated.get((winner or {}).get("candidate_id", ""), {}),
        }

    def _benchmark_decoder_outline(self, retrieval_report: Dict[str, Any], blueprint_report: Dict[str, Any]) -> Dict[str, Any]:
        prepared = blueprint_report.get("prepared") or {}
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["decoder_outline"][0]
        results = []
        generated = {}
        total = len(self.candidate_config["decoder_outline"])
        for index, candidate in enumerate(self.candidate_config["decoder_outline"], start=1):
            self._announce(f"  [decoder_outline {index}/{total}] {candidate['candidate_id']}")
            if not self._probe_candidate(candidate):
                results.append({
                    "candidate_id": candidate["candidate_id"],
                    "status": "unavailable",
                    "elapsed_seconds": 0.0,
                    "validity_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_failures": 1.0,
                    "error": "probe_failed",
                })
                continue
            llm = LLMClient(mode=candidate["mode"], ollama_model_override=candidate.get("model_override", ""))
            service = NarrativeGenerationService(planner_llm_client=llm, prose_llm_client=llm)
            compiled = prepared["compiled"]
            blueprint = prepared["blueprint"]
            world_state = service.initialise_world_state(compiled)
            output, elapsed, error = timed_call(
                service.generate_chapter_outline,
                blueprint=blueprint,
                compiled_context=compiled,
                world_state=world_state,
                previous_summaries=[],
                chapter_number=int(case["chapter_number"]),
            )
            score = outline_score(output or {}, case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **score,
            }
            results.append(payload)
            if not error and output:
                generated[candidate["candidate_id"]] = {"compiled": compiled, "blueprint": blueprint, "outline": output, "world_state": world_state}
            save_case_artifact(
                self.output_root,
                task_name="decoder_outline",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or {}, **payload},
            )
        winner = choose_winner(results)
        return {
            "results": results,
            "winner": winner,
            "summary": summarize_task_results(results),
            "prepared": generated.get((winner or {}).get("candidate_id", ""), {}),
        }

    def _benchmark_decoder_prose(
        self,
        retrieval_report: Dict[str, Any],
        blueprint_report: Dict[str, Any],
        outline_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        prepared = outline_report.get("prepared") or {}
        if not prepared:
            return {"results": [], "winner": None, "summary": summarize_task_results([])}
        case = self.case_config["decoder_prose"][0]
        results = []
        total = len(self.candidate_config["decoder_prose"])
        for index, candidate in enumerate(self.candidate_config["decoder_prose"], start=1):
            self._announce(f"  [decoder_prose {index}/{total}] {candidate['candidate_id']}")
            if not self._probe_candidate(candidate):
                results.append({
                    "candidate_id": candidate["candidate_id"],
                    "status": "unavailable",
                    "elapsed_seconds": 0.0,
                    "validity_score": 0.0,
                    "semantic_score": 0.0,
                    "structural_failures": 1.0,
                    "error": "probe_failed",
                })
                continue
            llm = LLMClient(mode=candidate["mode"], ollama_model_override=candidate.get("model_override", ""))
            service = NarrativeGenerationService(planner_llm_client=llm, prose_llm_client=llm)
            outline = prepared["outline"]
            scene_outline = (outline.get("scenes") or [{}])[0]
            output, elapsed, error = timed_call(
                service.generate_scene_prose,
                scene_outline=scene_outline,
                chapter_outline=outline,
                world_state=prepared["world_state"],
                previous_scene_ending="",
                book_title=str(prepared["compiled"].get("book_title") or ""),
                scene_memory=service._empty_scene_memory(),
                generation_controls=prepared["compiled"].get("generation_controls") or {},
            )
            score = prose_score(output or "", case)
            payload = {
                "candidate_id": candidate["candidate_id"],
                "status": "ok" if not error else "error",
                "elapsed_seconds": elapsed,
                "error": error,
                **score,
            }
            results.append(payload)
            save_case_artifact(
                self.output_root,
                task_name="decoder_prose",
                candidate_id=candidate["candidate_id"],
                case_id=case["case_id"],
                payload={"output": output or "", **payload},
            )
        winner = choose_winner(results)
        return {"results": results, "winner": winner, "summary": summarize_task_results(results)}

    def _build_assignments(
        self,
        *,
        chapter_report: Dict[str, Any],
        extraction_report: Dict[str, Any],
        inventory_report: Dict[str, Any],
        identity_report: Dict[str, Any],
        stable_state_report: Dict[str, Any],
        retrieval_report: Dict[str, Any],
        blueprint_report: Dict[str, Any],
        outline_report: Dict[str, Any],
        prose_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        current = load_json_config("subtask_assignments.json")
        current["status"] = "benchmarked"
        current["updated_at_utc"] = now_utc()
        mapping = {
            "chapter_batching": chapter_report,
            "narrative_extraction": extraction_report,
            "identity_inventory_update": inventory_report,
            "identity_consolidation": identity_report,
            "stable_state_build": stable_state_report,
            "retrieval_build": retrieval_report,
            "decoder_blueprint": blueprint_report,
            "decoder_outline": outline_report,
            "decoder_prose": prose_report,
        }
        for task_name, report in mapping.items():
            if report.get("winner"):
                current["assignments"][task_name] = {
                    "candidate_id": report["winner"]["candidate_id"],
                    "source": "benchmark",
                }
        return current

    def _probe_candidate(self, candidate: Dict[str, Any]) -> bool:
        mode = candidate.get("mode")
        if not mode:
            return True
        try:
            if mode in {LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS}:
                probe_client = LLMClient(mode=mode, ollama_model_override=candidate.get("model_override", ""), max_retries=1, base_delay=0.0, timeout=30)
                probe = LLMClient.probe_ollama_mode_access(mode, probe_client._ollama_model_for_mode())
            elif mode == LLMClient.MODE_GENERAL_COMPUTE:
                api_key = self.gc_rotator.acquire_api_key_for_request(
                    estimated_input_tokens=2500,
                    estimated_output_tokens=1200,
                    wait=False,
                )
                if not api_key:
                    return False
                probe_client = LLMClient(mode=mode, ollama_model_override=candidate.get("model_override", ""), max_retries=1, base_delay=0.0, timeout=30)
                probe = LLMClient.probe_general_compute_model_access(probe_client._general_compute_model_for_mode())
            else:
                probe = {"status": "ok"}
        except Exception:
            return False
        return probe.get("status") == "ok"

    def _prepare_runtime(self, chapters_payload: Dict[str, Any], extraction_report: Dict[str, Any]) -> Dict[str, Any] | None:
        if self._prepared_runtime is not None:
            return self._prepared_runtime
        winner = extraction_report.get("winner") or {}
        extraction_candidate_id = winner.get("candidate_id")
        extraction_spec = next(
            (item for item in self.candidate_config["narrative_extraction"] if item["candidate_id"] == extraction_candidate_id),
            None,
        )
        if not extraction_spec:
            return None
        stage = NarrativeExtractionStage(
            llm_mode=extraction_spec["mode"],
            model_override=extraction_spec.get("model_override", ""),
            analysis_mode=extraction_spec.get("analysis_mode", "structured"),
        )
        roster = self._build_incremental_identity_roster(chapters_payload, self.case_config["identity_inventory"])
        case = self.case_config["identity_inventory"][0]
        batches = ChapterBatcher(target_scene_words=0).build_batches(
            chapters_payload["chapters"],
            series_id=chapters_payload["series_id"],
            series_title=chapters_payload["series_title"],
        )
        target_batches = [
            batch for batch in batches
            if batch["book_index"] == case["book_index"] and set(batch["chapter_indices"]).intersection(case["chapter_indices"])
        ]
        inventory = empty_identity_inventory(chapters_payload["series_id"])
        updater = IdentityInventoryUpdater()
        scene_analyses: List[Dict[str, Any]] = []
        elapsed_total = 0.0
        for batch in target_batches:
            snapshot = roster.snapshot_for_batch(
                book_index=int(batch["book_index"]),
                chapter_indices=batch["chapter_indices"],
            )
            output, elapsed, error = timed_call(
                stage.analyze_batch,
                batch,
                alias_map=snapshot["alias_map"],
                rejected_identities=snapshot["rejected_identities"],
                scene_context=snapshot["scene_context"],
            )
            elapsed_total += elapsed
            if error or not output:
                continue
            roster.apply_extraction_feedback(batch=batch, extraction=output)
            inventory = updater.update(inventory, output)
            scene_analyses.append(self._extraction_to_scene(output))
        inventory = roster.merge_into_inventory(inventory)
        consolidator = IdentityConsolidator()
        consolidated = consolidator.consolidate(inventory)
        identity_result = {
            **inventory_to_identity_result(inventory),
            "alias_map": consolidated["alias_map"],
            "rejected_non_characters": consolidated["rejected_non_characters"],
        }
        prepared = {
            "inventory": inventory,
            "identity_inventory_projection": consolidated,
            "identity_result": identity_result,
            "scene_analyses": scene_analyses,
            "inventory_elapsed_seconds": round(elapsed_total, 2),
            "extraction_spec": extraction_spec,
            "identity_roster_seed": {"entries": roster.entries, "rejected_identities": roster.rejected_identities},
        }
        self._prepared_runtime = prepared
        return prepared

    def _build_incremental_identity_roster(self, chapters_payload: Dict[str, Any], cases: List[Dict[str, Any]]) -> IncrementalIdentityRoster:
        if self._identity_roster is not None:
            return deepcopy(self._identity_roster)
        max_chapters_by_book: Dict[int, int] = {}
        for case in cases:
            book_index = int(case.get("book_index") or 1)
            chapter_max = max(int(value) for value in (case.get("chapter_indices") or [1])) + 2
            max_chapters_by_book[book_index] = max(max_chapters_by_book.get(book_index, 0), chapter_max)
        roster = IncrementalIdentityRoster.build_from_books(
            series_id=chapters_payload["series_id"],
            books=chapters_payload["books"],
            max_chapters_by_book=max_chapters_by_book,
            cleanup_llm_mode=LLMClient.MODE_GPT_OSS,
            cleanup_model_override="",
            lookahead_chapters=2,
        )
        self._identity_roster = deepcopy(roster)
        return roster

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

    def _stage(self, index: int, total: int, label: str) -> None:
        filled = max(1, int((index / max(total, 1)) * 28))
        bar = "#" * filled + "-" * max(0, 28 - filled)
        self._announce(f"[{bar}] {index}/{total} {label}")

    def _announce(self, message: str) -> None:
        print(message, flush=True)


def run_all_benchmarks(output_root: str | Path = "redesign_lab/reports") -> Dict[str, Any]:
    return RedesignBenchmarkSuite(output_root=output_root).run_all()
