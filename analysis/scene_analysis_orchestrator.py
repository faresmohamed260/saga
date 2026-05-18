"""Orchestrates local evidence extraction and structured/tool analysis modes."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from analysis.evidence_filter import score_and_filter_evidence
from analysis.identity_analyzer import IdentityAnalyzer
from analysis.local_entity_extractor import LocalEntityExtractor
from analysis.microtasks.semantic_evidence_refiner import SemanticEvidenceRefiner
from analysis.microtasks.identity_semantic_reviewer import IdentitySemanticReviewer
from analysis.microtasks.scene_semantic_reviewer import SceneSemanticReviewer
from analysis.pov_anchor_resolver import resolve_pov_anchor
from analysis.scene_analyzer import SceneAnalyzer
from infrastructure.llm_client import LLMClient


class SceneAnalysisOrchestrator:
    """Run local extraction first, then route into structured or tool analysis."""

    def __init__(
        self,
        analysis_model: str = "gpt_oss",
        identity_model: str = "gpt_oss",
        identity_pass_enabled: bool = True,
        local_entity_extractor: Optional[LocalEntityExtractor] = None,
        semantic_evidence_refiner: Optional[SemanticEvidenceRefiner] = None,
        identity_semantic_reviewer: Optional[IdentitySemanticReviewer] = None,
        scene_semantic_reviewer: Optional[SceneSemanticReviewer] = None,
        scene_analyzer: Optional[SceneAnalyzer] = None,
        identity_analyzer: Optional[IdentityAnalyzer] = None,
    ):
        self.local_entity_extractor = local_entity_extractor or LocalEntityExtractor()
        self.semantic_evidence_refiner = semantic_evidence_refiner or SemanticEvidenceRefiner()
        self.identity_semantic_reviewer = identity_semantic_reviewer or IdentitySemanticReviewer()
        self.scene_semantic_reviewer = scene_semantic_reviewer or SceneSemanticReviewer()
        self.scene_analyzer = scene_analyzer or SceneAnalyzer(llm_client=LLMClient(mode=analysis_model))
        self.identity_analyzer = identity_analyzer or IdentityAnalyzer(llm_client=LLMClient(mode=identity_model))
        self.identity_pass_enabled = identity_pass_enabled

    def analyze_scene(
        self,
        scene: Dict,
        alias_map: Optional[Dict[str, List[str]]] = None,
        rejected_identities: Optional[List[str]] = None,
        scene_context: str = "",
        analysis_mode: str = "structured",
    ) -> Dict:
        alias_map = alias_map or {}
        rejected_identities = rejected_identities or []
        pov_anchor = resolve_pov_anchor(scene)
        raw_local_evidence = self.local_entity_extractor.extract(scene.get("text", ""))
        local_evidence = score_and_filter_evidence(raw_local_evidence)
        local_evidence = self.semantic_evidence_refiner.refine(local_evidence, scene.get("text", ""))
        enriched_scene = {**scene, "local_evidence": local_evidence, "pov_anchor": pov_anchor}

        started_at = time.perf_counter()
        if analysis_mode == "compare":
            tool_result = self._run_pair(enriched_scene, alias_map, rejected_identities, scene_context, "tool")
            structured_result = self._run_pair(enriched_scene, alias_map, rejected_identities, scene_context, "structured")
            primary = self._merge_scene_outputs(enriched_scene, tool_result["content"], tool_result["identity"], time.perf_counter() - started_at)
            primary = self.identity_semantic_reviewer.review(primary, enriched_scene.get("text", ""), enriched_scene.get("local_evidence"), enriched_scene.get("pov_anchor", ""))
            primary = self.scene_semantic_reviewer.review(primary, enriched_scene.get("text", ""))
            primary["comparison_results"] = {
                "tool": self.scene_semantic_reviewer.review(
                    self.identity_semantic_reviewer.review(
                        self._merge_scene_outputs(enriched_scene, tool_result["content"], tool_result["identity"], tool_result["elapsed_seconds"]),
                        enriched_scene.get("text", ""),
                        enriched_scene.get("local_evidence"),
                        enriched_scene.get("pov_anchor", ""),
                    ),
                    enriched_scene.get("text", ""),
                ),
                "structured": self.scene_semantic_reviewer.review(
                    self.identity_semantic_reviewer.review(
                        self._merge_scene_outputs(enriched_scene, structured_result["content"], structured_result["identity"], structured_result["elapsed_seconds"]),
                        enriched_scene.get("text", ""),
                        enriched_scene.get("local_evidence"),
                        enriched_scene.get("pov_anchor", ""),
                    ),
                    enriched_scene.get("text", ""),
                ),
            }
            primary["local_evidence_raw"] = raw_local_evidence
            primary["analysis_mode"] = "compare"
            return primary

        pair_result = self._run_pair(enriched_scene, alias_map, rejected_identities, scene_context, analysis_mode)
        merged = self._merge_scene_outputs(enriched_scene, pair_result["content"], pair_result["identity"], pair_result["elapsed_seconds"])
        merged = self.identity_semantic_reviewer.review(merged, enriched_scene.get("text", ""), enriched_scene.get("local_evidence"), enriched_scene.get("pov_anchor", ""))
        merged = self.scene_semantic_reviewer.review(merged, enriched_scene.get("text", ""))
        merged["local_evidence_raw"] = raw_local_evidence
        merged["analysis_mode"] = analysis_mode
        merged["pov_anchor"] = pov_anchor
        return merged

    def _run_pair(
        self,
        scene: Dict,
        alias_map: Dict[str, List[str]],
        rejected_identities: List[str],
        scene_context: str,
        analysis_mode: str,
    ) -> Dict:
        local_evidence = scene.get("local_evidence") or {}
        started_at = time.perf_counter()
        if not self.identity_pass_enabled:
            content_result = self.scene_analyzer.analyze(
                scene,
                alias_map=alias_map,
                rejected_identities=rejected_identities,
                scene_context=scene_context,
                local_evidence=local_evidence,
                analysis_mode=analysis_mode,
            )
            identity_result = {
                "canonical_characters": content_result.get("canonical_characters", []),
                "character_mentions": content_result.get("character_mentions", []),
                "alias_updates": content_result.get("alias_updates", []),
                "rejected_identity_candidates": content_result.get("rejected_identity_candidates", []),
                "tool_runtime": content_result.get("tool_runtime", {}),
            }
            return {
                "content": content_result,
                "identity": identity_result,
                "elapsed_seconds": time.perf_counter() - started_at,
            }
        with ThreadPoolExecutor(max_workers=2) as executor:
            content_future = executor.submit(
                self.scene_analyzer.analyze,
                scene,
                alias_map=alias_map,
                rejected_identities=rejected_identities,
                scene_context=scene_context,
                local_evidence=local_evidence,
                analysis_mode=analysis_mode,
            )
            identity_future = executor.submit(
                self.identity_analyzer.analyze,
                scene,
                alias_map=alias_map,
                rejected_identities=rejected_identities,
                scene_context=scene_context,
                local_evidence=local_evidence,
                analysis_mode=analysis_mode,
            )
            content_result = content_future.result()
            identity_result = identity_future.result()
        return {
            "content": content_result,
            "identity": identity_result,
            "elapsed_seconds": time.perf_counter() - started_at,
        }

    def _merge_scene_outputs(self, scene: Dict, content_result: Dict, identity_result: Dict, elapsed_seconds: float) -> Dict:
        merged = dict(content_result)
        merged["canonical_characters"] = identity_result.get("canonical_characters", [])
        merged["character_mentions"] = identity_result.get("character_mentions", [])
        merged["alias_updates"] = identity_result.get("alias_updates", [])
        merged["rejected_identity_candidates"] = identity_result.get("rejected_identity_candidates", [])
        merged["local_evidence"] = scene.get("local_evidence") or {}
        merged["tool_runtime"] = {
            "content": content_result.get("tool_runtime", {}),
            "identity": identity_result.get("tool_runtime", {}),
        }
        merged["analysis_duration_seconds"] = round(elapsed_seconds, 2)
        merged.setdefault("book_index", scene.get("book_index"))
        merged.setdefault("chapter_index", scene.get("chapter_index"))
        merged.setdefault("scene_index", scene.get("scene_index"))
        merged.setdefault("length", scene.get("length"))
        merged.setdefault("text", scene.get("text", ""))
        return merged
