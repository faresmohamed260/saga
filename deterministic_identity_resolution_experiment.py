"""GLiNER-primary local extraction + deterministic identity memory experiment."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import DefaultDict, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import networkx as nx
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
import spacy
from gliner import GLiNER

from services.epub_processor import EPUBProcessor

MentionType = Literal["name", "pronoun", "descriptor", "title", "role"]
SpanRoute = Literal["canonical_seed", "temporary_person", "quarantine", "supporting", "ignore", "pronoun"]
DecisionStatus = Literal["resolved", "tentative", "unresolved"]
EntityStatus = Literal["canonical", "temporary"]
SupportingEntityKind = Literal["location", "group", "object", "creature", "unknown"]

HONORIFICS = {"mr", "mrs", "ms", "dr", "sir", "lady", "lord", "king", "queen", "prince", "princess"}
SHARED_TITLES = {"high lady", "high lord", "king", "queen", "prince", "princess", "professor", "captain", "commander", "general"}
KINSHIP_ROLES = {"father", "mother", "sister", "brother", "daughter", "son", "husband", "wife", "aunt", "uncle"}
PERSONISH_NOUNS = {"man", "woman", "boy", "girl", "person", "stranger", "hunter", "mercenary", "guard", "servant", "acolyte", "mother", "father", "sister", "brother", "daughter", "son", "wife", "husband", "child", "warrior", "priest", "soldier", "female", "male"}
PRONOUN_GENDER = {"she": "female", "her": "female", "hers": "female", "he": "male", "him": "male", "his": "male", "they": "plural", "them": "plural", "their": "plural", "theirs": "plural"}
SUPPORTING_ENTITY_LABELS = {"GPE": "location", "LOC": "location", "FAC": "location", "ORG": "group", "NORP": "group", "PRODUCT": "object", "EVENT": "object"}
REVEAL_PATTERNS = [
    re.compile(r"\b(?:her|his|their)\s+name\s+was\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"),
    re.compile(r"\bcalled\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"),
    re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*the\s+([a-z][a-z\s-]{1,40})"),
    re.compile(r"\bthe\s+([a-z][a-z\s-]{1,40})\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"),
]
POV_CHAPTER_PATTERN = re.compile(r"^chapter\s+\d+\s*:\s*(.+)$", re.IGNORECASE)
QUOTE_PATTERN = re.compile(r'[\"“”]')


class WindowRecord(BaseModel):
    chapter_index: int
    window_index: int
    chapter_title: str
    text: str
    paragraph_start: int
    paragraph_end: int


class ExtractedMention(BaseModel):
    text: str
    canonical_form: str
    mention_type: MentionType
    referent_type: Literal["person", "location", "group", "object", "unknown"]
    confidence: float
    start_char: int = -1
    end_char: int = -1
    sentence_index: int = -1
    in_quote: bool = False
    source: str = "llm_extraction"


class MentionHistoryRecord(BaseModel):
    surface_text: str
    canonical_form: str
    mention_type: MentionType
    referent_type: str
    confidence: float
    route: str
    chapter_index: int
    window_index: int
    sentence_index: int
    sentence_text: str
    in_quote: bool
    source: str
    positive_features: Dict[str, float] = Field(default_factory=dict)
    negative_features: Dict[str, float] = Field(default_factory=dict)
    entity_label: str = ""
    syntactic_role: str = "other"
    head_lemma: str = ""


class Mention(BaseModel):
    text: str
    mention_type: MentionType
    start: int
    end: int
    chapter_index: int
    window_index: int
    sentence_index: int
    resolved_to: str = ""
    score: float = 0.0
    method: str = ""
    confidence: str = "low"
    status: DecisionStatus = "unresolved"
    route: SpanRoute = "ignore"
    typed_label: str = ""


class ResolutionRecord(BaseModel):
    mention_text: str
    mention_type: MentionType
    route: SpanRoute
    candidate_scores: Dict[str, float]
    resolved_to: str = ""
    status: DecisionStatus
    method: str
    confidence: str
    reasons: List[str] = Field(default_factory=list)


@dataclass
class CharacterMemory:
    entity_id: str
    canonical_name: str
    status: EntityStatus
    first_seen_chapter: int
    first_seen_window: int
    last_seen_chapter: int
    last_seen_window: int
    aliases: set[str] = field(default_factory=set)
    titles: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    descriptors: set[str] = field(default_factory=set)
    gender: str = ""
    mention_count: int = 0
    evidence_windows: List[Tuple[int, int]] = field(default_factory=list)
    seed_label_type: MentionType = "name"
    max_person_likelihood: float = 0.0
    model_person_hits: int = 0
    honorific_backed: bool = False


@dataclass
class WeakMentionMemory:
    weak_id: str
    text: str
    mention_type: MentionType
    first_seen_chapter: int
    first_seen_window: int
    last_seen_chapter: int
    last_seen_window: int
    person_likelihood: float
    occurrence_count: int = 0
    evidence_windows: List[Tuple[int, int]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class SupportingEntityMemory:
    entity_id: str
    name: str
    entity_kind: SupportingEntityKind
    first_seen_chapter: int
    first_seen_window: int
    last_seen_chapter: int
    last_seen_window: int
    mention_count: int = 0


@dataclass
class EntityEvidenceProfile:
    entity_id: str
    entity_name: str
    entity_bucket: Literal["canonical", "temporary", "supporting", "weak"]
    total_mentions: int = 0
    proper_name_mentions: int = 0
    person_model_hits: int = 0
    pronoun_links: int = 0
    quote_speaker_hits: int = 0
    title_role_hits: int = 0
    nearby_known_person_hits: int = 0
    location_group_hits: int = 0
    object_generic_hits: int = 0
    malformed_name_hits: int = 0
    first_seen: Tuple[int, int] = (0, 0)
    last_seen: Tuple[int, int] = (0, 0)
    surface_forms: set[str] = field(default_factory=set)
    positive_evidence: DefaultDict[str, float] = field(default_factory=lambda: defaultdict(float))
    negative_evidence: DefaultDict[str, float] = field(default_factory=lambda: defaultdict(float))
    example_sentences: List[str] = field(default_factory=list)

    @property
    def character_evidence_score(self) -> float:
        score = 0.0
        score += min(1.5, self.proper_name_mentions * 0.18)
        score += min(1.2, self.person_model_hits * 0.22)
        score += min(0.9, self.pronoun_links * 0.12)
        score += min(0.7, self.quote_speaker_hits * 0.20)
        score += min(0.6, self.title_role_hits * 0.10)
        score += min(0.8, self.nearby_known_person_hits * 0.08)
        score += min(0.4, self.total_mentions * 0.02)
        score += sum(self.positive_evidence.values()) * 0.15
        return round(score, 3)

    @property
    def non_character_evidence_score(self) -> float:
        score = 0.0
        score += min(1.4, self.location_group_hits * 0.22)
        score += min(1.4, self.object_generic_hits * 0.16)
        score += min(0.8, self.malformed_name_hits * 0.35)
        score += sum(self.negative_evidence.values()) * 0.18
        return round(score, 3)

    @property
    def ambiguity_score(self) -> float:
        return round(abs(self.character_evidence_score - self.non_character_evidence_score), 3)


class NameClusterer:
    def _normalize_surface(self, text: str) -> str:
        cleaned = re.sub(r"[’']s\b", "", text or "")
        return re.sub(r"\s+", " ", cleaned.strip())

    def _parse_name(self, text: str) -> Tuple[str, str, Tuple[str, ...]]:
        working_text = self._normalize_surface(text)
        raw_tokens = [
            token.strip(".,;:!?\"'“”‘’()[]{}")
            for token in re.sub(r"\s+", " ", working_text.strip()).split()
            if token.strip(".,;:!?\"'“”‘’()[]{}")
        ]
        if not raw_tokens:
            return "", "", ()
        honorific = raw_tokens[0].lower().rstrip(".") if raw_tokens[0].lower().rstrip(".") in HONORIFICS else ""
        core_tokens = raw_tokens[1:] if honorific else raw_tokens
        normalized_full = " ".join(token.lower().rstrip(".") for token in raw_tokens)
        normalized_core_tokens = tuple(token.lower().rstrip(".") for token in core_tokens)
        return normalized_full, honorific, normalized_core_tokens

    def normalize_name(self, text: str) -> str:
        _, _, core_tokens = self._parse_name(text)
        return " ".join(core_tokens)

    def match_canonical(self, text: str, canonicals: Dict[str, CharacterMemory]) -> str:
        normalized_full, honorific, core_tokens = self._parse_name(text)
        normalized_core = " ".join(core_tokens)
        if not normalized_full:
            return ""
        exact_matches: List[str] = []
        for entity_id, entity in canonicals.items():
            names = {entity.canonical_name, *entity.aliases}
            normalized_names = {self._parse_name(item)[0] for item in names if item}
            if normalized_full in normalized_names:
                exact_matches.append(entity_id)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(core_tokens) >= 2:
            stripped_matches: List[str] = []
            for entity_id, entity in canonicals.items():
                names = {entity.canonical_name, *entity.aliases}
                for item in names:
                    item_full, item_honorific, item_core_tokens = self._parse_name(item)
                    if not item_full or len(item_core_tokens) < 2:
                        continue
                    if normalized_core != " ".join(item_core_tokens):
                        continue
                    if honorific and item_honorific and honorific != item_honorific:
                        continue
                    stripped_matches.append(entity_id)
                    break
            if len(stripped_matches) == 1:
                return stripped_matches[0]
            token_set = set(core_tokens)
            subset_matches: List[str] = []
            for entity_id, entity in canonicals.items():
                candidate_tokens = set(self._parse_name(entity.canonical_name)[2])
                if len(candidate_tokens) >= 2 and token_set <= candidate_tokens:
                    subset_matches.append(entity_id)
            if len(subset_matches) == 1:
                return subset_matches[0]
            fuzzy_matches: List[Tuple[str, int]] = []
            for entity_id, entity in canonicals.items():
                names = {entity.canonical_name, *entity.aliases}
                best_score = 0
                for item in names:
                    candidate_core = " ".join(self._parse_name(item)[2])
                    if len(candidate_core.split()) < 2:
                        continue
                    best_score = max(best_score, fuzz.ratio(normalized_core, candidate_core))
                if best_score >= 95:
                    fuzzy_matches.append((entity_id, best_score))
            fuzzy_matches.sort(key=lambda item: item[1], reverse=True)
            if fuzzy_matches and (len(fuzzy_matches) == 1 or fuzzy_matches[0][1] > fuzzy_matches[1][1]):
                return fuzzy_matches[0][0]
        elif len(core_tokens) == 1:
            candidates: List[Tuple[str, int]] = []
            for entity_id, entity in canonicals.items():
                entity_tokens = self._parse_name(entity.canonical_name)[2]
                if not entity_tokens:
                    continue
                if core_tokens[0] in entity_tokens:
                    candidates.append((entity_id, len(entity_tokens)))
            candidates.sort(key=lambda item: item[1], reverse=True)
            if len(candidates) == 1:
                return candidates[0][0]
        return ""


class IdentityMemoryManager:
    def __init__(self, graph: nx.DiGraph, name_clusterer: NameClusterer) -> None:
        self.graph = graph
        self.name_clusterer = name_clusterer
        self.canonical_characters: Dict[str, CharacterMemory] = {}
        self.temporary_person_candidates: Dict[str, CharacterMemory] = {}
        self.weak_mentions_quarantine: Dict[str, WeakMentionMemory] = {}
        self.supporting_entities: Dict[str, SupportingEntityMemory] = {}
        self.alias_index: DefaultDict[str, set[str]] = defaultdict(set)
        self.title_index: DefaultDict[str, set[str]] = defaultdict(set)
        self.role_index: DefaultDict[str, set[str]] = defaultdict(set)
        self.global_stable_cache: List[str] = []
        self.local_active_cache: List[str] = []
        self._canonical_counter = 0
        self._temporary_counter = 0
        self._weak_counter = 0
        self._supporting_counter = 0

    def register_supporting_by_name(
        self,
        name: str,
        entity_kind: SupportingEntityKind,
        chapter_index: int,
        window_index: int,
    ) -> str:
        display_name = self._canonicalize_supporting_name(name)
        if not display_name:
            return ""
        normalized = self._normalize(display_name)
        for entity_id, entity in self.supporting_entities.items():
            if self._normalize(entity.name) == normalized:
                entity.last_seen_chapter = chapter_index
                entity.last_seen_window = window_index
                entity.mention_count += 1
                return entity_id
        self._supporting_counter += 1
        entity_id = f"support_{self._supporting_counter}"
        self.supporting_entities[entity_id] = SupportingEntityMemory(
            entity_id=entity_id,
            name=display_name,
            entity_kind=entity_kind,
            first_seen_chapter=chapter_index,
            first_seen_window=window_index,
            last_seen_chapter=chapter_index,
            last_seen_window=window_index,
            mention_count=1,
        )
        self.graph.add_node(entity_id, kind=entity_kind, name=display_name)
        return entity_id

    def remember_weak_mention_by_text(
        self,
        text: str,
        mention_type: MentionType,
        person_likelihood: float,
        chapter_index: int,
        window_index: int,
    ) -> str:
        surface = self._normalize_entity_surface(text)
        if not surface:
            return ""
        normalized = self._normalize(surface)
        for weak_id, entity in self.weak_mentions_quarantine.items():
            if self._normalize(entity.text) == normalized:
                entity.last_seen_chapter = chapter_index
                entity.last_seen_window = window_index
                entity.occurrence_count += 1
                entity.person_likelihood = min(0.95, max(entity.person_likelihood, person_likelihood) + 0.05)
                entity.evidence_windows.append((chapter_index, window_index))
                return weak_id
        self._weak_counter += 1
        weak_id = f"weak_{self._weak_counter}"
        self.weak_mentions_quarantine[weak_id] = WeakMentionMemory(
            weak_id=weak_id,
            text=surface,
            mention_type=mention_type,
            first_seen_chapter=chapter_index,
            first_seen_window=window_index,
            last_seen_chapter=chapter_index,
            last_seen_window=window_index,
            person_likelihood=person_likelihood,
            occurrence_count=1,
            evidence_windows=[(chapter_index, window_index)],
        )
        self.graph.add_node(weak_id, kind="weak_mention", name=surface)
        return weak_id

    def attach_mention_by_id(
        self,
        entity_id: str,
        text: str,
        mention_type: MentionType,
        chapter_index: int,
        window_index: int,
    ) -> None:
        mention = Mention(
            text=text,
            mention_type=mention_type,
            start=-1,
            end=-1,
            chapter_index=chapter_index,
            window_index=window_index,
            sentence_index=-1,
            resolved_to=entity_id,
            score=1.0,
            method="llm_extraction",
            confidence="high",
            status="resolved",
            route="canonical_seed",
            typed_label="llm_person",
        )
        self.attach_mention(entity_id, mention)

    def attach_title_or_role(self, entity_id: str, text: str, mention_type: MentionType) -> None:
        entity = self.get_character(entity_id)
        if not entity:
            return
        if mention_type == "title":
            entity.titles.add(text)
        elif mention_type == "role":
            entity.roles.add(text)
        elif mention_type == "descriptor":
            entity.descriptors.add(text)
        self._index_character(entity)

    def seed_or_match_canonical_name(self, name: str, chapter_index: int, window_index: int, seed_type: MentionType) -> str:
        normalized_name = self._normalize_entity_surface(name)
        if not normalized_name:
            return ""
        existing = self.name_clusterer.match_canonical(normalized_name, self.canonical_characters)
        if existing:
            return existing
        return self._create_canonical(normalized_name, chapter_index, window_index, seed_type)

    def maybe_promote_weak_to_temp(self, weak_id: str) -> str:
        weak = self.weak_mentions_quarantine.get(weak_id)
        if not weak:
            return ""
        if weak.mention_type != "name" or weak.person_likelihood < 0.6:
            return ""
        if weak.occurrence_count < 2 or len(set(weak.evidence_windows)) < 2:
            return ""
        normalized = self._normalize(weak.text)
        for entity_id, entity in self.temporary_person_candidates.items():
            if self._normalize(entity.canonical_name) == normalized:
                return entity_id
        existing_canonical = self.name_clusterer.match_canonical(weak.text, self.canonical_characters)
        if existing_canonical:
            return existing_canonical
        return self._create_temp_person(weak.text, weak.first_seen_chapter, weak.first_seen_window, "name")

    def maybe_promote_temporary_to_canonical(self, entity_id: str) -> str:
        temp = self.temporary_person_candidates.get(entity_id)
        if not temp:
            return ""
        _, honorific, core_tokens = self.name_clusterer._parse_name(temp.canonical_name)
        if temp.seed_label_type != "name":
            return ""
        if temp.canonical_name.lower() in SHARED_TITLES:
            return ""
        unique_windows = len(set(temp.evidence_windows))
        if temp.mention_count < 2 or unique_windows < 2:
            return ""
        promotable = False
        if honorific and len(core_tokens) >= 1 and temp.max_person_likelihood >= 0.72:
            promotable = True
        elif len(core_tokens) >= 2:
            promotable = True
        elif len(core_tokens) == 1 and temp.max_person_likelihood >= 0.88 and temp.model_person_hits >= 2 and temp.mention_count >= 3:
            promotable = True
        if not promotable:
            return ""
        existing = self.name_clusterer.match_canonical(temp.canonical_name, self.canonical_characters)
        if existing:
            self.merge_temp_into_canonical(entity_id, existing, "repeated_multitoken_name")
            return existing
        canonical_id = self._create_canonical(temp.canonical_name, temp.first_seen_chapter, temp.first_seen_window, temp.seed_label_type)
        self.merge_temp_into_canonical(entity_id, canonical_id, "repeated_multitoken_name")
        return canonical_id

    def create_temp_if_supported(
        self,
        name: str,
        chapter_index: int,
        window_index: int,
        person_likelihood: float,
        mention_type: MentionType,
        has_model_person: bool = False,
        has_ner_person: bool = False,
    ) -> str:
        if mention_type != "name":
            return ""
        surface = self._normalize_entity_surface(name)
        if not surface:
            return ""
        normalized = self._normalize(surface)
        _, honorific, core_tokens = self.name_clusterer._parse_name(surface)
        if len(core_tokens) == 1 and not honorific:
            if person_likelihood < 0.72 and not has_model_person and not has_ner_person:
                return ""
        for entity_id, entity in self.temporary_person_candidates.items():
            if self._normalize(entity.canonical_name) == normalized:
                entity.max_person_likelihood = max(entity.max_person_likelihood, person_likelihood)
                entity.model_person_hits += 1 if has_model_person or has_ner_person else 0
                return entity_id
        return self._create_temp_person(
            surface,
            chapter_index,
            window_index,
            "name",
            person_likelihood=person_likelihood,
            model_person_hit=has_model_person or has_ner_person,
        )

    def resolve_pronoun_candidates(self, pronoun_text: str) -> List[str]:
        wanted_gender = PRONOUN_GENDER.get(pronoun_text.lower(), "")
        candidates = list(reversed(self.local_active_cache)) or list(reversed(self.global_stable_cache))
        output: List[str] = []
        for entity_id in candidates:
            entity = self.get_character(entity_id)
            if not entity or entity.status == "temporary":
                continue
            if entity.gender and wanted_gender and entity.gender not in {wanted_gender, "plural"}:
                continue
            output.append(entity_id)
        return output

    def attach_mention(self, entity_id: str, mention: Mention) -> None:
        entity = self.get_character(entity_id)
        if not entity:
            return
        entity.last_seen_chapter = mention.chapter_index
        entity.last_seen_window = mention.window_index
        entity.mention_count += 1
        entity.evidence_windows.append((mention.chapter_index, mention.window_index))
        if mention.mention_type == "title":
            entity.titles.add(mention.text)
        elif mention.mention_type == "role":
            entity.roles.add(mention.text)
        elif mention.mention_type == "descriptor":
            entity.descriptors.add(mention.text)
        elif mention.mention_type == "name" and self._normalize(mention.text) != self._normalize(entity.canonical_name):
            entity.aliases.add(mention.text)
        elif mention.mention_type == "pronoun":
            self._infer_gender(entity, mention.text)
        self._index_character(entity)
        self._touch_caches(entity_id)

    def merge_temp_into_canonical(self, temp_id: str, canonical_id: str, reason: str) -> None:
        temp = self.temporary_person_candidates.get(temp_id)
        canonical = self.canonical_characters.get(canonical_id)
        if not temp or not canonical:
            return
        canonical.aliases.update(temp.aliases)
        canonical.titles.update(temp.titles)
        canonical.roles.update(temp.roles)
        canonical.descriptors.update(temp.descriptors)
        if temp.seed_label_type == "name":
            canonical.aliases.add(temp.canonical_name)
        canonical.last_seen_chapter = max(canonical.last_seen_chapter, temp.last_seen_chapter)
        canonical.last_seen_window = max(canonical.last_seen_window, temp.last_seen_window)
        canonical.mention_count += temp.mention_count
        canonical.max_person_likelihood = max(canonical.max_person_likelihood, temp.max_person_likelihood)
        canonical.model_person_hits += temp.model_person_hits
        canonical.honorific_backed = canonical.honorific_backed or temp.honorific_backed
        self.graph.add_edge(temp_id, canonical_id, kind="merged_into", reason=reason)
        del self.temporary_person_candidates[temp_id]
        self._index_character(canonical)
        self._touch_caches(canonical_id)

    def merge_canonical_into_canonical(self, source_id: str, target_id: str, reason: str) -> None:
        if source_id == target_id:
            return
        source = self.canonical_characters.get(source_id)
        target = self.canonical_characters.get(target_id)
        if not source or not target:
            return
        target.aliases.update(source.aliases)
        target.titles.update(source.titles)
        target.roles.update(source.roles)
        target.descriptors.update(source.descriptors)
        target.aliases.add(source.canonical_name)
        target.first_seen_chapter = min(target.first_seen_chapter, source.first_seen_chapter)
        target.first_seen_window = min(target.first_seen_window, source.first_seen_window)
        target.last_seen_chapter = max(target.last_seen_chapter, source.last_seen_chapter)
        target.last_seen_window = max(target.last_seen_window, source.last_seen_window)
        target.mention_count += source.mention_count
        target.max_person_likelihood = max(target.max_person_likelihood, source.max_person_likelihood)
        target.model_person_hits += source.model_person_hits
        target.honorific_backed = target.honorific_backed or source.honorific_backed
        self.graph.add_edge(source_id, target_id, kind="canonical_merged_into", reason=reason)
        del self.canonical_characters[source_id]
        self.rebuild_indexes()

    def get_character(self, entity_id: str) -> Optional[CharacterMemory]:
        return self.canonical_characters.get(entity_id) or self.temporary_person_candidates.get(entity_id)

    def _create_canonical(self, name: str, chapter_index: int, window_index: int, seed_type: MentionType) -> str:
        name = self._normalize_entity_surface(name)
        if not name:
            return ""
        self._canonical_counter += 1
        entity_id = f"char_{self._canonical_counter}"
        _, honorific, _ = self.name_clusterer._parse_name(name)
        entity = CharacterMemory(
            entity_id=entity_id,
            canonical_name=name,
            status="canonical",
            first_seen_chapter=chapter_index,
            first_seen_window=window_index,
            last_seen_chapter=chapter_index,
            last_seen_window=window_index,
            seed_label_type=seed_type,
            honorific_backed=bool(honorific),
        )
        self._infer_gender(entity, name)
        self.canonical_characters[entity_id] = entity
        self.graph.add_node(entity_id, kind="character", name=name, status="canonical")
        self._index_character(entity)
        self._touch_caches(entity_id, stable=True)
        return entity_id

    def _create_temp_person(
        self,
        name: str,
        chapter_index: int,
        window_index: int,
        seed_type: MentionType,
        person_likelihood: float = 0.0,
        model_person_hit: bool = False,
    ) -> str:
        name = self._normalize_entity_surface(name)
        if not name:
            return ""
        self._temporary_counter += 1
        entity_id = f"temp_char_{self._temporary_counter}"
        _, honorific, _ = self.name_clusterer._parse_name(name)
        entity = CharacterMemory(
            entity_id=entity_id,
            canonical_name=name,
            status="temporary",
            first_seen_chapter=chapter_index,
            first_seen_window=window_index,
            last_seen_chapter=chapter_index,
            last_seen_window=window_index,
            seed_label_type=seed_type,
            max_person_likelihood=person_likelihood,
            model_person_hits=1 if model_person_hit else 0,
            honorific_backed=bool(honorific),
        )
        if seed_type == "title":
            entity.titles.add(name)
        elif seed_type == "role":
            entity.roles.add(name)
        elif seed_type == "descriptor":
            entity.descriptors.add(name)
        self.temporary_person_candidates[entity_id] = entity
        self.graph.add_node(entity_id, kind="character", name=name, status="temporary")
        self._index_character(entity)
        return entity_id

    def _index_character(self, entity: CharacterMemory) -> None:
        for label in {entity.canonical_name, *entity.aliases}:
            normalized = self._normalize(label)
            if normalized:
                self.alias_index[normalized].add(entity.entity_id)
        for title in entity.titles:
            normalized = self._normalize(title)
            if normalized:
                self.title_index[normalized].add(entity.entity_id)
        for role in entity.roles:
            normalized = self._normalize(role)
            if normalized:
                self.role_index[normalized].add(entity.entity_id)

    def rebuild_indexes(self) -> None:
        self.alias_index = defaultdict(set)
        self.title_index = defaultdict(set)
        self.role_index = defaultdict(set)
        for entity in self.canonical_characters.values():
            self._index_character(entity)
        for entity in self.temporary_person_candidates.values():
            self._index_character(entity)
        self.global_stable_cache = [item for item in self.global_stable_cache if item in self.canonical_characters]
        self.local_active_cache = [
            item for item in self.local_active_cache
            if item in self.canonical_characters or item in self.temporary_person_candidates
        ]

    def _touch_caches(self, entity_id: str, stable: bool = False) -> None:
        self.local_active_cache = [item for item in self.local_active_cache if item != entity_id]
        self.local_active_cache.append(entity_id)
        self.local_active_cache = self.local_active_cache[-18:]
        if stable or entity_id in self.canonical_characters:
            self.global_stable_cache = [item for item in self.global_stable_cache if item != entity_id]
            self.global_stable_cache.append(entity_id)
            self.global_stable_cache = self.global_stable_cache[-128:]

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _canonicalize_supporting_name(self, text: str) -> str:
        cleaned = self._normalize_entity_surface(text)
        if not cleaned:
            return ""
        return re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)

    def _normalize_entity_surface(self, text: str) -> str:
        cleaned = self.name_clusterer._normalize_surface(text)
        cleaned = re.sub(r"^[\"'“”‘’]+|[\"'“”‘’.,;:!?]+$", "", cleaned).strip()
        return cleaned

    def _infer_gender(self, entity: CharacterMemory, token: str) -> None:
        lowered_tokens = [item.lower().rstrip(".") for item in re.sub(r"\s+", " ", (token or "").strip()).split() if item]
        if any(item in {"she", "her", "hers", "lady", "queen", "princess", "mother", "sister", "daughter", "mrs", "ms"} for item in lowered_tokens):
            entity.gender = entity.gender or "female"
        elif any(item in {"he", "him", "his", "lord", "king", "prince", "father", "brother", "son", "mr", "sir"} for item in lowered_tokens):
            entity.gender = entity.gender or "male"


class LegacyAPIExtractionServiceUnused:
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 1024
    TEMPERATURE = 0.0
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self) -> None:
        self.available = True
        self.failure_reason = ""
        self.total_calls = 0
        self.failed_calls = 0
        self.last_outcome = "success"

    def extract(self, window: WindowRecord) -> List[ExtractedMention]:
        text_hash = str(hash(window.text))
        try:
            payload = self._cached_extract(window.chapter_index, window.window_index, text_hash, window.text)
        except requests.RequestException as exc:
            self.available = False
            self.failure_reason = repr(exc)
            self.failed_calls += 1
            self.last_outcome = "api_failure"
            return []
        if payload is None:
            self.last_outcome = "api_failure"
            return []
        try:
            mentions = self._parse_mentions(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self.failure_reason = repr(exc)
            self.failed_calls += 1
            self.last_outcome = "parse_failure"
            return []
        self.last_outcome = "empty" if not mentions else "success"
        return mentions[:300]

    @lru_cache(maxsize=128)
    def _cached_extract(self, chapter_index: int, window_index: int, text_hash: str, text: str) -> Optional[str]:
        _ = (chapter_index, window_index, text_hash)
        return self._call_api(text)

    def _call_api(self, text: str) -> Optional[str]:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            self.available = False
            self.failure_reason = "Missing ANTHROPIC_API_KEY"
            self.last_outcome = "api_failure"
            return None
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        system_prompt = (
            "You are an entity extraction engine for literary text. Extract every mention of a named or "
            "referred-to entity from the passage provided. For each mention return structured JSON only — "
            "no explanation, no markdown, no preamble.\n\n"
            'Return a JSON object with a single key "mentions" containing an array. Each element must have '
            'exactly these fields:\n'
            '- "text": the exact surface text of the mention as it appears in the passage\n'
            '- "canonical_form": your best single canonical name for the entity this mention refers to\n'
            '- "mention_type": one of "name", "pronoun", "descriptor", "title", "role"\n'
            '- "referent_type": one of "person", "location", "group", "object", "unknown"\n'
            '- "confidence": a float between 0.0 and 1.0\n'
            '- "in_quote": true if this mention appears inside dialogue, false otherwise\n\n'
            "Rules:\n"
            "- Include pronouns and resolve them to their most likely referent in context.\n"
            "- Include descriptors and resolve them.\n"
            "- Include titles used as address and attach them to their referent.\n"
            "- For locations, groups, and objects set referent_type accordingly and still include them.\n"
            "- Do not invent mentions. Only extract text that literally appears in the passage.\n"
            '- If a pronoun is ambiguous and you cannot resolve it, set canonical_form to "" and confidence to 0.2.\n'
            '- Canonical forms must be proper names, not descriptors.\n'
            "- Return every mention as a separate item, even if the same entity is mentioned multiple times. "
            "Do not deduplicate."
        )
        body = {
            "model": self.MODEL,
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.TEMPERATURE,
            "system": system_prompt,
            "messages": [{"role": "user", "content": text}],
        }
        self.total_calls += 1
        response = requests.post(self.API_URL, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        text_blocks = [item.get("text", "") for item in content if item.get("type") == "text"]
        return "\n".join(text_blocks).strip()

    def _strip_fences(self, text: str) -> str:
        stripped = text.strip()
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

    def _parse_mentions(self, payload: str) -> List[ExtractedMention]:
        cleaned = self._strip_fences(payload)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict) or "mentions" not in parsed or not isinstance(parsed["mentions"], list):
            raise ValueError("LLM response missing mentions array")
        mentions: List[ExtractedMention] = []
        for item in parsed["mentions"]:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            normalized.setdefault("start_char", -1)
            normalized.setdefault("end_char", -1)
            normalized.setdefault("sentence_index", -1)
            normalized.setdefault("source", "llm_extraction")
            mentions.append(ExtractedMention(**normalized))
        return mentions

class GLiNERExtractionService:
    _LEADING_VERB_FORMS = frozenset({
        "trailing", "leading", "following", "watching", "turning", "standing", "walking",
        "running", "sitting", "lying", "saying", "asking", "telling", "calling",
        "looking", "seeing", "hearing", "feeling", "playing", "moving", "holding",
        "shaking", "glancing", "smiling", "laughing", "crying", "shouting", "whispering",
        "hesitant", "surprised", "startled", "shocked",
    })
    _NAME_ENDING_PARTICLES = frozenset({"jr", "sr", "ii", "iii", "iv", "von", "de", "el", "al"})
    _BAD_FIRST_TOKEN_SUFFIXES = ("ing", "ly")
    _IMPERATIVE_VERB_FIRST_TOKENS = frozenset({
        "play", "go", "stop", "come", "look", "run", "wait", "stay", "get",
        "take", "make", "let", "put", "set", "find", "keep", "turn", "use",
    })
    _COMMON_WORD_BLOCKLIST = frozenset({
        "he", "she", "they", "it", "bastard", "handsome", "hesitant", "thick",
        "faster", "shh", "masklike", "void", "wolf", "thick", "shh", "faster",
        "brighter", "horror", "tattoos", "solstice-time",
    })

    def __init__(self, gliner_model_id: str = "urchade/gliner_small-v2.1") -> None:
        self._gliner_model = None
        self._gliner_available = False
        self._gliner_failure_reason = ""
        self._gliner_model_id = gliner_model_id
        self._gliner_labels = ["person", "character"]
        self._gliner_threshold = 0.65
        self._gliner_chunk_size = 380
        self._gliner_chunk_overlap = 40
        self._nlp = self._build_nlp()
        self._try_load_gliner()

    def _build_nlp(self):
        try:
            return spacy.load("en_core_web_sm")
        except Exception:
            nlp = spacy.blank("en")
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")
            return nlp

    def _try_load_gliner(self) -> None:
        try:
            self._gliner_model = GLiNER.from_pretrained(self._gliner_model_id)
            self._gliner_available = True
        except Exception as exc:
            self._gliner_available = False
            self._gliner_failure_reason = repr(exc)

    def _sentence_start_map(self, doc) -> List[Tuple[int, int]]:
        return [(sent.start_char, index) for index, sent in enumerate(doc.sents)]

    def _lookup_sentence_index(self, sentence_starts: List[Tuple[int, int]], start_char: int) -> int:
        index = 0
        for sent_start, sent_index in sentence_starts:
            if sent_start <= start_char:
                index = sent_index
            else:
                break
        return index

    def _clean_span_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        return re.sub(r"^[\"'“”‘’]+|[\"'“”‘’.,;:!?]+$", "", cleaned)

    def _is_in_quote(self, text: str, start_char: int) -> bool:
        return len(QUOTE_PATTERN.findall(text[:start_char])) % 2 == 1

    def _covered_by(self, start: int, end: int, ranges: set[tuple[int, int]]) -> bool:
        for r_start, r_end in ranges:
            overlap = max(0, min(end, r_end) - max(start, r_start))
            span_len = max(1, end - start)
            if overlap / span_len >= 0.5:
                return True
        return False

    def _spans_overlap(self, a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        return max(0, min(a_end, b_end) - max(a_start, b_start)) > 0

    def _looks_sane_gliner_person_span(self, text: str) -> bool:
        tokens = [token.strip(".,;:!?\"'“”‘’()[]{}") for token in text.split() if token.strip(".,;:!?\"'“”‘’()[]{}")]
        if not tokens:
            return False
        if len(tokens) > 4:
            return False
        if any(mark in text for mark in {",", ";", ":", "\"", "“", "”", "‘", "’"}):
            return False
        if not any(token[:1].isupper() for token in tokens if token[:1].isalpha()):
            return False
        if tokens[0].lower() in self._LEADING_VERB_FORMS:
            return False
        last_token = tokens[-1].strip(".,;:!?\"'“”‘’()[]{}").lower()
        last_token_raw = tokens[-1].strip(".,;:!?\"'“”‘’()[]{}")
        if not last_token_raw[:1].isupper() and last_token not in self._NAME_ENDING_PARTICLES:
            return False
        if len(tokens) > 1:
            first_token_lower = tokens[0].strip(".,;:!?\"'“”‘’()[]{}").lower()
            if first_token_lower.endswith(self._BAD_FIRST_TOKEN_SUFFIXES) and first_token_lower not in HONORIFICS:
                return False
            if first_token_lower in self._IMPERATIVE_VERB_FIRST_TOKENS:
                return False
        if len(tokens) == 1 and tokens[0].lower() in self._COMMON_WORD_BLOCKLIST:
            return False
        if any(token.islower() and token.lower() not in HONORIFICS for token in tokens if token.isalpha()):
            return False
        return True

    def _extract_gliner_mentions(self, text: str, sentence_starts: List[Tuple[int, int]]) -> List[ExtractedMention]:
        if not self._gliner_available or not self._gliner_model:
            return []
        raw_hits: List[Tuple[int, int, str, float]] = []
        words = text.split()
        if not words:
            return []
        step = self._gliner_chunk_size - self._gliner_chunk_overlap
        chunk_start_word = 0
        while chunk_start_word < len(words):
            chunk_end_word = min(chunk_start_word + self._gliner_chunk_size, len(words))
            chunk_text = " ".join(words[chunk_start_word:chunk_end_word])
            char_offset = len(" ".join(words[:chunk_start_word])) + (1 if chunk_start_word > 0 else 0)
            try:
                predictions = self._gliner_model.predict_entities(chunk_text, self._gliner_labels, threshold=self._gliner_threshold)
            except Exception:
                predictions = []
            for item in predictions:
                raw_hits.append((char_offset + int(item["start"]), char_offset + int(item["end"]), str(item["text"]), float(item["score"])))
            if chunk_end_word >= len(words):
                break
            chunk_start_word += step
        raw_hits.sort(key=lambda h: (-h[3], h[0]))
        kept: List[Tuple[int, int, str, float]] = []
        for hit in raw_hits:
            if not any(self._spans_overlap(hit[0], hit[1], k[0], k[1]) for k in kept):
                kept.append(hit)
        output: List[ExtractedMention] = []
        for start_char, end_char, span_text, score in kept:
            cleaned = self._clean_span_text(span_text)
            if not cleaned:
                continue
            if not self._looks_sane_gliner_person_span(cleaned):
                continue
            output.append(
                ExtractedMention(
                    text=cleaned,
                    canonical_form=cleaned,
                    mention_type="name",
                    referent_type="person",
                    confidence=score,
                    start_char=start_char,
                    end_char=end_char,
                    sentence_index=self._lookup_sentence_index(sentence_starts, start_char),
                    in_quote=self._is_in_quote(text, start_char),
                    source="ent_gliner",
                )
            )
        return output

    def _dedupe(self, mentions: Iterable[ExtractedMention]) -> List[ExtractedMention]:
        ordered = sorted(
            mentions,
            key=lambda item: (
                item.start_char,
                -(item.end_char - item.start_char),
                {"ent_gliner": 0, "ent_person": 1, "ent_supporting": 2, "pronoun": 3}.get(item.source, 99),
                item.source,
            ),
        )
        output: List[ExtractedMention] = []
        seen = set()
        active_end = -1
        for item in ordered:
            key = (item.start_char, item.end_char, item.text.lower(), item.source)
            if key in seen:
                continue
            seen.add(key)
            if item.start_char < active_end and item.source != "pronoun":
                continue
            output.append(item)
            if item.source != "pronoun":
                active_end = item.end_char
        return output

    def extract(self, window: WindowRecord) -> List[ExtractedMention]:
        doc = self._nlp(window.text)
        sentence_starts = self._sentence_start_map(doc)
        mentions: List[ExtractedMention] = []
        gliner_mentions = self._extract_gliner_mentions(window.text, sentence_starts)
        mentions.extend(gliner_mentions)
        gliner_ranges = {(m.start_char, m.end_char) for m in gliner_mentions}
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                if not self._covered_by(ent.start_char, ent.end_char, gliner_ranges):
                    cleaned = self._clean_span_text(ent.text)
                    if cleaned and self._looks_sane_gliner_person_span(cleaned):
                        mentions.append(
                            ExtractedMention(
                                text=cleaned,
                                canonical_form=cleaned,
                                mention_type="name",
                                referent_type="person",
                                confidence=0.9,
                                start_char=ent.start_char,
                                end_char=ent.end_char,
                                sentence_index=self._lookup_sentence_index(sentence_starts, ent.start_char),
                                in_quote=self._is_in_quote(window.text, ent.start_char),
                                source="ent_person",
                            )
                        )
            elif ent.label_ in SUPPORTING_ENTITY_LABELS:
                cleaned = self._clean_span_text(ent.text)
                if cleaned:
                    mentions.append(
                        ExtractedMention(
                            text=cleaned,
                            canonical_form=cleaned,
                            mention_type="name",
                            referent_type=SUPPORTING_ENTITY_LABELS[ent.label_],
                            confidence=0.8,
                            start_char=ent.start_char,
                            end_char=ent.end_char,
                            sentence_index=self._lookup_sentence_index(sentence_starts, ent.start_char),
                            in_quote=self._is_in_quote(window.text, ent.start_char),
                            source="ent_supporting",
                        )
                    )
        for token in doc:
            if token.text.lower() in PRONOUN_GENDER:
                mentions.append(
                    ExtractedMention(
                        text=token.text,
                        canonical_form="",
                        mention_type="pronoun",
                        referent_type="person",
                        confidence=0.7,
                        start_char=token.idx,
                        end_char=token.idx + len(token.text),
                        sentence_index=self._lookup_sentence_index(sentence_starts, token.idx),
                        in_quote=self._is_in_quote(window.text, token.idx),
                        source="pronoun",
                    )
                )
        return self._dedupe(mentions)


class WindowResolver:
    _MODIFIER_PREFIXES = frozenset({
        "stupid", "foolish", "leave", "dear", "poor", "damn", "bloody", "wretched",
    })
    _NAME_PARTICLES = frozenset({"jr", "sr", "ii", "iii", "iv", "von", "de", "el", "al"})
    _NON_PERSON_SINGLE_TOKEN_BLOCKLIST = frozenset({
        "bomb", "brighter", "catching", "chains", "dark", "faerie", "gaudy", "greenbriar",
        "handsome", "hesitant", "horror", "hogwarts", "house", "licked", "magic", "mist",
        "muggles", "nightfell", "perfume", "quidditch", "rita", "roofed", "seelie",
        "shh", "sidra", "snap", "solstice", "starfall", "stung", "tattoos", "thick",
        "tick", "undersea", "velaris",
    })
    _NON_PERSON_EXACT_SURFACES = frozenset({
        "autumn court", "blood rite", "caraval", "castillo maldito", "chocolate frogs",
        "cold season", "conquered isles", "court of shadows", "dark mark", "del ojos beach",
        "diagon alley", "glass tavern", "great hall", "greenbriar", "gryffindor",
        "hewn city", "high court", "high king", "high king eldred", "high lord", "high lady",
        "house of wind", "hollow hall", "hufflepuff", "illyrian mountains", "king cross",
        "meridian empire", "ministry of magic", "night court", "nightfell", "privet drive",
        "prythian", "quidditch", "rainbow", "ravenclaw", "sidra", "solstice", "solstice eve",
        "sorcerer stone", "spring court", "starfall", "summer court", "undersea", "velaris",
    })
    _NON_PERSON_ANYWHERE_MARKERS = frozenset({
        "autumn", "blood", "caraval", "castle", "castillo", "city", "court", "drive",
        "eve", "fae", "faerie", "fall", "forest", "gringotts", "hall", "high", "hogwarts",
        "house", "hybern", "illyrian", "king", "kingdom", "lord", "magic", "master",
        "ministry", "mountain", "mountains", "night", "prythian", "quidditch", "rite",
        "river", "road", "seelie", "sidra", "solstice", "spring", "starfall", "street",
        "summer", "tournament", "undersea", "velaris", "wind", "winter",
    })

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _confidence_bucket(self, score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.5:
            return "medium"
        return "low"

    def _clean_tokens(self, text: str) -> List[str]:
        return [
            token.strip(".,;:!?\"'()[]{}")
            for token in (text or "").split()
            if token.strip(".,;:!?\"'()[]{}")
        ]

    def _strip_modifier_prefix(self, text: str) -> str:
        tokens = self._clean_tokens(text)
        if len(tokens) < 2:
            return re.sub(r"\s+", " ", (text or "").strip())
        first_lower = tokens[0].lower()
        if first_lower not in self._MODIFIER_PREFIXES:
            return re.sub(r"\s+", " ", (text or "").strip())
        remainder = tokens[1:]
        if not any(token[:1].isupper() for token in remainder):
            return re.sub(r"\s+", " ", (text or "").strip())
        return " ".join(remainder)

    def _looks_non_person_surface(self, text: str) -> bool:
        tokens = self._clean_tokens(text)
        if not tokens:
            return True
        lowered = [token.lower().rstrip(".") for token in tokens]
        normalized_text = " ".join(lowered)
        if normalized_text in self._NON_PERSON_EXACT_SURFACES:
            return True
        if lowered[0] in {"not", "no", "never"}:
            return True
        if len(tokens) == 1 and lowered[0] in self._NON_PERSON_SINGLE_TOKEN_BLOCKLIST:
            return True
        if lowered[-1] in {"alley", "frogs", "court", "city", "stone", "mountains", "hall", "drive", "beach", "tavern"}:
            return True
        if any(token in self._NON_PERSON_ANYWHERE_MARKERS for token in lowered):
            return True
        if len(tokens) >= 2 and lowered[-1] in {"eve", "hall", "house", "mountains", "rite", "tournament"}:
            return True
        return False

    def _looks_human_name_surface(self, text: str) -> bool:
        tokens = self._clean_tokens(text)
        if not tokens:
            return False
        if self._looks_non_person_surface(text):
            return False
        lowered = [token.lower().rstrip(".") for token in tokens]
        if lowered[0] in HONORIFICS and len(tokens) >= 2:
            return all(token[:1].isupper() or token.lower() in self._NAME_PARTICLES for token in tokens[1:])
        if len(tokens) == 1:
            token = tokens[0]
            lower = lowered[0]
            if not token[:1].isupper():
                return False
            if lower in SHARED_TITLES or lower in PERSONISH_NOUNS:
                return False
            return True
        return all(
            token[:1].isupper() or token.lower() in self._NAME_PARTICLES
            for token in tokens
        )

    def _can_seed_canonical(self, text: str) -> bool:
        tokens = self._clean_tokens(text)
        if not self._looks_human_name_surface(text):
            return False
        lowered = [token.lower().rstrip(".") for token in tokens]
        if lowered and lowered[0] in HONORIFICS:
            return len(tokens) >= 2
        return len(tokens) >= 2

    def _recent_entity_fallback(
        self,
        mention: ExtractedMention,
        memory: IdentityMemoryManager,
    ) -> str:
        wanted_gender = PRONOUN_GENDER.get(mention.text.lower(), "")
        for entity_id in reversed(memory.local_active_cache):
            entity = memory.get_character(entity_id)
            if not entity:
                continue
            if wanted_gender and entity.gender and entity.gender not in {wanted_gender, "plural"}:
                continue
            return entity_id
        return ""

    def _record_history(
        self,
        mention_history_index: DefaultDict[str, List[MentionHistoryRecord]],
        mention: ExtractedMention,
        route: str,
        chapter_index: int,
        window_index: int,
        sentence_text: str,
        history_key: str,
        syntactic_role: str = "other",
    ) -> None:
        positive: Dict[str, float] = {}
        negative: Dict[str, float] = {}
        entity_label = ""
        if mention.referent_type == "person":
            positive["llm_person_confidence"] = mention.confidence
            if mention.mention_type == "name":
                positive["proper_name_source"] = 0.10
            if mention.in_quote and mention.mention_type == "name":
                positive["in_quote"] = 0.03
                syntactic_role = "subject"
        elif mention.referent_type in {"location", "group", "object"}:
            negative["supporting_llm"] = 0.48
            if mention.referent_type == "location":
                entity_label = "LOC"
            elif mention.referent_type == "group":
                entity_label = "NORP"
            elif mention.referent_type == "object":
                entity_label = "PRODUCT"
        mention_history_index[history_key].append(
            MentionHistoryRecord(
                surface_text=mention.text,
                canonical_form=mention.canonical_form,
                mention_type=mention.mention_type,
                referent_type=mention.referent_type,
                confidence=mention.confidence,
                route=route,
                chapter_index=chapter_index,
                window_index=window_index,
                sentence_index=mention.sentence_index,
                sentence_text=sentence_text,
                in_quote=mention.in_quote,
                source=mention.source,
                positive_features=positive,
                negative_features=negative,
                entity_label=entity_label,
                syntactic_role=syntactic_role,
                head_lemma=(mention.canonical_form or mention.text).split()[-1].lower() if (mention.canonical_form or mention.text) else "",
            )
        )

    def resolve(
        self,
        mentions: List[ExtractedMention],
        window: WindowRecord,
        memory: IdentityMemoryManager,
        name_clusterer: NameClusterer,
        mention_log: List[Mention],
        resolution_log: List[ResolutionRecord],
        mention_history_index: DefaultDict[str, List[MentionHistoryRecord]],
        resolved_layer_updates: List[Dict],
        pov_prior_id: str = "",
    ) -> None:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", window.text) if segment.strip()]
        for mention in mentions:
            if mention.confidence < 0.35 or mention.referent_type == "unknown":
                continue
            sentence_text = sentences[mention.sentence_index] if 0 <= mention.sentence_index < len(sentences) else ""
            canonical_form = self._strip_modifier_prefix(re.sub(r"\s+", " ", (mention.canonical_form or "").strip()))
            history_surface = canonical_form or mention.text
            history_key = self._normalize(history_surface)

            if mention.referent_type in {"location", "group", "object"}:
                display_name = canonical_form or mention.text
                support_id = memory.register_supporting_by_name(display_name, mention.referent_type, window.chapter_index, window.window_index)
                self._record_history(
                    mention_history_index,
                    mention,
                    "supporting",
                    window.chapter_index,
                    window.window_index,
                    sentence_text,
                    self._normalize(display_name),
                )
                mention_log.append(
                    Mention(
                        text=mention.text,
                        mention_type=mention.mention_type,
                        start=mention.start_char,
                        end=mention.end_char,
                        chapter_index=window.chapter_index,
                        window_index=window.window_index,
                        sentence_index=mention.sentence_index,
                        resolved_to=support_id,
                        score=round(mention.confidence, 3),
                        method="llm_supporting",
                        confidence=self._confidence_bucket(mention.confidence),
                        status="resolved",
                        route="supporting",
                        typed_label=f"llm_{mention.referent_type}",
                    )
                )
                resolution_log.append(
                    ResolutionRecord(
                        mention_text=mention.text,
                        mention_type=mention.mention_type,
                        route="supporting",
                        candidate_scores={},
                        resolved_to=support_id,
                        status="resolved",
                        method="llm_supporting",
                        confidence=self._confidence_bucket(mention.confidence),
                    )
                )
                continue

            if mention.referent_type == "person" and mention.mention_type == "pronoun":
                candidates = memory.resolve_pronoun_candidates(mention.text)
                if candidates:
                    entity_id = candidates[0]
                    memory.attach_mention_by_id(entity_id, mention.text, "pronoun", window.chapter_index, window.window_index)
                    self._record_history(
                        mention_history_index,
                        mention,
                        "pronoun",
                        window.chapter_index,
                        window.window_index,
                        sentence_text,
                        self._normalize(memory.get_character(entity_id).canonical_name if memory.get_character(entity_id) else mention.text),
                    )
                    mention_log.append(
                        Mention(
                            text=mention.text,
                            mention_type="pronoun",
                            start=mention.start_char,
                            end=mention.end_char,
                            chapter_index=window.chapter_index,
                            window_index=window.window_index,
                            sentence_index=mention.sentence_index,
                            resolved_to=entity_id,
                            score=round(mention.confidence, 3),
                            method="llm_pronoun_resolution",
                            confidence=self._confidence_bucket(mention.confidence),
                            status="resolved",
                            route="pronoun",
                            typed_label="llm_person",
                        )
                    )
                    resolution_log.append(
                        ResolutionRecord(
                            mention_text=mention.text,
                            mention_type="pronoun",
                            route="pronoun",
                            candidate_scores={entity_id: round(mention.confidence, 3)},
                            resolved_to=entity_id,
                            status="resolved",
                            method="llm_pronoun_resolution",
                            confidence=self._confidence_bucket(mention.confidence),
                        )
                    )
                else:
                    resolution_log.append(
                        ResolutionRecord(
                            mention_text=mention.text,
                            mention_type="pronoun",
                            route="pronoun",
                            candidate_scores={},
                            resolved_to="",
                            status="unresolved",
                            method="llm_pronoun_unresolved",
                            confidence="low",
                        )
                    )
                continue

            if mention.referent_type != "person":
                continue

            if canonical_form and self._looks_non_person_surface(canonical_form):
                normalized_tokens = set(self._normalize(canonical_form).split())
                support_kind: SupportingEntityKind = "group" if normalized_tokens & {"court", "fae", "muggles", "seelie"} else "location"
                support_id = memory.register_supporting_by_name(canonical_form, support_kind, window.chapter_index, window.window_index)
                self._record_history(
                    mention_history_index,
                    mention,
                    "supporting",
                    window.chapter_index,
                    window.window_index,
                    sentence_text,
                    self._normalize(canonical_form),
                )
                mention_log.append(
                    Mention(
                        text=mention.text,
                        mention_type="name",
                        start=mention.start_char,
                        end=mention.end_char,
                        chapter_index=window.chapter_index,
                        window_index=window.window_index,
                        sentence_index=mention.sentence_index,
                        resolved_to=support_id,
                        score=round(mention.confidence, 3),
                        method="llm_person_demoted_to_supporting",
                        confidence=self._confidence_bucket(mention.confidence),
                        status="resolved",
                        route="supporting",
                        typed_label="llm_non_person_surface",
                    )
                )
                resolution_log.append(
                    ResolutionRecord(
                        mention_text=mention.text,
                        mention_type="name",
                        route="supporting",
                        candidate_scores={},
                        resolved_to=support_id,
                        status="resolved",
                        method="llm_person_demoted_to_supporting",
                        confidence=self._confidence_bucket(mention.confidence),
                    )
                )
                continue

            entity_id = ""
            route: SpanRoute = "quarantine"

            if canonical_form:
                alias_hits = sorted(memory.alias_index.get(self._normalize(canonical_form), set()))
                if len(alias_hits) == 1:
                    entity_id = alias_hits[0]
                if not entity_id:
                    entity_id = name_clusterer.match_canonical(canonical_form, memory.canonical_characters) or name_clusterer.match_canonical(canonical_form, memory.temporary_person_candidates)
            if not entity_id and mention.mention_type in {"descriptor", "title", "role"}:
                entity_id = self._recent_entity_fallback(mention, memory)

            if entity_id:
                route = "canonical_seed" if entity_id in memory.canonical_characters else "temporary_person"
                memory.attach_mention_by_id(entity_id, mention.text, mention.mention_type, window.chapter_index, window.window_index)
                if mention.mention_type in {"title", "role", "descriptor"}:
                    memory.attach_title_or_role(entity_id, mention.text, mention.mention_type)
                target = memory.get_character(entity_id)
                history_name = target.canonical_name if target else (canonical_form or mention.text)
                self._record_history(
                    mention_history_index,
                    mention,
                    route,
                    window.chapter_index,
                    window.window_index,
                    sentence_text,
                    self._normalize(history_name),
                )
                mention_log.append(
                    Mention(
                        text=mention.text,
                        mention_type=mention.mention_type,
                        start=mention.start_char,
                        end=mention.end_char,
                        chapter_index=window.chapter_index,
                        window_index=window.window_index,
                        sentence_index=mention.sentence_index,
                        resolved_to=entity_id,
                        score=round(mention.confidence, 3),
                        method="llm_existing_match",
                        confidence=self._confidence_bucket(mention.confidence),
                        status="resolved",
                        route=route,
                        typed_label="llm_person",
                    )
                )
                resolution_log.append(
                    ResolutionRecord(
                        mention_text=mention.text,
                        mention_type=mention.mention_type,
                        route=route,
                        candidate_scores={entity_id: round(mention.confidence, 3)},
                        resolved_to=entity_id,
                        status="resolved",
                        method="llm_existing_match",
                        confidence=self._confidence_bucket(mention.confidence),
                    )
                )
                if entity_id.startswith("char_") and mention.confidence >= 0.8:
                    resolved_layer_updates.append(
                        {
                            "entity_id": entity_id,
                            "mention_text": mention.text,
                            "chapter_index": window.chapter_index,
                            "window_index": window.window_index,
                            "confidence": self._confidence_bucket(mention.confidence),
                            "method": "llm_existing_match",
                            "update_type": "high_confidence_resolution",
                        }
                    )
                continue

            if mention.mention_type != "name" or not canonical_form:
                weak_id = memory.remember_weak_mention_by_text(
                    mention.text,
                    mention.mention_type,
                    mention.confidence,
                    window.chapter_index,
                    window.window_index,
                )
                self._record_history(
                    mention_history_index,
                    mention,
                    "quarantine",
                    window.chapter_index,
                    window.window_index,
                    sentence_text,
                    self._normalize(mention.text),
                )
                resolution_log.append(
                    ResolutionRecord(
                        mention_text=mention.text,
                        mention_type=mention.mention_type,
                        route="quarantine",
                        candidate_scores={},
                        resolved_to=weak_id,
                        status="unresolved",
                        method="llm_weak_quarantine",
                        confidence="low",
                    )
                )
                continue

            if mention.confidence >= 0.85 and self._can_seed_canonical(canonical_form):
                entity_id = memory.seed_or_match_canonical_name(canonical_form, window.chapter_index, window.window_index, "name")
                route = "canonical_seed"
                memory.attach_mention_by_id(entity_id, mention.text, "name", window.chapter_index, window.window_index)
            elif mention.confidence >= 0.60:
                if self._looks_human_name_surface(canonical_form):
                    entity_id = memory.create_temp_if_supported(
                        canonical_form,
                        window.chapter_index,
                        window.window_index,
                        mention.confidence,
                        "name",
                        has_model_person=True,
                        has_ner_person=True,
                    )
                    if entity_id:
                        memory.attach_mention_by_id(entity_id, mention.text, "name", window.chapter_index, window.window_index)
                        promoted = memory.maybe_promote_temporary_to_canonical(entity_id) if self._can_seed_canonical(canonical_form) else ""
                        if promoted and self._can_seed_canonical(memory.get_character(promoted).canonical_name if memory.get_character(promoted) else canonical_form):
                            entity_id = promoted
                            route = "canonical_seed"
                        else:
                            route = "temporary_person"
                    else:
                        route = "quarantine"
                else:
                    route = "quarantine"
            else:
                route = "quarantine"

            if route == "quarantine" or not entity_id:
                weak_id = memory.remember_weak_mention_by_text(
                    canonical_form or mention.text,
                    "name",
                    mention.confidence,
                    window.chapter_index,
                    window.window_index,
                )
                self._record_history(
                    mention_history_index,
                    mention,
                    "quarantine",
                    window.chapter_index,
                    window.window_index,
                    sentence_text,
                    self._normalize(canonical_form or mention.text),
                )
                resolution_log.append(
                    ResolutionRecord(
                        mention_text=mention.text,
                        mention_type="name",
                        route="quarantine",
                        candidate_scores={},
                        resolved_to=weak_id,
                        status="unresolved",
                        method="llm_weak_quarantine",
                        confidence="low",
                    )
                )
                continue

            target = memory.get_character(entity_id)
            history_name = target.canonical_name if target else canonical_form
            self._record_history(
                mention_history_index,
                mention,
                route,
                window.chapter_index,
                window.window_index,
                sentence_text,
                self._normalize(history_name),
            )
            mention_log.append(
                Mention(
                    text=mention.text,
                    mention_type="name",
                    start=mention.start_char,
                    end=mention.end_char,
                    chapter_index=window.chapter_index,
                    window_index=window.window_index,
                    sentence_index=mention.sentence_index,
                    resolved_to=entity_id,
                    score=round(mention.confidence, 3),
                    method="llm_new_entity",
                    confidence=self._confidence_bucket(mention.confidence),
                    status="resolved" if route == "canonical_seed" else "tentative",
                    route=route,
                    typed_label="llm_person",
                )
            )
            resolution_log.append(
                ResolutionRecord(
                    mention_text=mention.text,
                    mention_type="name",
                    route=route,
                    candidate_scores={entity_id: round(mention.confidence, 3)},
                    resolved_to=entity_id,
                    status="resolved" if route == "canonical_seed" else "tentative",
                    method="llm_new_entity",
                    confidence=self._confidence_bucket(mention.confidence),
                )
            )


class DeterministicIdentityResolver:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.extractor = GLiNERExtractionService()
        self.resolver = WindowResolver()
        self.name_clusterer = NameClusterer()
        self.memory = IdentityMemoryManager(self.graph, self.name_clusterer)
        self.mention_log: List[Mention] = []
        self.resolution_log: List[ResolutionRecord] = []
        self.resolved_layer_updates: List[Dict] = []
        self.mention_history_index: DefaultDict[str, List[MentionHistoryRecord]] = defaultdict(list)
        self._stabilized = False
        self.stabilization_metrics: Dict[str, int] = {}
        self.extraction_metrics: Dict[str, int] = {
            "gliner_spans_proposed": 0,
            "spacy_person_spans_proposed": 0,
            "gliner_unavailable_windows": 0,
        }

    def process_epub(
        self,
        path: str | Path,
        *,
        max_chapters: int = 9999,
        max_windows: int = 999999,
        paragraphs_per_window: int = 6,
        overlap_paragraphs: int = 1,
        progress_callback=None,
    ) -> Dict:
        processor = EPUBProcessor()
        raw_chapters = processor.process(str(path))
        windows_processed = 0
        total_chapters = min(len(raw_chapters), max_chapters)
        for chapter_index, chapter in enumerate(raw_chapters[:max_chapters], start=1):
            if progress_callback:
                progress_callback(chapter_index, total_chapters, chapter.get("chapter_title", ""))
            windows = self._build_windows(
                chapter.get("content", ""),
                chapter_index=chapter_index,
                chapter_title=chapter.get("chapter_title", ""),
                paragraphs_per_window=paragraphs_per_window,
                overlap_paragraphs=overlap_paragraphs,
            )
            for window in windows:
                self.process_window(window)
                windows_processed += 1
                if windows_processed >= max_windows:
                    return self.build_result()
        return self.build_result()

    def process_window(self, window: WindowRecord) -> None:
        pov_prior_name, _ = self._establish_window_prior(window)
        pov_prior_id = self.name_clusterer.match_canonical(pov_prior_name, self.memory.canonical_characters) if pov_prior_name else ""
        mentions = self.extractor.extract(window)
        self.extraction_metrics["gliner_spans_proposed"] += sum(1 for item in mentions if item.source == "ent_gliner")
        self.extraction_metrics["spacy_person_spans_proposed"] += sum(1 for item in mentions if item.source == "ent_person")
        if not self.extractor._gliner_available:
            self.extraction_metrics["gliner_unavailable_windows"] += 1
        self.resolver.resolve(
            mentions=mentions,
            window=window,
            memory=self.memory,
            name_clusterer=self.name_clusterer,
            mention_log=self.mention_log,
            resolution_log=self.resolution_log,
            mention_history_index=self.mention_history_index,
            resolved_layer_updates=self.resolved_layer_updates,
            pov_prior_id=pov_prior_id,
        )

    def build_result(self) -> Dict:
        self._run_postpass_stabilization()
        profiles = self._build_entity_profiles()
        canonical_payload = {
            entity_id: self._serialize_character(entity)
            for entity_id, entity in sorted(
                self.memory.canonical_characters.items(),
                key=lambda item: (item[1].first_seen_chapter, item[1].first_seen_window, item[1].canonical_name.lower()),
            )
        }
        temporary_payload = {
            entity_id: self._serialize_character(entity)
            for entity_id, entity in sorted(
                self.memory.temporary_person_candidates.items(),
                key=lambda item: (item[1].first_seen_chapter, item[1].first_seen_window, item[1].canonical_name.lower()),
            )
        }
        weak_payload = {
            weak_id: self._serialize_weak_mention(entity)
            for weak_id, entity in sorted(
                self.memory.weak_mentions_quarantine.items(),
                key=lambda item: (item[1].first_seen_chapter, item[1].first_seen_window, item[1].text.lower()),
            )
        }
        meaningful_supporting, discarded_supporting = self._partition_supporting_entities()
        supporting_payload = {entity_id: self._serialize_supporting_entity(entity) for entity_id, entity in meaningful_supporting.items()}
        discarded_payload = {entity_id: self._serialize_supporting_entity(entity) for entity_id, entity in discarded_supporting.items()}
        return {
            "canonical_characters": canonical_payload,
            "temporary_person_candidates": temporary_payload,
            "weak_mentions_quarantine": weak_payload,
            "supporting_entities": supporting_payload,
            "meaningful_supporting_entities": supporting_payload,
            "discarded_non_character_mentions": discarded_payload,
            "evaluation_summary": {
                "canonical_count": len(canonical_payload),
                "temporary_count": len(temporary_payload),
                "quarantine_count": len(weak_payload),
                "supporting_count": len(supporting_payload),
                "discarded_non_character_count": len(discarded_payload),
                "stabilization_metrics": dict(self.stabilization_metrics),
                "extraction_metrics": {
                    "gliner_available": self.extractor._gliner_available,
                    "gliner_failure_reason": self.extractor._gliner_failure_reason,
                    "gliner_spans_proposed": self.extraction_metrics["gliner_spans_proposed"],
                    "spacy_person_spans_proposed": self.extraction_metrics["spacy_person_spans_proposed"],
                    "gliner_unavailable_windows": self.extraction_metrics["gliner_unavailable_windows"],
                },
                "top_false_positive_canonicals": self._top_false_positive_canonicals(canonical_payload, profiles),
                "top_remaining_likely_person_supporting_entities": self._top_likely_person_supporting_entities(meaningful_supporting, profiles),
                "suspicious_entity_diagnostics": self._suspicious_entity_diagnostics(profiles),
                "temporary_candidates_diagnostics": [
                    {
                        "name": entity.canonical_name,
                        "mention_count": entity.mention_count,
                        "unique_windows": len(set(entity.evidence_windows)),
                        "max_person_likelihood": entity.max_person_likelihood,
                        "model_person_hits": entity.model_person_hits,
                        "honorific_backed": entity.honorific_backed,
                    }
                    for entity in sorted(
                        self.memory.temporary_person_candidates.values(),
                        key=lambda item: (-item.mention_count, item.canonical_name.lower()),
                    )
                ],
            },
            "title_index": {key: sorted(value) for key, value in sorted(self.memory.title_index.items())},
            "role_index": {key: sorted(value) for key, value in sorted(self.memory.role_index.items())},
            "mentions": [item.model_dump() for item in self.mention_log],
            "resolutions": [item.model_dump() for item in self.resolution_log],
            "resolved_layer_updates": list(self.resolved_layer_updates),
            "graph_nodes": list(self.graph.nodes(data=True)),
            "graph_edges": list(self.graph.edges(data=True)),
        }

    def _exportable_aliases(self, canonical_name: str, aliases: set[str]) -> List[str]:
        cleaned: set[str] = set()
        for alias in {canonical_name} | aliases:
            alias = (alias or "").strip()
            if not alias:
                continue
            if self.resolver._looks_non_person_surface(alias):
                continue
            if alias != canonical_name and not self.resolver._looks_human_name_surface(alias):
                continue
            cleaned.add(alias)
        return sorted(cleaned, key=str.lower)

    def _should_export_canonical_entity(self, entity: CharacterMemory) -> bool:
        canonical_name = (entity.canonical_name or "").strip()
        if not canonical_name or self.resolver._looks_non_person_surface(canonical_name):
            return False
        _, honorific, core_tokens = self.name_clusterer._parse_name(canonical_name)
        if honorific and len(core_tokens) >= 1:
            return entity.mention_count >= 2 or entity.max_person_likelihood >= 0.72
        if len(core_tokens) >= 2:
            return entity.mention_count >= 2 or entity.max_person_likelihood >= 0.7
        return entity.mention_count >= 4 and (entity.max_person_likelihood >= 0.82 or entity.model_person_hits >= 2)

    def _should_export_temporary_entity(self, entity: CharacterMemory) -> bool:
        canonical_name = (entity.canonical_name or "").strip()
        if not canonical_name or self.resolver._looks_non_person_surface(canonical_name):
            return False
        _, honorific, core_tokens = self.name_clusterer._parse_name(canonical_name)
        if honorific and len(core_tokens) >= 1:
            return entity.mention_count >= 4 and entity.max_person_likelihood >= 0.78
        if len(core_tokens) >= 2:
            return entity.mention_count >= 6 and entity.max_person_likelihood >= 0.82 and entity.model_person_hits >= 1
        return False

    def build_identity_result(self) -> Dict:
        if not self._stabilized:
            self._run_postpass_stabilization()

        alias_map: Dict[str, List[str]] = {}
        rejected_non_characters: List[str] = []
        decisions: List[Dict] = []
        alias_history: List[Dict] = []

        for entity in self.memory.canonical_characters.values():
            canonical_name = (entity.canonical_name or "").strip()
            if not canonical_name:
                continue
            if self.resolver._looks_non_person_surface(canonical_name):
                rejected_non_characters.append(canonical_name)
                continue
            if not self._should_export_canonical_entity(entity):
                continue
            exported_aliases = self._exportable_aliases(canonical_name, entity.aliases)
            if not exported_aliases:
                continue
            alias_map[canonical_name] = exported_aliases
            decisions.append(
                {
                    "decision_type": "resolver_canonical",
                    "character": canonical_name,
                    "canonical_name": canonical_name,
                    "same_character": True,
                    "confidence": round(min(1.0, entity.max_person_likelihood), 3),
                    "reasoning": (
                        f"Canonical entity. mention_count={entity.mention_count}, "
                        f"first_seen=ch{entity.first_seen_chapter}w{entity.first_seen_window}."
                    ),
                    "scene_ref": {
                        "chapter_index": entity.first_seen_chapter,
                        "window_index": entity.first_seen_window,
                    },
                }
            )
            for alias in sorted(entity.aliases, key=str.lower):
                if alias != canonical_name and alias in alias_map[canonical_name]:
                    alias_history.append(
                        {
                            "canonical_name": canonical_name,
                            "alias_name": alias,
                            "scene_ref": {
                                "chapter_index": entity.first_seen_chapter,
                                "window_index": entity.first_seen_window,
                            },
                        }
                    )

        for entity in self.memory.temporary_person_candidates.values():
            canonical_name = (entity.canonical_name or "").strip()
            if not canonical_name or canonical_name in alias_map:
                continue
            if self.resolver._looks_non_person_surface(canonical_name):
                rejected_non_characters.append(canonical_name)
                continue
            if not self._should_export_temporary_entity(entity):
                continue
            exported_aliases = self._exportable_aliases(canonical_name, entity.aliases)
            if not exported_aliases:
                continue
            alias_map[canonical_name] = exported_aliases
            decisions.append(
                {
                    "decision_type": "resolver_temporary_exported",
                    "character": canonical_name,
                    "canonical_name": canonical_name,
                    "same_character": True,
                    "confidence": round(min(1.0, entity.max_person_likelihood * 0.85), 3),
                    "reasoning": f"Temporary candidate. mention_count={entity.mention_count}.",
                    "scene_ref": {
                        "chapter_index": entity.first_seen_chapter,
                        "window_index": entity.first_seen_window,
                    },
                }
            )

        _, discarded = self._partition_supporting_entities()
        meaningful_supporting = {
            entity_id: entity
            for entity_id, entity in self.memory.supporting_entities.items()
            if entity_id not in discarded
        }
        for entity in meaningful_supporting.values():
            if entity.entity_kind in {"location", "group", "object"}:
                name = (entity.name or "").strip()
                if name and name not in alias_map:
                    rejected_non_characters.append(name)
        for entity in discarded.values():
            name = (entity.name or "").strip()
            if name and name not in alias_map:
                rejected_non_characters.append(name)

        for weak in self.memory.weak_mentions_quarantine.values():
            name = (weak.text or "").strip()
            if name and name not in alias_map and weak.occurrence_count < 2:
                rejected_non_characters.append(name)

        alias_keys_lower = {key.lower() for key in alias_map}
        seen_rejected: set[str] = set()
        deduped_rejected: List[str] = []
        for name in rejected_non_characters:
            key = name.lower()
            if key not in seen_rejected and key not in alias_keys_lower:
                seen_rejected.add(key)
                deduped_rejected.append(name)

        return {
            "alias_map": alias_map,
            "rejected_non_characters": deduped_rejected,
            "decisions": decisions,
            "alias_history": alias_history,
        }

    def _run_postpass_stabilization(self) -> None:
        if self._stabilized:
            return
        pre_canonical_count = len(self.memory.canonical_characters)
        pre_supporting_count = len(self.memory.supporting_entities)
        purged_empty_temp_count = self._purge_empty_temp_shells()
        merged_count = self._merge_canonical_variants()
        profiles = self._build_entity_profiles()
        promoted_temp_count = self._promote_temporary_character_candidates(profiles)
        if promoted_temp_count:
            self.memory.rebuild_indexes()
            profiles = self._build_entity_profiles()
        rescued_count = self._rescue_supporting_character_candidates(profiles)
        if rescued_count:
            self.memory.rebuild_indexes()
            profiles = self._build_entity_profiles()
        demoted_count = self._demote_false_positive_canonicals(profiles)
        self.memory.rebuild_indexes()
        meaningful_supporting, discarded_supporting = self._partition_supporting_entities()
        self.stabilization_metrics = {
            "pre_canonical_count": pre_canonical_count,
            "post_canonical_count": len(self.memory.canonical_characters),
            "pre_supporting_count": pre_supporting_count,
            "post_supporting_count": len(meaningful_supporting),
            "merged_canonical_count": merged_count,
            "promoted_temporary_count": promoted_temp_count,
            "demoted_canonical_count": demoted_count,
            "rescued_supporting_count": rescued_count,
            "discarded_supporting_count": len(discarded_supporting),
            "purged_empty_temp_count": purged_empty_temp_count,
        }
        self._stabilized = True

    def _promote_temporary_character_candidates(self, profiles: Dict[str, EntityEvidenceProfile]) -> int:
        promoted_count = 0
        temp_ids = sorted(
            self.memory.temporary_person_candidates.keys(),
            key=lambda entity_id: (
                -self.memory.temporary_person_candidates[entity_id].mention_count,
                self.memory.temporary_person_candidates[entity_id].canonical_name.lower(),
            ),
        )
        for entity_id in temp_ids:
            entity = self.memory.temporary_person_candidates.get(entity_id)
            profile = profiles.get(entity_id)
            if not entity or not profile:
                continue
            if not self.resolver._looks_human_name_surface(entity.canonical_name):
                continue
            if self.resolver._looks_non_person_surface(entity.canonical_name):
                continue
            _, honorific, core_tokens = self.name_clusterer._parse_name(entity.canonical_name)
            repeated_person_behavior = profile.proper_name_mentions >= 2 and (
                profile.person_model_hits >= 1 or entity.max_person_likelihood >= 0.72
            )
            contextual_person_behavior = (
                profile.pronoun_links >= 1
                or profile.quote_speaker_hits >= 1
                or profile.nearby_known_person_hits >= 2
            )
            promotable = False
            if honorific and len(core_tokens) >= 1:
                promotable = entity.mention_count >= 2 and (repeated_person_behavior or contextual_person_behavior or entity.max_person_likelihood >= 0.72)
            elif len(core_tokens) >= 2:
                promotable = entity.mention_count >= 2 and (profile.character_evidence_score >= 0.9 or repeated_person_behavior or contextual_person_behavior)
            elif len(core_tokens) == 1:
                promotable = (
                    entity.mention_count >= 4
                    and profile.character_evidence_score >= 1.0
                    and (repeated_person_behavior or contextual_person_behavior or entity.max_person_likelihood >= 0.8)
                )
            if not promotable:
                continue
            existing = self.name_clusterer.match_canonical(entity.canonical_name, self.memory.canonical_characters)
            if existing:
                self.memory.merge_temp_into_canonical(entity_id, existing, "postpass_strong_temporary")
            else:
                canonical_id = self.memory._create_canonical(
                    entity.canonical_name,
                    entity.first_seen_chapter,
                    entity.first_seen_window,
                    entity.seed_label_type,
                )
                self.memory.merge_temp_into_canonical(entity_id, canonical_id, "postpass_strong_temporary")
            promoted_count += 1
        return promoted_count

    def _purge_empty_temp_shells(self) -> int:
        purged = 0
        for entity_id in list(self.memory.temporary_person_candidates.keys()):
            entity = self.memory.temporary_person_candidates.get(entity_id)
            if entity and entity.mention_count == 0 and entity.max_person_likelihood == 0.0 and not entity.evidence_windows:
                del self.memory.temporary_person_candidates[entity_id]
                purged += 1
        return purged

    def _build_entity_profiles(self) -> Dict[str, EntityEvidenceProfile]:
        profiles: Dict[str, EntityEvidenceProfile] = {}
        for entity_id, entity in self.memory.canonical_characters.items():
            profiles[entity_id] = self._profile_for_character(entity, "canonical")
        for entity_id, entity in self.memory.temporary_person_candidates.items():
            profiles[entity_id] = self._profile_for_character(entity, "temporary")
        for entity_id, entity in self.memory.supporting_entities.items():
            profiles[entity_id] = self._profile_for_supporting(entity)
        for entity_id, entity in self.memory.weak_mentions_quarantine.items():
            profiles[entity_id] = self._profile_for_weak(entity)
        return profiles

    def _profile_for_character(self, entity: CharacterMemory, bucket: Literal["canonical", "temporary"]) -> EntityEvidenceProfile:
        labels = {
            self._normalize(entity.canonical_name),
            *(self._normalize(item) for item in entity.aliases),
            *(self._normalize(item) for item in entity.titles),
            *(self._normalize(item) for item in entity.roles),
            *(self._normalize(item) for item in entity.descriptors),
        }
        profile = EntityEvidenceProfile(
            entity_id=entity.entity_id,
            entity_name=entity.canonical_name,
            entity_bucket=bucket,
            first_seen=(entity.first_seen_chapter, entity.first_seen_window),
            last_seen=(entity.last_seen_chapter, entity.last_seen_window),
        )
        self._accumulate_profile_from_history(profile, labels)
        self._accumulate_profile_from_resolutions(profile, entity.entity_id)
        return profile

    def _profile_for_supporting(self, entity: SupportingEntityMemory) -> EntityEvidenceProfile:
        profile = EntityEvidenceProfile(
            entity_id=entity.entity_id,
            entity_name=entity.name,
            entity_bucket="supporting",
            first_seen=(entity.first_seen_chapter, entity.first_seen_window),
            last_seen=(entity.last_seen_chapter, entity.last_seen_window),
        )
        self._accumulate_profile_from_history(profile, {self._normalize(entity.name)})
        return profile

    def _profile_for_weak(self, entity: WeakMentionMemory) -> EntityEvidenceProfile:
        profile = EntityEvidenceProfile(
            entity_id=entity.weak_id,
            entity_name=entity.text,
            entity_bucket="weak",
            first_seen=(entity.first_seen_chapter, entity.first_seen_window),
            last_seen=(entity.last_seen_chapter, entity.last_seen_window),
        )
        self._accumulate_profile_from_history(profile, {self._normalize(entity.text)})
        return profile

    def _accumulate_profile_from_history(self, profile: EntityEvidenceProfile, labels: set[str]) -> None:
        for normalized in {label for label in labels if label}:
            for record in self.mention_history_index.get(normalized, []):
                profile.total_mentions += 1
                profile.surface_forms.add(record.surface_text)
                if record.mention_type == "name" and (
                    record.source in {"llm_extraction", "proper_name", "ent_person", "reveal_pattern", "appositive_reveal"}
                    or "proper_name_source" in record.positive_features
                ):
                    profile.proper_name_mentions += 1
                if "llm_person_confidence" in record.positive_features or record.referent_type == "person":
                    profile.person_model_hits += 1
                if record.mention_type in {"title", "role"}:
                    profile.title_role_hits += 1
                if record.in_quote and record.syntactic_role == "subject":
                    profile.quote_speaker_hits += 1
                if self._looks_location_like_surface(record.surface_text) or record.entity_label in {"GPE", "LOC", "FAC", "ORG", "NORP"}:
                    profile.location_group_hits += 1
                if record.head_lemma and record.head_lemma not in PERSONISH_NOUNS and record.mention_type == "descriptor":
                    profile.object_generic_hits += 1
                if self._looks_group_like_surface(record.surface_text):
                    profile.location_group_hits += 1
                if self._looks_malformed_canonical_surface(record.surface_text):
                    profile.malformed_name_hits += 1
                if self._sentence_mentions_other_known_person(record.sentence_text, profile.entity_name):
                    profile.nearby_known_person_hits += 1
                for key, value in record.positive_features.items():
                    profile.positive_evidence[key] += value
                for key, value in record.negative_features.items():
                    profile.negative_evidence[key] += value
                if record.sentence_text and record.sentence_text not in profile.example_sentences and len(profile.example_sentences) < 5:
                    profile.example_sentences.append(record.sentence_text)

    def _accumulate_profile_from_resolutions(self, profile: EntityEvidenceProfile, entity_id: str) -> None:
        for mention in self.mention_log:
            if mention.resolved_to != entity_id:
                continue
            if mention.mention_type == "pronoun":
                profile.pronoun_links += 1
            if mention.method and "quote" in mention.method:
                profile.quote_speaker_hits += 1
            if mention.mention_type in {"title", "role"}:
                profile.title_role_hits += 1

    def _sentence_mentions_other_known_person(self, sentence_text: str, current_name: str) -> bool:
        normalized_sentence = self._normalize(sentence_text)
        current_normalized = self._normalize(current_name)
        for entity in self.memory.canonical_characters.values():
            canonical = self._normalize(entity.canonical_name)
            if canonical and canonical != current_normalized and canonical in normalized_sentence:
                return True
        return False

    def _merge_canonical_variants(self) -> int:
        merged_count = 0
        changed = True
        while changed:
            changed = False
            canonical_ids = list(self.memory.canonical_characters.keys())
            for left_id in canonical_ids:
                if left_id not in self.memory.canonical_characters:
                    continue
                for right_id in canonical_ids:
                    if left_id == right_id or right_id not in self.memory.canonical_characters:
                        continue
                    decision = self._canonical_merge_target(left_id, right_id)
                    if not decision:
                        continue
                    source_id, target_id, reason = decision
                    self.memory.merge_canonical_into_canonical(source_id, target_id, reason)
                    merged_count += 1
                    changed = True
                    break
                if changed:
                    break
        return merged_count

    def _canonical_merge_target(self, left_id: str, right_id: str) -> Tuple[str, str, str] | None:
        left = self.memory.canonical_characters[left_id]
        right = self.memory.canonical_characters[right_id]
        _, left_honorific, left_core = self.name_clusterer._parse_name(left.canonical_name)
        _, right_honorific, right_core = self.name_clusterer._parse_name(right.canonical_name)
        if not left_core or not right_core:
            return None
        left_core_text = " ".join(left_core)
        right_core_text = " ".join(right_core)
        left_set = set(left_core)
        right_set = set(right_core)
        if left_set == right_set and (left_honorific or right_honorific or len(left_core) >= 2 or len(right_core) >= 2):
            preferred = self._prefer_canonical_target(left_id, right_id)
            rejected = right_id if preferred == left_id else left_id
            return rejected, preferred, "core_token_equivalence"
        if len(left_core) == 1 and len(right_core) >= 2 and left_core[0] in right_set:
            preferred = self._prefer_canonical_target(left_id, right_id)
            rejected = right_id if preferred == left_id else left_id
            return rejected, preferred, "single_token_subset"
        if len(right_core) == 1 and len(left_core) >= 2 and right_core[0] in left_set:
            preferred = self._prefer_canonical_target(left_id, right_id)
            rejected = right_id if preferred == left_id else left_id
            return rejected, preferred, "single_token_subset"
        if len(left_core) == 1 and len(right_core) == 1:
            if self._nickname_merge_supported(left_id, right_id, left_core_text, right_core_text):
                preferred = self._prefer_canonical_target(left_id, right_id)
                rejected = right_id if preferred == left_id else left_id
                return rejected, preferred, "nickname_evidence_match"
        return None

    def _prefer_canonical_target(self, left_id: str, right_id: str) -> str:
        left = self.memory.canonical_characters[left_id]
        right = self.memory.canonical_characters[right_id]
        left_score = (self._canonical_display_rank(left.canonical_name), left.mention_count)
        right_score = (self._canonical_display_rank(right.canonical_name), right.mention_count)
        return left_id if left_score >= right_score else right_id

    def _canonical_display_rank(self, name: str) -> Tuple[int, int, int]:
        _, honorific, core_tokens = self.name_clusterer._parse_name(name)
        if len(core_tokens) >= 2 and not honorific:
            return (3, len(core_tokens), 1)
        if honorific and len(core_tokens) >= 1:
            return (2, len(core_tokens), 1)
        return (1, len(core_tokens), len(name))

    def _nickname_merge_supported(self, left_id: str, right_id: str, left_core_text: str, right_core_text: str) -> bool:
        left = self.memory.canonical_characters[left_id]
        right = self.memory.canonical_characters[right_id]
        shorter_id, shorter_text, longer_id, longer_text = (
            (left_id, left_core_text, right_id, right_core_text)
            if len(left_core_text) <= len(right_core_text)
            else (right_id, right_core_text, left_id, left_core_text)
        )
        prefix_like = longer_text.startswith(shorter_text) and len(shorter_text) >= 2
        fuzzy_like = fuzz.partial_ratio(shorter_text, longer_text) >= 85
        if not (prefix_like or fuzzy_like):
            return False
        shorter_history = self.mention_history_index.get(shorter_text, [])
        longer_history = self.mention_history_index.get(longer_text, [])
        nearby = any(
            left_item.chapter_index == right_item.chapter_index and abs(left_item.window_index - right_item.window_index) <= 2
            for left_item in shorter_history
            for right_item in longer_history
        )
        shared_titles = bool(left.titles & right.titles)
        shared_roles = bool(left.roles & right.roles)
        repeated_after_long = False
        if longer_history and shorter_history:
            first_long = min((item.chapter_index, item.window_index) for item in longer_history)
            later_short = [
                (item.chapter_index, item.window_index)
                for item in shorter_history
                if (item.chapter_index, item.window_index) >= first_long and item.referent_type == "person"
            ]
            repeated_after_long = len(later_short) >= 2
        if not shorter_history or not longer_history:
            nearby = self._window_sets_are_nearby(left.evidence_windows, right.evidence_windows)
            repeated_after_long = repeated_after_long or (
                (right.first_seen_chapter < left.first_seen_chapter
                 or (right.first_seen_chapter == left.first_seen_chapter and right.first_seen_window <= left.first_seen_window))
                and left.mention_count >= 5
                and right.mention_count >= 10
            )
        compatible_person_evidence = (
            left.max_person_likelihood >= 0.75
            and right.max_person_likelihood >= 0.75
            and (left.model_person_hits > 0 or right.model_person_hits > 0 or shared_titles or shared_roles)
        )
        return nearby or repeated_after_long or compatible_person_evidence

    def _rescue_supporting_character_candidates(self, profiles: Dict[str, EntityEvidenceProfile]) -> int:
        rescued_count = 0
        for support_id in list(self.memory.supporting_entities.keys()):
            entity = self.memory.supporting_entities.get(support_id)
            if not entity:
                continue
            target_id = self._rescue_supporting_target(entity, profiles.get(support_id))
            if not target_id:
                continue
            target = self.memory.canonical_characters.get(target_id) or self.memory.temporary_person_candidates.get(target_id)
            if not target:
                continue
            target.aliases.add(entity.name)
            target.mention_count += entity.mention_count
            target.last_seen_chapter = max(target.last_seen_chapter, entity.last_seen_chapter)
            target.last_seen_window = max(target.last_seen_window, entity.last_seen_window)
            self.graph.add_edge(support_id, target_id, kind="supporting_rescued_into", reason="postpass_character_rescue")
            del self.memory.supporting_entities[support_id]
            rescued_count += 1
        return rescued_count

    def _rescue_supporting_target(self, entity: SupportingEntityMemory, profile: Optional[EntityEvidenceProfile]) -> str:
        normalized = self._normalize(entity.name)
        if normalized in self.memory.alias_index and self.memory.alias_index[normalized]:
            return sorted(self.memory.alias_index[normalized])[0]
        if self._looks_malformed_canonical_surface(entity.name):
            return ""
        if not self._looks_person_name_surface(entity.name):
            return ""
        if not profile:
            return ""
        if profile.non_character_evidence_score > profile.character_evidence_score + 0.4:
            return ""
        repeated_person_behavior = profile.proper_name_mentions >= 2 and profile.person_model_hits >= 1
        contextual_person_behavior = profile.quote_speaker_hits >= 1 or profile.pronoun_links >= 1 or profile.nearby_known_person_hits >= 2
        if entity.entity_kind in {"group", "location"} and not repeated_person_behavior and not contextual_person_behavior:
            if profile.character_evidence_score < 0.9:
                return ""
        if profile.character_evidence_score < 0.75 and not repeated_person_behavior and not contextual_person_behavior:
            return ""
        existing = self.name_clusterer.match_canonical(entity.name, self.memory.canonical_characters)
        if existing:
            return existing
        _, honorific, core_tokens = self.name_clusterer._parse_name(entity.name)
        mention_count_threshold = 40 if len(core_tokens) == 1 else 60
        if profile.character_evidence_score >= 1.2 or honorific or len(core_tokens) >= 2 or entity.mention_count >= mention_count_threshold:
            return self.memory._create_canonical(entity.name, entity.first_seen_chapter, entity.first_seen_window, "name")
        return self.memory._create_temp_person(
            entity.name,
            entity.first_seen_chapter,
            entity.first_seen_window,
            "name",
            person_likelihood=max(0.81, min(0.95, profile.character_evidence_score / 2.5)),
            model_person_hit=profile.person_model_hits > 0,
        )

    def _demote_false_positive_canonicals(self, profiles: Dict[str, EntityEvidenceProfile]) -> int:
        demoted_count = 0
        for entity_id in list(self.memory.canonical_characters.keys()):
            entity = self.memory.canonical_characters.get(entity_id)
            if not entity:
                continue
            reasons = self._canonical_false_positive_reasons(entity)
            if not reasons:
                continue
            profile = profiles.get(entity_id)
            if not self._canonical_demotable(entity, profile):
                continue
            self._demote_canonical_to_supporting(entity_id, entity, reasons)
            demoted_count += 1
        return demoted_count

    def _canonical_false_positive_reasons(self, entity: CharacterMemory) -> List[str]:
        reasons: List[str] = []
        if self._looks_location_like_surface(entity.canonical_name):
            reasons.append("location_like_name")
        if self._looks_group_like_surface(entity.canonical_name):
            reasons.append("group_or_species_like_name")
        if self.resolver._looks_non_person_surface(entity.canonical_name):
            reasons.append("non_person_surface")
        if self._looks_malformed_canonical_surface(entity.canonical_name):
            reasons.append("malformed_name")
        return reasons

    def _canonical_demotable(self, entity: CharacterMemory, profile: Optional[EntityEvidenceProfile]) -> bool:
        if not profile:
            return False
        if self.resolver._looks_non_person_surface(entity.canonical_name):
            strong_reference_behavior = profile.pronoun_links >= 2 or profile.quote_speaker_hits >= 1
            strong_person = profile.character_evidence_score >= 1.35 and strong_reference_behavior
            return not strong_person
        strong_person = profile.character_evidence_score >= 1.1 or profile.pronoun_links >= 2
        if strong_person:
            return False
        if entity.max_person_likelihood >= 0.88 and profile.location_group_hits == 0:
            return False
        strong_non_character = profile.non_character_evidence_score >= 0.28
        score_dominates = profile.non_character_evidence_score > profile.character_evidence_score
        structurally_non_character = profile.non_character_evidence_score >= 0.10 and (
            profile.location_group_hits >= 1 or profile.malformed_name_hits >= 1
        )
        return (strong_non_character and score_dominates) or structurally_non_character

    def _demote_canonical_to_supporting(self, entity_id: str, entity: CharacterMemory, reasons: List[str]) -> None:
        kind: SupportingEntityKind = "unknown"
        if "location_like_name" in reasons:
            kind = "location"
        elif "group_or_species_like_name" in reasons:
            kind = "group"
        elif "non_person_surface" in reasons:
            normalized_tokens = set(self._normalize(entity.canonical_name).split())
            if normalized_tokens & {"court", "fae", "muggles", "seelie"}:
                kind = "group"
            elif normalized_tokens & {"blood", "caraval", "quidditch", "rite", "solstice", "starfall", "tournament"}:
                kind = "object"
            else:
                kind = "location"
        support_id = f"support_demoted_{entity_id}"
        self.memory.supporting_entities[support_id] = SupportingEntityMemory(
            entity_id=support_id,
            name=entity.canonical_name,
            entity_kind=kind,
            first_seen_chapter=entity.first_seen_chapter,
            first_seen_window=entity.first_seen_window,
            last_seen_chapter=entity.last_seen_chapter,
            last_seen_window=entity.last_seen_window,
            mention_count=entity.mention_count,
        )
        self.graph.add_edge(entity_id, support_id, kind="canonical_demoted_into", reason=",".join(reasons))
        del self.memory.canonical_characters[entity_id]

    def _partition_supporting_entities(self) -> Tuple[Dict[str, SupportingEntityMemory], Dict[str, SupportingEntityMemory]]:
        meaningful: Dict[str, SupportingEntityMemory] = {}
        discarded: Dict[str, SupportingEntityMemory] = {}
        for entity_id, entity in self.memory.supporting_entities.items():
            if self._should_discard_supporting(entity):
                discarded[entity_id] = entity
            else:
                meaningful[entity_id] = entity
        return meaningful, discarded

    def _should_discard_supporting(self, entity: SupportingEntityMemory) -> bool:
        lowered = self._normalize(entity.name)
        generic = {
            "door", "stone", "air", "moment", "room", "head", "hand", "time", "game",
            "world", "day", "night", "things", "winter", "toast", "bacon", "count",
        }
        if lowered in generic:
            return True
        if entity.entity_kind == "unknown" and not self._looks_person_name_surface(entity.name):
            return True
        return False

    def _top_likely_person_supporting_entities(self, supporting_payload: Dict[str, SupportingEntityMemory], profiles: Dict[str, EntityEvidenceProfile]) -> List[Dict]:
        candidates: List[Dict] = []
        for entity_id, entity in supporting_payload.items():
            profile = profiles.get(entity_id)
            if not self._looks_person_name_surface(entity.name) or not profile:
                continue
            candidates.append(
                {
                    "entity_id": entity_id,
                    "name": entity.name,
                    "entity_kind": entity.entity_kind,
                    "mention_count": entity.mention_count,
                    "character_score": profile.character_evidence_score,
                    "non_character_score": profile.non_character_evidence_score,
                }
            )
        candidates.sort(key=lambda item: (-item["character_score"], item["non_character_score"], -item["mention_count"], item["name"].lower()))
        return candidates[:20]

    def _suspicious_entity_diagnostics(self, profiles: Dict[str, EntityEvidenceProfile]) -> List[Dict]:
        diagnostics: List[Dict] = []
        for entity_id, profile in profiles.items():
            if profile.entity_bucket not in {"canonical", "supporting"}:
                continue
            suspicious = profile.non_character_evidence_score >= 0.85 or (
                profile.entity_bucket == "supporting" and profile.character_evidence_score >= 0.6
            )
            if not suspicious:
                continue
            diagnostics.append(
                {
                    "entity_id": entity_id,
                    "entity_name": profile.entity_name,
                    "entity_bucket": profile.entity_bucket,
                    "character_score": profile.character_evidence_score,
                    "non_character_score": profile.non_character_evidence_score,
                    "top_positive_evidence": self._top_profile_evidence(profile.positive_evidence),
                    "top_negative_evidence": self._top_profile_evidence(profile.negative_evidence),
                    "example_sentences": profile.example_sentences[:3],
                }
            )
        diagnostics.sort(key=lambda item: (-max(item["character_score"], item["non_character_score"]), item["entity_name"].lower()))
        return diagnostics[:30]

    def _top_profile_evidence(self, evidence_map: Dict[str, float]) -> List[Dict]:
        items = sorted(evidence_map.items(), key=lambda item: item[1], reverse=True)
        return [{"feature": key, "weight": round(value, 3)} for key, value in items[:4]]

    def _serialize_character(self, entity: CharacterMemory) -> Dict:
        return {
            "entity_id": entity.entity_id,
            "canonical_name": entity.canonical_name,
            "status": entity.status,
            "aliases": sorted(entity.aliases),
            "titles": sorted(entity.titles),
            "roles": sorted(entity.roles),
            "descriptors": sorted(entity.descriptors),
            "gender": entity.gender,
            "mention_count": entity.mention_count,
            "first_seen": {"chapter": entity.first_seen_chapter, "window": entity.first_seen_window},
            "last_seen": {"chapter": entity.last_seen_chapter, "window": entity.last_seen_window},
            "seed_label_type": entity.seed_label_type,
            "max_person_likelihood": entity.max_person_likelihood,
            "model_person_hits": entity.model_person_hits,
            "honorific_backed": entity.honorific_backed,
        }

    def _serialize_weak_mention(self, entity: WeakMentionMemory) -> Dict:
        return {
            "weak_id": entity.weak_id,
            "text": entity.text,
            "mention_type": entity.mention_type,
            "person_likelihood": entity.person_likelihood,
            "occurrence_count": entity.occurrence_count,
            "first_seen": {"chapter": entity.first_seen_chapter, "window": entity.first_seen_window},
            "last_seen": {"chapter": entity.last_seen_chapter, "window": entity.last_seen_window},
            "reasons": list(entity.reasons),
        }

    def _serialize_supporting_entity(self, entity: SupportingEntityMemory) -> Dict:
        return {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "entity_kind": entity.entity_kind,
            "mention_count": entity.mention_count,
            "first_seen": {"chapter": entity.first_seen_chapter, "window": entity.first_seen_window},
            "last_seen": {"chapter": entity.last_seen_chapter, "window": entity.last_seen_window},
        }

    def _top_false_positive_canonicals(self, canonical_payload: Dict[str, Dict], profiles: Dict[str, EntityEvidenceProfile]) -> List[Dict]:
        suspicious: List[Dict] = []
        for entity_id, item in canonical_payload.items():
            name = item["canonical_name"]
            reasons = []
            if self._looks_location_like_surface(name):
                reasons.append("location_like_name")
            if self._looks_group_like_surface(name):
                reasons.append("group_or_species_like_name")
            if self._looks_malformed_canonical_surface(name):
                reasons.append("malformed_name")
            if reasons:
                profile = profiles.get(entity_id)
                suspicious.append(
                    {
                        "entity_id": entity_id,
                        "canonical_name": name,
                        "reason": ",".join(reasons),
                        "character_score": profile.character_evidence_score if profile else 0.0,
                        "non_character_score": profile.non_character_evidence_score if profile else 0.0,
                    }
                )
        suspicious.sort(key=lambda item: (-item["non_character_score"], item["character_score"], item["canonical_name"].lower()))
        return suspicious[:20]

    def _build_windows(self, content: str, *, chapter_index: int, chapter_title: str, paragraphs_per_window: int, overlap_paragraphs: int) -> List[WindowRecord]:
        paragraphs = [item.strip() for item in re.split(r"\n+", content or "") if item.strip()]
        if not paragraphs:
            return []
        paragraphs = self._strip_leading_paratext(paragraphs)
        paragraphs = self._merge_short_paragraphs(paragraphs)
        step = max(1, paragraphs_per_window - overlap_paragraphs)
        windows: List[WindowRecord] = []
        window_index = 1
        for start in range(0, len(paragraphs), step):
            end = min(len(paragraphs), start + paragraphs_per_window)
            window_text = "\n\n".join(paragraphs[start:end]).strip()
            if not window_text:
                continue
            windows.append(
                WindowRecord(
                    chapter_index=chapter_index,
                    window_index=window_index,
                    chapter_title=chapter_title,
                    text=window_text,
                    paragraph_start=start,
                    paragraph_end=end,
                )
            )
            window_index += 1
            if end == len(paragraphs):
                break
        return windows

    def _merge_short_paragraphs(self, paragraphs: Sequence[str]) -> List[str]:
        merged: List[str] = []
        pending_prefix = ""
        for paragraph in paragraphs:
            current = paragraph.strip()
            if pending_prefix:
                current = f"{pending_prefix}{current}".strip()
                pending_prefix = ""
            word_count = len(current.split())
            if word_count <= 2 and current.isalpha():
                pending_prefix = current
                continue
            if merged and word_count < 20:
                merged[-1] = f"{merged[-1]} {current}".strip()
            else:
                merged.append(current)
        if pending_prefix and merged:
            merged[-1] = f"{merged[-1]} {pending_prefix}".strip()
        return merged

    def _strip_leading_paratext(self, paragraphs: Sequence[str]) -> List[str]:
        start_index = 0
        for index, paragraph in enumerate(paragraphs):
            cleaned = paragraph.strip()
            tokens = cleaned.split()
            has_terminal_punctuation = any(mark in cleaned for mark in {".", "!", "?", "”", "\""})
            has_lowercase = any(char.islower() for char in cleaned)
            looks_sentence_like = len(tokens) >= 8 and has_lowercase and has_terminal_punctuation
            if looks_sentence_like:
                start_index = index
                break
        retained = list(paragraphs[start_index:])
        if start_index > 0:
            prefix = paragraphs[start_index - 1].strip()
            if len(prefix) <= 2 and prefix.isalpha() and retained:
                retained[0] = f"{prefix}{retained[0]}".strip()
        return retained

    def _looks_person_name_surface(self, text: str) -> bool:
        tokens = [token.strip(".,;:!?\"'“”‘’()[]{}") for token in text.split() if token.strip(".,;:!?\"'“”‘’()[]{}")]
        if not tokens:
            return False
        lowered = [token.lower().rstrip(".") for token in tokens]
        if self._looks_location_like_surface(text) or self._looks_group_like_surface(text) or self._looks_malformed_canonical_surface(text):
            return False
        if lowered[-1] in PERSONISH_NOUNS:
            return False
        if lowered[0] in HONORIFICS and len(tokens) >= 2:
            return True
        return all(token[:1].isupper() for token in tokens if token[:1].isalpha())

    def _looks_location_like_surface(self, text: str) -> bool:
        lowered = self._normalize(text)
        location_markers = {"mountain", "mountains", "court", "drive", "road", "street", "house", "hall", "city", "kingdom", "castle", "castillo", "forest", "river"}
        return bool(set(lowered.split()) & location_markers)

    def _looks_group_like_surface(self, text: str) -> bool:
        lowered = self._normalize(text)
        group_markers = {"fae", "people", "court", "guards", "guard", "soldiers", "soldier", "dynasty", "players", "dursleys"}
        return bool(set(lowered.split()) & group_markers)

    def _looks_malformed_canonical_surface(self, text: str) -> bool:
        lowered = self._normalize(text)
        return lowered.startswith("not ") or lowered.startswith("no ") or lowered.startswith("never ")

    def _window_sets_are_nearby(self, left: Sequence[Tuple[int, int]], right: Sequence[Tuple[int, int]]) -> bool:
        return any(a == c and abs(b - d) <= 2 for a, b in left for c, d in right)

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _establish_window_prior(self, window: WindowRecord) -> Tuple[str, bool]:
        first_person_window = bool(re.search(r"\bI\b|\bmy\b|\bme\b", window.text))
        match = POV_CHAPTER_PATTERN.match((window.chapter_title or "").strip())
        if not match or not first_person_window:
            return "", first_person_window
        candidate = match.group(1).strip()
        if not candidate or any(char.isdigit() for char in candidate) or self._normalize(candidate) in SHARED_TITLES:
            return "", first_person_window
        self.memory.seed_or_match_canonical_name(candidate, window.chapter_index, window.window_index, "name")
        return candidate, first_person_window


def run_real_book_smoke_test() -> Dict:
    book_path = Path("B:/Documents/PyCharm/graduationProject/uploads/A Court of Frost and Starlight.epub")
    if not book_path.exists():
        raise FileNotFoundError(f"Smoke-test book not found: {book_path}")
    resolver = DeterministicIdentityResolver()
    return resolver.process_epub(book_path, max_chapters=1, max_windows=4, paragraphs_per_window=3, overlap_paragraphs=1)


def run_harry_potter_regression_test() -> Dict:
    book_path = Path("B:/Documents/PyCharm/graduationProject/uploads/1 Harry Potter & the Philosophers Stone.epub")
    if not book_path.exists():
        raise FileNotFoundError(f"Regression-test book not found: {book_path}")
    resolver = DeterministicIdentityResolver()
    return resolver.process_epub(book_path, max_chapters=1, max_windows=6, paragraphs_per_window=3, overlap_paragraphs=1)


def run_gliner_extraction_regression_test() -> Dict:
    extractor = GLiNERExtractionService()
    window = WindowRecord(chapter_index=1, window_index=1, chapter_title="", text="Prince Cardan said he would return to Elfhame.", paragraph_start=0, paragraph_end=1)

    extractor._extract_gliner_mentions = lambda text, sentence_starts: [  # type: ignore[method-assign]
        ExtractedMention(text="Prince Cardan", canonical_form="Prince Cardan", mention_type="name", referent_type="person", confidence=0.93, start_char=0, end_char=13, sentence_index=0, in_quote=False, source="ent_gliner")
    ]
    mentions = extractor.extract(window)
    assert any(item.source == "ent_gliner" and item.text == "Prince Cardan" for item in mentions), "Expected GLiNER primary span"
    assert any(item.source == "pronoun" and item.text.lower() == "he" for item in mentions), "Expected pronoun extraction"

    unavailable = GLiNERExtractionService()
    unavailable._gliner_available = False
    unavailable._gliner_model = None
    mentions_fallback = unavailable.extract(window)
    assert not any(item.source == "ent_gliner" for item in mentions_fallback), "Unavailable GLiNER should not emit GLiNER spans"
    print("GLiNER extraction regression test passed.")
    return {"mention_count": len(mentions), "fallback_count": len(mentions_fallback)}


def run_postpass_stabilization_regression_test() -> Dict:
    resolver = DeterministicIdentityResolver()

    def add_history(
        key_text: str,
        *,
        surface_text: Optional[str] = None,
        mention_type: MentionType = "name",
        referent_type: str = "person",
        confidence: float = 0.9,
        route: str = "canonical_seed",
        chapter_index: int = 1,
        window_index: int = 1,
        sentence_text: str = "",
        in_quote: bool = False,
        positive_features: Optional[Dict[str, float]] = None,
        negative_features: Optional[Dict[str, float]] = None,
        entity_label: str = "",
        syntactic_role: str = "subject",
    ) -> None:
        resolver.mention_history_index[resolver._normalize(key_text)].append(
            MentionHistoryRecord(
                surface_text=surface_text or key_text,
                canonical_form=key_text,
                mention_type=mention_type,
                referent_type=referent_type,
                confidence=confidence,
                route=route,
                chapter_index=chapter_index,
                window_index=window_index,
                sentence_index=0,
                sentence_text=sentence_text or f"{surface_text or key_text} spoke softly to Feyre.",
                in_quote=in_quote,
                source="llm_extraction",
                positive_features=positive_features or ({"llm_person_confidence": confidence, "proper_name_source": 0.1} if referent_type == "person" else {}),
                negative_features=negative_features or {},
                entity_label=entity_label,
                syntactic_role=syntactic_role,
                head_lemma=(surface_text or key_text).split()[-1].lower(),
            )
        )

    harry_id = resolver.memory._create_canonical("Harry", 1, 1, "name")
    harry_full_id = resolver.memory._create_canonical("Harry Potter", 1, 2, "name")
    dumbledore_id = resolver.memory._create_canonical("Dumbledore", 1, 3, "name")
    professor_dumbledore_id = resolver.memory._create_canonical("Professor Dumbledore", 1, 4, "name")
    azriel_id = resolver.memory._create_canonical("Azriel", 2, 1, "name")
    az_id = resolver.memory._create_canonical("Az", 2, 2, "name")
    resolver.memory.canonical_characters[harry_id].mention_count = 8
    resolver.memory.canonical_characters[harry_full_id].mention_count = 16
    resolver.memory.canonical_characters[dumbledore_id].mention_count = 6
    resolver.memory.canonical_characters[professor_dumbledore_id].mention_count = 11
    resolver.memory.canonical_characters[azriel_id].mention_count = 20
    resolver.memory.canonical_characters[azriel_id].evidence_windows = [(2, 1), (2, 2), (2, 3)]
    resolver.memory.canonical_characters[az_id].mention_count = 30
    resolver.memory.canonical_characters[az_id].evidence_windows = [(2, 3), (2, 4), (2, 5)]
    resolver.memory.canonical_characters[azriel_id].titles.add("Shadowsinger")
    resolver.memory.canonical_characters[az_id].titles.add("Shadowsinger")
    add_history("Azriel", chapter_index=2, window_index=1, sentence_text="Azriel waited beside Feyre.")
    add_history("Azriel", chapter_index=2, window_index=2, sentence_text="Rhys glanced at Azriel.", positive_features={"llm_person_confidence": 0.9, "proper_name_source": 0.1})
    add_history("Az", chapter_index=2, window_index=3, sentence_text="Az stepped into the room after Azriel had vanished.")
    add_history("Az", chapter_index=2, window_index=4, sentence_text="Cassian told Az to stay close.")
    resolver.memory._create_canonical("Cardan", 3, 1, "name")
    resolver.memory._create_canonical("Prince Cardan", 3, 2, "name")
    high_fae_id = resolver.memory._create_canonical("High Fae", 1, 5, "name")
    resolver.memory._create_canonical("Illyrian Mountains", 1, 6, "name")
    resolver.memory._create_canonical("Castillo Maldito", 1, 7, "name")
    resolver.memory.canonical_characters[high_fae_id].max_person_likelihood = 0.91
    add_history("High Fae", referent_type="group", confidence=0.2, route="supporting", entity_label="NORP", negative_features={"supporting_llm": 0.48}, positive_features={})
    add_history("Illyrian Mountains", referent_type="location", confidence=0.1, route="supporting", entity_label="LOC", negative_features={"supporting_llm": 0.48}, positive_features={})
    add_history("Castillo Maldito", referent_type="location", confidence=0.15, route="supporting", entity_label="LOC", negative_features={"supporting_llm": 0.48}, positive_features={})
    add_history("Not Cassian", referent_type="person", confidence=0.25, route="quarantine", negative_features={"malformed_name": 0.4})

    resolver.memory.register_supporting_by_name("Julian", "group", 1, 1)
    resolver.memory.register_supporting_by_name("door", "unknown", 1, 1)
    resolver.memory.register_supporting_by_name("moment", "unknown", 1, 1)
    resolver.memory.register_supporting_by_name("Tamlin", "group", 2, 1)
    resolver.memory.register_supporting_by_name("Snape", "group", 3, 1)
    for entity in resolver.memory.supporting_entities.values():
        if entity.name == "Julian":
            entity.mention_count = 120
            entity.last_seen_window = 4
        if entity.name == "door":
            entity.mention_count = 80
            entity.last_seen_window = 4
        if entity.name == "moment":
            entity.mention_count = 40
            entity.last_seen_window = 4
        if entity.name == "Tamlin":
            entity.mention_count = 68
            entity.last_seen_window = 6
        if entity.name == "Snape":
            entity.mention_count = 45
            entity.last_seen_window = 4

    add_history("Julian", chapter_index=1, window_index=1, sentence_text='Julian said, "Follow me."', in_quote=True, positive_features={"llm_person_confidence": 0.86, "proper_name_source": 0.1, "in_quote": 0.03})
    add_history("Julian", chapter_index=1, window_index=2, sentence_text="Scarlett watched Julian cross the room.")
    add_history("Tamlin", chapter_index=2, window_index=1, sentence_text="Tamlin bowed his head.")
    add_history("Tamlin", chapter_index=2, window_index=3, sentence_text='Lucien heard Tamlin say, "Enough."', in_quote=True, positive_features={"llm_person_confidence": 0.8, "proper_name_source": 0.1, "in_quote": 0.03})
    add_history("Snape", chapter_index=3, window_index=1, sentence_text="Snape swept into the room.")
    add_history("Snape", chapter_index=3, window_index=2, sentence_text='Harry heard Snape say, "Turn to page three hundred and ninety-four."', in_quote=True, positive_features={"llm_person_confidence": 0.84, "proper_name_source": 0.1, "in_quote": 0.03})
    add_history("Snape", chapter_index=3, window_index=3, sentence_text="Ron glared at Snape.")
    add_history("door", referent_type="object", confidence=0.05, route="supporting", mention_type="descriptor", negative_features={"supporting_llm": 0.48})
    add_history("moment", referent_type="object", confidence=0.04, route="supporting", mention_type="descriptor", negative_features={"supporting_llm": 0.48})

    preferred_az_id = resolver._prefer_canonical_target(azriel_id, az_id)
    assert preferred_az_id == azriel_id, "Expected Azriel to outrank Az even when Az has higher mention count"

    result = resolver.build_result()
    canonical_names = {item["canonical_name"] for item in result["canonical_characters"].values()}
    temporary_names = {item["canonical_name"] for item in result["temporary_person_candidates"].values()}
    meaningful_supporting_names = {item["name"] for item in result["meaningful_supporting_entities"].values()}
    discarded_names = {item["name"] for item in result["discarded_non_character_mentions"].values()}
    all_supporting_names = meaningful_supporting_names | discarded_names

    assert "Harry Potter" in canonical_names and "Harry" not in canonical_names
    assert "Professor Dumbledore" in canonical_names and "Dumbledore" not in canonical_names
    assert "Prince Cardan" in canonical_names and "Cardan" not in canonical_names
    assert "Azriel" in canonical_names and "Az" not in canonical_names
    assert "Julian" in canonical_names
    assert "Tamlin" in canonical_names or "Tamlin" in temporary_names
    assert "Snape" in canonical_names or "Snape" in temporary_names
    assert "door" in discarded_names and "moment" in discarded_names
    assert "Julian" not in meaningful_supporting_names and "Tamlin" not in meaningful_supporting_names
    assert not {"High Fae", "Illyrian Mountains", "Castillo Maldito"} & canonical_names
    assert {"High Fae", "Illyrian Mountains", "Castillo Maldito"} <= all_supporting_names
    assert "Not Cassian" not in canonical_names and "Not Cassian" not in temporary_names
    print("Post-pass stabilization regression test passed.")
    return result


if __name__ == "__main__":
    run_gliner_extraction_regression_test()
    run_postpass_stabilization_regression_test()
