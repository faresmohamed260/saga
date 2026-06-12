"""Dedicated visual/world-state extraction for image-generation continuity."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from analysis.visual_prompt_schema import (
    compile_character_edit_prompt,
    compile_character_turnaround_prompt,
    enrich_persistent_profile_from_legacy_fields,
    normalize_dynamic_visual_changes,
    normalize_persistent_profile,
    profile_specificity_score,
)
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
        - For character baseline prompts, focus on persistent traits only, not temporary injuries, dirt, blood, fear, tears, or single-scene outfit swaps.
        - Translate book-specific lore labels into model-understandable visual language. Example: "Illyrian warrior" should become "winged fantasy humanoid warrior" unless the text supplies better plain visual wording.
        - Build first-appearance character prompts as reusable neutral studio turnaround references for later image generation.
        - Track temporary visual changes separately as image-edit updates that preserve the base identity.
        - If a persistent baseline trait is uncertain, leave the field blank rather than guessing.
        - Treat character baseline extraction like building a production character sheet for image generation.
        - For baseline character appearance, actively seek only durable visual identity details:
          - sex/gender presentation if explicit
          - species/race translated into plain visual language
          - build and height impression
          - skin tone/texture
          - hair color/style/length
          - eye color
          - facial structure
          - approximate age impression
          - persistent clothing or signature attire only if clearly recurring or introductory
          - distinguishing marks, tattoos, scars, wings, ears, horns, or other stable fantasy anatomy
          - signature equipment only if it functions as a stable identifying item
        - Do NOT use scene staging as a baseline trait. Examples of forbidden baseline content:
          - where the character is standing or sitting
          - what room they are currently in
          - what they are looking at
          - action context like carrying a deer, entering a market, arguing, or watching someone
          - temporary emotional reaction unless it is a stable resting expression repeatedly described
        - If the text only gives temporary state and no durable physical description, keep the baseline sparse and move the temporary detail into dynamic_visual_changes instead.
        - Never fill baseline slots with placeholders like "not described", "eyes unseen", "unknown", or scene summaries.
        - Prefer a sparse but true character sheet over a rich but contaminated one.

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
              "persistent_visual_profile": {{
                "gender_presentation": "",
                "species_or_race": "",
                "role_or_archetype": "",
                "model_safe_identity": "",
                "presence_description": "",
                "height_description": "",
                "body_type": "",
                "skin_description": "",
                "hair_description": "",
                "eye_description": "",
                "facial_structure": "",
                "age_appearance": "",
                "expression": "",
                "clothing_description": "",
                "footwear_description": "",
                "accessories_description": "",
                "distinguishing_marks": "",
                "fantasy_features": "",
                "equipment_or_signature_items": "",
                "lore_terms": ["Illyrian"]
              }},
              "dynamic_visual_changes": [
                {{
                  "change_label": "",
                  "change_summary": "",
                  "outfit_change": "",
                  "visible_condition_change": "",
                  "body_language_change": "",
                  "fantasy_feature_change": "",
                  "equipment_change": "",
                  "scene_context": "",
                  "source_evidence": "",
                  "confidence": "high | medium | low"
                }}
              ],
              "persistent_visual_prompt": "",
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

        Extra character-baseline guidance:
        - When `visual_role` is `initial_character_description`, the baseline should read like a neutral reusable design sheet.
        - Good baseline examples:
          - "lean young man with shaggy brown hair and dark eyes"
          - "tall winged fantasy humanoid male with dark hair, violet eyes, and large dark feathered wings"
          - "young woman with pale skin, long brown hair, gray-blue eyes, and threadbare winter clothing"
        - Bad baseline examples:
          - "standing near the fire with a dead deer"
          - "watching her sister argue"
          - "eyes unseen in text"
          - "in a dim cottage"
        - Use `dynamic_visual_changes` for:
          - blood, bruises, exhaustion, dirt, tears
          - a one-scene outfit or armor variation
          - carrying a specific object in this moment
          - posture or facial expression tied to a scene beat
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
                "persistent_visual_profile": normalize_persistent_profile(row.get("persistent_visual_profile") or {}),
                "dynamic_visual_changes": normalize_dynamic_visual_changes(
                    row.get("dynamic_visual_changes") or [],
                    display_name=name,
                ),
                "persistent_visual_prompt": self._clean(row.get("persistent_visual_prompt")),
                "image_prompt": self._clean(row.get("image_prompt")),
                "image_edit_prompt": self._clean(row.get("image_edit_prompt")),
                "source_evidence": self._clean(row.get("source_evidence")),
                "confidence": self._confidence(row.get("confidence")),
            }
            values["persistent_visual_profile"] = enrich_persistent_profile_from_legacy_fields(
                values["persistent_visual_profile"],
                physical_description=values["physical_description"],
                outfit=values["outfit"],
                body_language=values["body_language"],
            )
            if role == "initial_character_description":
                existing_prompt = values["persistent_visual_prompt"]
                prompt_needs_rebuild = (
                    not existing_prompt
                    or "three-view layout" not in existing_prompt.lower()
                    or len(existing_prompt.split()) < 35
                )
                if prompt_needs_rebuild:
                    values["persistent_visual_prompt"] = compile_character_turnaround_prompt(
                        values["persistent_visual_profile"],
                        display_name=name,
                    )
                if not values["image_prompt"]:
                    values["image_prompt"] = values["persistent_visual_prompt"]
                if profile_specificity_score(values["persistent_visual_profile"]) <= 1:
                    values["confidence"] = "low"
            else:
                if not values["image_edit_prompt"] and values["dynamic_visual_changes"]:
                    values["image_edit_prompt"] = values["dynamic_visual_changes"][0].get("image_edit_prompt", "")
                if not values["image_edit_prompt"]:
                    values["image_edit_prompt"] = compile_character_edit_prompt(
                        display_name=name,
                        change={
                            "change_summary": self._join_nonempty(
                                [
                                    values["visible_condition"],
                                    values["outfit"],
                                    values["body_language"],
                                ]
                            ),
                            "outfit_change": values["outfit"],
                            "visible_condition_change": values["visible_condition"],
                            "body_language_change": values["body_language"],
                        },
                    )
            if not any(values[key] for key in ["physical_description", "outfit", "visible_condition", "body_language", "image_prompt", "image_edit_prompt", "persistent_visual_prompt"]) and not values["dynamic_visual_changes"]:
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

    def _join_nonempty(self, values: List[str]) -> str:
        return ", ".join(value for value in values if self._clean(value))
