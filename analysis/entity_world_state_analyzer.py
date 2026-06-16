"""Dedicated typed entity/world-state extraction for richer canonical analysis."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from analysis.evidence_schema import compact_evidence_bundle, normalize_evidence_bundle
from core.trait_taxonomy import (
    TYPED_ATTRIBUTE_KEYS as CANONICAL_TYPED_ATTRIBUTE_KEYS,
    practical_dynamic_fields,
    practical_persistent_fields,
)
from infrastructure.llm_client import LLMClient


class EntityWorldStateAnalyzer:
    """Extract typed entity state with first-appearance and change tracking."""

    AGENT_VERSION = "entity_world_state_analyzer_v1"
    GC_JSON_RESPONSE_FORMAT = {"type": "json_object"}
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    MAX_PROMPT_ALIAS_ROWS = 10
    MAX_PROMPT_CONTEXT_CHARS = 1000
    MAX_PROMPT_SCENE_TEXT_CHARS = 5200
    ENTITY_TYPES = {"character", "object", "location", "creature"}
    TYPED_ATTRIBUTE_KEYS = CANONICAL_TYPED_ATTRIBUTE_KEYS

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
            response = self._generate_json(prompt, validator=self._validate_response)
            last_response = response
            if "error" not in response:
                normalized = self._normalize_response(response, alias_map=alias_map or {})
                normalized.update(
                    {
                        "book_index": scene.get("book_index"),
                        "chapter_index": scene.get("chapter_index"),
                        "scene_index": scene.get("scene_index"),
                        "entity_world_state_agent_version": self.AGENT_VERSION,
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
            "entity_world_state_agent_version": self.AGENT_VERSION,
            "entities": [],
            "diagnostics": {
                "missing_baseline_entities": [],
                "unsupported_claims": [],
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

    def _generate_json(self, prompt: str, *, validator) -> Dict[str, Any]:
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

        compact_alias_map = self._compact_alias_map(alias_map, scene_text)
        alias_context = [
            {"canonical_name": canonical, "aliases": aliases}
            for canonical, aliases in sorted(compact_alias_map.items(), key=lambda item: item[0].lower())
        ]
        compact_local_evidence = compact_evidence_bundle(local_evidence)
        compact_scene_context = self._compact_scene_context(scene_context)
        prompt_scene_text = self._compact_scene_text(scene_text)
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            return f"""
            Typed entity/world-state task. Return strict JSON only.

            {retry_line}

            Rules:
            - Extract consequential characters, objects, locations, and creatures only.
            - Ground every claim in scene text or recent context.
            - Baseline description = durable first-appearance physical/world detail.
            - Temporary conditions, injuries, outfits, ownership shifts, and environment changes go in state_changes or typed attributes, not baseline.
            - Do not invent colors, materials, powers, or motives.
            - If an entity matters but detail is sparse, include what is supported and omit the rest.
            - Fill practical structured fields only when the prose supports them. Leave unsupported fields blank.

            Output schema:
            {{
              "entities": [
                {{
                  "entity_name": "",
                  "entity_type": "character|object|location|creature",
                  "narrative_role": "",
                  "baseline_description": "",
                  "baseline_source": "",
                  "persistent_traits": {{"field_name": ""}},
                  "dynamic_visual_state": {{"field_name": ""}},
                  "typed_attributes": {{
                    "appearance": [], "outfit": [], "condition": [], "body_language": [],
                    "possessions": [], "abilities": [], "titles_or_roles": [], "affiliations": []
                  }},
                  "state_changes": [{{"attribute": "", "previous_state": "", "new_state": "", "change_type": "", "evidence": ""}}],
                  "source_evidence": [],
                  "confidence": "high|medium|low"
                }}
              ],
              "diagnostics": {{"missing_baseline_entities": [""], "unsupported_claims": [""]}}
            }}

            Alias map:
            {json.dumps(alias_context, ensure_ascii=False)}

            Local evidence:
            {json.dumps(compact_local_evidence, ensure_ascii=False)}

            Recent context:
            {compact_scene_context or "No recent context."}

            Scene:
            {prompt_scene_text}
            """

        return f"""
        You are the typed entity/world-state extraction agent for a canon encoder.
        Return only grounded JSON. This output becomes canonical contract data.

        {retry_line}

        Core mission:
        - Extract all consequential characters, objects, locations, and creatures that have usable scene evidence.
        - Capture baseline visual/world details when an entity receives its first meaningful physical introduction in the book.
        - Capture temporary changes when appearance, outfit, condition, ownership, damage, or environment changes during the story.
        - Prefer specific book-grounded detail over generic fantasy filler.
        - For characters, think in terms of a reusable visual reference sheet for later image generation, but stay strictly grounded in the text.
        - Use practical structured fields only for traits that prose can usually support reliably.

        Hard rules:
        - Use only supported evidence from the scene text and recent context.
        - Do not invent colors, body features, materials, magic systems, ranks, or motives.
        - Do not dump raw quotes. Summarize grounded evidence into concise factual phrases.
        - If a field lacks evidence, leave it out of the relevant list instead of hallucinating.
        - If an entity matters in the scene, include it even if only some typed fields are populated.
        - Baseline description means a durable first-appearance physical/world description, not a temporary mood or pose.
        - For character baseline description, actively seek durable visual identity details such as build, age impression, face, hair, skin, height impression, bearing, notable markings, wings, armor, or signature attire when the text actually supports them.
        - Do not mistake temporary scene conditions for baseline appearance. Hunger, blood, mud, shaking, cold, tears, battle damage, and exhaustion belong in temporary condition unless the text makes them durable traits.
        - Prefer complete first-appearance physical summaries over fragments. A good baseline description should read like a compact portrait, not a loose evidence dump.
        - Temporary conditions include injuries, exhaustion, blood, dirt, weather exposure, masks worn, armor worn, and similar scene-bound states.
        - Objects in fantasy may have abilities, curses, ownership, symbolic role, or current activation state.
        - Locations may have architecture, atmosphere, active magical or environmental features, damage, and current occupants.
        - Locations can be indoor or outdoor; capture that explicitly when the text supports it.
        - Creatures may have species/kind, threatening role, visible anatomy, condition, and active behavior.
        - Every state change must describe what changed and the evidence.

        Required JSON schema:
        {{
          "entities": [
            {{
              "entity_name": "Feyre",
              "entity_type": "character | object | location | creature",
              "narrative_role": "",
              "baseline_description": "",
              "baseline_source": "",
              "persistent_traits": {{"field_name": ""}},
              "dynamic_visual_state": {{"field_name": ""}},
              "typed_attributes": {{
                "appearance": [],
                "outfit": [],
                "condition": [],
                "body_language": [],
                "possessions": [],
                "abilities": [],
                "titles_or_roles": [],
                "affiliations": []
              }},
              "state_changes": [
                {{
                  "attribute": "",
                  "previous_state": "",
                  "new_state": "",
                  "change_type": "",
                  "evidence": ""
                }}
              ],
              "source_evidence": [],
              "confidence": "high | medium | low"
            }}
          ],
          "diagnostics": {{
            "missing_baseline_entities": ["Entity name"],
            "unsupported_claims": ["Unsupported claim omitted"]
          }}
        }}

        Alias map:
        {json.dumps(alias_context, ensure_ascii=False)}

        Local evidence candidates:
        {json.dumps(compact_local_evidence, ensure_ascii=False)}

        Recent context:
        {compact_scene_context or "No recent context."}

        Scene text:
        {prompt_scene_text}
        """

    def _compact_alias_map(self, alias_map: Dict[str, List[str]], scene_text: str) -> Dict[str, List[str]]:
        scene_lower = str(scene_text or "").lower()
        prioritized: list[tuple[str, List[str], int]] = []
        for canonical_name, aliases in sorted((alias_map or {}).items(), key=lambda item: item[0].lower()):
            alias_list = [str(alias).strip()[:80] for alias in (aliases or []) if str(alias).strip()]
            relevance = 1 if canonical_name.lower() in scene_lower else 0
            relevance += sum(1 for alias in alias_list if alias.lower() in scene_lower)
            prioritized.append((canonical_name[:80], alias_list[:6], relevance))
        prioritized.sort(key=lambda item: (-item[2], item[0].lower()))
        compacted: Dict[str, List[str]] = {}
        for canonical_name, aliases, _ in prioritized[: self.MAX_PROMPT_ALIAS_ROWS]:
            compacted[canonical_name] = aliases
        return compacted

    def _compact_scene_context(self, scene_context: str) -> str:
        cleaned = " ".join(str(scene_context or "").split())
        if len(cleaned) <= self.MAX_PROMPT_CONTEXT_CHARS:
            return cleaned
        return cleaned[: self.MAX_PROMPT_CONTEXT_CHARS].rsplit(" ", 1)[0] + " ..."

    def _compact_scene_text(self, scene_text: str) -> str:
        cleaned = str(scene_text or "").strip()
        if len(cleaned) <= self.MAX_PROMPT_SCENE_TEXT_CHARS:
            return cleaned
        segment = max(1100, self.MAX_PROMPT_SCENE_TEXT_CHARS // 3)
        middle_start = max(0, (len(cleaned) // 2) - (segment // 2))
        middle_end = middle_start + segment
        parts = [
            cleaned[:segment].rstrip(),
            cleaned[middle_start:middle_end].strip(),
            cleaned[-segment:].lstrip(),
        ]
        return "\n...\n".join(part for part in parts if part)

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("entities"), list)
            and isinstance(response.get("diagnostics"), dict)
        )

    def _normalize_response(self, response: Dict[str, Any], *, alias_map: Dict[str, List[str]]) -> Dict[str, Any]:
        return {
            "entities": self._normalize_entities(response.get("entities") or [], alias_map=alias_map),
            "diagnostics": self._normalize_diagnostics(response.get("diagnostics") or {}),
        }

    def _normalize_entities(self, rows: List[Dict[str, Any]], *, alias_map: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen = set()
        for row in rows[:40]:
            if not isinstance(row, dict):
                continue
            name = self._clean(row.get("entity_name"))
            entity_type = self._clean(row.get("entity_type")).lower()
            if not name or entity_type not in self.ENTITY_TYPES:
                continue
            if entity_type == "character":
                name = self._canonicalize_character_name(name, alias_map)
                if not name:
                    continue
            typed_attributes = self._normalize_typed_attributes(entity_type, row.get("typed_attributes") or {})
            persistent_traits = self._normalize_practical_traits(entity_type, row.get("persistent_traits") or {}, scope="persistent")
            dynamic_visual_state = self._normalize_practical_traits(entity_type, row.get("dynamic_visual_state") or {}, scope="dynamic")
            baseline_description = self._clean(row.get("baseline_description"))
            state_changes = self._normalize_state_changes(row.get("state_changes") or [])
            source_evidence = self._normalize_string_list(row.get("source_evidence") or [])
            typed_attributes = self._backfill_typed_attributes(
                entity_type=entity_type,
                typed_attributes=typed_attributes,
                persistent_traits=persistent_traits,
                dynamic_visual_state=dynamic_visual_state,
            )
            if not baseline_description and not any(typed_attributes.values()) and not state_changes and not any(persistent_traits.values()) and not any(dynamic_visual_state.values()):
                continue
            key = (
                name.lower(),
                entity_type,
                baseline_description.lower(),
                "|".join(source_evidence).lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "entity_name": name,
                    "entity_type": entity_type,
                    "narrative_role": self._clean(row.get("narrative_role")),
                    "baseline_description": baseline_description,
                    "baseline_source": self._clean(row.get("baseline_source")),
                    "persistent_traits": persistent_traits,
                    "dynamic_visual_state": dynamic_visual_state,
                    "typed_attributes": typed_attributes,
                    "state_changes": state_changes,
                    "source_evidence": source_evidence,
                    "confidence": self._confidence(row.get("confidence")),
                }
            )
        return normalized

    def _canonicalize_character_name(self, name: str, alias_map: Dict[str, List[str]]) -> str:
        cleaned = self._clean(name)
        if not cleaned:
            return ""
        normalized = self._normalize_key(cleaned)
        article_free = self._article_insensitive_key(cleaned)
        candidates: List[tuple[str, str]] = []
        for canonical_name, aliases in sorted((alias_map or {}).items(), key=lambda item: item[0].lower()):
            known_names = [canonical_name, *(aliases or [])]
            for known_name in known_names:
                if self._normalize_key(known_name) == normalized:
                    return canonical_name
                if self._article_insensitive_key(known_name) == article_free:
                    return canonical_name
                candidates.append((canonical_name, known_name))
        if " " not in normalized and len(normalized) >= 4:
            matches = set()
            for canonical_name, known_name in candidates:
                known_key = self._normalize_key(known_name)
                if " " in known_key:
                    short, long_name = sorted([normalized, known_key], key=len)
                    if len(long_name) - len(short) >= 2 and long_name.startswith(short):
                        matches.add(canonical_name)
            if len(matches) == 1:
                return next(iter(matches))
        return cleaned

    def _normalize_key(self, value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _article_insensitive_key(self, value: str) -> str:
        normalized = self._normalize_key(value)
        for prefix in ("the ", "a ", "an "):
            if normalized.startswith(prefix):
                return normalized[len(prefix):]
        return normalized

    def _normalize_typed_attributes(self, entity_type: str, raw: Dict[str, Any]) -> Dict[str, List[str]]:
        allowed_keys = self.TYPED_ATTRIBUTE_KEYS[entity_type]
        normalized: Dict[str, List[str]] = {}
        if not isinstance(raw, dict):
            return {key: [] for key in allowed_keys}
        for key in allowed_keys:
            normalized[key] = self._normalize_string_list(raw.get(key) or [])
        return normalized

    def _normalize_practical_traits(self, entity_type: str, raw: Dict[str, Any], *, scope: str) -> Dict[str, str]:
        allowed_fields = practical_persistent_fields(entity_type) if scope == "persistent" else practical_dynamic_fields(entity_type)
        normalized: Dict[str, str] = {}
        if not isinstance(raw, dict):
            return {field: "" for field in allowed_fields}
        for field in allowed_fields:
            normalized[field] = self._clean(raw.get(field))
        return normalized

    def _backfill_typed_attributes(
        self,
        *,
        entity_type: str,
        typed_attributes: Dict[str, List[str]],
        persistent_traits: Dict[str, str],
        dynamic_visual_state: Dict[str, str],
    ) -> Dict[str, List[str]]:
        merged = {key: list(values or []) for key, values in typed_attributes.items()}

        def _append(bucket: str, value: str) -> None:
            cleaned = self._clean(value)
            if not cleaned:
                return
            slot = merged.setdefault(bucket, [])
            if cleaned not in slot:
                slot.append(cleaned)

        if entity_type == "character":
            for field in [
                "height_impression", "build", "skin_tone_or_complexion", "hair_color",
                "hair_length_or_style", "eye_color", "facial_features", "distinguishing_marks",
                "fantasy_features",
            ]:
                _append("appearance", persistent_traits.get(field, ""))
            for field in ["default_clothing_style", "default_accessories", "default_footwear"]:
                _append("outfit", persistent_traits.get(field, ""))
            for field in ["scene_outfit", "scene_accessories", "scene_footwear"]:
                _append("outfit", dynamic_visual_state.get(field, ""))
            for field in ["visible_condition", "injuries", "dirt_blood_markings"]:
                _append("condition", dynamic_visual_state.get(field, ""))
            for field in ["body_language", "expression"]:
                _append("body_language", dynamic_visual_state.get(field, ""))
            _append("possessions", persistent_traits.get("signature_items", ""))
            _append("possessions", dynamic_visual_state.get("carried_items", ""))
            for field in ["species_or_race", "apparent_age_group", "world_genre_cues"]:
                _append("affiliations", persistent_traits.get(field, ""))
        elif entity_type == "creature":
            for field in ["size_class", "body_plan", "surface_covering", "coloration", "head_features", "eyes", "natural_weapons", "wings", "tail", "magical_features"]:
                _append("appearance", persistent_traits.get(field, ""))
            for field in ["visible_condition", "injuries", "behavior_state", "threat_posture"]:
                _append("condition", dynamic_visual_state.get(field, ""))
            _append("species_or_kind", persistent_traits.get("species_kind", ""))
        elif entity_type == "object":
            for field in ["shape_form", "size_scale", "color_finish", "surface_texture", "condition_default"]:
                _append("appearance", persistent_traits.get(field, ""))
            for field in ["primary_material", "secondary_materials"]:
                _append("materials", persistent_traits.get(field, ""))
            _append("owner_or_holder", dynamic_visual_state.get("owner_or_holder", ""))
            for field in ["activation_state", "damage_state", "location_context"]:
                _append("current_state", dynamic_visual_state.get(field, ""))
            _append("abilities", persistent_traits.get("magical_properties", ""))
            _append("symbolic_role", persistent_traits.get("symbolic_markings", ""))
        elif entity_type == "location":
            for field in ["location_class", "indoor_outdoor", "environment_type", "architecture_or_terrain_style", "dominant_materials", "lighting_default", "weather_exposure", "notable_features", "magic_or_tech_presence"]:
                _append("appearance", persistent_traits.get(field, ""))
            _append("atmosphere", persistent_traits.get("ambient_mood", ""))
            for field in ["lighting_current", "weather_current", "occupancy_state", "atmosphere_shift"]:
                _append("atmosphere", dynamic_visual_state.get(field, ""))
            for field in ["damage_state", "temporary_setup"]:
                _append("damage_or_change", dynamic_visual_state.get(field, ""))
            _append("active_features", dynamic_visual_state.get("active_effects", ""))
        return merged

    def _normalize_state_changes(self, rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalized = []
        for row in rows[:20]:
            if not isinstance(row, dict):
                continue
            attribute = self._clean(row.get("attribute"))
            new_state = self._clean(row.get("new_state"))
            evidence = self._clean(row.get("evidence"))
            if not attribute or not new_state or not evidence:
                continue
            normalized.append(
                {
                    "attribute": attribute,
                    "previous_state": self._clean(row.get("previous_state")),
                    "new_state": new_state,
                    "change_type": self._clean(row.get("change_type")) or "state_update",
                    "evidence": evidence,
                }
            )
        return normalized

    def _normalize_diagnostics(self, diagnostics: Dict[str, Any]) -> Dict[str, List[str]]:
        missing = diagnostics.get("missing_baseline_entities") or []
        rejected = diagnostics.get("unsupported_claims") or []
        return {
            "missing_baseline_entities": self._normalize_string_list(missing)[:40] if isinstance(missing, list) else [],
            "unsupported_claims": self._normalize_string_list(rejected)[:40] if isinstance(rejected, list) else [],
        }

    def _normalize_string_list(self, values: List[Any]) -> List[str]:
        output = []
        seen = set()
        for value in values:
            cleaned = self._clean(value)
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            output.append(cleaned)
        return output

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
        return " ".join(str(value or "").strip().split())[:700]
