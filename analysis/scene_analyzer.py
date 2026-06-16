"""Primary scene analysis module for structured narrative extraction."""

import json
import logging
from typing import Dict, List, Optional

from analysis.evidence_schema import compact_evidence_bundle, normalize_evidence_bundle
from analysis.tool_runtime import SceneToolRuntime
from infrastructure.llm_client import LLMClient


logger = logging.getLogger(__name__)


class SceneAnalyzer:
    """
    Produces a rich, validated scene analysis payload with one LLM call per scene.
    """

    GC_JSON_RESPONSE_FORMAT = {"type": "json_object"}
    MAX_PROMPT_ALIAS_ROWS = 12
    MAX_PROMPT_CONTEXT_CHARS = 1200
    MAX_PROMPT_SCENE_TEXT_CHARS = 6500

    EVENT_TYPES = {"action", "interaction", "movement", "discovery"}
    ENTITY_TYPES = {"character", "object", "location", "creature"}
    DESCRIPTION_TYPES = {"stable_trait", "temporary_condition", "possession", "appearance_note"}
    CHANGE_TYPES = {
        "physical_state",
        "status",
        "possession",
        "location",
        "condition",
        "relationship",
        "knowledge",
    }
    FORBIDDEN_IDENTITY_LABELS = {
        "i",
        "me",
        "my",
        "myself",
        "he",
        "she",
        "they",
        "them",
        "him",
        "her",
        "his",
        "hers",
        "their",
        "theirs",
        "it",
        "its",
        "narrator",
        "protagonist",
        "person",
        "character",
    }
    GENERIC_ALIAS_LABELS = {"man", "woman", "boy", "girl", "person", "figure", "voice"}
    MENTION_TYPES = {"name", "title", "descriptor", "role"}

    def __init__(self, llm_client: Optional[LLMClient] = None, max_attempts: int = 2):
        self.llm = llm_client or LLMClient()
        self.max_attempts = max_attempts

    def analyze(
        self,
        scene: Dict,
        alias_map: Optional[Dict[str, List[str]]] = None,
        rejected_identities: Optional[List[str]] = None,
        scene_context: str = "",
        local_evidence: Optional[Dict] = None,
        analysis_mode: str = "structured",
    ) -> Dict:
        last_response = None
        evidence_bundle = normalize_evidence_bundle(local_evidence)
        scene_ref = (
            f"b{scene.get('book_index', '?')}:"
            f"c{scene.get('chapter_index', '?')}:"
            f"s{scene.get('scene_index', '?')}"
        )
        logger.info(
            "SceneAnalyzer start | scene=%s mode=%s analysis_mode=%s text_chars=%s alias_count=%s rejected_count=%s",
            scene_ref,
            getattr(self.llm, "mode", "unknown"),
            analysis_mode,
            len(str(scene.get("text", "") or "")),
            len(alias_map or {}),
            len(rejected_identities or []),
        )

        if analysis_mode == "tool":
            result = self._analyze_with_tools(
                scene=scene,
                alias_map=alias_map or {},
                rejected_identities=rejected_identities or [],
                scene_context=scene_context,
                local_evidence=evidence_bundle,
            )
            logger.info(
                "SceneAnalyzer done | scene=%s mode=tool final_status=%s error=%s",
                scene_ref,
                result.get("final_status") or "unknown",
                result.get("error") or "",
            )
            return result

        for attempt in range(1, self.max_attempts + 1):
            logger.info(
                "SceneAnalyzer attempt | scene=%s attempt=%s/%s prompt_mode=structured",
                scene_ref,
                attempt,
                self.max_attempts,
            )
            prompt = self._build_prompt(
                scene_text=scene.get("text", ""),
                alias_map=alias_map or {},
                rejected_identities=rejected_identities or [],
                scene_context=scene_context,
                local_evidence=evidence_bundle,
                retry_hint=attempt > 1,
            )
            response = self._generate_scene_json(prompt, validator=self._validate_response)
            last_response = response

            if "error" not in response:
                normalized = self._normalize_response(response)
                normalized.update({
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                    "length": scene.get("length"),
                    "text": scene.get("text", ""),
                })
                normalized.update(self._scene_runtime_metadata(attempt_count=attempt, final_status="success"))
                logger.info(
                    "SceneAnalyzer success | scene=%s attempt=%s events=%s entities=%s state_changes=%s relationship_changes=%s",
                    scene_ref,
                    attempt,
                    len(normalized.get("events") or []),
                    len(normalized.get("entities_present") or []),
                    len(normalized.get("state_changes") or []),
                    len(normalized.get("relationship_changes") or []),
                )
                return normalized
            logger.warning(
                "SceneAnalyzer retry | scene=%s attempt=%s error=%s last_error=%s",
                scene_ref,
                attempt,
                response.get("error") if isinstance(response, dict) else "unknown_error",
                response.get("last_error") if isinstance(response, dict) else "",
            )

        failed = {
            "book_index": scene.get("book_index"),
            "chapter_index": scene.get("chapter_index"),
            "scene_index": scene.get("scene_index"),
            "length": scene.get("length"),
            "text": scene.get("text", ""),
            "scene_summary": "",
            "events": [],
            "entities_present": [],
            "entity_descriptions": [],
            "state_changes": [],
            "relationship_changes": [],
            "location": {},
            "time_signals": [],
            "canonical_characters": [],
            "character_mentions": [],
            "alias_updates": [],
            "rejected_identity_candidates": [],
            "error": last_response.get("error") if isinstance(last_response, dict) else "unknown_error",
            "last_error": last_response.get("last_error") if isinstance(last_response, dict) else "",
            **self._scene_runtime_metadata(
                attempt_count=self.max_attempts,
                final_status="failed",
                error=last_response.get("error") if isinstance(last_response, dict) else "unknown_error",
                last_error=last_response.get("last_error") if isinstance(last_response, dict) else "",
            ),
        }
        logger.error(
            "SceneAnalyzer failed | scene=%s attempts=%s error=%s last_error=%s",
            scene_ref,
            self.max_attempts,
            failed.get("error") or "",
            failed.get("last_error") or "",
        )
        return failed

    def _analyze_with_tools(
        self,
        scene: Dict,
        alias_map: Dict[str, List[str]],
        rejected_identities: List[str],
        scene_context: str,
        local_evidence: Dict,
    ) -> Dict:
        last_response = None
        runtime = SceneToolRuntime()
        scene_ref = (
            f"b{scene.get('book_index', '?')}:"
            f"c{scene.get('chapter_index', '?')}:"
            f"s{scene.get('scene_index', '?')}"
        )

        for attempt in range(1, self.max_attempts + 1):
            logger.info(
                "SceneAnalyzer tool attempt | scene=%s attempt=%s/%s",
                scene_ref,
                attempt,
                self.max_attempts,
            )
            prompt = self._build_tool_prompt(
                scene_text=scene.get("text", ""),
                alias_map=alias_map,
                rejected_identities=rejected_identities,
                scene_context=scene_context,
                local_evidence=local_evidence,
                retry_hint=attempt > 1,
            )
            response = self._generate_scene_tool_calls(prompt, validator=self._validate_tool_response)
            last_response = response
            if "error" not in response:
                tool_result = runtime.apply_tool_calls(response.get("tool_calls") or [])
                normalized = self._normalize_response(tool_result)
                normalized["tool_runtime"] = tool_result.get("_tool_runtime", {})
                normalized.update({
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                    "length": scene.get("length"),
                    "text": scene.get("text", ""),
                })
                normalized.update(self._scene_runtime_metadata(attempt_count=attempt, final_status="success"))
                logger.info(
                    "SceneAnalyzer tool success | scene=%s attempt=%s events=%s entities=%s",
                    scene_ref,
                    attempt,
                    len(normalized.get("events") or []),
                    len(normalized.get("entities_present") or []),
                )
                return normalized
            logger.warning(
                "SceneAnalyzer tool retry | scene=%s attempt=%s error=%s last_error=%s",
                scene_ref,
                attempt,
                response.get("error") if isinstance(response, dict) else "unknown_error",
                response.get("last_error") if isinstance(response, dict) else "",
            )

        failed = {
            "book_index": scene.get("book_index"),
            "chapter_index": scene.get("chapter_index"),
            "scene_index": scene.get("scene_index"),
            "length": scene.get("length"),
            "text": scene.get("text", ""),
            "scene_summary": "",
            "events": [],
            "entities_present": [],
            "entity_descriptions": [],
            "state_changes": [],
            "relationship_changes": [],
            "location": {},
            "time_signals": [],
            "canonical_characters": [],
            "character_mentions": [],
            "alias_updates": [],
            "rejected_identity_candidates": [],
            "error": last_response.get("error") if isinstance(last_response, dict) else "unknown_error",
            "last_error": last_response.get("last_error") if isinstance(last_response, dict) else "",
            **self._scene_runtime_metadata(
                attempt_count=self.max_attempts,
                final_status="failed",
                error=last_response.get("error") if isinstance(last_response, dict) else "unknown_error",
                last_error=last_response.get("last_error") if isinstance(last_response, dict) else "",
            ),
        }
        logger.error(
            "SceneAnalyzer tool failed | scene=%s attempts=%s error=%s last_error=%s",
            scene_ref,
            self.max_attempts,
            failed.get("error") or "",
            failed.get("last_error") or "",
        )
        return failed

    def analyze_many(self, scenes: List[Dict]) -> List[Dict]:
        return [self.analyze(scene) for scene in scenes]

    def _scene_runtime_metadata(
        self,
        *,
        attempt_count: int,
        final_status: str,
        error: str = "",
        last_error: str = "",
    ) -> Dict:
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

    def _generate_scene_json(self, prompt: str, *, validator) -> Dict:
        kwargs = {
            "strict": True,
            "validator": validator,
        }
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            kwargs["response_format"] = self.GC_JSON_RESPONSE_FORMAT
        try:
            return self.llm.generate_json(prompt, **kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            return self.llm.generate_json(prompt, **kwargs)

    def _generate_scene_tool_calls(self, prompt: str, *, validator) -> Dict:
        kwargs = {
            "strict": True,
            "validator": validator,
        }
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            kwargs["tools"] = self._gc_scene_tools()
            kwargs["tool_choice"] = "required"
        try:
            return self.llm.generate_json(prompt, **kwargs)
        except TypeError:
            kwargs.pop("tool_choice", None)
            kwargs.pop("tools", None)
            return self.llm.generate_json(prompt, **kwargs)

    def _gc_scene_tools(self) -> List[Dict]:
        return [
            self._function_tool("set_scene_summary", {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}),
            self._function_tool("add_canonical_character", {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "is_new_character": {"type": "boolean"},
                    "names_used": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name"],
            }),
            self._function_tool("add_character_mention", {
                "type": "object",
                "properties": {
                    "mention_text": {"type": "string"},
                    "mention_type": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "is_consequential_character": {"type": "boolean"},
                },
                "required": ["mention_text", "mention_type"],
            }),
            self._function_tool("add_event", {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "entities_involved": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                    "outcome": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["description"],
            }),
            self._function_tool("add_entity", {
                "type": "object",
                "properties": {"name": {"type": "string"}, "entity_type": {"type": "string"}},
                "required": ["name", "entity_type"],
            }),
            self._function_tool("add_entity_description", {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "description": {"type": "string"},
                    "description_type": {"type": "string"},
                },
                "required": ["entity_name", "entity_type", "description", "description_type"],
            }),
            self._function_tool("add_state_change", {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "attribute": {"type": "string"},
                    "previous_state": {"type": "string"},
                    "new_state": {"type": "string"},
                    "change_type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["entity_name", "entity_type", "attribute", "new_state", "change_type", "evidence"],
            }),
            self._function_tool("add_relationship_change", {
                "type": "object",
                "properties": {
                    "source_entity": {"type": "string"},
                    "target_entity": {"type": "string"},
                    "relationship": {"type": "string"},
                    "change": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["source_entity", "target_entity", "relationship", "change", "evidence"],
            }),
            self._function_tool("set_location", {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "entity_type"],
            }),
            self._function_tool("add_time_signal", {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}),
            self._function_tool("add_alias_update", {
                "type": "object",
                "properties": {
                    "alias": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "action": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": ["alias", "canonical_name", "action", "reasoning"],
            }),
            self._function_tool("reject_identity_candidate", {"type": "object", "properties": {"candidate": {"type": "string"}}, "required": ["candidate"]}),
        ]

    def _function_tool(self, name: str, parameters: Dict) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": f"Populate scene-analysis state via {name}.",
                "parameters": parameters,
            },
        }

    def _build_prompt(
        self,
        scene_text: str,
        alias_map: Dict[str, List[str]],
        rejected_identities: List[str],
        scene_context: str = "",
        local_evidence: Optional[Dict] = None,
        retry_hint: bool = False,
    ) -> str:
        retry_line = ""
        if retry_hint:
            retry_line = (
                "Your previous response was invalid. "
                "Return only valid JSON matching the exact required schema.\n"
            )

        compact_alias_map = self._compact_alias_map(alias_map, scene_text)
        alias_context = [
            {
                "canonical_name": canonical_name,
                "aliases": aliases,
            }
            for canonical_name, aliases in sorted(compact_alias_map.items(), key=lambda item: item[0].lower())
        ]
        known_character_roster = [
            canonical_name
            for canonical_name, aliases in sorted(compact_alias_map.items(), key=lambda item: item[0].lower())
            if canonical_name or aliases
        ]
        local_evidence = compact_evidence_bundle(local_evidence)
        compact_scene_context = self._compact_scene_context(scene_context)

        prompt_scene_text = self._compact_scene_text(scene_text)
        if getattr(self.llm, "mode", "") == LLMClient.MODE_GENERAL_COMPUTE:
            return f"""
            Analyze this story scene and return strict JSON.

            {retry_line}

            Rules:
            - Use only scene text, recent context, alias map, and local evidence.
            - Treat local evidence as candidates, not truth.
            - Preserve known canonical names from the alias map.
            - Do not invent characters, aliases, or unsupported entities.
            - Keep entities deduplicated and consequential.
            - If an entity appears in an event, it must also appear in entities_present unless abstract.
            - Events should include entities_involved, reason, and outcome when supported.
            - Entity descriptions should capture grounded physical/world detail, possessions, temporary conditions, or appearance notes.
            - State changes should capture only newly true changes.
            - Relationship changes should capture only meaningful shifts.

            Output schema:
            {{
              "scene_summary": "",
              "canonical_characters": [{{"name": "", "role": "", "is_new_character": false, "names_used": [""]}}],
              "character_mentions": [{{"mention_text": "", "mention_type": "name|title|descriptor|role", "canonical_name": "", "is_consequential_character": true}}],
              "events": [{{"description": "", "characters": [""], "entities_involved": [""], "reason": "", "outcome": "", "type": "action|interaction|movement|discovery"}}],
              "entities_present": [{{"name": "", "entity_type": "character|object|location|creature"}}],
              "entity_descriptions": [{{"entity_name": "", "entity_type": "character|object|location|creature", "description": "", "description_type": "stable_trait|temporary_condition|possession|appearance_note"}}],
              "state_changes": [{{"entity_name": "", "entity_type": "character|object|location|creature", "attribute": "", "previous_state": "", "new_state": "", "change_type": "physical_state|status|possession|location|condition|relationship|knowledge", "evidence": ""}}],
              "relationship_changes": [{{"source_entity": "", "target_entity": "", "relationship": "", "change": "", "evidence": ""}}],
              "location": {{"name": "", "entity_type": "location", "description": ""}},
              "time_signals": [""],
              "alias_updates": [{{"alias": "", "canonical_name": "", "action": "map_alias", "reasoning": ""}}],
              "rejected_identity_candidates": [""]
            }}

            Alias map:
            {json.dumps(alias_context, ensure_ascii=False)}

            Local evidence:
            {json.dumps(local_evidence, ensure_ascii=False)}

            Rejected identities:
            {rejected_identities}

            Known canonical characters:
            {known_character_roster}

            Recent context:
            {compact_scene_context or "No additional context."}

            Scene:
            {prompt_scene_text}
            """

        return f"""
        Analyze this story scene and return a compact structured JSON payload.

        {retry_line}

        Rules:
        - Use only evidence from the scene
        - Treat local evidence as candidate evidence, not ground truth
        - Prefer validating, rejecting, or refining the provided candidates over inventing new ones from scratch
        - Keep output concise and grounded
        - Do not invent details
        - Do not leave meaningful entities empty: if an entity is consequential enough to include, explain either how it appears, what it is doing, where it is, who uses it, or how it changes
        - Avoid duplicate entities by normalizing obvious variants within the scene: singular/plural, article variants, capitalization, and aliases already present in the alias map
        - Treat the current alias map as ground truth memory for already-known characters
        - Do not invent characters, aliases, or narrator labels that are not explicitly supported by the text
        - Never create placeholder identities such as "Narrator" unless the text itself clearly uses that identity label
        - Maintain and extend the provided alias map only when the scene gives clear evidence
        - If a known canonical character already exists in the alias map, prefer that canonical name in events and entity lists
        - If an alias should map to a known canonical character, add an alias update rather than inventing a new identity
        - If a mentioned label is clearly not a consequential character, include it in rejected_identity_candidates
        - Do not invent a new canonical character unless the scene clearly introduces that character by name or stable role label
        - Never propose alias updates for labels already listed in rejected identities
        - Never use pronouns or placeholder labels as character identities
        - If the scene is first-person, resolve the first-person speaker to a known character when the text supports it; never output "I" or other pronouns as an identity
        - Characters are sentient agents; animals, prey, objects, materials, and places should stay entities unless they are clearly consequential sentient beings
        - Treat descriptors and temporary labels as mentions first, not canonicals
        - A canonical character should usually be a proper name or a stable recurring role label
        - character_mentions may include descriptive references, but canonical_characters must stay conservative
        - Events must use only canonical character names, never raw descriptor mentions
        - Ambiguous humanlike or sentient role labels should remain unresolved mentions, not rejected identities
        - Use rejected_identity_candidates only for clearly non-sentient or incidental references such as prey animals, scenery, materials, or obvious background objects
        - Never place clear proper names into rejected_identity_candidates; if a proper name appears, keep it as a canonical character or unresolved character mention
        - Extract at most 5 events
        - Extract only consequential entities
        - A consequential character may be named, role-based, or sentient nonhuman
        - Exclude incidental prey, scenery, generic background groups, and objects with no narrative relevance
        - Separate observations from durable state changes
        - For entity_descriptions:
          - The first time a character, creature, object, or location appears in this scene, actively look for a concrete physical description near that introduction
          - Physical description means visible form/material/color/shape/body/face/hair/clothing/armor/condition/setting details directly stated in the scene
          - Do not label mood, behavior, occupation, plot role, possession, or generic action as physical description
          - If no physical description is directly present, do not invent one; instead add a concise stable_trait or contextual note that explains why the entity matters
          - For characters and creatures, prioritize body/face/hair/build/skin/wings/mask/armor/clothing/injuries
          - For objects, prioritize material, shape, color, size, condition, magical appearance, owner/user, and location
          - For locations, prioritize architecture, terrain, lighting, atmosphere, sensory details, and state changes
          - Capture outfit/clothing/armor changes as possession or appearance_note
          - Capture injuries, visible exhaustion, blood, healing, masking, transformation, or damage as temporary_condition or state_changes
          - stable_trait = durable physical identity details
          - temporary_condition = temporary state such as injured, bloody, tired
          - possession = item carried/worn/owned in this scene
          - appearance_note = notable visible detail that is scene-specific
        - For state_changes:
          - include only changes that become newly true in this scene
          - if prior state is unknown, use an empty string for previous_state
        - For relationship_changes:
          - include only explicit relationship shifts established in this scene
          - good examples: first meeting, alliance, betrayal, promise, threat, rescue, confession, family revelation, trust gained/lost
          - if two characters merely appear together without a meaningful shift, leave relationship_changes empty
          - prefer a small number of strong relationship changes over weak guesses
        - Allowed event types: action, interaction, movement, discovery
        - Allowed entity types: character, object, location, creature
        - Allowed description types: stable_trait, temporary_condition, possession, appearance_note
        - Allowed change types: physical_state, status, possession, location, condition, relationship, knowledge
        - Events must include:
          - entities_involved: every consequential character/location/object/creature participating in the event
          - reason: why the event happens if the scene gives a cause or motive; otherwise empty string
          - outcome: what changes because of the event; otherwise empty string
          - characters: only canonical character names that actively participate in the event
          - description: one concrete canon event, not a vague whole-scene recap
        - Every entity named in events.entities_involved must also appear in entities_present unless it is only an abstract concept
        - If a character appears in events.characters, also include that character in events.entities_involved
        - If a scene introduces a consequential entity but you cannot ground its physical appearance yet, still include a concise contextual note explaining what it is or why it matters
        - Be especially careful in fantasy scenes to capture grounded magical/physical world details:
          - characters: visible form, face, hair, clothing, armor, wings, tattoos/marks, injuries, blood, exhaustion, transformation
          - objects/artifacts: material, shape, visible power, glow, damage, owner/holder, activation state, carried/worn status
          - locations: architecture, terrain, weather, lighting, atmosphere, crowding, damage, magical effects
          - creatures: anatomy, species/kind, threatening posture, wounds, transformation, unusual physical traits

        Return JSON:
        {{
          "scene_summary": "brief summary",
          "canonical_characters": [
            {{
              "name": "Feyre",
              "role": "huntress",
              "is_new_character": false,
              "names_used": ["Feyre", "the huntress"]
            }}
          ],
          "character_mentions": [
            {{
              "mention_text": "the huntress",
              "mention_type": "title",
              "canonical_name": "Feyre",
              "is_consequential_character": true
            }}
          ],
          "events": [
            {{
              "description": "short event description",
              "characters": ["Feyre"],
              "entities_involved": ["Feyre", "ash arrow", "wolf"],
              "reason": "Feyre needs food and sees the wolf threatening the doe",
              "outcome": "The wolf is killed and becomes a consequential dead creature",
              "type": "action"
            }}
          ],
          "entities_present": [
            {{
              "name": "Feyre",
              "entity_type": "character"
            }}
          ],
          "entity_descriptions": [
            {{
              "entity_name": "Feyre",
              "entity_type": "character",
              "description": "mud on her boots",
              "description_type": "appearance_note"
            }}
          ],
          "state_changes": [
            {{
              "entity_name": "Wolf",
              "entity_type": "creature",
              "attribute": "status",
              "previous_state": "alive",
              "new_state": "dead",
              "change_type": "physical_state",
              "evidence": "Feyre kills the wolf"
            }}
          ],
          "relationship_changes": [
            {{
              "source_entity": "Feyre",
              "target_entity": "Tamlin",
              "relationship": "meets",
              "change": "first direct encounter",
              "evidence": "Tamlin arrives and confronts Feyre"
            }}
          ],
          "location": {{
            "name": "the forest",
            "entity_type": "location",
            "description": "winter woods where the hunt takes place"
          }},
          "time_signals": ["winter", "before sunset"],
          "alias_updates": [
            {{
              "alias": "the huntress",
              "canonical_name": "Feyre",
              "action": "map_alias",
              "reasoning": "the scene clearly uses the huntress to refer to Feyre"
            }}
          ],
          "rejected_identity_candidates": ["doe"]
        }}

        Current Alias Map:
        {json.dumps(alias_context, ensure_ascii=False)}

        Local Evidence Bundle:
        {json.dumps(local_evidence, ensure_ascii=False)}

        Rejected Identities So Far:
        {rejected_identities}

        Known Canonical Characters:
        {known_character_roster}

        Recent Context:
        {compact_scene_context or "No additional context."}

        Scene:
        {prompt_scene_text}
        """

    def _build_tool_prompt(
        self,
        scene_text: str,
        alias_map: Dict[str, List[str]],
        rejected_identities: List[str],
        scene_context: str = "",
        local_evidence: Optional[Dict] = None,
        retry_hint: bool = False,
    ) -> str:
        retry_line = ""
        if retry_hint:
            retry_line = "Your previous tool-call response was invalid. Return only valid JSON with tool_calls.\n"

        local_evidence = compact_evidence_bundle(local_evidence)
        compact_alias_map = self._compact_alias_map(alias_map, scene_text)
        alias_context = [
            {"canonical_name": canonical_name, "aliases": aliases}
            for canonical_name, aliases in sorted(compact_alias_map.items(), key=lambda item: item[0].lower())
        ]
        compact_scene_context = self._compact_scene_context(scene_context)

        return f"""
        You are filling a scene-analysis record using tool calls only.

        {retry_line}

        Never return the final scene JSON directly.
        Return only:
        {{
          "tool_calls": [
            {{"tool": "set_scene_summary", "arguments": {{"summary": "..."}}}},
            {{"tool": "add_canonical_character", "arguments": {{"name": "...", "role": "", "is_new_character": false, "names_used": ["..."]}}}}
          ]
        }}

        Use these tools only:
        - set_scene_summary
        - add_canonical_character
        - add_character_mention
        - add_event
        - add_entity
        - add_entity_description
        - add_state_change
        - add_relationship_change
        - set_location
        - add_time_signal
        - add_alias_update
        - reject_identity_candidate

        Rules:
        - Use local evidence as candidates to validate or reject
        - Do not invent unsupported entities or aliases
        - Use filtered candidate_characters and candidate_entities as your default working set
        - If a candidate is weak or wrong, ignore or reject it rather than replacing it with speculative new items
        - Use add_event, add_state_change, and add_relationship_change to populate those sections explicitly
        - Event tool calls should include entities_involved, reason, and outcome whenever the scene supports them
        - If an event mentions an object, location, creature, or character, also add that item through add_entity
        - If an entity is important enough to add, add at least one physical/contextual description or state change when supported by the text
        - Actively inspect first appearances for physical description: visible body/form/material/color/clothing/armor/injury/location atmosphere, not generic behavior
        - Track outfit, injury, condition, object ownership, object location, object damage, and location state changes as descriptions or state changes
        - When a character is added to an event, include the same canonical name in entities_involved too
        - If the scene contains consequential actions, discoveries, state transitions, or relationship shifts, emit those through tools rather than leaving them implicit in the summary
        - Prefer a small number of strong, well-supported tool calls over broad speculative coverage
        - Only emit add_state_change when the scene makes a new state true
        - Only emit add_relationship_change when the scene establishes a meaningful shift rather than mere co-presence
        - Events must use canonical character names, not raw mention text
        - Pronouns may appear in raw evidence but must never become aliases
        - Generic labels like man, woman, boy, girl, person, figure, voice should not be aliases
        - Only reject candidates that are clearly noise or non-characters

        Current Alias Map:
        {json.dumps(alias_context, ensure_ascii=False)}

        Rejected Identities:
        {rejected_identities}

        Local Evidence Bundle:
        {json.dumps(local_evidence, ensure_ascii=False)}

        Recent Context:
        {compact_scene_context or "No additional context."}

        Scene:
        {scene_text}
        """

    def _normalize_response(self, response: Dict) -> Dict:
        return {
            "scene_summary": (response.get("scene_summary") or "").strip(),
            "canonical_characters": self._normalize_canonical_characters(response.get("canonical_characters") or []),
            "character_mentions": self._normalize_character_mentions(response.get("character_mentions") or []),
            "events": self._normalize_events(response.get("events") or []),
            "entities_present": self._normalize_entities(response.get("entities_present") or []),
            "entity_descriptions": self._normalize_descriptions(response.get("entity_descriptions") or []),
            "state_changes": self._normalize_state_changes(response.get("state_changes") or []),
            "relationship_changes": self._normalize_relationship_changes(response.get("relationship_changes") or []),
            "location": self._normalize_location(response.get("location") or {}),
            "time_signals": self._normalize_time_signals(response.get("time_signals") or []),
            "alias_updates": self._normalize_alias_updates(response.get("alias_updates") or []),
            "rejected_identity_candidates": self._normalize_identity_candidates(response.get("rejected_identity_candidates") or []),
        }

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
        segment = max(1400, self.MAX_PROMPT_SCENE_TEXT_CHARS // 3)
        middle_start = max(0, (len(cleaned) // 2) - (segment // 2))
        middle_end = middle_start + segment
        parts = [
            cleaned[:segment].rstrip(),
            cleaned[middle_start:middle_end].strip(),
            cleaned[-segment:].lstrip(),
        ]
        return "\n...\n".join(part for part in parts if part)

    def _normalize_canonical_characters(self, characters: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()

        for item in characters:
            if not isinstance(item, dict):
                continue

            name = (item.get("name") or "").strip()
            if not name or self._is_forbidden_identity(name):
                continue

            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            names_used = item.get("names_used") or []
            if not isinstance(names_used, list):
                names_used = []

            cleaned_names_used = []
            used_seen = set()
            for alias in names_used:
                cleaned = str(alias).strip()
                if not cleaned or self._is_forbidden_identity(cleaned):
                    continue
                lowered = cleaned.lower()
                if lowered in used_seen:
                    continue
                used_seen.add(lowered)
                cleaned_names_used.append(cleaned)

            if name.lower() not in used_seen:
                cleaned_names_used.insert(0, name)

            normalized.append({
                "name": name,
                "role": (item.get("role") or "").strip(),
                "is_new_character": bool(item.get("is_new_character", False)),
                "names_used": cleaned_names_used,
            })

        return normalized

    def _normalize_character_mentions(self, mentions: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()

        for item in mentions:
            if not isinstance(item, dict):
                continue

            mention_text = (item.get("mention_text") or "").strip()
            mention_type = (item.get("mention_type") or "").strip().lower()
            canonical_name = (item.get("canonical_name") or "").strip()
            is_character = bool(item.get("is_consequential_character", False))

            if not mention_text or mention_type not in self.MENTION_TYPES:
                continue
            if self._is_forbidden_identity(mention_text):
                continue

            if canonical_name and self._is_forbidden_identity(canonical_name):
                canonical_name = ""

            key = (mention_text.lower(), mention_type, canonical_name.lower(), is_character)
            if key in seen:
                continue
            seen.add(key)

            normalized.append({
                "mention_text": mention_text,
                "mention_type": mention_type,
                "canonical_name": canonical_name,
                "is_consequential_character": is_character,
            })

        return normalized

    def _normalize_events(self, events: List[Dict]) -> List[Dict]:
        normalized = []
        for index, event in enumerate(events[:5], start=1):
            if not isinstance(event, dict):
                continue

            description = (event.get("description") or "").strip()
            if not description:
                continue

            event_type = (event.get("type") or "").strip().lower()
            if event_type not in self.EVENT_TYPES:
                event_type = self._classify_event_type(event)

            characters = event.get("characters") or []
            if not isinstance(characters, list):
                characters = []
            entities_involved = event.get("entities_involved") or []
            if not isinstance(entities_involved, list):
                entities_involved = []

            cleaned_characters = []
            seen_characters = set()
            for character in characters:
                cleaned = str(character).strip()
                lowered = cleaned.lower()
                if (
                    not cleaned
                    or lowered in seen_characters
                    or self._is_forbidden_identity(cleaned)
                    or self._is_generic_alias(cleaned)
                ):
                    continue
                seen_characters.add(lowered)
                cleaned_characters.append(cleaned)

            cleaned_entities = []
            seen_entities = set()
            for entity in entities_involved:
                cleaned = str(entity).strip()
                lowered = cleaned.lower()
                if not cleaned or lowered in seen_entities:
                    continue
                seen_entities.add(lowered)
                cleaned_entities.append(cleaned)
            for character in cleaned_characters:
                lowered = character.lower()
                if lowered not in seen_entities:
                    seen_entities.add(lowered)
                    cleaned_entities.append(character)

            normalized.append({
                "event_id": f"evt_{index}",
                "description": description,
                "characters": cleaned_characters,
                "entities_involved": cleaned_entities,
                "reason": (event.get("reason") or "").strip(),
                "outcome": (event.get("outcome") or "").strip(),
                "type": event_type,
            })
        return normalized

    def _classify_event_type(self, event: Dict) -> str:
        text = " ".join(
            str(part or "").strip().lower()
            for part in [
                event.get("description"),
                event.get("reason"),
                event.get("outcome"),
            ]
        )
        movement_markers = {"walk", "walks", "travel", "travels", "ride", "rides", "return", "returns", "leave", "leaves", "enter", "enters", "go", "goes", "carry", "carries"}
        discovery_markers = {"notice", "notices", "learn", "learns", "realize", "realizes", "discover", "discovers", "find", "finds", "see", "sees", "reveal", "reveals"}
        interaction_markers = {"say", "says", "tell", "tells", "ask", "asks", "speak", "speaks", "argue", "argues", "promise", "promises", "warn", "warns", "confide", "confides"}
        if any(marker in text for marker in interaction_markers):
            return "interaction"
        if any(marker in text for marker in discovery_markers):
            return "discovery"
        if any(marker in text for marker in movement_markers):
            return "movement"
        return "action"

    def _normalize_entities(self, entities: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()
        by_name = {}
        type_priority = {"character": 0, "creature": 1, "location": 2, "object": 3}

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            name = (entity.get("name") or "").strip()
            entity_type = (entity.get("entity_type") or "").strip().lower()
            if not name or entity_type not in self.ENTITY_TYPES:
                continue

            key = (name.lower(), entity_type)
            name_key = " ".join(name.lower().split())
            existing_index = by_name.get(name_key)
            if existing_index is not None:
                existing_type = normalized[existing_index]["entity_type"]
                if type_priority.get(entity_type, 99) < type_priority.get(existing_type, 99):
                    old_key = (name_key, existing_type)
                    seen.discard(old_key)
                    normalized[existing_index] = {"name": name, "entity_type": entity_type}
                    seen.add(key)
                continue
            if key in seen:
                continue
            seen.add(key)
            by_name[name_key] = len(normalized)
            normalized.append({
                "name": name,
                "entity_type": entity_type,
            })

        return normalized

    def _normalize_descriptions(self, descriptions: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()
        for item in descriptions:
            if not isinstance(item, dict):
                continue

            entity_name = (item.get("entity_name") or "").strip()
            entity_type = (item.get("entity_type") or "").strip().lower()
            description = (item.get("description") or "").strip()
            description_type = (item.get("description_type") or "").strip().lower()

            if (
                not entity_name
                or not description
                or entity_type not in self.ENTITY_TYPES
                or description_type not in self.DESCRIPTION_TYPES
            ):
                continue

            key = (entity_name.lower(), entity_type, description.lower(), description_type)
            if key in seen:
                continue
            seen.add(key)

            normalized.append({
                "entity_name": entity_name,
                "entity_type": entity_type,
                "description": description,
                "description_type": description_type,
            })

        return normalized

    def _normalize_state_changes(self, changes: List[Dict]) -> List[Dict]:
        normalized = []
        for item in changes:
            if not isinstance(item, dict):
                continue

            entity_name = (item.get("entity_name") or "").strip()
            entity_type = (item.get("entity_type") or "").strip().lower()
            attribute = (item.get("attribute") or "").strip()
            new_state = (item.get("new_state") or "").strip()
            change_type = (item.get("change_type") or "").strip().lower()
            evidence = (item.get("evidence") or "").strip()

            if (
                not entity_name
                or not attribute
                or not new_state
                or not evidence
                or entity_type not in self.ENTITY_TYPES
                or change_type not in self.CHANGE_TYPES
            ):
                continue

            normalized.append({
                "entity_name": entity_name,
                "entity_type": entity_type,
                "attribute": attribute,
                "previous_state": (item.get("previous_state") or "").strip(),
                "new_state": new_state,
                "change_type": change_type,
                "evidence": evidence,
            })

        return normalized

    def _normalize_relationship_changes(self, changes: List[Dict]) -> List[Dict]:
        normalized = []
        for item in changes:
            if not isinstance(item, dict):
                continue

            source_entity = (item.get("source_entity") or "").strip()
            target_entity = (item.get("target_entity") or "").strip()
            relationship = (item.get("relationship") or "").strip()
            change = (item.get("change") or "").strip()
            evidence = (item.get("evidence") or "").strip()

            if not source_entity or not target_entity or not relationship or not change or not evidence:
                continue

            normalized.append({
                "source_entity": source_entity,
                "target_entity": target_entity,
                "relationship": relationship,
                "change": change,
                "evidence": evidence,
            })

        return normalized

    def _normalize_location(self, location: Dict) -> Dict:
        if not isinstance(location, dict):
            return {}

        name = (location.get("name") or "").strip()
        entity_type = (location.get("entity_type") or "").strip().lower()
        description = (location.get("description") or "").strip()

        if not name or entity_type != "location":
            return {}

        return {
            "name": name,
            "entity_type": entity_type,
            "description": description,
        }

    def _normalize_time_signals(self, time_signals: List[str]) -> List[str]:
        if not isinstance(time_signals, list):
            return []
        return [str(item).strip() for item in time_signals if str(item).strip()]

    def _normalize_alias_updates(self, alias_updates: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()

        for item in alias_updates:
            if not isinstance(item, dict):
                continue

            alias = (item.get("alias") or "").strip()
            canonical_name = (item.get("canonical_name") or "").strip()
            action = (item.get("action") or "").strip().lower()
            reasoning = (item.get("reasoning") or "").strip()

            if not alias or not canonical_name or not reasoning:
                continue
            if action not in {"map_alias", "new_canonical"}:
                continue
            if self._is_forbidden_identity(alias) or self._is_forbidden_identity(canonical_name):
                continue

            key = (alias.lower(), canonical_name.lower(), action)
            if key in seen:
                continue
            seen.add(key)

            normalized.append({
                "alias": alias,
                "canonical_name": canonical_name,
                "action": action,
                "reasoning": reasoning,
            })
        return normalized

    def _normalize_identity_candidates(self, rejected_candidates: List[str]) -> List[str]:
        if not isinstance(rejected_candidates, list):
            return []
        seen = set()
        normalized = []
        for item in rejected_candidates:
            candidate = str(item).strip()
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
        return normalized

    def _is_forbidden_identity(self, value: str) -> bool:
        cleaned = (value or "").strip().lower()
        return cleaned in self.FORBIDDEN_IDENTITY_LABELS or len(cleaned) <= 1

    def _is_generic_alias(self, value: str) -> bool:
        return (value or "").strip().lower() in self.GENERIC_ALIAS_LABELS

    def _validate_response(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("scene_summary"), str)
            and isinstance(response.get("canonical_characters"), list)
            and isinstance(response.get("character_mentions"), list)
            and isinstance(response.get("events"), list)
            and isinstance(response.get("entities_present"), list)
            and isinstance(response.get("entity_descriptions"), list)
            and isinstance(response.get("state_changes"), list)
            and isinstance(response.get("relationship_changes"), list)
            and isinstance(response.get("location"), dict)
            and isinstance(response.get("time_signals"), list)
            and isinstance(response.get("alias_updates"), list)
            and isinstance(response.get("rejected_identity_candidates"), list)
        )

    def _validate_tool_response(self, response: Dict) -> bool:
        return isinstance(response, dict) and isinstance(response.get("tool_calls"), list)
