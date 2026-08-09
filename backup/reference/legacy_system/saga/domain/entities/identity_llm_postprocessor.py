"""Conservative LLM review over deterministic identity-resolution leftovers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from saga.domain.canon_normalization import CanonicalEntityNormalizer
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client
from saga.services.web_entity_hint_service import WebEntityHintService


class IdentityLLMPostProcessor:
    """Review residual identity ambiguity after deterministic resolution."""

    MAX_REVIEW_CANDIDATES = 64
    REVIEW_BATCH_SIZE = 12

    def __init__(
        self,
        llm_client: Optional[ReasoningClient] = None,
        enabled: bool = True,
        web_hint_service: Optional[WebEntityHintService] = None,
        web_hints_enabled: bool = False,
    ) -> None:
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS)
        self.enabled = enabled
        self.normalizer = CanonicalEntityNormalizer()
        self.web_hint_service = web_hint_service or WebEntityHintService()
        self.web_hints_enabled = web_hints_enabled

    def review(
        self,
        identity_result: Dict[str, Any],
        detailed_result: Dict[str, Any],
        *,
        series_id: str = "",
    ) -> Dict[str, Any]:
        reviewed = deepcopy(identity_result or {})
        detailed = detailed_result or {}
        anchor_entities = self._build_anchor_entities(detailed)
        heuristic_hints = self._load_heuristic_hints(series_id, reviewed, detailed)
        if not self.enabled:
            reviewed["llm_post_review"] = {
                "enabled": False,
                "heuristic_hints_used": sorted(heuristic_hints),
                "anchor_entities": sorted(anchor_entities),
            }
            return reviewed

        candidates = self._build_candidates(reviewed, detailed, heuristic_hints=heuristic_hints, anchor_entities=anchor_entities)
        if not candidates:
            self._apply_anchor_entities(reviewed, anchor_entities)
            self._finalize_identity_map(reviewed, heuristic_hints=heuristic_hints, anchor_entities=anchor_entities)
            reviewed["llm_post_review"] = {
                "enabled": True,
                "candidates_reviewed": 0,
                "applied_decisions": [],
                "heuristic_hints_used": sorted(heuristic_hints),
                "anchor_entities": sorted(anchor_entities),
            }
            return reviewed

        applied: List[Dict[str, Any]] = []
        errors: List[str] = []
        reviewed_count = 0
        for start in range(0, len(candidates), self.REVIEW_BATCH_SIZE):
            batch = candidates[start:start + self.REVIEW_BATCH_SIZE]
            decision_result = self.llm.generate_json(
                self._build_prompt(reviewed, batch, heuristic_hints=heuristic_hints),
                strict=True,
                validator=lambda payload, cand=batch: self._validate_response(payload, cand),
            )
            reviewed_count += len(batch)
            if not isinstance(decision_result, dict) or "error" in decision_result:
                errors.append(decision_result.get("error") if isinstance(decision_result, dict) else "unknown_error")
                continue
            applied.extend(self._apply_decisions(reviewed, batch, decision_result.get("decisions") or []))

        self._apply_anchor_entities(reviewed, anchor_entities)
        self._finalize_identity_map(reviewed, heuristic_hints=heuristic_hints, anchor_entities=anchor_entities)
        reviewed["llm_post_review"] = {
            "enabled": True,
            "candidates_reviewed": reviewed_count,
            "applied_decisions": applied,
            "heuristic_hints_used": sorted(heuristic_hints),
            "anchor_entities": sorted(anchor_entities),
        }
        if errors:
            reviewed["llm_post_review"]["errors"] = errors
        return reviewed

    def _load_heuristic_hints(
        self,
        series_id: str,
        identity_result: Dict[str, Any],
        detailed_result: Dict[str, Any],
    ) -> Dict[str, Dict[str, str]]:
        if not self.web_hints_enabled or not series_id:
            return {}
        return self.web_hint_service.load_series_hints(
            series_id,
            self._candidate_names_for_hints(identity_result, detailed_result),
        )

    def _candidate_names_for_hints(self, identity_result: Dict[str, Any], detailed_result: Dict[str, Any]) -> List[str]:
        names: List[str] = []
        for canonical_name, aliases in (identity_result.get("alias_map") or {}).items():
            names.append(canonical_name)
            names.extend(aliases or [])
        for item in (((detailed_result.get("evaluation_summary") or {}).get("top_false_positive_canonicals")) or []):
            names.append(str(item.get("canonical_name") or "").strip())
        for item in (((detailed_result.get("evaluation_summary") or {}).get("temporary_candidates_diagnostics")) or []):
            names.append(str(item.get("name") or "").strip())
        for item in (((detailed_result.get("evaluation_summary") or {}).get("top_remaining_likely_person_supporting_entities")) or []):
            names.append(str(item.get("name") or "").strip())
        names.extend(identity_result.get("rejected_non_characters") or [])
        return [name for name in names if str(name or "").strip()]

    def _build_anchor_entities(self, detailed_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        anchor_entities: Dict[str, Dict[str, Any]] = {}
        for collection_name in ("canonical_characters", "temporary_person_candidates"):
            payload = detailed_result.get(collection_name) or {}
            for entity in payload.values():
                if not isinstance(entity, dict):
                    continue
                canonical_name = str(entity.get("canonical_name") or "").strip()
                aliases = [str(item).strip() for item in (entity.get("aliases") or []) if str(item).strip()]
                mention_count = int(entity.get("mention_count") or 0)
                person_likelihood = float(entity.get("max_person_likelihood") or 0.0)
                model_person_hits = int(entity.get("model_person_hits") or 0)
                honorific_backed = bool(entity.get("honorific_backed"))
                preferred_name = self._preferred_anchor_name(canonical_name, aliases)
                if not preferred_name:
                    continue
                if not self._should_protect_anchor(
                    preferred_name,
                    mention_count=mention_count,
                    person_likelihood=person_likelihood,
                    model_person_hits=model_person_hits,
                    honorific_backed=honorific_backed,
                ):
                    continue
                anchor_entities[preferred_name] = {
                    "preferred_name": preferred_name,
                    "aliases": sorted({preferred_name, *aliases, canonical_name}, key=str.lower),
                    "mention_count": mention_count,
                    "person_likelihood": person_likelihood,
                    "model_person_hits": model_person_hits,
                    "honorific_backed": honorific_backed,
                    "source_bucket": collection_name,
                }
        return anchor_entities

    def _preferred_anchor_name(self, canonical_name: str, aliases: List[str]) -> str:
        options = [canonical_name, *aliases]
        cleaned = [self.normalizer.canonicalize_candidate_name(item) for item in options if str(item or "").strip()]
        cleaned = [item for item in cleaned if item and self.normalizer.looks_like_character_name(item)]
        if not cleaned:
            return ""
        return self.normalizer.choose_canonical_name(cleaned)

    def _should_protect_anchor(
        self,
        name: str,
        *,
        mention_count: int,
        person_likelihood: float,
        model_person_hits: int,
        honorific_backed: bool,
    ) -> bool:
        if not name or not self.normalizer.looks_like_character_name(name):
            return False
        token_count = len(name.split())
        if token_count >= 2:
            return mention_count >= 3 or person_likelihood >= 0.74 or model_person_hits >= 1 or honorific_backed
        return mention_count >= 20 or person_likelihood >= 0.92 or model_person_hits >= 5

    def _build_candidates(
        self,
        identity_result: Dict[str, Any],
        detailed_result: Dict[str, Any],
        *,
        heuristic_hints: Dict[str, Dict[str, str]],
        anchor_entities: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        alias_map = identity_result.get("alias_map") or {}
        candidate_map: Dict[str, Dict[str, Any]] = {}
        canonical_names = sorted(alias_map.keys(), key=str.lower)

        for item in (((detailed_result.get("evaluation_summary") or {}).get("top_false_positive_canonicals")) or []):
            name = str(item.get("canonical_name") or "").strip()
            if not name:
                continue
            candidate_map[name.lower()] = {
                "name": name,
                "candidate_type": "suspicious_canonical",
                "suggested_targets": self._suggest_targets(name, canonical_names, exclude=name),
                "metrics": {
                    "character_score": item.get("character_score", 0.0),
                    "non_character_score": item.get("non_character_score", 0.0),
                    "reason": item.get("reason", ""),
                },
            }

        temporary_payload = detailed_result.get("temporary_person_candidates") or {}
        for item in (((detailed_result.get("evaluation_summary") or {}).get("temporary_candidates_diagnostics")) or []):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            payload = self._find_character_payload(temporary_payload, name)
            candidate_map[name.lower()] = {
                "name": name,
                "candidate_type": "temporary_person",
                "aliases": sorted(set(payload.get("aliases") or [])) if payload else [],
                "suggested_targets": self._suggest_targets(name, canonical_names),
                "metrics": {
                    "mention_count": item.get("mention_count", 0),
                    "max_person_likelihood": item.get("max_person_likelihood", 0.0),
                    "model_person_hits": item.get("model_person_hits", 0),
                    "honorific_backed": bool(item.get("honorific_backed")),
                },
            }

        for item in (((detailed_result.get("evaluation_summary") or {}).get("top_remaining_likely_person_supporting_entities")) or []):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            candidate_map.setdefault(
                name.lower(),
                {
                    "name": name,
                    "candidate_type": "supporting_person",
                    "suggested_targets": self._suggest_targets(name, canonical_names),
                    "metrics": {
                        "mention_count": item.get("mention_count", 0),
                        "character_score": item.get("character_score", 0.0),
                        "non_character_score": item.get("non_character_score", 0.0),
                    },
                },
            )

        alias_history = identity_result.get("alias_history") or []
        for item in alias_history:
            alias_name = str(item.get("alias_name") or "").strip()
            canonical_name = str(item.get("canonical_name") or "").strip()
            if not alias_name or not canonical_name:
                continue
            normalized_alias = self.normalizer.canonicalize_candidate_name(alias_name)
            if normalized_alias and normalized_alias.lower() == canonical_name.lower():
                continue
            candidate_map.setdefault(
                alias_name.lower(),
                {
                    "name": alias_name,
                    "candidate_type": "alias_variant",
                    "suggested_targets": self._suggest_targets(alias_name, canonical_names, exclude=alias_name) or [canonical_name],
                    "metrics": {
                        "canonical_name": canonical_name,
                        "normalized_alias": normalized_alias,
                    },
                },
            )

        for canonical_name, aliases in alias_map.items():
            normalized_canonical = self.normalizer.canonicalize_candidate_name(canonical_name)
            if not normalized_canonical or normalized_canonical.lower() != canonical_name.lower():
                candidate_map.setdefault(
                    canonical_name.lower(),
                    {
                        "name": canonical_name,
                        "candidate_type": "noisy_exported_canonical",
                        "suggested_targets": self._suggest_targets(canonical_name, canonical_names, exclude=canonical_name),
                        "metrics": {
                            "normalized_name": normalized_canonical,
                            "alias_count": len(aliases or []),
                        },
                    },
                )
            for alias_name in aliases or []:
                alias_name = str(alias_name or "").strip()
                if not alias_name or alias_name.lower() == canonical_name.lower():
                    continue
                normalized_alias = self.normalizer.canonicalize_candidate_name(alias_name)
                if normalized_alias and normalized_alias.lower() == canonical_name.lower():
                    continue
                if self.normalizer.is_bad_alias_like_name(alias_name) or not normalized_alias or normalized_alias.lower() != alias_name.lower():
                    candidate_map.setdefault(
                        alias_name.lower(),
                        {
                            "name": alias_name,
                            "candidate_type": "noisy_exported_alias",
                            "suggested_targets": self._suggest_targets(alias_name, canonical_names, exclude=alias_name) or [canonical_name],
                            "metrics": {
                                "canonical_name": canonical_name,
                                "normalized_alias": normalized_alias,
                            },
                        },
                    )

        for rejected_name in identity_result.get("rejected_non_characters") or []:
            rejected_name = str(rejected_name or "").strip()
            normalized_rejected = self.normalizer.canonicalize_candidate_name(rejected_name)
            if not rejected_name or not normalized_rejected:
                continue
            if not self.normalizer.looks_like_character_name(normalized_rejected):
                continue
            candidate_map.setdefault(
                rejected_name.lower(),
                {
                    "name": rejected_name,
                    "candidate_type": "rejected_reconsideration",
                    "suggested_targets": self._suggest_targets(rejected_name, canonical_names, exclude=rejected_name),
                    "metrics": {
                        "normalized_name": normalized_rejected,
                    },
                },
            )

        for canonical_name in canonical_names:
            hint = heuristic_hints.get(self.normalizer.normalized_entity_key(canonical_name)) or {}
            if hint.get("entity_type") in {"location", "object", "creature"}:
                candidate_map.setdefault(
                    canonical_name.lower(),
                    {
                        "name": canonical_name,
                        "candidate_type": "heuristic_non_character",
                        "suggested_targets": self._suggest_targets(canonical_name, canonical_names, exclude=canonical_name),
                        "metrics": {
                            "entity_type": hint.get("entity_type", ""),
                            "matched_title": hint.get("matched_title", ""),
                            "confidence": hint.get("confidence", ""),
                            "categories": hint.get("categories", ""),
                        },
                    },
                )

        for anchor_name, anchor in anchor_entities.items():
            if anchor_name in alias_map:
                continue
            candidate_map.setdefault(
                anchor_name.lower(),
                {
                    "name": anchor_name,
                    "candidate_type": "anchor_inventory",
                    "aliases": list(anchor.get("aliases") or []),
                    "suggested_targets": self._suggest_targets(anchor_name, canonical_names),
                    "metrics": {
                        "mention_count": anchor.get("mention_count", 0),
                        "person_likelihood": anchor.get("person_likelihood", 0.0),
                        "model_person_hits": anchor.get("model_person_hits", 0),
                        "source_bucket": anchor.get("source_bucket", ""),
                    },
                },
            )

        candidates = list(candidate_map.values())
        candidates.sort(
            key=lambda item: (
                self._candidate_priority(item.get("candidate_type", "")),
                -float(item.get("metrics", {}).get("mention_count", 0) or 0),
                -float(item.get("metrics", {}).get("character_score", 0.0) or 0.0),
                item["name"].lower(),
            )
        )
        return candidates[: self.MAX_REVIEW_CANDIDATES]

    def _candidate_priority(self, candidate_type: str) -> int:
        order = {
            "heuristic_non_character": 0,
            "anchor_inventory": 1,
            "suspicious_canonical": 2,
            "noisy_exported_canonical": 3,
            "noisy_exported_alias": 4,
            "alias_variant": 5,
            "temporary_person": 6,
            "rejected_reconsideration": 7,
            "supporting_person": 8,
        }
        return order.get(str(candidate_type or ""), 9)

    def _find_character_payload(self, payload: Dict[str, Dict[str, Any]], name: str) -> Dict[str, Any]:
        for item in payload.values():
            if str(item.get("canonical_name") or "").strip().lower() == name.lower():
                return item
        return {}

    def _suggest_targets(self, name: str, canonical_names: List[str], exclude: str = "") -> List[str]:
        suggestions: List[str] = []
        normalized = self.normalizer.normalized_entity_key(name)
        name_tokens = [token.lower() for token in name.replace("-", " ").split() if token]
        for canonical in canonical_names:
            if exclude and canonical.lower() == exclude.lower():
                continue
            canonical_normalized = self.normalizer.normalized_entity_key(canonical)
            canonical_tokens = [token.lower() for token in canonical.replace("-", " ").split() if token]
            if normalized and normalized == canonical_normalized:
                suggestions.append(canonical)
                continue
            if len(name_tokens) == 1 and name_tokens[0] in canonical_tokens:
                suggestions.append(canonical)
                continue
            if len(canonical_tokens) == 1 and canonical_tokens[0] in name_tokens:
                suggestions.append(canonical)
                continue
        deduped: List[str] = []
        seen = set()
        for item in suggestions:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped[:5]

    def _build_prompt(
        self,
        identity_result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        *,
        heuristic_hints: Dict[str, Dict[str, str]],
    ) -> str:
        canonicals = sorted((identity_result.get("alias_map") or {}).keys(), key=str.lower)
        rendered_candidates = []
        for candidate in candidates:
            rendered = dict(candidate)
            hint = heuristic_hints.get(self.normalizer.normalized_entity_key(candidate.get("name", ""))) or {}
            if hint:
                rendered["heuristic_hint"] = hint
            rendered_candidates.append(rendered)
        return (
            "You are reviewing residual identity ambiguity after a deterministic book-identity resolver.\n"
            "The deterministic resolver already processed the full series/books supplied to the encoder, not a single book in isolation.\n"
            "Be conservative. Prefer keeping the deterministic result unless there is clear evidence.\n"
            "Allowed actions per candidate:\n"
            "- keep_unresolved: do nothing\n"
            "- merge_existing: merge this candidate into one suggested canonical target\n"
            "- promote_canonical: keep this candidate as its own canonical character\n"
            "- reject_non_character: mark this candidate as not a character\n\n"
            "Rules:\n"
            "- Only merge into one of the provided suggested_targets.\n"
            "- Do not invent new names.\n"
            "- Do not reject a clear person name unless it is obviously malformed or non-character.\n"
            "- Only promote when the candidate clearly looks like a real person left unresolved by deterministic rules.\n"
            "- Use heuristic hints only as supporting evidence. If a hint says a term is a location, object, creature, or school, treat that as strong evidence against it being a person.\n\n"
            f"Existing canonical characters:\n{canonicals}\n\n"
            f"Candidates to review:\n{rendered_candidates}\n\n"
            "Return JSON only:\n"
            "{\n"
            '  "decisions": [\n'
            "    {\n"
            '      "name": "candidate name from Candidates to review",\n'
            '      "action": "keep_unresolved|merge_existing|promote_canonical|reject_non_character",\n'
            '      "target_name": "required only for merge_existing and must be one suggested target",\n'
            '      "reason": "short grounded reason"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Every candidate must have exactly one decision."
        )

    def _validate_response(self, payload: Dict[str, Any], candidates: List[Dict[str, Any]]) -> bool:
        if not isinstance(payload, dict) or not isinstance(payload.get("decisions"), list):
            return False
        candidate_names = {item["name"] for item in candidates}
        candidate_by_name = {item["name"]: item for item in candidates}
        seen = set()
        for item in payload.get("decisions") or []:
            if not isinstance(item, dict):
                return False
            name = str(item.get("name") or "").strip()
            action = str(item.get("action") or "").strip()
            target_name = str(item.get("target_name") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if name not in candidate_names or name in seen or not reason:
                return False
            if action not in {"keep_unresolved", "merge_existing", "promote_canonical", "reject_non_character"}:
                return False
            if action == "merge_existing":
                if target_name not in set(candidate_by_name[name].get("suggested_targets") or []):
                    return False
            elif target_name:
                return False
            seen.add(name)
        return seen == candidate_names

    def _apply_decisions(
        self,
        identity_result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        alias_map = {
            str(canonical).strip(): list(aliases or [])
            for canonical, aliases in (identity_result.get("alias_map") or {}).items()
            if str(canonical).strip()
        }
        rejected = list(identity_result.get("rejected_non_characters") or [])
        rejected_lookup = {item.lower() for item in rejected}
        applied: List[Dict[str, Any]] = []
        candidate_lookup = {item["name"]: item for item in candidates}

        for decision in decisions:
            name = str(decision.get("name") or "").strip()
            action = str(decision.get("action") or "").strip()
            target_name = str(decision.get("target_name") or "").strip()
            if not name or action == "keep_unresolved":
                continue
            candidate = candidate_lookup.get(name) or {}
            aliases = [str(item).strip() for item in (candidate.get("aliases") or []) if str(item).strip()]

            if action == "merge_existing" and target_name:
                merged = {target_name, name, *alias_map.get(target_name, []), *aliases}
                alias_map[target_name] = sorted({item for item in merged if item and item.lower() != target_name.lower()} | {target_name}, key=str.lower)
                alias_map[target_name] = sorted(set(alias_map[target_name]), key=str.lower)
                alias_map.pop(name, None)
            elif action == "promote_canonical":
                alias_map.setdefault(name, sorted(set([name, *aliases]), key=str.lower))
            elif action == "reject_non_character":
                alias_map.pop(name, None)
                if name.lower() not in rejected_lookup:
                    rejected.append(name)
                    rejected_lookup.add(name.lower())
            applied.append(
                {
                    "name": name,
                    "action": action,
                    "target_name": target_name,
                    "reason": str(decision.get("reason") or "").strip(),
                }
            )

        normalized_alias_map: Dict[str, List[str]] = {}
        for canonical_name, aliases in alias_map.items():
            values = {canonical_name}
            values.update(alias for alias in aliases if alias)
            normalized_alias_map[canonical_name] = sorted(values, key=str.lower)
        identity_result["alias_map"] = normalized_alias_map
        identity_result["rejected_non_characters"] = rejected
        if applied:
            decisions_log = list(identity_result.get("decisions") or [])
            for item in applied:
                decisions_log.append(
                    {
                        "decision_type": f"llm_post_{item['action']}",
                        "character": item["name"],
                        "canonical_name": item["target_name"] or item["name"],
                        "same_character": item["action"] in {"merge_existing", "promote_canonical"},
                        "confidence": 0.75,
                        "reasoning": item["reason"],
                        "scene_ref": {},
                    }
                )
            identity_result["decisions"] = decisions_log
        return applied

    def _apply_anchor_entities(self, identity_result: Dict[str, Any], anchor_entities: Dict[str, Dict[str, Any]]) -> None:
        alias_map = {
            str(canonical).strip(): sorted({str(item).strip() for item in (aliases or []) if str(item).strip()} | {str(canonical).strip()}, key=str.lower)
            for canonical, aliases in (identity_result.get("alias_map") or {}).items()
            if str(canonical).strip()
        }
        decisions_log = list(identity_result.get("decisions") or [])
        for anchor_name, anchor in anchor_entities.items():
            aliases = [str(item).strip() for item in (anchor.get("aliases") or []) if str(item).strip()]
            values = {anchor_name}
            values.update(alias for alias in aliases if self.normalizer.canonicalize_candidate_name(alias))
            alias_map.setdefault(anchor_name, [])
            alias_map[anchor_name] = sorted(set(alias_map[anchor_name]) | values, key=str.lower)
            if not any(
                str(item.get("decision_type") or "") == "llm_post_anchor_preserved"
                and str(item.get("canonical_name") or "") == anchor_name
                for item in decisions_log
            ):
                decisions_log.append(
                    {
                        "decision_type": "llm_post_anchor_preserved",
                        "character": anchor_name,
                        "canonical_name": anchor_name,
                        "same_character": True,
                        "confidence": 0.8,
                        "reasoning": (
                            f"Preserved high-confidence series anchor from {anchor.get('source_bucket', 'deterministic_inventory')} "
                            f"(mention_count={anchor.get('mention_count', 0)}, person_likelihood={anchor.get('person_likelihood', 0.0)})."
                        ),
                        "scene_ref": {},
                    }
                )
        identity_result["alias_map"] = alias_map
        identity_result["decisions"] = decisions_log

    def _finalize_identity_map(
        self,
        identity_result: Dict[str, Any],
        *,
        heuristic_hints: Dict[str, Dict[str, str]],
        anchor_entities: Dict[str, Dict[str, Any]],
    ) -> None:
        raw_alias_map = identity_result.get("alias_map") or {}
        rejected = [str(item).strip() for item in (identity_result.get("rejected_non_characters") or []) if str(item).strip()]
        rejected_lookup = {item.lower() for item in rejected}
        protected_anchors = {name.lower(): anchor for name, anchor in anchor_entities.items()}

        cleaned_alias_map: Dict[str, List[str]] = {}
        all_names: List[str] = []
        for canonical_name, aliases in raw_alias_map.items():
            normalized_canonical = self.normalizer.canonicalize_candidate_name(canonical_name)
            if not normalized_canonical:
                if canonical_name and canonical_name.lower() not in rejected_lookup:
                    rejected.append(canonical_name)
                    rejected_lookup.add(canonical_name.lower())
                continue
            cleaned_aliases: List[str] = []
            for alias in aliases or []:
                normalized_alias = self.normalizer.canonicalize_candidate_name(alias)
                if not normalized_alias:
                    if alias and alias.lower() not in rejected_lookup:
                        rejected.append(alias)
                        rejected_lookup.add(alias.lower())
                    continue
                cleaned_aliases.append(normalized_alias)
            cleaned_alias_map.setdefault(normalized_canonical, [])
            cleaned_alias_map[normalized_canonical].extend(cleaned_aliases)
            all_names.append(normalized_canonical)
            all_names.extend(cleaned_aliases)

        fragment_rewrites: Dict[str, str] = {}
        for canonical_name, aliases in list(cleaned_alias_map.items()):
            if canonical_name.lower() in protected_anchors:
                continue
            if self.normalizer.looks_like_character_name(canonical_name) and not self.normalizer.is_bad_alias_like_name(canonical_name):
                continue
            target = self._anchor_target_for_fragment(canonical_name, aliases, list(anchor_entities))
            if not target:
                continue
            fragment_rewrites[canonical_name] = target
        if fragment_rewrites:
            rewritten_alias_map: Dict[str, List[str]] = {}
            for canonical_name, aliases in cleaned_alias_map.items():
                target = fragment_rewrites.get(canonical_name, canonical_name)
                rewritten_alias_map.setdefault(target, [])
                rewritten_alias_map[target].append(canonical_name)
                rewritten_alias_map[target].extend(aliases)
            cleaned_alias_map = rewritten_alias_map

        merge_map, _ = self.normalizer.build_merge_map(
            names=all_names,
            alias_map=cleaned_alias_map,
        )
        merged_alias_map: Dict[str, List[str]] = {}
        for canonical_name, aliases in cleaned_alias_map.items():
            target = merge_map.get(canonical_name, canonical_name)
            merged_alias_map.setdefault(target, [])
            merged_alias_map[target].append(canonical_name)
            merged_alias_map[target].extend(aliases)

        normalized_alias_map: Dict[str, List[str]] = {}
        for canonical_name, aliases in merged_alias_map.items():
            target = self.normalizer.canonicalize_candidate_name(canonical_name)
            hint = heuristic_hints.get(self.normalizer.normalized_entity_key(target)) or {}
            if not target or not self.normalizer.looks_like_character_name(target):
                for alias in aliases:
                    if alias and alias.lower() not in rejected_lookup:
                        rejected.append(alias)
                        rejected_lookup.add(alias.lower())
                continue
            if (
                target.lower() not in protected_anchors
                and hint.get("entity_type") in {"location", "object", "creature"}
                and hint.get("confidence") == "high"
                and not self.normalizer.looks_like_character_name(target)
            ):
                for alias in [target, *aliases]:
                    if alias and alias.lower() not in rejected_lookup:
                        rejected.append(alias)
                        rejected_lookup.add(alias.lower())
                continue
            values = {target}
            for alias in aliases:
                normalized_alias = self.normalizer.canonicalize_candidate_name(alias)
                if not normalized_alias:
                    continue
                if normalized_alias.lower() == target.lower():
                    values.add(target)
                    continue
                if normalized_alias.lower() in protected_anchors:
                    values.add(anchor_entities[normalized_alias].get("preferred_name", normalized_alias))
                    continue
                if not self.normalizer.looks_like_character_name(normalized_alias):
                    if normalized_alias.lower() not in rejected_lookup:
                        rejected.append(normalized_alias)
                        rejected_lookup.add(normalized_alias.lower())
                    continue
                values.add(normalized_alias)
            normalized_alias_map[target] = sorted(values, key=str.lower)

        for anchor_name, anchor in anchor_entities.items():
            values = {
                self.normalizer.canonicalize_candidate_name(item)
                for item in [anchor_name, *(anchor.get("aliases") or [])]
            }
            values = {item for item in values if item}
            if not values:
                continue
            normalized_alias_map.setdefault(anchor_name, [])
            normalized_alias_map[anchor_name] = sorted(set(normalized_alias_map[anchor_name]) | values | {anchor_name}, key=str.lower)

        deduped_rejected: List[str] = []
        seen_rejected = set()
        protected = {key.lower() for key in normalized_alias_map}
        for aliases in normalized_alias_map.values():
            protected.update(alias.lower() for alias in aliases)
        for name in rejected:
            key = name.lower()
            if key in seen_rejected or key in protected:
                continue
            seen_rejected.add(key)
            deduped_rejected.append(name)

        identity_result["alias_map"] = normalized_alias_map
        identity_result["rejected_non_characters"] = deduped_rejected

    def _anchor_target_for_fragment(self, canonical_name: str, aliases: List[str], anchor_names: List[str]) -> str:
        candidates = [canonical_name, *(aliases or [])]
        best_target = ""
        for candidate in candidates:
            suggestion = self.normalizer.expand_short_character_name(candidate, anchor_names)
            if suggestion:
                return suggestion
            suggestions = self._suggest_targets(candidate, anchor_names, exclude=candidate)
            if suggestions:
                best_target = suggestions[0]
        return best_target

