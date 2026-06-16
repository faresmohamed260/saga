from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from infrastructure.llm_client import LLMClient

DEFAULT_WIKI_BASE_URL = "https://acourtofthornsandroses.fandom.com"
DEFAULT_SERIES_ID = "acotar"
SERIES_WIKI_BASE_URLS = {
    "acotar": "https://acourtofthornsandroses.fandom.com",
    "harry-potter": "https://harrypotter.fandom.com",
    "hp": "https://harrypotter.fandom.com",
}

ACOTAR_TITLE_OVERRIDES = {
    "feyre": "Feyre_Archeron",
    "tamlin": "Tamlin",
    "lucien": "Lucien_Vanserra",
    "rhysand": "Rhysand",
    "nesta": "Nesta_Archeron",
    "elain": "Elain_Archeron",
    "alis": "Alis",
    "amarantha": "Amarantha",
    "suriel": "Suriel",
    "attor": "Attor",
    "the attor": "Attor",
}


class WikiCharacterReferenceService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        *,
        wiki_base_url: str = DEFAULT_WIKI_BASE_URL,
        series_id: str = DEFAULT_SERIES_ID,
        timeout: int = 30,
    ):
        self.llm = llm_client or LLMClient(mode=LLMClient.MODE_CODEX)
        self.series_id = series_id
        resolved_base = SERIES_WIKI_BASE_URLS.get(str(series_id or "").strip().lower(), wiki_base_url)
        self.wiki_base_url = resolved_base.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def research_names(
        self,
        names: list[str],
        *,
        context_map: dict[str, dict[str, Any]] | None = None,
        contract_title: str = "",
    ) -> dict[str, Any]:
        entries = []
        context_map = context_map or {}
        for name in names:
            clean_name = str(name or "").strip()
            if not clean_name:
                continue
            entries.append(
                self.research_character(
                    clean_name,
                    local_context=context_map.get(clean_name.lower()) or {},
                    contract_title=contract_title,
                )
            )
        return {
            "series_id": self.series_id,
            "wiki_base_url": self.wiki_base_url,
            "provider": self.llm.provider_name(),
            "model": self.llm.resolved_model_name(),
            "contract_title": contract_title,
            "entries": entries,
        }

    def research_character(self, name: str, *, local_context: dict[str, Any] | None = None, contract_title: str = "") -> dict[str, Any]:
        local_context = local_context or {}
        resolution = self._resolve_page_title(name)
        page_title = resolution.get("page_title") or ""
        appearance_excerpt = ""
        intro_excerpt = ""
        issues: list[str] = []
        target_scope = self._infer_target_scope(name, contract_title=contract_title, local_context=local_context)
        if page_title:
            intro_excerpt = self._fetch_intro_excerpt(page_title)
            appearance_excerpt = self._fetch_appearance_excerpt(page_title)
            if not appearance_excerpt:
                issues.append("appearance_excerpt_missing")
        else:
            issues.append("page_not_found")

        response = self.llm.generate_json(
            self._build_structuring_prompt(
                display_name=name,
                page_title=page_title,
                target_scope=target_scope,
                intro_excerpt=intro_excerpt,
                appearance_excerpt=appearance_excerpt,
                local_context=local_context,
            ),
            strict=True,
            validator=self._validate_structured_reference,
        )
        if isinstance(response, dict) and "error" not in response:
            payload = dict(response)
            payload["display_name"] = name
            payload["page_title"] = page_title or ""
            payload["page_url"] = self._page_url(page_title) if page_title else ""
            payload["appearance_excerpt"] = appearance_excerpt
            payload["intro_excerpt"] = intro_excerpt
            payload["search_query"] = resolution.get("search_query") or ""
            payload["search_candidates"] = resolution.get("search_candidates") or []
            payload["resolved_via"] = resolution.get("resolved_via") or ""
            payload["target_scope"] = target_scope
            payload["local_context"] = local_context
            payload["agent_web_search_used"] = True
            payload["agent_web_search_mode"] = "mediawiki_api_search"
            payload["issues"] = list(payload.get("issues") or []) + issues
            return payload
        return {
            "display_name": name,
            "page_title": page_title or "",
            "page_url": self._page_url(page_title) if page_title else "",
            "appearance_excerpt": appearance_excerpt,
            "intro_excerpt": intro_excerpt,
            "search_query": resolution.get("search_query") or "",
            "search_candidates": resolution.get("search_candidates") or [],
            "resolved_via": resolution.get("resolved_via") or "",
            "target_scope": target_scope,
            "local_context": local_context,
            "agent_web_search_used": bool(page_title),
            "agent_web_search_mode": "mediawiki_api_search" if page_title else "mediawiki_api_search_failed",
            "entity_type": "character",
            "baseline_scope": "",
            "canon_notes": [],
            "structured_traits": {
                "hair_description": "",
                "eye_description": "",
                "skin_description": "",
                "body_type": "",
                "facial_structure": "",
                "clothing_description": "",
                "footwear_description": "",
                "world_aesthetic_cues": "",
                "distinguishing_marks": "",
                "fantasy_features": "",
            },
            "confidence": "low",
            "issues": issues + [f"llm_error:{response.get('error') if isinstance(response, dict) else 'unknown'}"],
        }

    def _resolve_page_title(self, name: str) -> dict[str, Any]:
        key = name.strip().lower()
        direct_title = self._direct_title_match(name)
        if direct_title:
            return {
                "page_title": direct_title,
                "search_query": f'title:"{name}"',
                "search_candidates": [direct_title.replace("_", " ")],
                "resolved_via": "direct_title_match",
            }
        search_query = f'intitle:"{name}"'
        query = self._api_get(
            {
                "action": "query",
                "list": "search",
                "srsearch": search_query,
                "srlimit": 5,
                "format": "json",
            }
        )
        candidates = ((query.get("query") or {}).get("search") or []) if isinstance(query, dict) else []
        candidate_titles = [str(row.get("title") or "").strip() for row in candidates if str(row.get("title") or "").strip()]
        normalized = name.replace("_", " ").strip().lower()
        if self.series_id == DEFAULT_SERIES_ID and key in ACOTAR_TITLE_OVERRIDES:
            override = ACOTAR_TITLE_OVERRIDES[key]
            if any(title.replace(" ", "_") == override for title in candidate_titles) or not candidate_titles:
                return {
                    "page_title": override,
                    "search_query": search_query,
                    "search_candidates": candidate_titles,
                    "resolved_via": "series_override",
                }
        for row in candidates:
            title = str(row.get("title") or "")
            if title.strip().lower() == normalized:
                return {
                    "page_title": title.replace(" ", "_"),
                    "search_query": search_query,
                    "search_candidates": candidate_titles,
                    "resolved_via": "exact_search_match",
                }
        for row in candidates:
            title = str(row.get("title") or "")
            if normalized in title.strip().lower() and not self._looks_like_media_page(title):
                return {
                    "page_title": title.replace(" ", "_"),
                    "search_query": search_query,
                    "search_candidates": candidate_titles,
                    "resolved_via": "partial_search_match",
                }
        return {
            "page_title": "",
            "search_query": search_query,
            "search_candidates": candidate_titles,
            "resolved_via": "not_found",
        }

    def _direct_title_match(self, name: str) -> str:
        payload = self._api_get(
            {
                "action": "query",
                "titles": name,
                "redirects": 1,
                "format": "json",
            }
        )
        pages = (((payload or {}).get("query") or {}).get("pages") or {})
        for _, page in pages.items():
            if str(page.get("missing") or ""):
                continue
            title = str(page.get("title") or "").strip()
            if title and not self._looks_like_media_page(title):
                return title.replace(" ", "_")
        return ""

    def _looks_like_media_page(self, title: str) -> bool:
        lowered = str(title or "").strip().lower()
        media_markers = [
            "(film)",
            "(movie)",
            "(novel)",
            "(book)",
            "(soundtrack)",
            "video game",
            "game",
            "chapter",
        ]
        return any(marker in lowered for marker in media_markers)

    def _fetch_intro_excerpt(self, page_title: str) -> str:
        html = self._parse_page_html(page_title)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        root = soup.find("div", class_="mw-parser-output") or soup
        paragraphs: list[str] = []
        for node in root.find_all("p", recursive=False):
            text = node.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
            if len(paragraphs) >= 2:
                break
        return "\n".join(paragraphs[:2]).strip()

    def _fetch_appearance_excerpt(self, page_title: str) -> str:
        html = self._parse_page_html(page_title)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        headline = soup.find("span", id="Appearance")
        if not headline:
            return ""
        header = headline.find_parent(["h2", "h3"])
        if not header:
            return ""
        chunks: list[str] = []
        node = header.find_next_sibling()
        while node and node.name not in {"h2", "h3"}:
            text = node.get_text(" ", strip=True)
            if text:
                chunks.append(text)
            node = node.find_next_sibling()
        return "\n".join(chunks).strip()

    def _parse_page_html(self, page_title: str) -> str:
        payload = self._api_get(
            {
                "action": "parse",
                "page": page_title,
                "prop": "text",
                "format": "json",
                "formatversion": "2",
            }
        )
        return str(((payload.get("parse") or {}).get("text")) or "") if isinstance(payload, dict) else ""

    def _api_get(self, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(f"{self.wiki_base_url}/api.php", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _page_url(self, page_title: str | None) -> str:
        if not page_title:
            return ""
        return f"{self.wiki_base_url}/wiki/{quote(page_title, safe='_')}"

    def _build_structuring_prompt(
        self,
        *,
        display_name: str,
        page_title: str,
        target_scope: str,
        intro_excerpt: str,
        appearance_excerpt: str,
        local_context: dict[str, Any],
    ) -> str:
        return f"""
You are a canon appearance research agent. Return strict JSON only.

Task:
- Read the fandom wiki intro and Appearance excerpt for one character or creature.
- Use the target scope and local contract context to filter out later-book or alternate-form drift when it conflicts with the requested baseline.
- Extract only stable baseline visual traits.
- Ignore powers unless they create stable visible anatomy or marks.
- Ignore scene-specific emotions unless they clearly describe a stable resting look.
- If the subject is a creature rather than a person-like character, mark `entity_type` as `creature`.
- Keep notes concise and image-generation useful.

Required JSON schema:
{{
  "display_name": "{display_name}",
  "entity_type": "character|creature",
  "baseline_scope": "",
  "canon_notes": [""],
  "structured_traits": {{
    "hair_description": "",
    "eye_description": "",
    "skin_description": "",
    "body_type": "",
    "facial_structure": "",
    "clothing_description": "",
    "footwear_description": "",
    "world_aesthetic_cues": "",
    "distinguishing_marks": "",
    "fantasy_features": ""
  }},
  "confidence": "high|medium|low",
  "issues": [""]
}}

Character:
- display_name: {display_name}
- page_title: {page_title}
- target_scope: {target_scope or "none"}

Local contract context:
{json.dumps(local_context, ensure_ascii=False)}

Intro excerpt:
{intro_excerpt or "none"}

Appearance excerpt:
{appearance_excerpt or "none"}
"""

    def _infer_target_scope(self, name: str, *, contract_title: str, local_context: dict[str, Any]) -> str:
        title = str(contract_title or "").strip()
        profile = local_context.get("persistent_visual_profile") or {}
        species = str(profile.get("species_or_race") or "").strip().lower()
        role = str(profile.get("role_or_archetype") or "").strip().lower()
        scope_parts: list[str] = []
        if title:
            scope_parts.append(f"Target contract book: {title}.")
        if species:
            scope_parts.append(f"Prefer a baseline consistent with the local contract species/state: {species}.")
        if role:
            scope_parts.append(f"Local role cue: {role}.")
        if title.lower().startswith("a court of thorns and roses") and "feyre" in name.lower() and "human" in species:
            scope_parts.append("Use Feyre's Book 1 mortal baseline before later High Fae transformation and later-series tattoos.")
        if title.lower().startswith("a court of thorns and roses") and "nesta" in name.lower() and "human" in species:
            scope_parts.append("Prefer Nesta's Book 1 mortal baseline over later High Fae changes.")
        if title.lower().startswith("a court of thorns and roses") and "elain" in name.lower() and "human" in species:
            scope_parts.append("Prefer Elain's Book 1 mortal baseline over later High Fae changes.")
        if "creature" in species or any(token in role for token in {"creature", "monster", "beast"}):
            scope_parts.append("Treat this subject as a creature baseline, not a humanoid fashion sheet.")
        return " ".join(scope_parts).strip()

    @staticmethod
    def _validate_structured_reference(response: dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("canon_notes"), list)
            and isinstance(response.get("structured_traits"), dict)
            and isinstance(response.get("issues"), list)
        )


def flatten_reference_entries(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload.get("entries") or []
    flattened: dict[str, Any] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        name = str(row.get("display_name") or "").strip().lower()
        if not name:
            continue
        flattened[name] = row
    return flattened
