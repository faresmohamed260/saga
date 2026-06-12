"""Narrative extraction stage for redesign batches."""

from __future__ import annotations

from typing import Any, Dict, List

from analysis.scene_analyzer import SceneAnalyzer
from infrastructure.llm_client import LLMClient
from redesign_lab.pipeline.contracts import validate_contract


class NarrativeExtractionStage:
    """Run chapter-batch extraction using provider-supported structured mode."""

    def __init__(
        self,
        *,
        llm_mode: str,
        model_override: str = "",
        analysis_mode: str = "structured",
        max_attempts: int = 2,
    ) -> None:
        self.llm_mode = llm_mode
        self.model_override = str(model_override or "").strip()
        self.analysis_mode = analysis_mode
        self.llm = LLMClient(
            mode=llm_mode,
            ollama_model_override=self.model_override,
            max_retries=2,
            base_delay=0.0,
            timeout=120,
        )
        self.analyzer = SceneAnalyzer(llm_client=self.llm, max_attempts=max_attempts)

    @property
    def candidate_label(self) -> str:
        return self.model_override or self.llm_mode

    def analyze_batch(
        self,
        batch: Dict[str, Any],
        *,
        alias_map: Dict[str, List[str]] | None = None,
        rejected_identities: List[str] | None = None,
        scene_context: str = "",
    ) -> Dict[str, Any]:
        scene = {
            "book_index": batch["book_index"],
            "chapter_index": batch["start_chapter_index"],
            "scene_index": batch["scene_index"],
            "length": batch["word_count"],
            "text": batch["text"],
        }
        result = self.analyzer.analyze(
            scene,
            alias_map=alias_map or {},
            rejected_identities=rejected_identities or [],
            scene_context=scene_context,
            local_evidence=None,
            analysis_mode=self.analysis_mode,
        )
        payload = {
            "batch_id": batch["batch_id"],
            "series_id": batch["series_id"],
            "book_index": batch["book_index"],
            "chapter_indices": batch["chapter_indices"],
            "scene_summary": result.get("scene_summary", ""),
            "events": result.get("events", []),
            "entities_present": result.get("entities_present", []),
            "entity_descriptions": result.get("entity_descriptions", []),
            "state_changes": result.get("state_changes", []),
            "relationship_changes": result.get("relationship_changes", []),
            "location": result.get("location", {}),
            "time_signals": result.get("time_signals", []),
            "canonical_characters": result.get("canonical_characters", []),
            "character_mentions": result.get("character_mentions", []),
            "alias_updates": result.get("alias_updates", []),
            "rejected_identity_candidates": result.get("rejected_identity_candidates", []),
            "model": self.candidate_label,
            "error": result.get("error", ""),
            "last_error": result.get("last_error", ""),
            "text": batch["text"],
        }
        return validate_contract("narrative_extraction_result", payload)

