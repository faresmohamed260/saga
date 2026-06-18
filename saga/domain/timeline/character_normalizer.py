import re
from typing import Dict, List, Set, Tuple


class CharacterNormalizer:
    """
    Applies deterministic normalization before any LLM-based identity work.

    Current rules:
    - case-insensitive exact-name merges
    - article-insensitive role-label merges such as hunter -> the hunter
    - simple shortened-name merges such as Rhys -> Rhysand
    """

    INVALID_IDENTITIES = {
        "i",
        "me",
        "my",
        "myself",
        "narrator",
        "protagonist",
        "character",
        "person",
        "someone",
        "somebody",
        "voice",
        "figure",
    }

    def normalize(self, character_timelines: List[Dict]) -> Dict:
        merged_timelines = self._filter_invalid_identities(character_timelines)
        alias_map = {}

        merged_timelines, article_aliases = self._merge_article_variants(merged_timelines)
        alias_map.update(article_aliases)

        merged_timelines, case_aliases = self._merge_case_variants(merged_timelines)
        alias_map = self._merge_alias_maps(alias_map, case_aliases)

        merged_timelines, compact_aliases = self._merge_compact_variants(merged_timelines)
        alias_map = self._merge_alias_maps(alias_map, compact_aliases)

        merged_timelines, short_aliases = self._merge_shortened_names(merged_timelines)
        alias_map = self._merge_alias_maps(alias_map, short_aliases)

        merged_timelines, final_case_aliases = self._merge_case_variants(merged_timelines)
        alias_map = self._merge_alias_maps(alias_map, final_case_aliases)

        return {
            "character_timelines": sorted(merged_timelines, key=lambda item: item["character"].lower()),
            "alias_map": {
                canonical: sorted(aliases, key=str.lower)
                for canonical, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
            },
        }

    def _filter_invalid_identities(self, character_timelines: List[Dict]) -> List[Dict]:
        filtered = []
        for item in character_timelines:
            character = (item.get("character") or "").strip()
            if not character:
                continue
            if self._normalize_name(character) in self.INVALID_IDENTITIES:
                continue
            filtered.append(self._clone_timeline(item))
        return filtered

    def _merge_article_variants(self, character_timelines: List[Dict]) -> Tuple[List[Dict], Dict[str, Set[str]]]:
        groups = {}
        passthrough = []

        for item in character_timelines:
            article_key = self._article_insensitive_name(item["character"])
            if article_key == self._normalize_name(item["character"]):
                passthrough.append(item)
                continue
            groups.setdefault(article_key, []).append(item)

        merged = list(passthrough)
        alias_map = {}

        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
                continue

            canonical = self._choose_canonical(group)
            combined_events = []
            aliases = set()

            for item in group:
                combined_events.extend(item["events"])
                aliases.add(item["character"])

            merged.append({
                "character": canonical,
                "events": self._sort_events(combined_events),
            })
            alias_map[canonical] = aliases

        return merged, alias_map

    def _merge_case_variants(self, character_timelines: List[Dict]) -> Tuple[List[Dict], Dict[str, Set[str]]]:
        groups = {}
        for item in character_timelines:
            groups.setdefault(self._normalize_name(item["character"]), []).append(item)

        merged = []
        alias_map = {}

        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
                continue

            canonical = self._choose_canonical(group)
            combined_events = []
            aliases = set()

            for item in group:
                combined_events.extend(item["events"])
                aliases.add(item["character"])

            merged.append({
                "character": canonical,
                "events": self._sort_events(combined_events),
            })
            alias_map[canonical] = aliases

        return merged, alias_map

    def _merge_shortened_names(self, character_timelines: List[Dict]) -> Tuple[List[Dict], Dict[str, Set[str]]]:
        items = [self._clone_timeline(item) for item in character_timelines]
        alias_map = {}
        consumed = set()
        merged = []

        for i, item in enumerate(items):
            if i in consumed:
                continue

            canonical = item
            aliases = {item["character"]}
            combined_events = list(item["events"])

            for j, other in enumerate(items[i + 1:], start=i + 1):
                if j in consumed:
                    continue

                if not self._is_shortened_variant(canonical["character"], other["character"]):
                    continue

                preferred = self._preferred_long_form(canonical, other)
                secondary = other if preferred is canonical else canonical

                canonical = preferred
                aliases.add(secondary["character"])
                aliases.add(preferred["character"])
                combined_events.extend(secondary["events"])
                consumed.add(j)

            merged.append({
                "character": canonical["character"],
                "events": self._sort_events(combined_events),
            })

            if len(aliases) > 1:
                alias_map[canonical["character"]] = aliases

        return merged, alias_map

    def _merge_compact_variants(self, character_timelines: List[Dict]) -> Tuple[List[Dict], Dict[str, Set[str]]]:
        groups = {}
        for item in character_timelines:
            groups.setdefault(self._compact_key(item["character"]), []).append(item)

        merged = []
        alias_map = {}

        for compact_key, group in groups.items():
            if not compact_key or len(group) == 1:
                merged.extend(group)
                continue

            canonical = self._choose_canonical(group)
            combined_events = []
            aliases = set()

            for item in group:
                combined_events.extend(item["events"])
                aliases.add(item["character"])

            merged.append({
                "character": canonical,
                "events": self._sort_events(combined_events),
            })
            alias_map[canonical] = aliases

        return merged, alias_map

    def _is_shortened_variant(self, name_a: str, name_b: str) -> bool:
        token_a = self._single_token(name_a)
        token_b = self._single_token(name_b)
        if not token_a or not token_b or token_a == token_b:
            return False

        short, long_name = sorted([token_a, token_b], key=len)
        if len(short) < 4 or len(long_name) - len(short) < 2:
            return False

        return long_name.startswith(short)

    def _preferred_long_form(self, item_a: Dict, item_b: Dict) -> Dict:
        token_a = self._single_token(item_a["character"]) or ""
        token_b = self._single_token(item_b["character"]) or ""

        if len(token_a) != len(token_b):
            return item_a if len(token_a) > len(token_b) else item_b

        return item_a if len(item_a["events"]) >= len(item_b["events"]) else item_b

    def _choose_canonical(self, items: List[Dict]) -> str:
        best = sorted(
            items,
            key=lambda item: (
                -len(item["events"]),
                not any(ch.isupper() for ch in item["character"]),
                len(item["character"]),
                item["character"].lower(),
            ),
        )[0]
        return best["character"]

    def _sort_events(self, events: List[Dict]) -> List[Dict]:
        unique = {}
        for event in events:
            key = (
                event.get("time_index"),
                event.get("book_index"),
                event.get("chapter_index"),
                event.get("scene_index"),
                event.get("event_id"),
                event.get("summary"),
            )
            unique[key] = event

        return sorted(
            unique.values(),
            key=lambda event: (
                event.get("time_index", 10**9),
                event.get("book_index", 10**9),
                event.get("chapter_index", 10**9),
                event.get("scene_index", 10**9),
            ),
        )

    def _merge_alias_maps(self, first: Dict[str, Set[str]], second: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        merged = {canonical: set(aliases) for canonical, aliases in first.items()}

        for canonical, aliases in second.items():
            merged.setdefault(canonical, set()).update(aliases)

        return merged

    def _single_token(self, name: str) -> str:
        tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", (name or "").strip())
        if len(tokens) != 1:
            return ""
        return tokens[0].lower()

    def _normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", (name or "").strip().lower())

    def _article_insensitive_name(self, name: str) -> str:
        normalized = self._normalize_name(name)
        return re.sub(r"^(the|a|an)\s+", "", normalized)

    def _compact_key(self, name: str) -> str:
        return "".join(re.findall(r"[A-Za-z]+", (name or "").lower()))

    def _clone_timeline(self, item: Dict) -> Dict:
        return {
            "character": item["character"],
            "events": list(item.get("events", [])),
        }
