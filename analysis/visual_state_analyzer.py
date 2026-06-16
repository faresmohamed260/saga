"""Dedicated visual/world-state extraction for image-generation continuity."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from analysis.evidence_schema import compact_evidence_bundle, normalize_evidence_bundle
from analysis.visual_prompt_schema import (
    compile_character_edit_prompt,
    compile_character_turnaround_prompt,
    enrich_persistent_profile_from_legacy_fields,
    normalize_dynamic_visual_changes,
    normalize_persistent_profile,
    promote_persistent_profile_from_visual_changes,
    profile_specificity_score,
)
from infrastructure.llm_client import LLMClient


logger = logging.getLogger(__name__)


class VisualStateAnalyzer:
    """Extract visual continuity packets as a separate scene-analysis agent."""

    AGENT_VERSION = "visual_state_analyzer_v2"
    GC_JSON_RESPONSE_FORMAT = {"type": "json_object"}
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    MAX_PROMPT_ALIAS_ROWS = 10
    MAX_PROMPT_CONTEXT_CHARS = 1000
    MAX_PROMPT_SCENE_TEXT_CHARS = 5200
    CHARACTER_ROLES = {"initial_character_description", "character_change"}
    CREATURE_MARKERS = {
        "attor", "creature", "monster", "beast", "animal", "wolf", "kelpie", "naga", "suriel", "bogge",
        "fangs", "talons", "claws", "clawed", "snout", "muzzle", "scaled", "scales", "fur", "hide", "bat-like",
        "leathery", "predatory", "skeletal", "wings and talons",
    }
    HUMANOID_MARKERS = {
        "human", "humanoid", "woman", "man", "male", "female", "person", "warrior", "lord", "lady",
        "noble", "priestess", "servant", "attendant", "hunter", "fighter", "soldier", "high fae", "fae",
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
        evidence_bundle = normalize_evidence_bundle(local_evidence)
        scene_ref = (
            f"b{scene.get('book_index', '?')}:"
            f"c{scene.get('chapter_index', '?')}:"
            f"s{scene.get('scene_index', '?')}"
        )
        logger.info(
            "VisualStateAnalyzer start | scene=%s mode=%s text_chars=%s alias_count=%s",
            scene_ref,
            getattr(self.llm, "mode", "unknown"),
            len(str(scene.get("text") or "")),
            len(alias_map or {}),
        )
        baseline_response, baseline_attempts = self._run_baseline_pass(
            scene_text=str(scene.get("text") or ""),
            alias_map=alias_map or {},
            scene_context=scene_context,
            local_evidence=evidence_bundle,
        )
        if "error" in baseline_response:
            error = baseline_response.get("error") if isinstance(baseline_response, dict) else "unknown_error"
            last_error = baseline_response.get("last_error") if isinstance(baseline_response, dict) else ""
            logger.error(
                "VisualStateAnalyzer baseline failed | scene=%s attempts=%s error=%s last_error=%s",
                scene_ref,
                baseline_attempts,
                error,
                last_error,
            )
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
                    attempt_count=baseline_attempts,
                    final_status="failed",
                    error=error,
                    last_error=last_error,
                ),
            }

        dynamic_response, dynamic_attempts = self._run_dynamic_pass(
            scene_text=str(scene.get("text") or ""),
            alias_map=alias_map or {},
            scene_context=scene_context,
            local_evidence=evidence_bundle,
        )
        if "error" in dynamic_response:
            error = dynamic_response.get("error") if isinstance(dynamic_response, dict) else "unknown_error"
            last_error = dynamic_response.get("last_error") if isinstance(dynamic_response, dict) else ""
            logger.error(
                "VisualStateAnalyzer dynamic failed | scene=%s attempts=%s error=%s last_error=%s",
                scene_ref,
                dynamic_attempts,
                error,
                last_error,
            )
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
                    attempt_count=baseline_attempts + dynamic_attempts,
                    final_status="failed",
                    error=error,
                    last_error=last_error,
                ),
            }

        merged = self._merge_pass_responses(baseline_response, dynamic_response)
        normalized = self._normalize_response(merged)
        normalized.update(
            {
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
                "visual_agent_version": self.AGENT_VERSION,
            }
        )
        normalized.update(
            self._runtime_metadata(
                attempt_count=baseline_attempts + dynamic_attempts,
                final_status="success",
            )
        )
        logger.info(
            "VisualStateAnalyzer success | scene=%s baseline_attempts=%s dynamic_attempts=%s characters=%s creatures=%s objects=%s locations=%s",
            scene_ref,
            baseline_attempts,
            dynamic_attempts,
            len(normalized.get("characters") or []),
            len(normalized.get("creatures") or []),
            len(normalized.get("objects") or []),
            len(normalized.get("locations") or []),
        )
        return normalized

    def _run_baseline_pass(
        self,
        *,
        scene_text: str,
        alias_map: Dict[str, List[str]],
        scene_context: str,
        local_evidence: Dict[str, Any],
    ) -> tuple[Dict[str, Any], int]:
        last_response: Dict[str, Any] | None = None
        for attempt in range(1, self.max_attempts + 1):
            logger.info("VisualStateAnalyzer baseline attempt | attempt=%s/%s", attempt, self.max_attempts)
            prompt = self._build_baseline_prompt(
                scene_text=scene_text,
                alias_map=alias_map,
                scene_context=scene_context,
                local_evidence=local_evidence,
                retry_hint=attempt > 1,
            )
            response = self._generate_visual_json(prompt, validator=self._validate_baseline_response)
            last_response = response
            if "error" not in response:
                return response, attempt
            logger.warning(
                "VisualStateAnalyzer baseline retry | attempt=%s error=%s last_error=%s",
                attempt,
                response.get("error") if isinstance(response, dict) else "unknown_error",
                response.get("last_error") if isinstance(response, dict) else "",
            )
        error = last_response.get("error") if isinstance(last_response, dict) else "unknown_error"
        last_error = last_response.get("last_error") if isinstance(last_response, dict) else ""
        return {"error": error, "last_error": last_error}, self.max_attempts

    def _run_dynamic_pass(
        self,
        *,
        scene_text: str,
        alias_map: Dict[str, List[str]],
        scene_context: str,
        local_evidence: Dict[str, Any],
    ) -> tuple[Dict[str, Any], int]:
        last_response: Dict[str, Any] | None = None
        for attempt in range(1, self.max_attempts + 1):
            logger.info("VisualStateAnalyzer dynamic attempt | attempt=%s/%s", attempt, self.max_attempts)
            prompt = self._build_dynamic_prompt(
                scene_text=scene_text,
                alias_map=alias_map,
                scene_context=scene_context,
                local_evidence=local_evidence,
                retry_hint=attempt > 1,
            )
            response = self._generate_visual_json(prompt, validator=self._validate_dynamic_response)
            last_response = response
            if "error" not in response:
                return response, attempt
            logger.warning(
                "VisualStateAnalyzer dynamic retry | attempt=%s error=%s last_error=%s",
                attempt,
                response.get("error") if isinstance(response, dict) else "unknown_error",
                response.get("last_error") if isinstance(response, dict) else "",
            )
        error = last_response.get("error") if isinstance(last_response, dict) else "unknown_error"
        last_error = last_response.get("last_error") if isinstance(last_response, dict) else ""
        return {
            "error": error,
            "last_error": last_error,
        }, self.max_attempts

    def _generate_visual_json(self, prompt: str, *, validator) -> Dict[str, Any]:
        kwargs = {"strict": True, "validator": validator}
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            kwargs["response_format"] = self.GC_JSON_RESPONSE_FORMAT
        try:
            return self.llm.generate_json(prompt, **kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            return self.llm.generate_json(prompt, **kwargs)

    def _build_baseline_prompt(
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
        compact_scene_context = self._compact_scene_context(scene_context)
        compact_local_evidence = compact_evidence_bundle(local_evidence)
        prompt_scene_text = self._compact_scene_text(scene_text)
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            return f"""
            Visual baseline extraction for image generation. Return strict JSON only.

            {retry_line}

            Rules:
            - Use only scene text plus recent context.
            - Extract baseline visuals only. Do not include temporary movement, action staging, scene behavior, or injuries as baseline.
            - Baseline character sheets should seek face, hair, eyes, build, clothing silhouette/materials, footwear, and class/era/world aesthetic cues when supported.
            - Translate lore-only labels into plain visual language a model can render.
            - Omit unsupported details rather than filling blanks with generic fantasy.
            - If an entity lacks usable baseline visual evidence, put it in diagnostics instead of creating an empty prompt.

            Required JSON schema:
            {{
              "characters": [
                {{
                  "entity_name": "",
                  "visual_role": "initial_character_description",
                  "physical_description": "",
                  "outfit": "",
                  "persistent_visual_profile": {{
                    "gender_presentation": "", "species_or_race": "", "role_or_archetype": "", "model_safe_identity": "",
                    "world_aesthetic_cues": "", "presence_description": "", "height_description": "", "body_type": "",
                    "skin_description": "", "hair_description": "", "eye_description": "", "facial_structure": "",
                    "age_appearance": "", "expression": "", "clothing_description": "", "footwear_description": "",
                    "accessories_description": "", "distinguishing_marks": "", "fantasy_features": "",
                    "equipment_or_signature_items": "", "lore_terms": [""]
                  }},
                  "persistent_visual_prompt": "",
                  "image_prompt": "",
                  "source_evidence": "",
                  "confidence": "high|medium|low"
                }}
              ],
              "objects": [{{"entity_name": "", "entity_type": "object", "visual_description": "", "state_or_ownership": "", "image_prompt": "", "image_edit_prompt": "", "source_evidence": "", "confidence": "high|medium|low"}}],
              "creatures": [{{"entity_name": "", "entity_type": "creature", "visual_description": "", "state_or_condition": "", "image_prompt": "", "image_edit_prompt": "", "source_evidence": "", "confidence": "high|medium|low"}}],
              "locations": [{{"entity_name": "", "entity_type": "location", "physical_description": "", "atmosphere": "", "state_change": "", "image_prompt": "", "image_edit_prompt": "", "source_evidence": "", "confidence": "high|medium|low"}}],
              "diagnostics": {{"missing_visual_evidence": [""], "rejected_visual_claims": [""]}}
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
        You are the baseline visual extraction agent for a canon encoder.
        Return only grounded baseline continuity data for image generation.

        {retry_line}

        Hard rules:
        - Use only details explicitly supported by this scene text or the provided recent context.
        - Do not infer age, ethnicity, attractiveness, body shape, colors, props, outfits, injuries, or architecture unless stated.
        - Do not copy long book passages. Use short factual summaries and image-prompt phrasing.
        - Extract first-appearance visual descriptions only when the scene introduces a character, creature, object, or location with concrete visible detail.
        - Do not output character changes or scene compositions in this pass.
        - Keep baseline character appearance separate from temporary scene-specific condition, body language, action, and staging.
        - Extract object/artifact and creature visual descriptions plus state/ownership/location changes.
        - Extract location architecture, terrain, lighting, atmosphere, damage, crowding, weather, and spatial changes.
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
          - class, era, and world-material cues that affect how clothing and design should read on screen
          - build and height impression
          - skin tone/texture
          - hair color/style/length
          - eye color
          - facial structure
          - approximate age impression
          - first-appearance clothing silhouette, layer structure, and visible materials when the text gives them
          - footwear when visible or explicitly described
          - persistent clothing or signature attire only if clearly recurring or introductory
          - distinguishing marks, tattoos, scars, wings, ears, horns, or other stable fantasy anatomy
          - signature equipment only if it functions as a stable identifying item
        - For initial character descriptions, explicitly try to fill these baseline slots whenever the text supports them:
          - facial structure
          - hair
          - eyes
          - build
          - clothing silhouette and materials
          - footwear
          - class/era/world aesthetic cues
        - Do NOT use scene staging as a baseline trait. Examples of forbidden baseline content:
          - where the character is standing or sitting
          - what room they are currently in
          - what they are looking at
          - action context like carrying a deer, entering a market, arguing, or watching someone
          - temporary emotional reaction unless it is a stable resting expression repeatedly described
        - Do NOT include current action in `physical_description`. Action belongs in the separate dynamic pass.
        - Do NOT include temporary body language or temporary mood in `physical_description`.
        - If the text only gives temporary state and no durable physical description, keep the baseline sparse and move the temporary detail into dynamic_visual_changes instead.
        - Never fill baseline slots with placeholders like "not described", "eyes unseen", "unknown", or scene summaries.
        - Prefer a sparse but true character sheet over a rich but contaminated one.

        Required JSON schema:
        {{
          "characters": [
            {{
              "entity_name": "Feyre",
              "visual_role": "initial_character_description",
              "physical_description": "",
              "outfit": "",
              "persistent_visual_profile": {{
                "gender_presentation": "",
                "species_or_race": "",
                "role_or_archetype": "",
                "model_safe_identity": "",
                "world_aesthetic_cues": "",
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
              "persistent_visual_prompt": "",
              "image_prompt": "",
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
          "diagnostics": {{
            "missing_visual_evidence": ["Entity name"],
            "rejected_visual_claims": ["Unsupported claim omitted"]
          }}
        }}

        Current alias map:
        {json.dumps(alias_context, ensure_ascii=False)}

        Local evidence candidates:
        {json.dumps(compact_local_evidence, ensure_ascii=False)}

        Recent context:
        {compact_scene_context or "No recent context."}

        Scene text:
        {prompt_scene_text}

        Extra character-baseline guidance:
        - When `visual_role` is `initial_character_description`, the baseline should read like a neutral reusable design sheet.
        - Good baseline examples:
          - "lean young man with shaggy brown hair and dark eyes"
          - "tall winged fantasy humanoid male with dark hair, violet eyes, and large dark feathered wings"
          - "young woman with pale skin, long brown hair, gray-blue eyes, and threadbare winter clothing made from rough natural layers"
        - Bad baseline examples:
          - "standing near the fire with a dead deer"
          - "watching her sister argue"
          - "eyes unseen in text"
          - "in a dim cottage"
        """

    def _build_dynamic_prompt(
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
        compact_scene_context = self._compact_scene_context(scene_context)
        compact_local_evidence = compact_evidence_bundle(local_evidence)
        prompt_scene_text = self._compact_scene_text(scene_text)
        return f"""
        You are the dynamic visual change and scene-composition extraction agent for a canon encoder.
        Return only grounded scene-bound visual change data for image generation.

        {retry_line}

        Hard rules:
        - This pass captures temporary visual changes and scene compositions only.
        - Do not restate the baseline character sheet unless the scene changes that baseline in a visible way.
        - Use character_change rows for injuries, exhaustion, blood, dirt, tears, armor worn, mask worn, weapon carried, magical transformation, posture, and expression tied to this specific beat.
        - Use scene_compositions for discrete visual beats inside the chapter-sized scene. If there are multiple distinct visual beats, emit multiple rows.
        - Keep claims grounded in visible evidence from the scene text and recent context.
        - Omit unsupported details instead of improvising.

        Required JSON schema:
        {{
          "characters": [
            {{
              "entity_name": "Feyre",
              "visual_role": "character_change",
              "outfit": "",
              "visible_condition": "",
              "body_language": "",
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
        {json.dumps(alias_context, ensure_ascii=False)}

        Local evidence candidates:
        {json.dumps(compact_local_evidence, ensure_ascii=False)}

        Recent context:
        {compact_scene_context or "No recent context."}

        Scene text:
        {prompt_scene_text}
        """

    def _merge_pass_responses(self, baseline_response: Dict[str, Any], dynamic_response: Dict[str, Any]) -> Dict[str, Any]:
        baseline_diag = baseline_response.get("diagnostics") or {}
        dynamic_diag = dynamic_response.get("diagnostics") or {}
        return {
            "characters": (baseline_response.get("characters") or []) + (dynamic_response.get("characters") or []),
            "objects": baseline_response.get("objects") or [],
            "creatures": baseline_response.get("creatures") or [],
            "locations": baseline_response.get("locations") or [],
            "scene_compositions": dynamic_response.get("scene_compositions") or [],
            "diagnostics": {
                "missing_visual_evidence": (baseline_diag.get("missing_visual_evidence") or []) + (dynamic_diag.get("missing_visual_evidence") or []),
                "rejected_visual_claims": (baseline_diag.get("rejected_visual_claims") or []) + (dynamic_diag.get("rejected_visual_claims") or []),
            },
        }

    def _validate_baseline_response(self, response: Dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("characters"), list)
            and isinstance(response.get("objects"), list)
            and isinstance(response.get("creatures"), list)
            and isinstance(response.get("locations"), list)
            and isinstance(response.get("diagnostics"), dict)
        )

    def _validate_dynamic_response(self, response: Dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("characters"), list)
            and isinstance(response.get("scene_compositions"), list)
            and isinstance(response.get("diagnostics"), dict)
        )

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
            and isinstance(response.get("characters"), list)
            and isinstance(response.get("objects"), list)
            and isinstance(response.get("creatures"), list)
            and isinstance(response.get("locations"), list)
            and isinstance(response.get("scene_compositions"), list)
            and isinstance(response.get("diagnostics"), dict)
        )

    def _normalize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        raw_characters = response.get("characters") or []
        redirected_creatures: List[Dict[str, Any]] = []
        kept_characters: List[Dict[str, Any]] = []
        for row in raw_characters:
            if self._looks_like_creature_row(row):
                redirected_creatures.append(row)
            else:
                kept_characters.append(row)
        return {
            "characters": self._normalize_characters(kept_characters),
            "objects": self._normalize_entities(response.get("objects") or [], "object"),
            "creatures": self._normalize_entities((response.get("creatures") or []) + redirected_creatures, "creature"),
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
                if profile_specificity_score(values["persistent_visual_profile"]) <= 2 and values["dynamic_visual_changes"]:
                    values["persistent_visual_profile"] = promote_persistent_profile_from_visual_changes(
                        values["persistent_visual_profile"],
                        values["dynamic_visual_changes"],
                    )
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
                "visual_description": self._clean(row.get("visual_description") or row.get("physical_description")),
                "state_or_ownership": self._clean(row.get("state_or_ownership") or row.get("state_or_condition") or row.get("visible_condition")),
                "image_prompt": self._clean(row.get("image_prompt") or row.get("persistent_visual_prompt")),
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

    def _looks_like_creature_row(self, row: Any) -> bool:
        if not isinstance(row, dict):
            return False
        profile = row.get("persistent_visual_profile") or {}
        haystack = " ".join(
            self._clean(value)
            for value in [
                row.get("entity_name"),
                row.get("physical_description"),
                row.get("visible_condition"),
                row.get("source_evidence"),
                profile.get("species_or_race"),
                profile.get("role_or_archetype"),
                profile.get("model_safe_identity"),
                profile.get("fantasy_features"),
                profile.get("presence_description"),
            ]
        ).lower()
        has_creature = any(marker in haystack for marker in self.CREATURE_MARKERS)
        has_humanoid = any(marker in haystack for marker in self.HUMANOID_MARKERS)
        return has_creature and not has_humanoid
