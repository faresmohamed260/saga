"""Fallback local-model synthesis for missing scene artifacts."""

from __future__ import annotations

from typing import Dict, List, Optional

from saga.agents.microtasks.task_registry import MicroTaskRegistry
from saga.providers.local_semantic_client import LocalSemanticClient


class SceneFallbackSynthesizer:
    """Recover a small number of grounded scene events when the main analyzer misses them."""

    EVENT_TYPES = {"action", "interaction", "movement", "discovery"}

    def __init__(
        self,
        task_registry: Optional[MicroTaskRegistry] = None,
        client_factory=None,
        enabled: bool = True,
    ) -> None:
        self.task_registry = task_registry or MicroTaskRegistry()
        self.client_factory = client_factory or (lambda config: LocalSemanticClient(model=config.model, timeout=config.timeout))
        self.enabled = enabled

    def synthesize_events(self, scene_result: Dict, scene_text: str) -> List[Dict]:
        if not self.enabled:
            return []
        config = self.task_registry.get("extract_scene_events")
        client = self.client_factory(config)
        prompt = f"""
Task: extract at most 3 consequential canon events from this scene.

Return JSON:
{{
  "events": [
    {{
      "description": "short grounded event",
      "characters": ["Feyre"],
      "type": "action"
    }}
  ]
}}

Rules:
- only include consequential canon-relevant events
- do not include background atmosphere with no narrative movement
- allowed type values: action, interaction, movement, discovery
- keep descriptions concise and grounded in the scene
- use only character names clearly supported by the scene summary/text
- if no strong event exists, return an empty events list

Scene summary:
{scene_result.get("scene_summary", "")}

Canonical characters:
{[item.get("name") for item in scene_result.get("canonical_characters", [])]}

Scene:
{scene_text[:2200]}
"""
        result = client.generate_json(prompt, validator=self._validate_event_payload)
        if "error" in result:
            return []
        return self._normalize_events(result.get("events") or [])

    def _validate_event_payload(self, response: Dict) -> bool:
        return isinstance(response, dict) and isinstance(response.get("events"), list)

    def _normalize_events(self, events: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()
        for index, event in enumerate(events[:3], start=1):
            if not isinstance(event, dict):
                continue
            description = (event.get("description") or "").strip()
            event_type = (event.get("type") or "").strip().lower()
            characters = [
                str(item).strip()
                for item in (event.get("characters") or [])
                if str(item).strip()
            ]
            if not description:
                continue
            if event_type not in self.EVENT_TYPES:
                event_type = "action"
            key = (description.lower(), tuple(item.lower() for item in characters), event_type)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "event_id": f"fallback_evt_{index}",
                "description": description,
                "characters": characters,
                "type": event_type,
                "source": "local_fallback_synthesizer",
            })
        return normalized
