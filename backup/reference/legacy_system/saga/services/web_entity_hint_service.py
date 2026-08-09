"""Optional web-backed entity heuristics shared by encoder and hardening flows."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from packages.web_search_runtime.tool_contracts import WebSearchTool
from saga.domain.canon_normalization import CanonicalEntityNormalizer
from saga.services.web_search_service import WebSearchService


class WebEntityHintService:
    """Load conservative wiki hints for entity cleanup without overriding book truth."""

    CHARACTER_CATEGORY_TOKENS = {
        "character", "characters", "people", "person", "witches", "wizards", "humans", "fae", "families",
        "births", "deaths", "students", "attendees", "professors", "headmasters", "headmistresses",
    }
    LOCATION_CATEGORY_TOKENS = {
        "location", "locations", "place", "places", "school", "schools", "court", "courts", "kingdom", "kingdoms",
        "realm", "realms", "castle", "castles", "house", "houses", "manor", "manors", "village", "villages",
        "city", "cities", "land", "lands", "woods", "forest", "forests",
    }
    OBJECT_CATEGORY_TOKENS = {"artifact", "artifacts", "object", "objects", "weapon", "weapons", "book", "books", "item", "items", "spell", "spells"}
    CREATURE_CATEGORY_TOKENS = {"creature", "creatures", "monster", "monsters", "beast", "beasts", "animal", "animals"}

    def __init__(
        self,
        *,
        timeout_seconds: int = 8,
        max_candidates: int = 40,
        web_search_tool: WebSearchTool | None = None,
    ) -> None:
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_candidates = max(1, int(max_candidates))
        self.normalizer = CanonicalEntityNormalizer()
        self.web_search = web_search_tool or WebSearchService()

    def load_series_hints(self, series_id: str, candidate_names: Iterable[str]) -> Dict[str, Dict[str, str]]:
        base_url = self.web_search.resolve_mediawiki_base_url(series_id=str(series_id or "").strip())
        if not base_url:
            return {}
        hints: Dict[str, Dict[str, str]] = {}
        for name in self._candidate_subset(candidate_names):
            normalized = self.normalizer.normalized_entity_key(name)
            if not normalized:
                continue
            hint = self._lookup_hint(base_url, name)
            if hint:
                hints[normalized] = hint
        return hints

    def _candidate_subset(self, candidate_names: Iterable[str]) -> List[str]:
        unique: List[str] = []
        seen = set()
        for raw in candidate_names:
            name = str(raw or "").strip()
            if not name:
                continue
            normalized = self.normalizer.normalized_entity_key(name)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(name)
        unique.sort(key=lambda item: (0 if self.normalizer.looks_like_character_name(item) else 1, len(item), item.lower()))
        return unique[: self.max_candidates]

    @lru_cache(maxsize=512)
    def _lookup_hint(self, base_url: str, candidate_name: str) -> Optional[Dict[str, str]]:
        title, description = self._search_result(base_url, candidate_name)
        if not title:
            return None
        categories = self.web_search.mediawiki_page_categories(title, base_url=base_url).get("categories") or []
        entity_type = self._infer_entity_type(categories, candidate_name, title, description)
        if not entity_type:
            return None
        return {
            "candidate_name": candidate_name,
            "matched_title": title,
            "description": description,
            "entity_type": entity_type,
            "categories": ", ".join(categories[:12]),
            "confidence": "high" if self._is_exactish_match(candidate_name, title) else "medium",
        }

    def _search_result(self, base_url: str, candidate_name: str) -> tuple[str, str]:
        try:
            results = self.web_search.search_mediawiki(candidate_name, base_url=base_url, max_results=1).get("results") or []
        except Exception:
            return "", ""
        for row in results:
            text = str(row.get("title") or "").strip()
            if text:
                return text, str(row.get("snippet") or "").strip()
        return "", ""

    def _infer_entity_type(self, categories: List[str], candidate_name: str, matched_title: str, description: str) -> str:
        lowered = " | ".join(categories).lower()
        title_lower = matched_title.lower()
        description_lower = str(description or "").lower()
        has_location = (
            any(token in lowered for token in self.LOCATION_CATEGORY_TOKENS)
            or "school of" in title_lower
            or any(token in description_lower for token in {"school", "castle", "village", "city", "court", "location", "realm"})
        )
        has_object = any(token in lowered for token in self.OBJECT_CATEGORY_TOKENS)
        has_creature = any(token in lowered for token in self.CREATURE_CATEGORY_TOKENS)
        has_character = (
            any(token in lowered for token in self.CHARACTER_CATEGORY_TOKENS)
            or any(token in description_lower for token in {"wizard", "witch", "student", "professor", "headmaster", "headmistress", "character", "person"})
        )
        has_biography_signal = any(token in lowered for token in {"births", "deaths", "attendees", "students", "professors"})

        if has_character and has_biography_signal:
            return "character"
        if has_character and not (has_location or has_object or has_creature):
            return "character"
        if has_location:
            return "location"
        if has_object:
            return "object"
        if has_creature:
            return "creature"
        if has_character:
            return "character"
        if self._is_exactish_match(candidate_name, matched_title) and self.normalizer.looks_like_character_name(candidate_name):
            return "character"
        if self._is_exactish_match(candidate_name, matched_title) and self.normalizer.looks_like_location_name(matched_title):
            return "location"
        return ""

    def _is_exactish_match(self, candidate_name: str, matched_title: str) -> bool:
        candidate_key = self.normalizer.normalized_entity_key(candidate_name)
        title_key = self.normalizer.normalized_entity_key(matched_title)
        if not candidate_key or not title_key:
            return False
        return candidate_key == title_key or candidate_key in title_key or title_key in candidate_key
