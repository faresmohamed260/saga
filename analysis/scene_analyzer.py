"""Primary scene analysis module for structured narrative extraction."""

from typing import Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from analysis.tool_runtime import SceneToolRuntime
from infrastructure.llm_client import LLMClient


class SceneAnalyzer:
    """
    Produces a rich, validated scene analysis payload with one LLM call per scene.
    """

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

        if analysis_mode == "tool":
            return self._analyze_with_tools(
                scene=scene,
                alias_map=alias_map or {},
                rejected_identities=rejected_identities or [],
                scene_context=scene_context,
                local_evidence=evidence_bundle,
            )

        for attempt in range(1, self.max_attempts + 1):
            prompt = self._build_prompt(
                scene_text=scene.get("text", ""),
                alias_map=alias_map or {},
                rejected_identities=rejected_identities or [],
                scene_context=scene_context,
                local_evidence=evidence_bundle,
                retry_hint=attempt > 1,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
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
                return normalized

        return {
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
        }

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

        for attempt in range(1, self.max_attempts + 1):
            prompt = self._build_tool_prompt(
                scene_text=scene.get("text", ""),
                alias_map=alias_map,
                rejected_identities=rejected_identities,
                scene_context=scene_context,
                local_evidence=local_evidence,
                retry_hint=attempt > 1,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_tool_response)
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
                return normalized

        return {
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
        }

    def analyze_many(self, scenes: List[Dict]) -> List[Dict]:
        return [self.analyze(scene) for scene in scenes]

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

        alias_context = [
            {
                "canonical_name": canonical_name,
                "aliases": aliases,
            }
            for canonical_name, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]
        known_character_roster = [
            canonical_name
            for canonical_name, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
            if canonical_name or aliases
        ]
        local_evidence = normalize_evidence_bundle(local_evidence)

        return f"""
        Analyze this story scene and return a compact structured JSON payload.

        {retry_line}

        Rules:
        - Use only evidence from the scene
        - Treat local evidence as candidate evidence, not ground truth
        - Prefer validating, rejecting, or refining the provided candidates over inventing new ones from scratch
        - Keep output concise and grounded
        - Do not invent details
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
        {alias_context}

        Local Evidence Bundle:
        {local_evidence}

        Rejected Identities So Far:
        {rejected_identities}

        Known Canonical Characters:
        {known_character_roster}

        Recent Context:
        {scene_context or "No additional context."}

        Scene:
        {scene_text}
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

        local_evidence = normalize_evidence_bundle(local_evidence)
        alias_context = [
            {"canonical_name": canonical_name, "aliases": aliases}
            for canonical_name, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]

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
        - If the scene contains consequential actions, discoveries, state transitions, or relationship shifts, emit those through tools rather than leaving them implicit in the summary
        - Prefer a small number of strong, well-supported tool calls over broad speculative coverage
        - Only emit add_state_change when the scene makes a new state true
        - Only emit add_relationship_change when the scene establishes a meaningful shift rather than mere co-presence
        - Events must use canonical character names, not raw mention text
        - Pronouns may appear in raw evidence but must never become aliases
        - Generic labels like man, woman, boy, girl, person, figure, voice should not be aliases
        - Only reject candidates that are clearly noise or non-characters

        Current Alias Map:
        {alias_context}

        Rejected Identities:
        {rejected_identities}

        Local Evidence Bundle:
        {local_evidence}

        Recent Context:
        {scene_context or "No additional context."}

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
                event_type = "action"

            characters = event.get("characters") or []
            if not isinstance(characters, list):
                characters = []

            normalized.append({
                "event_id": f"evt_{index}",
                "description": description,
                "characters": [
                    str(character).strip()
                    for character in characters
                    if str(character).strip()
                    and not self._is_forbidden_identity(str(character))
                    and not self._is_generic_alias(str(character))
                ],
                "type": event_type,
            })
        return normalized

    def _normalize_entities(self, entities: List[Dict]) -> List[Dict]:
        normalized = []
        seen = set()

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            name = (entity.get("name") or "").strip()
            entity_type = (entity.get("entity_type") or "").strip().lower()
            if not name or entity_type not in self.ENTITY_TYPES:
                continue

            key = (name.lower(), entity_type)
            if key in seen:
                continue
            seen.add(key)

            normalized.append({
                "name": name,
                "entity_type": entity_type,
            })

        return normalized

    def _normalize_descriptions(self, descriptions: List[Dict]) -> List[Dict]:
        normalized = []
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
