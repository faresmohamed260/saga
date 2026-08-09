from __future__ import annotations

from typing import Any

from packages.web_search_runtime.contracts import WebSearchClient
from saga.providers.web_search_runtime_adapter import create_runtime_web_search_client, resolve_mediawiki_base_url


class WebSearchService:
    """Thin saga-facing adapter over the portable web-search runtime."""

    def __init__(self, web_client: WebSearchClient | None = None) -> None:
        self.web = web_client or create_runtime_web_search_client()

    def search(self, query: str, *, max_results: int = 8, site: str = "") -> dict[str, Any]:
        results = self.web.search(query, max_results=max_results, site=site)
        return {
            "provider": self.web.provider_name(),
            "query": query,
            "site": site,
            "results": [
                {
                    "title": row.title,
                    "url": row.url,
                    "snippet": row.snippet,
                    "source": row.source,
                    "rank": row.rank,
                    "metadata": row.metadata,
                }
                for row in results
            ],
            "metadata": self.web.last_request_metadata(),
        }

    def fetch_document(self, url: str) -> dict[str, Any]:
        document = self.web.fetch_document(url)
        return {
            "url": document.url,
            "title": document.title,
            "text": document.text,
            "html": document.html,
            "metadata": document.metadata,
        }

    def resolve_mediawiki_base_url(self, *, series_id: str = "", base_url: str = "") -> str:
        return resolve_mediawiki_base_url(series_id, fallback=base_url)

    def search_mediawiki(self, query: str, *, series_id: str = "", base_url: str = "", max_results: int = 5) -> dict[str, Any]:
        resolved_base_url = self.resolve_mediawiki_base_url(series_id=series_id, base_url=base_url)
        results = self.web.mediawiki_search(resolved_base_url, query, max_results=max_results)
        return {
            "provider": self.web.provider_name(),
            "series_id": series_id,
            "base_url": resolved_base_url,
            "query": query,
            "results": [
                {
                    "title": row.title,
                    "url": row.url,
                    "snippet": row.snippet,
                    "source": row.source,
                    "rank": row.rank,
                    "metadata": row.metadata,
                }
                for row in results
            ],
            "metadata": self.web.last_request_metadata(),
        }

    def mediawiki_get(self, params: dict[str, Any], *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        resolved_base_url = self.resolve_mediawiki_base_url(series_id=series_id, base_url=base_url)
        payload = self.web.mediawiki_get(resolved_base_url, params)
        return {
            "provider": self.web.provider_name(),
            "series_id": series_id,
            "base_url": resolved_base_url,
            "params": dict(params or {}),
            "payload": payload,
            "metadata": self.web.last_request_metadata(),
        }

    def mediawiki_page_categories(self, page_title: str, *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        resolved_base_url = self.resolve_mediawiki_base_url(series_id=series_id, base_url=base_url)
        categories = self.web.mediawiki_page_categories(resolved_base_url, page_title)
        return {
            "provider": self.web.provider_name(),
            "series_id": series_id,
            "base_url": resolved_base_url,
            "page_title": page_title,
            "categories": categories,
            "metadata": self.web.last_request_metadata(),
        }

    def mediawiki_parse_html(self, page_title: str, *, series_id: str = "", base_url: str = "") -> dict[str, Any]:
        resolved_base_url = self.resolve_mediawiki_base_url(series_id=series_id, base_url=base_url)
        html = self.web.mediawiki_parse_html(resolved_base_url, page_title)
        return {
            "provider": self.web.provider_name(),
            "series_id": series_id,
            "base_url": resolved_base_url,
            "page_title": page_title,
            "html": html,
            "metadata": self.web.last_request_metadata(),
        }

    def mediawiki_page_url(self, page_title: str, *, series_id: str = "", base_url: str = "") -> str:
        resolved_base_url = self.resolve_mediawiki_base_url(series_id=series_id, base_url=base_url)
        return self.web.mediawiki_page_url(resolved_base_url, page_title)
