"""Portable agent-facing tool contracts for web-search workflows."""

from __future__ import annotations

from typing import Any, Protocol


class WebSearchTool(Protocol):
    def search(self, query: str, *, max_results: int = 8, site: str = "") -> dict[str, Any]:
        ...

    def fetch_document(self, url: str) -> dict[str, Any]:
        ...

    def resolve_mediawiki_base_url(self, *, series_id: str = "", base_url: str = "") -> str:
        ...

    def search_mediawiki(self, query: str, *, series_id: str = "", base_url: str = "", max_results: int = 5) -> dict[str, Any]:
        ...

    def mediawiki_get(self, params: dict[str, Any], *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        ...

    def mediawiki_page_categories(self, page_title: str, *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        ...

    def mediawiki_parse_html(self, page_title: str, *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        ...

    def mediawiki_page_url(self, page_title: str, *, series_id: str = "", base_url: str = "") -> str:
        ...
