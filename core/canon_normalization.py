"""Shared canon entity normalization helpers for ingest, repair, and retrieval."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CanonicalEntityContext:
    alias_lookup: Dict[str, str]
    normalized_lookup: Dict[str, str]
    entity_types: Dict[str, str]
    known_characters: Dict[str, str]


class CanonicalEntityNormalizer:
    BAD_ENTITY_PREFIXES = {
        "toward",
        "towards",
        "are",
        "remember",
        "get",
        "leave",
        "marked",
        "mourning",
        "fed",
        "just",
        "more",
        "so",
        "begged",
        "asked",
        "told",
        "watched",
        "watching",
        "seeing",
        "saw",
        "heard",
        "hearing",
        "thinking",
        "thought",
        "looked",
        "looking",
        "turning",
        "turned",
        "facing",
        "faced",
        "following",
        "followed",
        "beside",
        "behind",
        "before",
        "after",
        "into",
        "through",
        "beneath",
        "above",
        "across",
        "around",
        "of",
        "as",
        "along",
        "letting",
        "without",
    }
    TITLE_PREFIXES = {
        "high lord",
        "high lady",
        "lord",
        "lady",
        "queen",
        "king",
        "prince",
        "princess",
        "sir",
        "madam",
        "mr",
        "mrs",
        "ms",
        "dr",
        "captain",
        "commander",
        "general",
        "professor",
        "headmaster",
        "headmistress",
    }
    PRONOUN_LIKE = {
        "i", "me", "my", "myself", "we", "us", "our", "ourselves",
        "they", "them", "their", "theirs", "he", "him", "his",
        "she", "her", "hers", "you", "your", "yours", "it", "its",
    }
    FRAGMENT_STOPWORDS = {"and", "than", "how", "are", "you", "your", "our", "their", "his", "her", "or", "is", "as", "of"}
    CONTEXTUAL_TOKENS = {
        "for",
        "ago",
        "years",
        "year",
        "months",
        "month",
        "weeks",
        "week",
        "days",
        "day",
        "duty",
        "siphons",
        "slung",
        "hefted",
        "marked",
        "including",
        "cursebreaker",
        "solstice",
        "darkbringers",
        "or",
        "is",
        "as",
        "saw",
        "turned",
        "lowered",
        "seized",
        "support",
        "stunning",
        "grabbed",
        "holding",
        "carried",
        "followed",
        "watching",
        "called",
        "as",
        "once",
        "though",
        "neither",
        "welcome",
        "tell",
        "with",
        "without",
        "near",
        "over",
        "under",
        "inside",
        "outside",
        "at",
    }
    GENERIC_TITLE_MODIFIERS = {
        "mortal",
        "ancient",
        "young",
        "old",
        "masked",
        "golden",
        "red-haired",
        "fox-masked",
        "unnamed",
        "mysterious",
    }
    NON_CHARACTER_SINGLE_TOKENS = {
        "war",
        "army",
        "apartment",
        "arrow",
        "asshole",
        "blacksmith",
        "blank",
        "blanket",
        "bow",
        "cabin",
        "camp",
        "cavern",
        "chill",
        "clearing",
        "death",
        "darkness",
        "middle",
        "mountain",
        "library",
        "house",
        "room",
        "hall",
        "study",
        "cottage",
        "manor",
        "palace",
        "court",
        "mask",
        "crown",
        "harp",
        "book",
        "ribbon",
        "bridge",
        "lake",
        "river",
        "forest",
        "garden",
        "lands",
        "arena",
        "cell",
        "bedroom",
        "foyer",
        "kitchen",
        "fireplace",
        "painting",
        "sword",
        "dagger",
        "tent",
        "valkyrie",
        "spring",
        "summer",
        "winter",
        "autumn",
        "potions",
        "siphons",
        "solstice",
        "cursebreaker",
        "darkbringers",
        "charms",
        "chapter",
        "support",
    }
    LOCATION_KEYWORDS = {
        "house",
        "court",
        "palace",
        "city",
        "town",
        "townhouse",
        "village",
        "manor",
        "estate",
        "keep",
        "fortress",
        "castle",
        "mountain",
        "lake",
        "river",
        "forest",
        "woods",
        "lands",
        "garden",
        "hall",
        "bedroom",
        "office",
        "foyer",
        "study",
        "library",
        "camp",
        "pass",
        "battlefield",
        "bog",
        "plains",
        "ruins",
        "prison",
        "cottage",
        "isle",
        "island",
        "border",
        "sea",
        "shore",
    }
    _ADDRESS_DETERMINERS = frozenset({
        "their", "your", "his", "her", "our", "my", "its",
    })
    _NUMBER_WORDS = frozenset({
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
        "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
        "eighth", "ninth", "tenth",
    })
    NON_CHARACTER_TYPES = {"location", "object", "artifact", "creature", "place"}
    KNOWN_CHARACTER_TYPES = {"character", "person", "human", "fae", "high_fae"}

    def normalized_entity_key(self, value: str) -> str:
        stripped = self.strip_title_prefix(str(value or "").strip())
        return re.sub(r"[^a-z0-9]", "", (stripped or value or "").lower())

    def title_case_like(self, value: str) -> str:
        parts: List[str] = []
        for token in str(value or "").strip().split():
            if token.isupper():
                parts.append(token)
            else:
                parts.append(token[:1].upper() + token[1:])
        return " ".join(parts).strip()

    def collapse_ocr_spacing(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"\b([A-Za-z]{2,})\s+([A-Za-z])\b", r"\1\2", text)
        text = re.sub(r"\b([A-Za-z])\s+([A-Za-z]{2,})\b", r"\1\2", text)
        text = re.sub(r"('s)([A-Za-z])", r"\1 \2", text)
        return re.sub(r"\s+", " ", text).strip()

    def strip_title_prefix(self, value: str) -> str:
        text = str(value or "").strip()
        lowered = re.sub(r"[^a-z0-9\s'-]", "", text.lower())
        lowered = re.sub(r"\s+", " ", lowered).strip()
        for prefix in sorted(self.TITLE_PREFIXES, key=len, reverse=True):
            if lowered.startswith(prefix + " "):
                return text[len(prefix):].strip()
        return text

    def looks_like_location_name(self, value: str) -> bool:
        text = str(value or "").strip()
        lowered = text.lower()
        if not lowered:
            return False
        if "'s house" in lowered or lowered.endswith(" house"):
            return True
        tokens = [token.strip(" ,.'\"") for token in lowered.split()]
        return any(token in self.LOCATION_KEYWORDS for token in tokens)

    def is_bad_alias_like_name(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        lowered = text.lower()
        if lowered in self.PRONOUN_LIKE:
            return True
        tokens = lowered.split()
        if not tokens or tokens[0] in self.BAD_ENTITY_PREFIXES:
            return True
        if len(tokens) > 5:
            return True
        if any(token.isdigit() for token in tokens):
            return True
        if any(token in {"toward", "towards", "into", "through", "beneath"} for token in tokens[:2]):
            return True
        if not self.looks_like_location_name(text) and len(tokens) >= 3 and any(token in self.FRAGMENT_STOPWORDS for token in tokens):
            return True
        return False

    def looks_like_character_name(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text or self.is_bad_alias_like_name(text) or self.looks_like_location_name(text):
            return False
        if text.lower() in self.TITLE_PREFIXES:
            return False
        tokens = text.split()
        if len(tokens) > 4:
            return False
        lowered_tokens = [token.strip(" ,.'\"").lower() for token in tokens]
        if lowered_tokens and lowered_tokens[0] in self._ADDRESS_DETERMINERS:
            return False
        if len(lowered_tokens) >= 2 and lowered_tokens[-1] in self._NUMBER_WORDS:
            return False
        if len(tokens) == 1 and lowered_tokens[0] in self.NON_CHARACTER_SINGLE_TOKENS:
            return False
        if (
            len(tokens) == 2
            and lowered_tokens[0] in self.GENERIC_TITLE_MODIFIERS
            and lowered_tokens[1] in {"queen", "king", "lord", "lady", "priestess", "warrior", "blacksmith"}
        ):
            return False
        if len(tokens) > 1 and any(token in self.CONTEXTUAL_TOKENS for token in lowered_tokens[1:]):
            return False
        return bool(re.match(r"^[A-Z][A-Za-z'`.-]*(?:\s+[A-Z][A-Za-z'`.-]*)*$", text))

    def infer_entity_type(
        self,
        name: str,
        *,
        existing_type: str = "",
        descriptions: Optional[Sequence[str]] = None,
    ) -> str:
        entity_type = str(existing_type or "").strip().lower()
        description_text = " ".join(str(item or "") for item in (descriptions or []))
        description_lower = description_text.lower()
        if self.is_bad_alias_like_name(name):
            return "unknown"
        if self.looks_like_location_name(name):
            return "location"
        if self.looks_like_character_name(name):
            return "character"
        if entity_type in self.KNOWN_CHARACTER_TYPES:
            return "character"
        if entity_type in self.NON_CHARACTER_TYPES:
            return entity_type
        if any(keyword in description_lower for keyword in self.LOCATION_KEYWORDS):
            return "location"
        if entity_type:
            return entity_type
        return "unknown"

    def canonicalize_candidate_name(self, raw: str, *, hints: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
        name = self.collapse_ocr_spacing(raw)
        if not name:
            return ""
        if re.match(r"^[Ii][A-Z][A-Za-z'`.-]+$", name):
            name = name[:1] + " " + name[1:]
        name = str(name).strip(" \t\r\n\"'“”‘’.,;:!?()[]{}")
        if len(name.split()) == 1 and name.endswith("'s"):
            possessive_root = name[:-2].strip()
            if possessive_root:
                name = possessive_root
        if "," in name:
            name = name.split(",", 1)[0].strip()
        raw_tokens = [token.strip(" \t\r\n\"'.,;:!?()[]{}") for token in name.split() if token.strip(" \t\r\n\"'.,;:!?()[]{}")]
        if (
            len(raw_tokens) >= 2
            and raw_tokens[0] in {"I", "i"}
            and raw_tokens[1][:1].isupper()
            and raw_tokens[1].lower() not in self.PRONOUN_LIKE
        ):
            raw_tokens = raw_tokens[1:]
            name = " ".join(raw_tokens)
        lowered_tokens = [token.lower() for token in raw_tokens]
        if len(raw_tokens) == 2 and lowered_tokens[0] in {"the", "a", "an"} and lowered_tokens[1] in self.NON_CHARACTER_SINGLE_TOKENS:
            return ""
        if len(raw_tokens) >= 2 and any(token in self.CONTEXTUAL_TOKENS for token in lowered_tokens):
            proper_tokens = [token for token in raw_tokens if token[:1].isupper()]
            if lowered_tokens[0] in {"welcome", "marked", "called", "asked", "begged", "once", "though", "neither", "tell"} and proper_tokens:
                name = proper_tokens[-1]
            elif "as" in lowered_tokens and proper_tokens:
                name = proper_tokens[-1]
            elif (
                raw_tokens[0][:1].isupper()
                and lowered_tokens[0] not in self.CONTEXTUAL_TOKENS
                and lowered_tokens[0] not in self.NON_CHARACTER_SINGLE_TOKENS
            ):
                name = raw_tokens[0]
            elif proper_tokens:
                name = proper_tokens[-1]
        elif len(raw_tokens) == 2:
            first_token, second_token = raw_tokens
            if first_token[:1].isupper() and second_token and second_token[0].islower():
                name = first_token
        name = self.strip_title_prefix(name)
        if self.is_bad_alias_like_name(name):
            return ""
        if len(name.split()) == 1 and name.lower() in self.NON_CHARACTER_SINGLE_TOKENS:
            return ""
        return self.title_case_like(name)

    def choose_canonical_name(self, options: Iterable[str], *, hints: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
        cleaned = [self.canonicalize_candidate_name(item, hints=hints or {}) for item in options]
        cleaned = [item for item in cleaned if item]
        if not cleaned:
            return ""

        def _score(value: str) -> Tuple[int, int, int, str]:
            return (
                2 if self.looks_like_character_name(value) else 0,
                0 if self.looks_like_location_name(value) else 1,
                len(value.split()),
                value,
            )

        cleaned = sorted(set(cleaned), key=_score, reverse=True)
        return cleaned[0]

    def expand_short_character_name(self, name: str, candidates: Iterable[str]) -> str:
        normalized = self.normalized_entity_key(name)
        matches: List[str] = []
        for candidate in candidates:
            if candidate == name:
                continue
            candidate_tokens = [token.lower() for token in candidate.split()]
            if normalized in {self.normalized_entity_key(token) for token in candidate_tokens}:
                matches.append(candidate)
            elif " " in candidate and self.normalized_entity_key(candidate).startswith(normalized):
                matches.append(candidate)
            elif len(normalized) >= 3:
                candidate_norm = self.normalized_entity_key(candidate)
                if candidate_norm.startswith(normalized) and len(candidate_norm) > len(normalized) + 1:
                    matches.append(candidate)
        unique = sorted(set(matches), key=lambda item: (len(item.split()), len(item)), reverse=True)
        if len(unique) == 1:
            return unique[0]
        return ""

    def build_context(
        self,
        *,
        entity_registry: Iterable[Dict[str, Any]],
        alias_map: Dict[str, List[str]],
    ) -> CanonicalEntityContext:
        alias_lookup: Dict[str, str] = {}
        normalized_lookup: Dict[str, str] = {}
        entity_types: Dict[str, str] = {}
        known_characters: Dict[str, str] = {}
        for row in entity_registry:
            name = self.canonicalize_candidate_name(row.get("name", ""))
            if not name:
                continue
            entity_type = self.infer_entity_type(
                name,
                existing_type=str(row.get("entity_type") or ""),
                descriptions=[entry.get("description", "") for entry in (row.get("descriptions") or []) if isinstance(entry, dict)],
            )
            entity_types[name] = entity_type
            normalized_lookup[self.normalized_entity_key(name)] = name
            if entity_type == "character":
                known_characters[self.normalized_entity_key(name)] = name
        for canonical, aliases in (alias_map or {}).items():
            canonical_name = self.canonicalize_candidate_name(canonical)
            if not canonical_name:
                continue
            alias_lookup[canonical_name] = canonical_name
            normalized_lookup[self.normalized_entity_key(canonical_name)] = canonical_name
            if self.infer_entity_type(canonical_name, existing_type=entity_types.get(canonical_name, "")) == "character":
                known_characters[self.normalized_entity_key(canonical_name)] = canonical_name
            for alias in aliases or []:
                alias_name = self.canonicalize_candidate_name(alias)
                if not alias_name:
                    continue
                alias_lookup[alias_name] = canonical_name
                normalized_lookup[self.normalized_entity_key(alias_name)] = canonical_name
        return CanonicalEntityContext(
            alias_lookup=alias_lookup,
            normalized_lookup=normalized_lookup,
            entity_types=entity_types,
            known_characters=known_characters,
        )

    def resolve_name(
        self,
        raw_name: str,
        *,
        context: CanonicalEntityContext,
        expect_character: bool = False,
    ) -> str:
        cleaned = self.canonicalize_candidate_name(raw_name)
        if not cleaned:
            return ""
        resolved = (
            context.alias_lookup.get(cleaned)
            or context.normalized_lookup.get(self.normalized_entity_key(cleaned))
            or cleaned
        )
        if expect_character:
            normalized = self.normalized_entity_key(resolved)
            if normalized in context.known_characters:
                return context.known_characters[normalized]
            if self.looks_like_character_name(resolved):
                return resolved
            return ""
        return resolved

    def build_merge_map(
        self,
        *,
        names: Iterable[str],
        alias_map: Dict[str, List[str]],
        hints: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        merge_map: Dict[str, str] = {}
        unresolved: List[Dict[str, Any]] = []
        name_list = sorted({str(name or "").strip() for name in names if str(name or "").strip()})
        character_like_names = [
            name
            for name in name_list
            if self.looks_like_character_name(self.canonicalize_candidate_name(name))
        ]

        for canonical, aliases in (alias_map or {}).items():
            target = self.canonicalize_candidate_name(canonical, hints=hints or {})
            if not target:
                continue
            merge_map[canonical] = target
            for alias in aliases or []:
                resolved_alias = self.canonicalize_candidate_name(alias, hints=hints or {})
                if resolved_alias:
                    merge_map[alias] = target

        by_norm: Dict[str, List[str]] = defaultdict(list)
        for name in name_list:
            candidate = self.canonicalize_candidate_name(name, hints=hints or {})
            if not candidate:
                continue
            by_norm[self.normalized_entity_key(candidate)].append(name)

        for normalized, options in by_norm.items():
            target = self.choose_canonical_name(options, hints=hints or {})
            if not target:
                continue
            unique_options = sorted(set(options))
            for option in unique_options:
                merge_map[option] = target
            if len({item for item in unique_options if self.canonicalize_candidate_name(item, hints=hints or {}) != target}) > 0:
                unresolved.append({"normalized_name": normalized, "options": unique_options, "selected": target})

        for name in name_list:
            if merge_map.get(name) not in (None, name):
                continue
            candidate = self.canonicalize_candidate_name(name, hints=hints or {})
            if candidate and candidate != name:
                merge_map[name] = candidate
                continue
            if (
                len(name.split()) == 1
                and len(self.normalized_entity_key(name)) >= 3
                and self.looks_like_character_name(candidate or name)
            ):
                expanded = self.expand_short_character_name(name, character_like_names)
                if expanded:
                    merge_map[name] = expanded

        return merge_map, unresolved[:50]

    def collect_named_values(self, payload: Any) -> List[str]:
        collected: List[str] = []
        self._collect_named_values_into(payload, collected)
        return collected

    def _collect_named_values_into(self, payload: Any, bucket: List[str]) -> None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in {"name", "entity_name", "character", "source_entity", "target_entity", "entity_a", "entity_b"} and isinstance(value, str):
                    bucket.append(value)
                elif key in {"characters", "canonical_characters"} and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            bucket.append(item)
                        elif isinstance(item, dict) and isinstance(item.get("name"), str):
                            bucket.append(item["name"])
                else:
                    self._collect_named_values_into(value, bucket)
        elif isinstance(payload, list):
            for item in payload:
                self._collect_named_values_into(item, bucket)
