"""Local first-pass mention and entity extraction.

This module is intentionally evidence-oriented. It generates candidate
mentions, clusters, aliases, characters, and non-character entities using only
local NLP and lightweight heuristics. Downstream analyzers can refine or reject
these candidates, but should not need to rediscover them from scratch.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional

from saga.agents.evidence_schema import (
    empty_evidence_bundle,
    is_forbidden_alias,
    is_generic_alias,
    normalize_evidence_bundle,
    normalize_identity_label,
)

try:
    import spacy  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    spacy = None


class LocalEntityExtractor:
    """Local candidate extractor with optional spaCy-backed enrichment."""

    PERSON_LABELS = {"PERSON", "PER"}
    NON_CHARACTER_TYPES = {"location", "object", "artifact", "group"}
    CHARACTERISH_HINTS = {"mr", "mrs", "miss", "lady", "lord", "captain", "prince", "princess", "king", "queen"}

    def __init__(self, model_name: str = "en_core_web_trf"):
        self.model_name = model_name
        self._nlp = self._load_model(model_name)

    def extract(self, text: str) -> Dict:
        if not text or not text.strip():
            return empty_evidence_bundle()

        bundle = empty_evidence_bundle()
        bundle["metadata"]["provider"] = "spacy" if self._nlp is not None else "regex"

        if self._nlp is None:
            return self._extract_with_heuristics(text, bundle)

        try:
            doc = self._nlp(text)
        except Exception:
            return self._extract_with_heuristics(text, bundle)

        bundle["metadata"]["transformer_available"] = "transformer" in self._nlp.pipe_names
        bundle["metadata"]["coreference_available"] = any("coref" in name.lower() for name in self._nlp.pipe_names)
        bundle["metadata"]["span_resolution_available"] = any("span" in name.lower() for name in self._nlp.pipe_names)

        mentions = []
        candidate_chars = {}
        candidate_entities = {}
        cluster_map: dict[str, dict] = {}
        alias_pairs = set()

        for ent in doc.ents:
            text_value = ent.text.strip()
            if not text_value:
                continue

            mention = {
                "text": text_value,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
                "token_start": ent.start,
                "token_end": ent.end,
                "is_pronoun": False,
            }
            mentions.append(mention)

            cluster_key = normalize_identity_label(text_value)
            cluster = cluster_map.setdefault(cluster_key, {
                "cluster_id": f"cluster_{len(cluster_map) + 1}",
                "canonical_text": text_value,
                "mentions": [],
                "candidate_type": "character" if ent.label_ in self.PERSON_LABELS else "entity",
            })
            cluster["mentions"].append(text_value)

            if ent.label_ in self.PERSON_LABELS:
                entry = candidate_chars.setdefault(cluster_key, {"name": text_value, "evidence_mentions": [], "source": "local_nlp"})
                entry["evidence_mentions"].append(text_value)
            else:
                entity_type = self._entity_type_from_label(ent.label_)
                entry = candidate_entities.setdefault(cluster_key, {"name": text_value, "entity_type": entity_type, "evidence_mentions": [], "source": "local_nlp"})
                entry["evidence_mentions"].append(text_value)

        self._merge_coreference_clusters(doc, cluster_map, candidate_chars, candidate_entities, alias_pairs)

        for match in re.finditer(r"\b(he|she|they|him|her|them|his|their|hers|theirs)\b", text, re.IGNORECASE):
            mentions.append({
                "text": match.group(0),
                "label": "PRONOUN",
                "start_char": match.start(),
                "end_char": match.end(),
                "token_start": -1,
                "token_end": -1,
                "is_pronoun": True,
            })

        # Heuristic role / descriptor mentions.
        for phrase in self._find_role_phrases(text):
            mentions.append({
                "text": phrase,
                "label": "ROLE",
                "start_char": -1,
                "end_char": -1,
                "token_start": -1,
                "token_end": -1,
                "is_pronoun": False,
            })
            normalized = normalize_identity_label(phrase)
            if is_forbidden_alias(phrase) or is_generic_alias(phrase):
                continue
            if normalized not in candidate_chars:
                candidate_chars[normalized] = {"name": phrase, "evidence_mentions": [phrase], "source": "local_role_phrase"}

        self._mark_ambiguities(bundle, candidate_chars, candidate_entities)

        for key, character in candidate_chars.items():
            for mention_text in character["evidence_mentions"]:
                if not is_forbidden_alias(mention_text) and not is_generic_alias(mention_text):
                    alias_pairs.add((character["name"], mention_text))

        bundle["mentions"] = mentions
        bundle["clusters"] = [
            {
                "cluster_id": value["cluster_id"],
                "canonical_text": value["canonical_text"],
                "mentions": sorted(set(value["mentions"]), key=str.lower),
                "candidate_type": value["candidate_type"],
            }
            for value in cluster_map.values()
        ]
        bundle["candidate_characters"] = [
            {
                "name": value["name"],
                "evidence_mentions": sorted(set(value["evidence_mentions"]), key=str.lower),
                "source": value["source"],
            }
            for value in candidate_chars.values()
        ]
        bundle["candidate_entities"] = [
            {
                "name": value["name"],
                "entity_type": value["entity_type"],
                "evidence_mentions": sorted(set(value["evidence_mentions"]), key=str.lower),
                "source": value["source"],
            }
            for value in candidate_entities.values()
        ]
        bundle["candidate_aliases"] = [
            {"canonical_name": canonical_name, "alias": alias}
            for canonical_name, alias in sorted(alias_pairs, key=lambda item: (item[0].lower(), item[1].lower()))
            if normalize_identity_label(canonical_name) != normalize_identity_label(alias)
        ]
        return normalize_evidence_bundle(bundle)

    def _extract_with_heuristics(self, text: str, bundle: Dict) -> Dict:
        mentions = []
        candidate_chars = {}
        candidate_entities = {}
        cluster_mentions = defaultdict(list)

        proper_name_pattern = re.compile(r"\b([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)+)\b")
        for match in proper_name_pattern.finditer(text):
            value = match.group(1).strip()
            mentions.append({
                "text": value,
                "label": "PERSON",
                "start_char": match.start(),
                "end_char": match.end(),
                "token_start": -1,
                "token_end": -1,
                "is_pronoun": False,
            })
            key = normalize_identity_label(value)
            cluster_mentions[key].append(value)
            candidate_chars.setdefault(key, {"name": value, "evidence_mentions": [], "source": "heuristic_name"})
            candidate_chars[key]["evidence_mentions"].append(value)

        noun_phrase_pattern = re.compile(r"\b(?:the\s+)?([a-z]+(?:\s+[a-z]+){0,2})\b")
        for match in noun_phrase_pattern.finditer(text):
            value = match.group(1).strip()
            normalized = normalize_identity_label(value)
            if not normalized or normalized in {"the"}:
                continue
            if normalized in candidate_chars:
                continue
            if is_forbidden_alias(value) or is_generic_alias(value):
                continue
            if len(value.split()) > 1 and any(token in self.CHARACTERISH_HINTS for token in normalized.split()):
                candidate_chars[normalized] = {"name": value, "evidence_mentions": [value], "source": "heuristic_role"}

        bundle["mentions"] = mentions
        bundle["clusters"] = [
            {
                "cluster_id": f"cluster_{index}",
                "canonical_text": values[0],
                "mentions": sorted(set(values), key=str.lower),
                "candidate_type": "character",
            }
            for index, values in enumerate(cluster_mentions.values(), start=1)
        ]
        bundle["candidate_characters"] = [
            {"name": value["name"], "evidence_mentions": sorted(set(value["evidence_mentions"]), key=str.lower), "source": value["source"]}
            for value in candidate_chars.values()
        ]
        bundle["candidate_entities"] = list(candidate_entities.values())
        bundle["candidate_aliases"] = []
        return normalize_evidence_bundle(bundle)

    def _load_model(self, model_name: str):
        if spacy is None:
            return None
        try:
            return spacy.load(model_name)
        except Exception:
            try:
                return spacy.load("en_core_web_sm")
            except Exception:
                return None

    def _merge_coreference_clusters(self, doc, cluster_map: Dict[str, Dict], candidate_chars: Dict[str, Dict], candidate_entities: Dict[str, Dict], alias_pairs: set):
        for cluster_mentions in self._iter_coref_clusters(doc):
            non_pronoun_mentions = [mention for mention in cluster_mentions if mention and not self._is_pronoun_text(mention)]
            if not non_pronoun_mentions:
                continue
            representative = self._select_representative(non_pronoun_mentions)
            normalized_rep = normalize_identity_label(representative)
            is_character = self._looks_like_character_candidate(representative)
            cluster = cluster_map.setdefault(
                normalized_rep,
                {
                    "cluster_id": f"cluster_{len(cluster_map) + 1}",
                    "canonical_text": representative,
                    "mentions": [],
                    "candidate_type": "character" if is_character else "entity",
                },
            )
            cluster["mentions"].extend(cluster_mentions)

            if is_character:
                entry = candidate_chars.setdefault(
                    normalized_rep,
                    {"name": representative, "evidence_mentions": [], "source": "local_coref"},
                )
                entry["evidence_mentions"].extend(non_pronoun_mentions)
                for mention in non_pronoun_mentions:
                    if normalize_identity_label(mention) != normalized_rep and not is_forbidden_alias(mention) and not is_generic_alias(mention):
                        alias_pairs.add((representative, mention))
            else:
                entry = candidate_entities.setdefault(
                    normalized_rep,
                    {"name": representative, "entity_type": "object", "evidence_mentions": [], "source": "local_coref"},
                )
                entry["evidence_mentions"].extend(non_pronoun_mentions)

    def _iter_coref_clusters(self, doc) -> List[List[str]]:
        clusters: List[List[str]] = []
        spans = getattr(doc, "spans", {}) or {}
        for key, value in spans.items():
            lowered = str(key).lower()
            if "coref" not in lowered and "cluster" not in lowered:
                continue
            if hasattr(value, "__iter__"):
                mentions = [getattr(span, "text", str(span)).strip() for span in value]
                mentions = [mention for mention in mentions if mention]
                if len(mentions) >= 2:
                    clusters.append(mentions)
        if hasattr(doc._, "coref_clusters"):
            try:
                for cluster in doc._.coref_clusters:
                    mentions = [getattr(mention, "text", str(mention)).strip() for mention in getattr(cluster, "mentions", [])]
                    mentions = [mention for mention in mentions if mention]
                    if len(mentions) >= 2:
                        clusters.append(mentions)
            except Exception:
                pass
        return clusters

    def _select_representative(self, mentions: List[str]) -> str:
        sorted_mentions = sorted(
            mentions,
            key=lambda item: (
                not self._looks_like_character_candidate(item),
                not self._looks_like_named_entity(item),
                -len(item),
            ),
        )
        return sorted_mentions[0]

    def _looks_like_named_entity(self, value: str) -> bool:
        tokens = [token for token in value.replace("-", " ").split() if token]
        return len(tokens) >= 2 and all(token[:1].isupper() for token in tokens if token[:1].isalpha())

    def _looks_like_character_candidate(self, value: str) -> bool:
        normalized = normalize_identity_label(value)
        if not normalized or is_forbidden_alias(value):
            return False
        if self._looks_like_named_entity(value):
            return True
        if any(token in self.CHARACTERISH_HINTS for token in normalized.split()):
            return True
        return " " in normalized and not is_generic_alias(value)

    def _is_pronoun_text(self, value: str) -> bool:
        return normalize_identity_label(value) in {"he", "she", "they", "them", "him", "her", "his", "their", "hers", "theirs", "it", "its"}

    def _mark_ambiguities(self, bundle: Dict, candidate_chars: Dict[str, Dict], candidate_entities: Dict[str, Dict]):
        ambiguities = []
        token_to_candidates = defaultdict(set)
        for item in candidate_chars.values():
            name = item.get("name") or ""
            for token in normalize_identity_label(name).split():
                if len(token) >= 4:
                    token_to_candidates[token].add(name)
        for token, names in token_to_candidates.items():
            if len(names) > 1:
                ambiguities.append({
                    "type": "shared_token",
                    "token": token,
                    "candidates": sorted(names),
                })
        descriptor_like = [
            item.get("name")
            for item in candidate_chars.values()
            if item.get("name") and not self._looks_like_named_entity(item.get("name", "")) and item.get("source") != "local_nlp"
        ]
        for name in descriptor_like[:10]:
            ambiguities.append({
                "type": "descriptor_candidate",
                "candidate": name,
            })
        bundle["metadata"]["ambiguities"] = ambiguities

    def _entity_type_from_label(self, label: str) -> str:
        label = (label or "").upper()
        if label in {"GPE", "LOC", "FAC"}:
            return "location"
        if label in {"ORG", "NORP"}:
            return "group"
        if label in {"PRODUCT", "WORK_OF_ART"}:
            return "artifact"
        return "object"

    def _find_role_phrases(self, text: str) -> List[str]:
        phrases = []
        for match in re.finditer(r"\b(?:the\s+)?([A-Za-z]+(?:-[A-Za-z]+)?\s+(?:lord|lady|captain|prince|princess|queen|king|general|commander|healer|seer|huntress|hunter))\b", text):
            phrases.append(match.group(0).strip())
        return phrases
