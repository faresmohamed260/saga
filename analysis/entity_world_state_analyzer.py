"""Dedicated typed entity/world-state extraction for richer canonical analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from infrastructure.llm_client import LLMClient


class EntityWorldStateAnalyzer:
    """Extract typed entity state with first-appearance and change tracking."""

    AGENT_VERSION = "entity_world_state_analyzer_v1"
    GC_JSON_RESPONSE_FORMAT = {"type": "json_object"}
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    ENTITY_TYPES = {"character", "object", "location", "creature"}
    TYPED_ATTRIBUTE_KEYS = {
        "character": [
            "appearance",
            "outfit",
            "condition",
            "body_language",
            "possessions",
            "abilities",
            "titles_or_roles",
            "affiliations",
        ],
        "object": [
            "appearance",
            "materials",
            "abilities",
            "owner_or_holder",
            "current_state",
            "symbolic_role",
        ],
        "location": [
            "appearance",
            "atmosphere",
            "active_features",
            "damage_or_change",
            "occupants",
            "symbolic_role",
        ],
        "creature": [
            "appearance",
            "condition",
            "behavior",
            "abilities",
            "species_or_kind",
            "threat_role",
        ],
    }

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

        alias_context = [
            {"canonical_name": canonical, "aliases": aliases}
            for canonical, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]
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
            baseline_description = self._clean(row.get("baseline_description"))
            state_changes = self._normalize_state_changes(row.get("state_changes") or [])
            source_evidence = self._normalize_string_list(row.get("source_evidence") or [])
            if not baseline_description and not any(typed_attributes.values()) and not state_changes:
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
