"""Model-backed refinement for local evidence bundles.

This layer sits after deterministic evidence filtering and before the larger
scene/identity analysis calls. It uses small local-model calls for bounded
validation decisions rather than asking a larger model to discover everything
from scratch.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

from analysis.evidence_schema import normalize_evidence_bundle
from analysis.microtasks.task_registry import MicroTaskRegistry
from infrastructure.local_semantic_client import LocalSemanticClient

OBVIOUS_FRAGMENT_PREFIXES = {
    "when",
    "while",
    "after",
    "before",
    "because",
    "if",
    "as",
    "then",
}

HONORIFIC_TOKENS = {"mr", "mrs", "ms", "dr", "sir", "lady", "lord"}

ENTITY_HINT_TYPES = {
    "court": "location",
    "drive": "location",
    "street": "location",
    "road": "location",
    "lane": "location",
    "house": "location",
    "hall": "location",
    "tower": "location",
    "castle": "location",
    "kingdom": "location",
    "city": "location",
    "school": "location",
    "ministry": "object",
    "order": "object",
}


class SemanticEvidenceRefiner:
    """Refine candidate characters/entities using bounded local semantic tasks."""

    def __init__(
        self,
        task_registry: Optional[MicroTaskRegistry] = None,
        client_factory=None,
        enabled: bool = True,
    ) -> None:
        self.task_registry = task_registry or MicroTaskRegistry()
        self.client_factory = client_factory or (lambda config: LocalSemanticClient(model=config.model, timeout=config.timeout))
        self.enabled = enabled

    def refine(self, bundle: Dict, scene_text: str) -> Dict:
        bundle = normalize_evidence_bundle(bundle)
        if not self.enabled:
            bundle["metadata"]["semantic_refinement"] = {"enabled": False}
            return bundle

        refined = deepcopy(bundle)
        normalized_candidates = []
        surface_rejections = []
        for item in refined.get("candidate_characters") or []:
            normalized = self._normalize_candidate_surface_form(item, scene_text)
            if normalized.get("decision") == "reject":
                surface_rejections.append({
                    "candidate": item.get("name", ""),
                    "reason": normalized.get("reason", ""),
                    "task": "normalize_candidate_surface_form",
                })
                continue
            if normalized.get("normalized_name"):
                item = {
                    **item,
                    "name": normalized["normalized_name"],
                }
            item["surface_form_verdict"] = normalized
            normalized_candidates.append(item)

        kept_characters = []
        rejected_characters = []
        promoted_entities = []
        for item in normalized_candidates:
            obvious_fragment_reason = self._obvious_fragment_reason(item.get("name", ""))
            if obvious_fragment_reason:
                rejected_characters.append({
                    "candidate": item.get("name", ""),
                    "reason": obvious_fragment_reason,
                    "task": "obvious_fragment_guardrail",
                })
                continue

            verdict = self._classify_candidate_identity_type(item, scene_text)
            decision = verdict.get("decision", "character")
            hinted_entity_type = self._hinted_entity_type(item.get("name", ""))
            if decision == "character" and hinted_entity_type and not self._looks_like_role_character_label(item.get("name", "")):
                decision = "entity"
                verdict = {
                    **verdict,
                    "decision": "entity",
                    "entity_type": hinted_entity_type,
                    "reason": "entity_hint_guardrail",
                    "confidence": "guardrail",
                }
            if decision == "character":
                validation = self._validate_character_candidate(item, scene_text)
                if validation.get("keep", True):
                    item["semantic_verdict"] = {
                        **verdict,
                        "validation": validation,
                    }
                    kept_characters.append(item)
                else:
                    if hinted_entity_type:
                        promoted_entities.append({
                            "name": item.get("name", ""),
                            "entity_type": hinted_entity_type,
                            "evidence_mentions": item.get("evidence_mentions", []),
                            "source": "semantic_validation_retyped_character_candidate",
                            "score": item.get("score", 0.0),
                            "semantic_verdict": {
                                **verdict,
                                "validation": validation,
                            },
                        })
                    else:
                        rejected_characters.append({
                            "candidate": item.get("name", ""),
                            "reason": validation.get("reason", ""),
                            "task": "validate_character_candidate",
                        })
            elif decision == "entity":
                promoted_entities.append({
                    "name": item.get("name", ""),
                    "entity_type": verdict.get("entity_type", "object"),
                    "evidence_mentions": item.get("evidence_mentions", []),
                    "source": "semantic_retyped_character_candidate",
                    "score": item.get("score", 0.0),
                    "semantic_verdict": verdict,
                })
            else:
                rejected_characters.append({
                    "candidate": item.get("name", ""),
                    "reason": verdict.get("reason", ""),
                    "task": "classify_candidate_identity_type",
                })

        kept_entities = list(promoted_entities)
        rejected_entities = []
        for item in (refined.get("candidate_entities") or []) + promoted_entities:
            verdict = self._validate_entity_candidate(item, scene_text)
            if verdict.get("keep", True):
                item["semantic_verdict"] = verdict
                if not any(existing.get("name", "").lower() == item.get("name", "").lower() and existing.get("entity_type") == item.get("entity_type") for existing in kept_entities):
                    kept_entities.append(item)
            else:
                rejected_entities.append({
                    "candidate": item.get("name", ""),
                    "reason": verdict.get("reason", ""),
                    "task": "validate_entity_candidate",
                })

        refined["candidate_characters"] = kept_characters
        refined["candidate_entities"] = kept_entities
        refined.setdefault("metadata", {})
        refined["metadata"]["semantic_refinement"] = {
            "enabled": True,
            "characters_kept": len(kept_characters),
            "characters_rejected": len(rejected_characters) + len(surface_rejections),
            "entities_kept": len(kept_entities),
            "entities_rejected": len(rejected_entities),
            "characters_retyped_to_entities": len(promoted_entities),
            "rejections": surface_rejections + rejected_characters + rejected_entities,
        }
        return refined

    def _normalize_candidate_surface_form(self, candidate: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("normalize_candidate_surface_form")
        client = self.client_factory(config)
        prompt = f"""
