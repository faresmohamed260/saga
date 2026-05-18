"""Identity-focused scene analyzer for canonicals, mentions, and aliases."""

from typing import Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from analysis.tool_runtime import SceneToolRuntime
from infrastructure.llm_client import LLMClient


class IdentityAnalyzer:
    """
    Dedicated per-scene identity extractor.

    Focuses only on canonical characters, character mentions, alias updates,
    and clearly non-character rejections so identity quality can be tuned
    independently from the main scene-analysis model.
    """

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
    MENTION_TYPES = {"name", "title", "descriptor", "role"}

    def __init__(self, llm_client: Optional[LLMClient] = None, max_attempts: int = 2):
        self.llm = llm_client or LLMClient(mode=LLMClient.MODE_GPT_OSS)
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
                return self._normalize_response(response)

        return {
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
                return normalized
        return {
            "canonical_characters": [],
            "character_mentions": [],
            "alias_updates": [],
            "rejected_identity_candidates": [],
            "error": last_response.get("error") if isinstance(last_response, dict) else "unknown_error",
            "last_error": last_response.get("last_error") if isinstance(last_response, dict) else "",
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

        alias_context = [
            {
                "canonical_name": canonical_name,
                "aliases": aliases,
            }
            for canonical_name, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]
        local_evidence = normalize_evidence_bundle(local_evidence)

        return f"""
        Analyze ONLY the character identity layer for this scene.

        {retry_line}

        Rules:
        - Use only evidence from the scene and provided context
        - Treat local evidence as candidate evidence, not truth
        - Prefer validating or rejecting provided candidates rather than inventing new ones from raw text
        - Do not invent facts, characters, or aliases
        - Preserve known characters from the alias map whenever possible
        - A clear proper name should never be rejected as a non-character
        - Ambiguous humanlike or sentient role labels should stay as mentions if unresolved
        - Reject only clearly non-character or incidental labels such as scenery, objects, materials, prey animals, or background groups
        - Canonical characters should be conservative:
          - proper names are strong canonicals
          - stable role labels are acceptable if no name exists
          - temporary descriptors should usually stay mentions, not canonicals
        - character_mentions may contain descriptors, titles, and role labels
        - alias_updates should only be emitted when the scene clearly supports the mapping
        - Never use pronouns as canonical characters or aliases

        Return JSON:
        {{
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

        alias_context = [
            {"canonical_name": canonical_name, "aliases": aliases}
            for canonical_name, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
        ]
        local_evidence = normalize_evidence_bundle(local_evidence)

        return f"""
        Analyze ONLY the identity layer using tool calls.

        {retry_line}

        Do not return a final schema object. Return:
        {{
          "tool_calls": [
            {{"tool": "add_canonical_character", "arguments": {{"name": "...", "role": "", "is_new_character": false, "names_used": ["..."]}}}}
          ]
        }}

        Allowed tools:
        - add_canonical_character
        - add_character_mention
        - add_alias_update
        - reject_identity_candidate

        Rules:
        - Use local evidence as candidate evidence
        - Use filtered candidate_characters and candidate_aliases as your primary working set
        - Validate, refine, or reject candidates
        - Never turn pronouns into aliases
        - Never reject clear proper names as non-characters

        Current Alias Map:
        {alias_context}

        Local Evidence Bundle:
        {local_evidence}

        Rejected Identities So Far:
        {rejected_identities}

        Recent Context:
        {scene_context or "No additional context."}

        Scene:
        {scene_text}
        """

    def _normalize_response(self, response: Dict) -> Dict:
        return {
            "canonical_characters": self._normalize_canonical_characters(response.get("canonical_characters") or []),
            "character_mentions": self._normalize_character_mentions(response.get("character_mentions") or []),
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
            lowered = name.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            names_used = []
            used_seen = set()
            for alias in item.get("names_used") or []:
                cleaned = str(alias).strip()
                if not cleaned or self._is_forbidden_identity(cleaned):
                    continue
                alias_lower = cleaned.lower()
                if alias_lower in used_seen:
                    continue
                used_seen.add(alias_lower)
                names_used.append(cleaned)
            if lowered not in used_seen:
                names_used.insert(0, name)
            normalized.append({
                "name": name,
                "role": (item.get("role") or "").strip(),
                "is_new_character": bool(item.get("is_new_character", False)),
                "names_used": names_used,
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
            if not mention_text or mention_type not in self.MENTION_TYPES:
                continue
            if self._is_forbidden_identity(mention_text):
                continue
            if canonical_name and self._is_forbidden_identity(canonical_name):
                canonical_name = ""
            key = (mention_text.lower(), mention_type, canonical_name.lower(), bool(item.get("is_consequential_character", False)))
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "mention_text": mention_text,
                "mention_type": mention_type,
                "canonical_name": canonical_name,
                "is_consequential_character": bool(item.get("is_consequential_character", False)),
            })
        return normalized

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

    def _normalize_identity_candidates(self, candidates: List[str]) -> List[str]:
        if not isinstance(candidates, list):
            return []
        normalized = []
        seen = set()
        for item in candidates:
            cleaned = str(item).strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned)
        return normalized

    def _is_forbidden_identity(self, value: str) -> bool:
        cleaned = (value or "").strip().lower()
        return cleaned in self.FORBIDDEN_IDENTITY_LABELS or len(cleaned) <= 1

    def _validate_response(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("canonical_characters"), list)
            and isinstance(response.get("character_mentions"), list)
            and isinstance(response.get("alias_updates"), list)
            and isinstance(response.get("rejected_identity_candidates"), list)
        )

    def _validate_tool_response(self, response: Dict) -> bool:
        return isinstance(response, dict) and isinstance(response.get("tool_calls"), list)
