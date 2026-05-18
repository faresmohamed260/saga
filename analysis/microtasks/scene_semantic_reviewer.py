"""Post-analysis semantic review for scene outputs.

This layer uses small local semantic tasks to filter and rank scene outputs
after the main analyzers run. It keeps the stable scene schema intact while
moving event/state/relationship quality decisions out of one large analysis
call and into bounded local-model micro-tasks.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Optional

from analysis.microtasks.scene_fallback_synthesizer import SceneFallbackSynthesizer
from analysis.microtasks.task_registry import MicroTaskRegistry
from infrastructure.local_semantic_client import LocalSemanticClient


class SceneSemanticReviewer:
    """Refine scene outputs with bounded local semantic review tasks."""

    def __init__(
        self,
        task_registry: Optional[MicroTaskRegistry] = None,
        client_factory=None,
        fallback_synthesizer: Optional[SceneFallbackSynthesizer] = None,
        enabled: bool = True,
    ) -> None:
        self.task_registry = task_registry or MicroTaskRegistry()
        self.client_factory = client_factory or (lambda config: LocalSemanticClient(model=config.model, timeout=config.timeout))
        self.fallback_synthesizer = fallback_synthesizer or SceneFallbackSynthesizer(
            task_registry=self.task_registry,
            client_factory=self.client_factory,
            enabled=enabled,
        )
        self.enabled = enabled

    def review(self, scene_result: Dict, scene_text: str) -> Dict:
        reviewed = deepcopy(scene_result)
        if not self.enabled:
            reviewed["semantic_post_review"] = {"enabled": False}
            return reviewed

        event_reviews = []
        kept_events = []
        for event in reviewed.get("events") or []:
            verdict = self._rank_event_significance(event, scene_result, scene_text)
            event_reviews.append(self._review_record(event, verdict))
            if verdict.get("keep", True):
                kept_events.append({**event, "semantic_review": verdict})

        state_reviews = []
        kept_state_changes = []
        for change in reviewed.get("state_changes") or []:
            verdict = self._classify_state_change_importance(change, scene_result, scene_text)
            state_reviews.append(self._review_record(change, verdict))
            if verdict.get("keep", True):
                kept_state_changes.append({**change, "semantic_review": verdict})

        relationship_reviews = []
        kept_relationship_changes = []
        for change in reviewed.get("relationship_changes") or []:
            verdict = self._classify_relationship_change(change, scene_result, scene_text)
            relationship_reviews.append(self._review_record(change, verdict))
            if verdict.get("keep", True):
                kept_relationship_changes.append({
                    **change,
                    "relationship": verdict.get("relationship") or change.get("relationship", ""),
                    "change": verdict.get("change") or change.get("change", ""),
                    "semantic_review": verdict,
                })

        if not kept_events and (reviewed.get("scene_summary") or "").strip():
            fallback_events = self.fallback_synthesizer.synthesize_events(reviewed, scene_text)
            for event in fallback_events:
                verdict = self._rank_event_significance(event, reviewed, scene_text)
                event_reviews.append(self._review_record(event, verdict))
                if verdict.get("keep", True):
                    kept_events.append({**event, "semantic_review": verdict})

        reviewed["events"] = kept_events
        reviewed["state_changes"] = kept_state_changes
        reviewed["relationship_changes"] = kept_relationship_changes
        reviewed["semantic_post_review"] = {
            "enabled": True,
            "events_before": len(scene_result.get("events") or []),
            "events_after": len(kept_events),
            "state_changes_before": len(scene_result.get("state_changes") or []),
            "state_changes_after": len(kept_state_changes),
            "relationship_changes_before": len(scene_result.get("relationship_changes") or []),
            "relationship_changes_after": len(kept_relationship_changes),
            "event_reviews": event_reviews,
            "state_change_reviews": state_reviews,
            "relationship_change_reviews": relationship_reviews,
        }
        return reviewed

    def _rank_event_significance(self, event: Dict, scene_result: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("rank_event_significance")
        client = self.client_factory(config)
        prompt = f"""
Task: decide if this event is consequential enough to keep for canon tracking.

Return JSON:
{{
  "keep": true,
  "importance": "high",
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep only consequential events for canon tracking
- drop redundant background beats or very minor motions
- allowed importance values: high, medium, low
- prefer keeping fewer, stronger canon events

Scene summary:
{scene_result.get("scene_summary", "")}

Event candidate:
description={event.get("description", "")}
characters={event.get("characters", [])}
type={event.get("type", "")}

Scene:
{scene_text[:1800]}
"""
        result = client.generate_json(prompt, validator=self._validate_rank_verdict)
        if "error" in result:
            return {"keep": True, "importance": "medium", "reason": "event_review_unavailable", "confidence": "fallback"}
        return result

    def _classify_state_change_importance(self, change: Dict, scene_result: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("classify_state_change_importance")
        client = self.client_factory(config)
        prompt = f"""
Task: decide if this state change is important enough to keep for canon tracking.

Return JSON:
{{
  "keep": true,
  "importance": "high",
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep durable or plot-relevant state changes
- drop overly minor transient details unless they matter to the scene outcome
- allowed importance values: high, medium, low

Scene summary:
{scene_result.get("scene_summary", "")}

State change candidate:
entity_name={change.get("entity_name", "")}
entity_type={change.get("entity_type", "")}
attribute={change.get("attribute", "")}
previous_state={change.get("previous_state", "")}
new_state={change.get("new_state", "")}
change_type={change.get("change_type", "")}
evidence={change.get("evidence", "")}

Scene:
{scene_text[:1800]}
"""
        result = client.generate_json(prompt, validator=self._validate_rank_verdict)
        if "error" in result:
            return {"keep": True, "importance": "medium", "reason": "state_review_unavailable", "confidence": "fallback"}
        return result

    def _classify_relationship_change(self, change: Dict, scene_result: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("classify_relationship_change")
        client = self.client_factory(config)
        prompt = f"""
Task: validate and lightly normalize this relationship change for canon tracking.

Return JSON:
{{
  "keep": true,
  "relationship": "allies",
  "change": "trust increases",
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep only meaningful relationship shifts
- preserve the original meaning; do not invent a different event
- if the candidate is too weak or merely co-presence, set keep false
- relationship and change must stay short and grounded

Scene summary:
{scene_result.get("scene_summary", "")}

Relationship change candidate:
source_entity={change.get("source_entity", "")}
target_entity={change.get("target_entity", "")}
relationship={change.get("relationship", "")}
change={change.get("change", "")}
evidence={change.get("evidence", "")}

Scene:
{scene_text[:1800]}
"""
        result = client.generate_json(prompt, validator=self._validate_relationship_verdict)
        if "error" in result:
            return {
                "keep": True,
                "relationship": change.get("relationship", ""),
                "change": change.get("change", ""),
                "reason": "relationship_review_unavailable",
                "confidence": "fallback",
            }
        return result

    def _validate_rank_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("keep"), bool)
            and response.get("importance") in {"high", "medium", "low"}
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _validate_relationship_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("keep"), bool)
            and isinstance(response.get("relationship"), str)
            and isinstance(response.get("change"), str)
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _review_record(self, item: Dict, verdict: Dict) -> Dict:
        return {
            "item": deepcopy(item),
            "verdict": deepcopy(verdict),
        }
