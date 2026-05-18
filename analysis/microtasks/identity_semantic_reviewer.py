"""Post-analysis semantic review for identity outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from analysis.microtasks.task_registry import MicroTaskRegistry
from infrastructure.local_semantic_client import LocalSemanticClient

ROLE_LABEL_TOKENS = {
    "high",
    "lady",
    "lord",
    "king",
    "queen",
    "prince",
    "princess",
    "general",
    "captain",
    "professor",
    "commander",
}


class IdentitySemanticReviewer:
    """Use bounded local semantic tasks to review identity decisions."""

    def __init__(
        self,
        task_registry: Optional[MicroTaskRegistry] = None,
        client_factory=None,
        enabled: bool = True,
    ) -> None:
        self.task_registry = task_registry or MicroTaskRegistry()
        self.client_factory = client_factory or (lambda config: LocalSemanticClient(model=config.model, timeout=config.timeout))
        self.enabled = enabled

    def review(
        self,
        scene_result: Dict,
        scene_text: str,
        local_evidence: Optional[Dict] = None,
        pov_anchor: str = "",
    ) -> Dict:
        reviewed = deepcopy(scene_result)
        if not self.enabled:
            reviewed["identity_semantic_review"] = {"enabled": False}
            return reviewed

        evidence_bundle = normalize_evidence_bundle(local_evidence)
        candidate_names = {
            (item.get("name") or "").strip().lower()
            for item in evidence_bundle.get("candidate_characters") or []
            if (item.get("name") or "").strip()
        }

        canonical_reviews = []
        kept_characters = []
        promoted_rejections = list(reviewed.get("rejected_identity_candidates") or [])
        seen_rejections = {item.lower() for item in promoted_rejections}

        for item in reviewed.get("canonical_characters") or []:
            item = self._apply_pov_anchor(item, scene_text, pov_anchor)
            verdict = self._validate_canonical_character(item, scene_text)
            canonical_reviews.append({"item": deepcopy(item), "verdict": deepcopy(verdict)})
            name = (item.get("name") or "").strip()
            if verdict.get("keep", True) or self._looks_like_proper_name(name) or name.lower() in candidate_names:
                kept_characters.append({**item, "semantic_review": verdict})
            elif name and name.lower() not in seen_rejections:
                promoted_rejections.append(name)
                seen_rejections.add(name.lower())

        alias_reviews = []
        kept_alias_updates = []
        for item in reviewed.get("alias_updates") or []:
            verdict = self._score_alias_merge(item, scene_text)
            alias_reviews.append({"item": deepcopy(item), "verdict": deepcopy(verdict)})
            if verdict.get("keep", True):
                kept_alias_updates.append({**item, "semantic_review": verdict})

        reviewed["canonical_characters"] = kept_characters
        reviewed["alias_updates"] = kept_alias_updates
        reviewed["rejected_identity_candidates"] = promoted_rejections
        reviewed["identity_semantic_review"] = {
            "enabled": True,
            "pov_anchor": pov_anchor,
            "canonical_characters_before": len(scene_result.get("canonical_characters") or []),
            "canonical_characters_after": len(kept_characters),
            "alias_updates_before": len(scene_result.get("alias_updates") or []),
            "alias_updates_after": len(kept_alias_updates),
            "canonical_reviews": canonical_reviews,
            "alias_reviews": alias_reviews,
        }
        return reviewed

    def _validate_canonical_character(self, character: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("validate_character_candidate")
        client = self.client_factory(config)
        prompt = f"""
Task: validate whether this scene-level canonical character should remain a consequential character identity.

Return JSON:
{{
  "keep": true,
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep clear named or stable role characters that matter in the scene
- reject weak, overly generic, or accidental canonicals
- be conservative about removing named people

Character candidate:
name={character.get("name", "")}
role={character.get("role", "")}
names_used={character.get("names_used", [])}

Scene:
{scene_text[:1800]}
"""
        result = client.generate_json(prompt, validator=self._validate_keep_verdict)
        if "error" in result:
            return {"keep": True, "reason": "canonical_review_unavailable", "confidence": "fallback"}
        return result

    def _score_alias_merge(self, alias_update: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("score_alias_merge")
        client = self.client_factory(config)
        prompt = f"""
Task: validate whether this alias mapping is well-supported by the scene.

Return JSON:
{{
  "keep": true,
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep only if the alias clearly refers to the canonical character in this scene
- reject weak, generic, or uncertain alias mappings
- be conservative with title/descriptor mappings

Alias update candidate:
alias={alias_update.get("alias", "")}
canonical_name={alias_update.get("canonical_name", "")}
action={alias_update.get("action", "")}
reasoning={alias_update.get("reasoning", "")}

Scene:
{scene_text[:1800]}
"""
        result = client.generate_json(prompt, validator=self._validate_keep_verdict)
        if "error" in result:
            return {"keep": True, "reason": "alias_review_unavailable", "confidence": "fallback"}
        return result

    def _apply_pov_anchor(self, character: Dict, scene_text: str, pov_anchor: str) -> Dict:
        anchor = (pov_anchor or "").strip()
        name = (character.get("name") or "").strip()
        if not anchor or not name:
            return character
        if name.lower() == anchor.lower():
            return character
        if self._looks_like_named_identity(name):
            return character
        if not self._looks_like_role_label(name):
            return character

        verdict = self._score_alias_merge(
            {
                "alias": name,
                "canonical_name": anchor,
                "action": "map_alias",
                "reasoning": "POV anchor remap candidate",
            },
            scene_text,
        )
        if not verdict.get("keep", True):
            return character

        names_used = list(character.get("names_used") or [])
        if name and name.lower() not in {item.lower() for item in names_used}:
            names_used.append(name)
        return {
            **character,
            "name": anchor,
            "names_used": names_used or [anchor, name],
            "pov_anchor_remap": verdict,
        }

    def _validate_keep_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("keep"), bool)
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _looks_like_proper_name(self, value: str) -> bool:
        tokens = [token for token in (value or "").strip().split() if token]
        if len(tokens) < 2:
            return False
        return all(token[:1].isupper() for token in tokens if token[:1].isalpha())

    def _looks_like_named_identity(self, value: str) -> bool:
        if self._looks_like_role_label(value):
            return False
        tokens = [token for token in (value or "").strip().split() if token]
        if not tokens:
            return False
        if len(tokens) == 1:
            token = tokens[0]
            return token[:1].isupper() and token.lower() not in ROLE_LABEL_TOKENS
        return self._looks_like_proper_name(value)

    def _looks_like_role_label(self, value: str) -> bool:
        tokens = [token.lower() for token in (value or "").strip().replace("-", " ").split() if token]
        return bool(tokens) and any(token in ROLE_LABEL_TOKENS for token in tokens)
