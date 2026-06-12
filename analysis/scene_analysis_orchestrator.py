"""Orchestrates local evidence extraction and structured/tool analysis modes."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from analysis.evidence_filter import score_and_filter_evidence
from analysis.entity_world_state_analyzer import EntityWorldStateAnalyzer
from analysis.identity_analyzer import IdentityAnalyzer
from analysis.local_entity_extractor import LocalEntityExtractor
from analysis.microtasks.semantic_evidence_refiner import SemanticEvidenceRefiner
from analysis.microtasks.identity_semantic_reviewer import IdentitySemanticReviewer
from analysis.microtasks.scene_semantic_reviewer import SceneSemanticReviewer
from analysis.pov_anchor_resolver import resolve_pov_anchor
from analysis.scene_analyzer import SceneAnalyzer
from analysis.scene_contract_reconciler import reconcile_scene_contract
from analysis.visual_state_analyzer import VisualStateAnalyzer
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
        visual_analyzer: Optional[VisualStateAnalyzer] = None,
        entity_world_state_analyzer: Optional[EntityWorldStateAnalyzer] = None,
    ):
        self.local_entity_extractor = local_entity_extractor or LocalEntityExtractor()
        self.semantic_evidence_refiner = semantic_evidence_refiner or SemanticEvidenceRefiner()
        self.identity_semantic_reviewer = identity_semantic_reviewer or IdentitySemanticReviewer()
        self.scene_semantic_reviewer = scene_semantic_reviewer or SceneSemanticReviewer()
        self.scene_analyzer = scene_analyzer or SceneAnalyzer(llm_client=LLMClient(mode=analysis_model))
        self.identity_analyzer = identity_analyzer or IdentityAnalyzer(llm_client=LLMClient(mode=identity_model))
        self.visual_analyzer = visual_analyzer or VisualStateAnalyzer(llm_client=LLMClient(mode=analysis_model))
        self.entity_world_state_analyzer = entity_world_state_analyzer or EntityWorldStateAnalyzer(llm_client=LLMClient(mode=analysis_model))
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
            primary = self._merge_scene_outputs(enriched_scene, tool_result["content"], tool_result["identity"], time.perf_counter() - started_at, tool_result.get("visual"), tool_result.get("entity_world_state"))
            primary = self.identity_semantic_reviewer.review(primary, enriched_scene.get("text", ""), enriched_scene.get("local_evidence"), enriched_scene.get("pov_anchor", ""))
            primary = self.scene_semantic_reviewer.review(primary, enriched_scene.get("text", ""))
            primary["comparison_results"] = {
                "tool": self.scene_semantic_reviewer.review(
                    self.identity_semantic_reviewer.review(
                        self._merge_scene_outputs(enriched_scene, tool_result["content"], tool_result["identity"], tool_result["elapsed_seconds"], tool_result.get("visual"), tool_result.get("entity_world_state")),
                        enriched_scene.get("text", ""),
                        enriched_scene.get("local_evidence"),
                        enriched_scene.get("pov_anchor", ""),
                    ),
                    enriched_scene.get("text", ""),
                ),
                "structured": self.scene_semantic_reviewer.review(
                    self.identity_semantic_reviewer.review(
                        self._merge_scene_outputs(enriched_scene, structured_result["content"], structured_result["identity"], structured_result["elapsed_seconds"], structured_result.get("visual"), structured_result.get("entity_world_state")),
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
        merged = self._merge_scene_outputs(enriched_scene, pair_result["content"], pair_result["identity"], pair_result["elapsed_seconds"], pair_result.get("visual"), pair_result.get("entity_world_state"))
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
            with ThreadPoolExecutor(max_workers=3) as executor:
                content_future = executor.submit(
                    self.scene_analyzer.analyze,
                    scene,
                    alias_map=alias_map,
                    rejected_identities=rejected_identities,
                    scene_context=scene_context,
                    local_evidence=local_evidence,
                    analysis_mode=analysis_mode,
                )
                visual_future = executor.submit(
                    self.visual_analyzer.analyze,
                    scene,
                    alias_map=alias_map,
                    scene_context=scene_context,
                    local_evidence=local_evidence,
                    analysis_mode=analysis_mode,
                )
                world_state_future = executor.submit(
                    self.entity_world_state_analyzer.analyze,
                    scene,
                    alias_map=alias_map,
                    scene_context=scene_context,
                    local_evidence=local_evidence,
                    analysis_mode=analysis_mode,
                )
                content_result = content_future.result()
                visual_result = visual_future.result()
                world_state_result = world_state_future.result()
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
                "visual": visual_result,
                "entity_world_state": world_state_result,
                "elapsed_seconds": time.perf_counter() - started_at,
            }
        with ThreadPoolExecutor(max_workers=4) as executor:
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
            visual_future = executor.submit(
                self.visual_analyzer.analyze,
                scene,
                alias_map=alias_map,
                scene_context=scene_context,
                local_evidence=local_evidence,
                analysis_mode=analysis_mode,
            )
            world_state_future = executor.submit(
                self.entity_world_state_analyzer.analyze,
                scene,
                alias_map=alias_map,
                scene_context=scene_context,
                local_evidence=local_evidence,
                analysis_mode=analysis_mode,
            )
            content_result = content_future.result()
            identity_result = identity_future.result()
            visual_result = visual_future.result()
            world_state_result = world_state_future.result()
        return {
            "content": content_result,
            "identity": identity_result,
            "visual": visual_result,
            "entity_world_state": world_state_result,
            "elapsed_seconds": time.perf_counter() - started_at,
        }

    def _merge_scene_outputs(
        self,
        scene: Dict,
        content_result: Dict,
        identity_result: Dict,
        elapsed_seconds: float,
        visual_result: Optional[Dict] = None,
        entity_world_state_result: Optional[Dict] = None,
    ) -> Dict:
        merged = dict(content_result)
        visual_result = visual_result or {
            "characters": [],
            "objects": [],
            "creatures": [],
            "locations": [],
            "scene_compositions": [],
            "diagnostics": {},
        }
        entity_world_state_result = entity_world_state_result or {
            "entities": [],
            "diagnostics": {},
        }
        if visual_result.get("error") and not merged.get("error"):
            merged["error"] = visual_result.get("error")
            merged["last_error"] = visual_result.get("last_error") or "visual_state_analyzer_failed"
            merged["error_category"] = visual_result.get("error_category") or ""
            merged["final_status"] = "failed"
        if entity_world_state_result.get("error") and not merged.get("error"):
            merged["error"] = entity_world_state_result.get("error")
            merged["last_error"] = entity_world_state_result.get("last_error") or "entity_world_state_analyzer_failed"
            merged["error_category"] = entity_world_state_result.get("error_category") or ""
            merged["final_status"] = "failed"
        self._apply_visual_state_to_scene(merged, visual_result)
        merged["visual_analysis"] = visual_result
        merged["entity_world_state"] = entity_world_state_result
        merged["canonical_characters"] = identity_result.get("canonical_characters", [])
        merged["character_mentions"] = identity_result.get("character_mentions", [])
        merged["alias_updates"] = identity_result.get("alias_updates", [])
        merged["rejected_identity_candidates"] = identity_result.get("rejected_identity_candidates", [])
        merged["local_evidence"] = scene.get("local_evidence") or {}
        merged["tool_runtime"] = {
            "content": content_result.get("tool_runtime", {}),
            "identity": identity_result.get("tool_runtime", {}),
            "visual": visual_result.get("tool_runtime", {}),
            "entity_world_state": entity_world_state_result.get("tool_runtime", {}),
        }
        merged["analysis_duration_seconds"] = round(elapsed_seconds, 2)
        merged.setdefault("book_index", scene.get("book_index"))
        merged.setdefault("chapter_index", scene.get("chapter_index"))
        merged.setdefault("scene_index", scene.get("scene_index"))
        merged.setdefault("length", scene.get("length"))
        merged.setdefault("text", scene.get("text", ""))
        return reconcile_scene_contract(merged)

    def _apply_visual_state_to_scene(self, merged: Dict, visual_result: Dict) -> None:
        entity_seen = {
            (str(item.get("name") or "").strip().lower(), str(item.get("entity_type") or "").strip().lower())
            for item in merged.get("entities_present") or []
            if isinstance(item, dict)
        }
        description_seen = {
            (
                str(item.get("entity_name") or "").strip().lower(),
                str(item.get("entity_type") or "").strip().lower(),
                str(item.get("description") or "").strip().lower(),
            )
            for item in merged.get("entity_descriptions") or []
            if isinstance(item, dict)
        }

        def add_entity(name: str, entity_type: str) -> None:
            key = (name.strip().lower(), entity_type.strip().lower())
            if not name or not entity_type or key in entity_seen:
                return
            entity_seen.add(key)
            merged.setdefault("entities_present", []).append({"name": name, "entity_type": entity_type})

        def add_description(name: str, entity_type: str, description: str, description_type: str) -> None:
            description = " ".join(str(description or "").strip().split())
            if not name or not description:
                return
            key = (name.strip().lower(), entity_type.strip().lower(), description.lower())
            if key in description_seen:
                return
            description_seen.add(key)
            merged.setdefault("entity_descriptions", []).append(
                {
                    "entity_name": name,
                    "entity_type": entity_type,
                    "description": description,
                    "description_type": description_type,
                    "visual_source": "visual_state_analyzer",
                }
            )

        def profile_baseline(row: Dict[str, Any]) -> str:
            profile = row.get("persistent_visual_profile") or {}
            parts = [
                profile.get("presence_description"),
                profile.get("height_description"),
                profile.get("body_type"),
                profile.get("skin_description"),
                profile.get("hair_description"),
                profile.get("eye_description"),
                profile.get("facial_structure"),
                profile.get("age_appearance"),
                profile.get("distinguishing_marks"),
                profile.get("fantasy_features"),
            ]
            return "; ".join(str(part).strip() for part in parts if str(part or "").strip())

        for row in visual_result.get("characters") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("entity_name") or "").strip()
            if not name:
                continue
            add_entity(name, "character")
            baseline_text = row.get("physical_description") or (profile_baseline(row) if row.get("visual_role") == "initial_character_description" else "")
            if baseline_text:
                add_description(name, "character", baseline_text, "stable_trait" if row.get("visual_role") == "initial_character_description" else "appearance_note")
            if row.get("outfit"):
                add_description(name, "character", row.get("outfit"), "appearance_note")
            if row.get("visible_condition"):
                add_description(name, "character", row.get("visible_condition"), "temporary_condition")
            if row.get("body_language"):
                add_description(name, "character", row.get("body_language"), "appearance_note")
            if row.get("visual_role") == "character_change":
                change_text = row.get("image_edit_prompt") or row.get("visible_condition") or row.get("outfit")
                if change_text:
                    merged.setdefault("state_changes", []).append(
                        {
                            "entity_name": name,
                            "entity_type": "character",
                            "attribute": "visual_state",
                            "previous_state": "",
                            "new_state": str(change_text).strip(),
                            "change_type": "physical_state",
                            "evidence": row.get("source_evidence") or str(change_text).strip(),
                            "visual_source": "visual_state_analyzer",
                        }
                    )

        for collection_name, entity_type, description_key, state_key in [
            ("objects", "object", "visual_description", "state_or_ownership"),
            ("creatures", "creature", "visual_description", "state_or_ownership"),
        ]:
            for row in visual_result.get(collection_name) or []:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("entity_name") or "").strip()
                if not name:
                    continue
                add_entity(name, entity_type)
                if row.get(description_key):
                    add_description(name, entity_type, row.get(description_key), "appearance_note")
                if row.get(state_key):
                    add_description(name, entity_type, row.get(state_key), "temporary_condition")

        for row in visual_result.get("locations") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("entity_name") or "").strip()
            if not name:
                continue
            add_entity(name, "location")
            if row.get("physical_description"):
                add_description(name, "location", row.get("physical_description"), "appearance_note")
            if row.get("atmosphere"):
                add_description(name, "location", row.get("atmosphere"), "temporary_condition")
            if row.get("state_change"):
                add_description(name, "location", row.get("state_change"), "temporary_condition")
