"""Structured tool runtime for scene analysis.

The LLM does not return the final scene payload directly in tool mode. Instead,
it emits tool calls and this runtime assembles the result deterministically.

This module is the schema enforcement boundary for tool mode. It validates,
deduplicates, and normalizes tool arguments so downstream code never depends on
raw model-shaped JSON.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List


class SceneToolRuntime:
    """Collect validated tool calls into the stable scene-analysis schema."""

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
    MENTION_TYPES = {"name", "title", "descriptor", "role"}
    ALIAS_ACTIONS = {"map_alias", "new_canonical"}
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

    def __init__(self):
        self.result = {
            "scene_summary": "",
            "canonical_characters": [],
            "character_mentions": [],
            "events": [],
            "entities_present": [],
            "entity_descriptions": [],
            "state_changes": [],
            "relationship_changes": [],
            "location": {},
            "time_signals": [],
            "alias_updates": [],
            "rejected_identity_candidates": [],
        }
        self._tool_stats = {
            "tool_calls_seen": 0,
            "tool_calls_applied": 0,
            "tool_calls_ignored": 0,
            "ignored_tools": [],
        }
        self._seen_character_keys = set()
        self._seen_mention_keys = set()
        self._seen_event_keys = set()
        self._seen_entity_keys = set()
        self._seen_description_keys = set()
        self._seen_state_change_keys = set()
        self._seen_relationship_keys = set()
        self._seen_alias_update_keys = set()
        self._seen_rejections = set()

    def apply_tool_calls(self, tool_calls: List[Dict]) -> Dict:
        for item in tool_calls:
            self._tool_stats["tool_calls_seen"] += 1
            if not isinstance(item, dict):
                self._tool_stats["tool_calls_ignored"] += 1
                self._tool_stats["ignored_tools"].append({"tool": "<invalid>", "reason": "tool_call_not_object"})
                continue
            tool_name = item.get("tool")
            arguments = item.get("arguments") or {}
            method = getattr(self, tool_name, None)
            if callable(method):
                before = self._snapshot_lengths()
                method(arguments)
                after = self._snapshot_lengths()
                if after != before or tool_name == "set_scene_summary" or tool_name == "set_location":
                    self._tool_stats["tool_calls_applied"] += 1
                else:
                    self._tool_stats["tool_calls_ignored"] += 1
                    self._tool_stats["ignored_tools"].append({"tool": tool_name, "reason": "validation_or_dedup_filtered"})
            else:
                self._tool_stats["tool_calls_ignored"] += 1
                self._tool_stats["ignored_tools"].append({"tool": str(tool_name or ""), "reason": "unknown_tool"})
        return self.build_result()

    def set_scene_summary(self, arguments: Dict):
        summary = (arguments.get("summary") or "").strip()
        if summary:
            self.result["scene_summary"] = summary

    def add_canonical_character(self, arguments: Dict):
        name = self._clean_identity(arguments.get("name"))
        if not name:
            return
        key = name.lower()
        if key in self._seen_character_keys:
            return
        self._seen_character_keys.add(key)
        self.result["canonical_characters"].append({
            "name": name,
            "role": (arguments.get("role") or "").strip(),
            "is_new_character": bool(arguments.get("is_new_character", False)),
            "names_used": self._clean_string_list(arguments.get("names_used") or [], allow_generic=True, allow_pronouns=False, ensure_value=name),
        })

    def add_character_mention(self, arguments: Dict):
        mention_text = self._clean_identity(arguments.get("mention_text"), allow_generic=True)
        mention_type = (arguments.get("mention_type") or "").strip().lower()
        canonical_name = self._clean_identity(arguments.get("canonical_name"))
        if not mention_text or mention_type not in self.MENTION_TYPES:
            return
        key = (mention_text.lower(), mention_type, canonical_name.lower(), bool(arguments.get("is_consequential_character", False)))
        if key in self._seen_mention_keys:
            return
        self._seen_mention_keys.add(key)
        self.result["character_mentions"].append({
            "mention_text": mention_text,
            "mention_type": mention_type,
            "canonical_name": canonical_name,
            "is_consequential_character": bool(arguments.get("is_consequential_character", False)),
        })

    def add_event(self, arguments: Dict):
        description = (arguments.get("description") or "").strip()
        event_type = (arguments.get("type") or "").strip().lower()
        characters = self._clean_string_list(arguments.get("characters") or [], allow_generic=False, allow_pronouns=False)
        if not description:
            return
        if event_type not in self.EVENT_TYPES:
            event_type = "action"
        key = (description.lower(), tuple(char.lower() for char in characters), event_type)
        if key in self._seen_event_keys:
            return
        self._seen_event_keys.add(key)
        self.result["events"].append({
            "description": description,
            "characters": characters,
            "type": event_type,
        })

    def add_entity(self, arguments: Dict):
        name = (arguments.get("name") or "").strip()
        entity_type = (arguments.get("entity_type") or "").strip().lower()
        if not name or entity_type not in self.ENTITY_TYPES:
            return
        key = (name.lower(), entity_type)
        if key in self._seen_entity_keys:
            return
        self._seen_entity_keys.add(key)
        self.result["entities_present"].append({
            "name": name,
            "entity_type": entity_type,
        })

    def add_entity_description(self, arguments: Dict):
        entity_name = (arguments.get("entity_name") or "").strip()
        entity_type = (arguments.get("entity_type") or "").strip().lower()
        description = (arguments.get("description") or "").strip()
        description_type = (arguments.get("description_type") or "").strip().lower()
        if not entity_name or not description or entity_type not in self.ENTITY_TYPES or description_type not in self.DESCRIPTION_TYPES:
            return
        key = (entity_name.lower(), entity_type, description.lower(), description_type)
        if key in self._seen_description_keys:
            return
        self._seen_description_keys.add(key)
        self.result["entity_descriptions"].append({
            "entity_name": entity_name,
            "entity_type": entity_type,
            "description": description,
            "description_type": description_type,
        })

    def add_state_change(self, arguments: Dict):
        entity_name = (arguments.get("entity_name") or "").strip()
        entity_type = (arguments.get("entity_type") or "").strip().lower()
        attribute = (arguments.get("attribute") or "").strip()
        previous_state = (arguments.get("previous_state") or "").strip()
        new_state = (arguments.get("new_state") or "").strip()
        change_type = (arguments.get("change_type") or "").strip().lower()
        evidence = (arguments.get("evidence") or "").strip()
        if not entity_name or not attribute or not new_state or not evidence:
            return
        if entity_type not in self.ENTITY_TYPES or change_type not in self.CHANGE_TYPES:
            return
        key = (entity_name.lower(), entity_type, attribute.lower(), previous_state.lower(), new_state.lower(), change_type, evidence.lower())
        if key in self._seen_state_change_keys:
            return
        self._seen_state_change_keys.add(key)
        self.result["state_changes"].append({
            "entity_name": entity_name,
            "entity_type": entity_type,
            "attribute": attribute,
            "previous_state": previous_state,
            "new_state": new_state,
            "change_type": change_type,
            "evidence": evidence,
        })

    def add_relationship_change(self, arguments: Dict):
        source_entity = self._clean_identity(arguments.get("source_entity"), allow_generic=True)
        target_entity = self._clean_identity(arguments.get("target_entity"), allow_generic=True)
        relationship = (arguments.get("relationship") or "").strip()
        change = (arguments.get("change") or "").strip()
        evidence = (arguments.get("evidence") or "").strip()
        if not source_entity or not target_entity or not relationship or not change or not evidence:
            return
        key = (source_entity.lower(), target_entity.lower(), relationship.lower(), change.lower(), evidence.lower())
        if key in self._seen_relationship_keys:
            return
        self._seen_relationship_keys.add(key)
        self.result["relationship_changes"].append({
            "source_entity": source_entity,
            "target_entity": target_entity,
            "relationship": relationship,
            "change": change,
            "evidence": evidence,
        })

    def set_location(self, arguments: Dict):
        name = (arguments.get("name") or "").strip()
        entity_type = (arguments.get("entity_type") or "").strip().lower()
        if not name or entity_type != "location":
            return
        self.result["location"] = {
            "name": name,
            "entity_type": entity_type,
            "description": (arguments.get("description") or "").strip(),
        }

    def add_time_signal(self, arguments: Dict):
        signal = (arguments.get("value") or "").strip()
        if signal:
            self.result["time_signals"].append(signal)

    def add_alias_update(self, arguments: Dict):
        alias = self._clean_identity(arguments.get("alias"), allow_generic=False)
        canonical_name = self._clean_identity(arguments.get("canonical_name"))
        action = (arguments.get("action") or "").strip().lower()
        reasoning = (arguments.get("reasoning") or "").strip()
        if not alias or not canonical_name or not reasoning or action not in self.ALIAS_ACTIONS:
            return
        if alias.lower() == canonical_name.lower():
            return
        key = (alias.lower(), canonical_name.lower(), action)
        if key in self._seen_alias_update_keys:
            return
        self._seen_alias_update_keys.add(key)
        self.result["alias_updates"].append({
            "alias": alias,
            "canonical_name": canonical_name,
            "action": action,
            "reasoning": reasoning,
        })

    def reject_identity_candidate(self, arguments: Dict):
        candidate = self._clean_identity(arguments.get("candidate"), allow_generic=True)
        if not candidate:
            return
        lowered = candidate.lower()
        if lowered in self._seen_rejections:
            return
        self._seen_rejections.add(lowered)
        self.result["rejected_identity_candidates"].append(candidate)

    def build_result(self) -> Dict:
        built = deepcopy(self.result)
        built["_tool_runtime"] = deepcopy(self._tool_stats)
        return built

    def _snapshot_lengths(self) -> Dict[str, int]:
        return {
            "scene_summary": int(bool(self.result["scene_summary"])),
            "canonical_characters": len(self.result["canonical_characters"]),
            "character_mentions": len(self.result["character_mentions"]),
            "events": len(self.result["events"]),
            "entities_present": len(self.result["entities_present"]),
            "entity_descriptions": len(self.result["entity_descriptions"]),
            "state_changes": len(self.result["state_changes"]),
            "relationship_changes": len(self.result["relationship_changes"]),
            "location": int(bool(self.result["location"])),
            "time_signals": len(self.result["time_signals"]),
            "alias_updates": len(self.result["alias_updates"]),
            "rejected_identity_candidates": len(self.result["rejected_identity_candidates"]),
        }

    def _clean_identity(self, value: str | None, allow_generic: bool = False) -> str:
        cleaned = (value or "").strip()
        lowered = cleaned.lower()
        if not cleaned:
            return ""
        if lowered in self.FORBIDDEN_IDENTITY_LABELS or len(lowered) <= 1:
            return ""
        if not allow_generic and lowered in self.GENERIC_ALIAS_LABELS:
            return ""
        return cleaned

    def _clean_string_list(
        self,
        values: List[str],
        *,
        allow_generic: bool,
        allow_pronouns: bool,
        ensure_value: str = "",
    ) -> List[str]:
        output = []
        seen = set()
        for value in values or []:
            cleaned = (str(value) or "").strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if not allow_pronouns and (lowered in self.FORBIDDEN_IDENTITY_LABELS or len(lowered) <= 1):
                continue
            if not allow_generic and lowered in self.GENERIC_ALIAS_LABELS:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            output.append(cleaned)
        ensured = (ensure_value or "").strip()
        if ensured and ensured.lower() not in seen:
            output.insert(0, ensured)
        return output
