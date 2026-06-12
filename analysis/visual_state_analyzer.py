"""Dedicated visual/world-state extraction for image-generation continuity."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from infrastructure.llm_client import LLMClient


class VisualStateAnalyzer:
    """Extract visual continuity packets as a separate scene-analysis agent."""

    AGENT_VERSION = "visual_state_analyzer_v1"
    GC_JSON_RESPONSE_FORMAT = {"type": "json_object"}
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    CHARACTER_ROLES = {"initial_character_description", "character_change"}

    def __init__(self, llm_client: Optional[LLMClient] = None, max_attempts: int = 2):
        self.llm = llm_client or LLMClient()
        self.max_attempts = max(1, int(max_attempts))

    def analyze(
        self,
        scene: Dict[str, Any],
        *,
        alias_map: Optional[Dict[str, List[str]]] = None,
        scene_context: str = "",
        local_evidence: Optional[Dict[str, Any]] = None,
        analysis_mode: str = "structured",
    ) -> Dict[str, Any]:
        del analysis_mode
        last_response: Dict[str, Any] | None = None
        evidence_bundle = normalize_evidence_bundle(local_evidence)

        for attempt in range(1, self.max_attempts + 1):
            prompt = self._build_prompt(
                scene_text=str(scene.get("text") or ""),
                alias_map=alias_map or {},
                scene_context=scene_context,
                local_evidence=evidence_bundle,
                retry_hint=attempt > 1,
            )
            response = self._generate_visual_json(prompt, validator=self._validate_response)
            last_response = response
            if "error" not in response:
                normalized = self._normalize_response(response)
                normalized.update(
                    {
                        "book_index": scene.get("book_index"),
                        "chapter_index": scene.get("chapter_index"),
                        "scene_index": scene.get("scene_index"),
                        "visual_agent_version": self.AGENT_VERSION,
                    }
                )
                normalized.update(self._runtime_metadata(attempt_count=attempt, final_status="success"))
                return normalized

        error = last_response.get("error") if isinstance(last_response, dict) else "unknown_error"
        last_error = last_response.get("last_error") if isinstance(last_response, dict) else ""
        return {
            "book_index": scene.get("book_index"),
            "chapter_index": scene.get("chapter_index"),
            "scene_index": scene.get("scene_index"),
            "visual_agent_version": self.AGENT_VERSION,
            "characters": [],
            "objects": [],
            "creatures": [],
            "locations": [],
            "scene_compositions": [],
            "diagnostics": {
                "missing_visual_evidence": [],
                "rejected_visual_claims": [],
            },
            "error": error,
            "last_error": last_error,
            **self._runtime_metadata(
                attempt_count=self.max_attempts,
                final_status="failed",
                error=error,
                last_error=last_error,
            ),
        }

    def _generate_visual_json(self, prompt: str, *, validator) -> Dict[str, Any]:
        kwargs = {"strict": True, "validator": validator}
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            kwargs["response_format"] = self.GC_JSON_RESPONSE_FORMAT
        try:
            return self.llm.generate_json(prompt, **kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            return self.llm.generate_json(prompt, **kwargs)

    def _build_prompt(
        self,
        *,
        scene_text: str,
        alias_map: Dict[str, List[str]],
        scene_context: str,
        local_evidence: Dict[str, Any],
        retry_hint: bool,
    ) -> str:
        retry_line = ""
        if retry_hint:
            retry_line = "Your previous response failed validation. Return only valid JSON matching the schema.\n"

        alias_context = [
            {"canonical_name": canonical, "aliases": aliases}
            for canonical, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]
        return f"""
        You are the visual/world-state extraction agent for a canon encoder.
        Return only grounded visual continuity data for image generation.

        {retry_line}

        Hard rules:
        - Use only details explicitly supported by this scene text or the provided recent context.
        - Do not infer age, ethnicity, attractiveness, body shape, colors, props, outfits, injuries, or architecture unless stated.
        - Do not copy long book passages. Use short factual summaries and image-prompt phrasing.
        - Extract first-appearance visual descriptions when the scene introduces a character, creature, object, or location with concrete visible detail.
        - Extract character changes as image-edit prompts: clothing, armor, hair/face/body changes, tattoos/marks, injury, healing, exhaustion, magical transformations, masks, weapons carried.
        - Keep baseline character appearance separate from temporary scene-specific condition.
        - Extract object/artifact and creature visual descriptions plus state/ownership/location changes.
        - Extract location architecture, terrain, lighting, atmosphere, damage, crowding, weather, and spatial changes.
        - Scene composition prompts should describe how visible entities fit together in the moment, as if composing or editing images.
        - If a chapter-sized scene contains multiple visual beats, output multiple scene_compositions.
        - If evidence is weak, omit the claim or mark confidence low; never fill blanks with generic fantasy imagery.
        - If an entity has no usable visual detail, include it only in diagnostics.missing_visual_evidence, not as an empty prompt.

        Required JSON schema:
        {{
          "characters": [
            {{
              "entity_name": "Feyre",
              "visual_role": "initial_character_description | character_change",
              "physical_description": "",
              "outfit": "",
              "visible_condition": "",
              "body_language": "",
              "image_prompt": "",
              "image_edit_prompt": "",
              "source_evidence": "",
              "confidence": "high | medium | low"
            }}
          ],
          "objects": [
            {{
              "entity_name": "Ataraxia",
              "entity_type": "object",
              "visual_description": "",
              "state_or_ownership": "",
              "image_prompt": "",
              "image_edit_prompt": "",
              "source_evidence": "",
              "confidence": "high | medium | low"
            }}
          ],
          "creatures": [
            {{
              "entity_name": "Kelpie",
              "entity_type": "creature",
              "visual_description": "",
              "state_or_condition": "",
              "image_prompt": "",
              "image_edit_prompt": "",
              "source_evidence": "",
              "confidence": "high | medium | low"
            }}
          ],
          "locations": [
            {{
              "entity_name": "House of Wind",
              "entity_type": "location",
              "physical_description": "",
              "atmosphere": "",
              "state_change": "",
              "image_prompt": "",
              "image_edit_prompt": "",
              "source_evidence": "",
              "confidence": "high | medium | low"
            }}
          ],
          "scene_compositions": [
            {{
              "beat_title": "",
              "entities": ["Feyre"],
              "location": "",
              "scene_prompt": "",
              "image_edit_prompt": "",
              "source_evidence": "",
              "confidence": "high | medium | low"
            }}
          ],
          "diagnostics": {{
            "missing_visual_evidence": ["Entity name"],
            "rejected_visual_claims": ["Unsupported claim omitted"]
          }}
        }}

        Current alias map:
        {alias_context}

        Local evidence candidates:
        {local_evidence}

        Recent context:
        {scene_context or "No recent context."}

        Scene text:
        {scene_text}
        """

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("characters"), list)
            and isinstance(response.get("objects"), list)
            and isinstance(response.get("creatures"), list)
            and isinstance(response.get("locations"), list)
            and isinstance(response.get("scene_compositions"), list)
            and isinstance(response.get("diagnostics"), dict)
        )

    def _normalize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "characters": self._normalize_characters(response.get("characters") or []),
            "objects": self._normalize_entities(response.get("objects") or [], "object"),
            "creatures": self._normalize_entities(response.get("creatures") or [], "creature"),
            "locations": self._normalize_locations(response.get("locations") or []),
            "scene_compositions": self._normalize_scene_compositions(response.get("scene_compositions") or []),
            "diagnostics": self._normalize_diagnostics(response.get("diagnostics") or {}),
        }

    def _normalize_characters(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = self._clean(row.get("entity_name"))
            role = self._clean(row.get("visual_role")).lower()
            if not name:
                continue
            if role not in self.CHARACTER_ROLES:
                role = "character_change"
            values = {
                "entity_name": name,
                "visual_role": role,
                "physical_description": self._clean(row.get("physical_description")),
                "outfit": self._clean(row.get("outfit")),
                "visible_condition": self._clean(row.get("visible_condition")),
                "body_language": self._clean(row.get("body_language")),
                "image_prompt": self._clean(row.get("image_prompt")),
                "image_edit_prompt": self._clean(row.get("image_edit_prompt")),
                "source_evidence": self._clean(row.get("source_evidence")),
                "confidence": self._confidence(row.get("confidence")),
            }
            if not any(values[key] for key in ["physical_description", "outfit", "visible_condition", "body_language", "image_prompt", "image_edit_prompt"]):
                continue
            key = (values["entity_name"].lower(), values["visual_role"], values["source_evidence"].lower())
            if key in seen:
                continue
            seen.add(key)
            normalized.append(values)
        return normalized[:20]

    def _normalize_entities(self, rows: List[Dict[str, Any]], entity_type: str) -> List[Dict[str, Any]]:
        normalized = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = self._clean(row.get("entity_name"))
            if not name:
                continue
            values = {
                "entity_name": name,
                "entity_type": entity_type,
                "visual_description": self._clean(row.get("visual_description")),
                "state_or_ownership": self._clean(row.get("state_or_ownership") or row.get("state_or_condition")),
                "image_prompt": self._clean(row.get("image_prompt")),
                "image_edit_prompt": self._clean(row.get("image_edit_prompt")),
                "source_evidence": self._clean(row.get("source_evidence")),
                "confidence": self._confidence(row.get("confidence")),
            }
            if not any(values[key] for key in ["visual_description", "state_or_ownership", "image_prompt", "image_edit_prompt"]):
                continue
            key = (values["entity_name"].lower(), values["source_evidence"].lower())
            if key in seen:
                continue
            seen.add(key)
            normalized.append(values)
        return normalized[:20]

    def _normalize_locations(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = self._clean(row.get("entity_name"))
            if not name:
                continue
            values = {
                "entity_name": name,
                "entity_type": "location",
                "physical_description": self._clean(row.get("physical_description")),
                "atmosphere": self._clean(row.get("atmosphere")),
                "state_change": self._clean(row.get("state_change")),
                "image_prompt": self._clean(row.get("image_prompt")),
                "image_edit_prompt": self._clean(row.get("image_edit_prompt")),
                "source_evidence": self._clean(row.get("source_evidence")),
                "confidence": self._confidence(row.get("confidence")),
            }
            if not any(values[key] for key in ["physical_description", "atmosphere", "state_change", "image_prompt", "image_edit_prompt"]):
                continue
            key = (values["entity_name"].lower(), values["source_evidence"].lower())
            if key in seen:
                continue
            seen.add(key)
            normalized.append(values)
        return normalized[:12]

    def _normalize_scene_compositions(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for index, row in enumerate(rows[:12], start=1):
            if not isinstance(row, dict):
                continue
            scene_prompt = self._clean(row.get("scene_prompt"))
            edit_prompt = self._clean(row.get("image_edit_prompt"))
            if not scene_prompt and not edit_prompt:
                continue
            entities = row.get("entities") or []
            if not isinstance(entities, list):
                entities = []
            normalized.append(
                {
                    "beat_id": f"visual_beat_{index}",
                    "beat_title": self._clean(row.get("beat_title")) or f"Visual beat {index}",
                    "entities": [self._clean(item) for item in entities if self._clean(item)],
                    "location": self._clean(row.get("location")),
                    "scene_prompt": scene_prompt,
                    "image_edit_prompt": edit_prompt,
                    "source_evidence": self._clean(row.get("source_evidence")),
                    "confidence": self._confidence(row.get("confidence")),
                }
            )
        return normalized

    def _normalize_diagnostics(self, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        missing = diagnostics.get("missing_visual_evidence") or []
        rejected = diagnostics.get("rejected_visual_claims") or []
        return {
            "missing_visual_evidence": [self._clean(item) for item in missing if self._clean(item)][:30] if isinstance(missing, list) else [],
            "rejected_visual_claims": [self._clean(item) for item in rejected if self._clean(item)][:30] if isinstance(rejected, list) else [],
        }

    def _runtime_metadata(
        self,
        *,
        attempt_count: int,
        final_status: str,
        error: str = "",
        last_error: str = "",
    ) -> Dict[str, Any]:
        request_meta = self.llm.last_request_metadata() if hasattr(self.llm, "last_request_metadata") else {}
        provider = self.llm.provider_name() if hasattr(self.llm, "provider_name") else "test"
        model = self.llm.resolved_model_name() if hasattr(self.llm, "resolved_model_name") else str(getattr(self.llm, "mode", "test"))
        return {
            "provider": provider,
            "provider_family": request_meta.get("provider_family") or provider,
            "model": model,
            "resolved_model": request_meta.get("resolved_model") or model,
            "provider_account_alias": request_meta.get("provider_account_alias") or "",
            "rotation_used": bool(request_meta.get("rotation_used")),
            "rotation_attempt_count": int(request_meta.get("rotation_attempt_count") or 0),
            "fallback_used": bool(request_meta.get("fallback_used")),
            "attempt_count": int(attempt_count),
            "final_status": final_status,
            "error_category": LLMClient.classify_error(error, last_error),
            "last_error": last_error or "",
        }

    def _confidence(self, value: Any) -> str:
        cleaned = self._clean(value).lower()
        return cleaned if cleaned in self.CONFIDENCE_VALUES else "medium"

    def _clean(self, value: Any) -> str:
        cleaned = " ".join(str(value or "").strip().split())
        return cleaned[:700]