Task: clean or reject this extracted candidate surface form.

Return JSON:
{{
  "decision": "keep",
  "normalized_name": "High Lady",
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- "keep" if the surface form is already good
- "normalize" if the extracted text includes an obvious malformed leading/trailing fragment and you can clean it safely
- "reject" if the extracted text is too malformed or untrustworthy to keep
- do not invent a new name not supported by the candidate text
- examples of malformed fragments: temporal/opening words accidentally attached to a name, broken parser fragments like 'When Mr'

Candidate:
name={candidate.get("name", "")}
mentions={candidate.get("evidence_mentions", [])}
source={candidate.get("source", "")}

Scene:
{scene_text[:2000]}
"""
        result = client.generate_json(prompt, validator=self._validate_surface_verdict)
        if "error" in result:
            return {"decision": "keep", "normalized_name": candidate.get("name", ""), "reason": "surface_normalization_unavailable", "confidence": "fallback"}
        if result.get("decision") == "normalize" and not result.get("normalized_name"):
            result["decision"] = "reject"
        if result.get("decision") == "keep" and not result.get("normalized_name"):
            result["normalized_name"] = candidate.get("name", "")
        if result.get("decision") in {"keep", "normalize"}:
            safe_name = self._safe_surface_name(candidate, result.get("normalized_name", ""))
            if not safe_name:
                return {
                    "decision": "keep",
                    "normalized_name": candidate.get("name", ""),
                    "reason": "unsafe_model_normalization_ignored",
                    "confidence": "guardrail",
                }
            result["normalized_name"] = safe_name
        return result

    def _classify_candidate_identity_type(self, candidate: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("classify_candidate_identity_type")
        client = self.client_factory(config)
        prompt = f"""
Task: classify this candidate as one of:
- "character"
- "entity"
- "reject"

If the answer is "entity", also provide the best entity_type:
- location
- object
- creature
- character

Return JSON:
{{
  "decision": "character",
  "entity_type": "character",
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- choose "character" only for a consequential sentient agent or durable person-like role identity
- choose "entity" for places, organizations, courts, houses, streets, artifacts, creatures, and non-sentient world items
- choose "reject" for malformed fragments, weak parser artifacts, or generic non-useful references
- do not be generous; prefer entity or reject over a wrong character label

Candidate:
name={candidate.get("name", "")}
mentions={candidate.get("evidence_mentions", [])}
source={candidate.get("source", "")}

Scene:
{scene_text[:3000]}
"""
        result = client.generate_json(prompt, validator=self._validate_identity_type_verdict)
        if "error" in result:
            return {"decision": "character", "entity_type": "character", "reason": "semantic_classification_unavailable", "confidence": "fallback"}
        return result

    def _validate_character_candidate(self, candidate: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("validate_character_candidate")
        client = self.client_factory(config)
        prompt = f"""
Task: validate whether this candidate should remain a consequential character candidate.

Return JSON:
{{
  "keep": true,
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep true only if the candidate appears to be a consequential character or durable role identity
- keep false for obvious noise, background references, or generic labels
- do not overthink; make a bounded local decision from the evidence

Candidate:
name={candidate.get("name", "")}
mentions={candidate.get("evidence_mentions", [])}
source={candidate.get("source", "")}

Scene:
{scene_text[:3000]}
"""
        result = client.generate_json(prompt, validator=self._validate_verdict)
        if "error" in result:
            return {"keep": True, "reason": "semantic_validation_unavailable", "confidence": "fallback"}
        return result

    def _validate_entity_candidate(self, candidate: Dict, scene_text: str) -> Dict:
        config = self.task_registry.get("validate_entity_candidate")
        client = self.client_factory(config)
        prompt = f"""
Task: validate whether this non-character entity candidate should remain in the scene evidence.

Return JSON:
{{
  "keep": true,
  "reason": "short grounded reason",
  "confidence": "high"
}}

Rules:
- keep true only if the candidate looks narratively relevant for canon tracking
- keep false for incidental scenery or weak background noise
- do not change the candidate type; only validate whether to keep it

Candidate:
name={candidate.get("name", "")}
entity_type={candidate.get("entity_type", "")}
mentions={candidate.get("evidence_mentions", [])}
source={candidate.get("source", "")}

Scene:
{scene_text[:3000]}
"""
        result = client.generate_json(prompt, validator=self._validate_verdict)
        if "error" in result:
            return {"keep": True, "reason": "semantic_validation_unavailable", "confidence": "fallback"}
        return result

    def _validate_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("keep"), bool)
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _validate_identity_type_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and response.get("decision") in {"character", "entity", "reject"}
            and response.get("entity_type") in {"character", "location", "object", "creature"}
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _validate_surface_verdict(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and response.get("decision") in {"keep", "normalize", "reject"}
            and isinstance(response.get("normalized_name"), str)
            and isinstance(response.get("reason"), str)
            and isinstance(response.get("confidence"), str)
        )

    def _safe_surface_name(self, candidate: Dict, proposed_name: str) -> str:
        proposed = (proposed_name or "").strip()
        if not proposed:
            return ""
        proposed_lower = proposed.lower().strip(".")
        if proposed_lower in HONORIFIC_TOKENS:
            return ""
        sources = [
            (candidate.get("name") or "").strip(),
            *[(item or "").strip() for item in (candidate.get("evidence_mentions") or [])],
        ]
        proposed_tokens = {token for token in proposed.lower().replace("-", " ").split() if token}
        if not proposed_tokens:
            return ""
        for source in sources:
            source_tokens = {token for token in source.lower().replace("-", " ").split() if token}
            if not source_tokens:
                continue
            if proposed.lower() == source.lower():
                return proposed
            if proposed_tokens.issubset(source_tokens):
                return proposed
            if source_tokens.issubset(proposed_tokens):
                return source
        return ""

    def _obvious_fragment_reason(self, name: str) -> str:
        tokens = [token for token in (name or "").strip().replace("-", " ").split() if token]
        if len(tokens) < 2:
            return ""
        if tokens[0].lower() in OBVIOUS_FRAGMENT_PREFIXES:
            return "obvious_fragment_prefix"
        if tokens[-1].lower() in {"mr", "mrs", "ms", "dr", "sir"}:
            return "obvious_fragment_suffix"
        return ""

    def _hinted_entity_type(self, name: str) -> str:
        tokens = [token.lower() for token in (name or "").strip().replace("-", " ").split() if token]
        for token in reversed(tokens):
            if token in ENTITY_HINT_TYPES:
                return ENTITY_HINT_TYPES[token]
        return ""

    def _looks_like_role_character_label(self, name: str) -> bool:
        tokens = [token for token in (name or "").strip().replace("-", " ").split() if token]
        if len(tokens) != 2:
            return False
        first, second = tokens[0].lower(), tokens[1].lower()
        return first in {"high", "young", "old", "lady", "lord", "professor", "captain"} and second not in ENTITY_HINT_TYPES
