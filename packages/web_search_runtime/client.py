"""Standalone web-search runtime that can be embedded in any project."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from packages.web_search_runtime.contracts import (
    MediaWikiSearchPayload,
    SearchResult,
    WebDocument,
    WebDocumentMetadata,
    WebEvidenceSentence,
    WebDocumentPayload,
    WebSearchResultMetadata,
    WebSearchRequestMetadata,
    WebSearchResultsPayload,
)
from packages.web_search_runtime.models import WebSearchProfile, WebSearchRuntimeConfig
from packages.runtime_common import build_structured_runtime_tool, create_trace, current_trace_context
import time


class WebSearchRuntimeClient:
    MODE_DUCKDUCKGO = "duckduckgo"

    def __init__(self, *, profile: WebSearchProfile, config: WebSearchRuntimeConfig) -> None:
        self.profile = profile
        self.config = config
        self.mode = str(profile.mode or self.MODE_DUCKDUCKGO).strip().lower() or self.MODE_DUCKDUCKGO
        self.timeout = max(5, int(profile.timeout_seconds))
        self.default_max_results = max(1, int(profile.max_results))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": str(profile.user_agent or "").strip()})
        self._last_request_metadata = WebSearchRequestMetadata()

    def search(self, query: str, *, max_results: int = 8, site: str = "") -> list[SearchResult]:
        if self.mode != self.MODE_DUCKDUCKGO:
            raise ValueError(f"Unsupported web-search mode '{self.mode}'.")
        return self._duckduckgo_search(query, max_results=max_results, site=site)

    def fetch_document(self, url: str, *, query: str = "") -> WebDocument:
        started_at_ms = self._begin_request_tracking(operation="fetch_document")
        mediawiki_document = self._mediawiki_document_from_url(url, query=query)
        if mediawiki_document is not None:
            self._last_request_metadata = WebSearchRequestMetadata(
                trace_id=self._last_request_metadata.trace_id,
                run_id=self._last_request_metadata.run_id,
                parent_trace_id=self._last_request_metadata.parent_trace_id,
                component="web_search_runtime",
                operation="fetch_document",
                provider=self.provider_name(),
                url=url,
                query=str(query or "").strip(),
                status_code=200,
                content_length=len(str(mediawiki_document.text or "")),
                started_at_ms=started_at_ms,
            )
            self._finalize_request_tracking(status="ok")
            return mediawiki_document
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        html = response.text or ""
        title, text, summary, excerpt, focus_text, evidence_sentences = self._extract_document_fields(html, url=url, query=query)
        self._last_request_metadata = WebSearchRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="web_search_runtime",
            operation="fetch_document",
            provider=self.provider_name(),
            url=url,
            query=str(query or "").strip(),
            status_code=int(response.status_code or 0),
            content_length=len(html),
            started_at_ms=started_at_ms,
        )
        self._finalize_request_tracking(status="ok")
        return WebDocument(
            url=url,
            title=title,
            summary=summary,
            excerpt=excerpt,
            focus_text=focus_text,
            query=str(query or "").strip(),
            evidence_sentences=evidence_sentences,
            text=text,
            html=html,
            metadata=WebDocumentMetadata(status_code=int(response.status_code or 0)),
        )

    def mediawiki_search(self, base_url: str, query: str, *, max_results: int = 5) -> list[SearchResult]:
        payload = self.mediawiki_get(
            base_url,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max(1, int(max_results)),
                "format": "json",
            },
        )
        rows = ((payload.get("query") or {}).get("search") or []) if isinstance(payload, dict) else []
        results: list[SearchResult] = []
        for index, row in enumerate(rows, start=1):
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            snippet = BeautifulSoup(str(row.get("snippet") or ""), "html.parser").get_text(" ", strip=True)
            results.append(
                SearchResult(
                    title=title,
                    url=self.mediawiki_page_url(base_url, title),
                    snippet=snippet,
                    source=self._host_label(base_url),
                    rank=index,
                    metadata=WebSearchResultMetadata(
                        page_title=title.replace(" ", "_"),
                        page_id=int(row.get("pageid") or 0),
                        source_type="mediawiki",
                    ),
                )
            )
        return results

    def mediawiki_get(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        started_at_ms = self._begin_request_tracking(operation="mediawiki_get")
        api_url = self._mediawiki_api_url(base_url)
        response = self.session.get(api_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json() or {}
        self._last_request_metadata = WebSearchRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="web_search_runtime",
            operation="mediawiki_get",
            provider=self.provider_name(),
            base_url=base_url,
            api_url=api_url,
            params=dict(params or {}),
            status_code=int(response.status_code or 0),
            started_at_ms=started_at_ms,
        )
        self._finalize_request_tracking(status="ok")
        return payload

    def mediawiki_page_categories(self, base_url: str, page_title: str) -> list[str]:
        payload = self.mediawiki_get(
            base_url,
            {
                "action": "query",
                "prop": "categories",
                "titles": page_title,
                "cllimit": "max",
                "redirects": 1,
                "format": "json",
            },
        )
        categories: list[str] = []
        pages = (((payload or {}).get("query") or {}).get("pages") or {}).values()
        for page in pages:
            for category in (page.get("categories") or []):
                title_text = str(category.get("title") or "").strip()
                if title_text.lower().startswith("category:"):
                    title_text = title_text.split(":", 1)[1]
                lowered = title_text.lower()
                if lowered.startswith("articles with ") or lowered.startswith("articles needing ") or lowered.startswith("articles to be "):
                    continue
                if title_text:
                    categories.append(title_text)
        return categories

    def mediawiki_parse_html(self, base_url: str, page_title: str) -> str:
        payload = self.mediawiki_get(
            base_url,
            {
                "action": "parse",
                "page": page_title,
                "prop": "text",
                "format": "json",
                "formatversion": "2",
            },
        )
        return str(((payload.get("parse") or {}).get("text")) or "") if isinstance(payload, dict) else ""

    def mediawiki_fetch_document(self, base_url: str, page_title: str, *, query: str = "") -> WebDocument:
        payload = self.mediawiki_get(
            base_url,
            {
                "action": "query",
                "prop": "extracts|categories",
                "titles": page_title,
                "redirects": 1,
                "exintro": 1,
                "explaintext": 1,
                "exsectionformat": "plain",
                "cllimit": "max",
                "format": "json",
            },
        )
        pages = (((payload or {}).get("query") or {}).get("pages") or {}) if isinstance(payload, dict) else {}
        page = next(iter(pages.values()), {}) if pages else {}
        resolved_title = str(page.get("title") or page_title or "").strip()
        text = str(page.get("extract") or "").strip()
        if not text:
            html = self.mediawiki_parse_html(base_url, resolved_title or page_title)
            title, parsed_text, summary, excerpt, focus_text, evidence_sentences = self._extract_document_fields(
                html,
                url=self.mediawiki_page_url(base_url, resolved_title or page_title),
                query=query,
            )
            categories = self.mediawiki_page_categories(base_url, resolved_title or page_title)
            return WebDocument(
                url=self.mediawiki_page_url(base_url, resolved_title or page_title),
                title=title or resolved_title,
                summary=summary,
                excerpt=excerpt,
                focus_text=focus_text,
                query=str(query or "").strip(),
                evidence_sentences=evidence_sentences,
                text=parsed_text,
                html=html,
                metadata=WebDocumentMetadata(
                    page_title=resolved_title.replace(" ", "_"),
                    page_id=int(page.get("pageid") or 0),
                    categories=categories,
                    source_type="mediawiki",
                ),
            )
        categories = []
        for category in (page.get("categories") or []):
            title_text = str(category.get("title") or "").strip()
            if title_text.lower().startswith("category:"):
                title_text = title_text.split(":", 1)[1]
            if title_text:
                categories.append(title_text)
        summary, excerpt, focus_text, evidence_sentences = self._document_evidence(text, query=query)
        return WebDocument(
            url=self.mediawiki_page_url(base_url, resolved_title or page_title),
            title=resolved_title or page_title,
            summary=summary,
            excerpt=excerpt,
            focus_text=focus_text,
            query=str(query or "").strip(),
            evidence_sentences=evidence_sentences,
            text=text,
            html="",
            metadata=WebDocumentMetadata(
                page_title=(resolved_title or page_title).replace(" ", "_"),
                page_id=int(page.get("pageid") or 0),
                categories=categories,
                source_type="mediawiki",
            ),
        )

    def mediawiki_page_url(self, base_url: str, page_title: str) -> str:
        safe_title = str(page_title or "").replace(" ", "_")
        return f"{base_url.rstrip('/')}/wiki/{quote(safe_title, safe='_')}"

    def provider_name(self) -> str:
        return self.mode

    def last_request_metadata(self) -> dict[str, Any]:
        return self._last_request_metadata.model_dump()

    def as_langgraph_tools(self) -> list[StructuredTool]:
        client = self

        class SearchArgs(BaseModel):
            query: str = Field(description="Natural language search query.")
            max_results: int = Field(default=8, ge=1, description="Maximum number of results to return.")
            site: str = Field(default="", description="Optional site/domain restriction.")

        class FetchDocumentArgs(BaseModel):
            url: str = Field(description="Document URL to fetch and extract.")
            query: str = Field(default="", description="Optional query used to rank the most relevant evidence sentence.")

        class MediaWikiSearchArgs(BaseModel):
            base_url: str = Field(description="MediaWiki base URL, for example a fandom wiki root.")
            query: str = Field(description="Search query to run against the MediaWiki site.")
            max_results: int = Field(default=5, ge=1, description="Maximum number of page hits to return.")

        def search_tool(query: str, max_results: int = 8, site: str = "") -> dict[str, Any]:
            results = client.search(query, max_results=max_results, site=site)
            return WebSearchResultsPayload(
                query=query,
                site=site,
                result_count=len(results),
                results=[SearchResult.model_validate(row.model_dump()) for row in results],
                request_metadata=WebSearchRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        def fetch_document_tool(url: str, query: str = "") -> dict[str, Any]:
            document = client.fetch_document(url, query=query)
            return WebDocumentPayload(
                url=document.url,
                title=document.title,
                summary=document.summary,
                excerpt=document.excerpt,
                focus_text=document.focus_text,
                query=document.query,
                evidence_sentences=[WebEvidenceSentence.model_validate(item.model_dump()) for item in document.evidence_sentences],
                text=document.text,
                html=document.html,
                metadata=document.metadata,
                request_metadata=WebSearchRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        def mediawiki_search_tool(base_url: str, query: str, max_results: int = 5) -> dict[str, Any]:
            results = client.mediawiki_search(base_url, query, max_results=max_results)
            return MediaWikiSearchPayload(
                base_url=base_url,
                query=query,
                result_count=len(results),
                results=[SearchResult.model_validate(row.model_dump()) for row in results],
                request_metadata=WebSearchRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        return [
            build_structured_runtime_tool(
                func=search_tool,
                name="web_search_search",
                description="Run a web search and return ranked results with title, URL, and snippet.",
                args_schema=SearchArgs,
                component="web_search_runtime",
                operation="search",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name},
                response_model=WebSearchResultsPayload,
                error_code="web_search_failed",
                error_details=lambda **kwargs: {"query": kwargs.get("query", ""), "site": kwargs.get("site", "")},
            ),
            build_structured_runtime_tool(
                func=fetch_document_tool,
                name="web_search_fetch_document",
                description="Fetch a web document and return extracted text plus raw HTML.",
                args_schema=FetchDocumentArgs,
                component="web_search_runtime",
                operation="fetch_document",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name},
                response_model=WebDocumentPayload,
                error_code="web_fetch_document_failed",
                error_details=lambda **kwargs: {"url": kwargs.get("url", ""), "query": kwargs.get("query", "")},
            ),
            build_structured_runtime_tool(
                func=mediawiki_search_tool,
                name="web_search_mediawiki_search",
                description="Search a MediaWiki-compatible site such as a fandom wiki.",
                args_schema=MediaWikiSearchArgs,
                component="web_search_runtime",
                operation="mediawiki_search",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name},
                response_model=MediaWikiSearchPayload,
                error_code="web_mediawiki_search_failed",
                error_details=lambda **kwargs: {"query": kwargs.get("query", ""), "base_url": kwargs.get("base_url", "")},
            ),
        ]

    def _duckduckgo_search(self, query: str, *, max_results: int, site: str) -> list[SearchResult]:
        started_at_ms = self._begin_request_tracking(operation="search")
        effective_query = str(query or "").strip()
        if site:
            effective_query = f"site:{site.strip()} {effective_query}".strip()
        response = self.session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": effective_query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text or "", "html.parser")
        results: list[SearchResult] = []
        limit = max(1, int(max_results or self.default_max_results))
        for index, node in enumerate(soup.select(".result"), start=1):
            link = node.select_one(".result__title a") or node.select_one("a.result__a")
            if link is None:
                continue
            title = link.get_text(" ", strip=True)
            url = str(link.get("href") or "").strip()
            if not title or not url:
                continue
            snippet_node = node.select_one(".result__snippet")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            results.append(
                SearchResult(
                    title=title,
                    url=self._normalize_duckduckgo_result_url(urljoin("https://duckduckgo.com", url)),
                    snippet=snippet,
                    source="duckduckgo",
                    rank=index,
                )
            )
            if len(results) >= limit:
                break
        self._last_request_metadata = WebSearchRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="web_search_runtime",
            operation="search",
            provider=self.MODE_DUCKDUCKGO,
            query=effective_query,
            site=site,
            status_code=int(response.status_code or 0),
            result_count=len(results),
            started_at_ms=started_at_ms,
        )
        self._finalize_request_tracking(status="ok")
        return results

    def _begin_request_tracking(self, *, operation: str) -> int:
        started_at_ms = int(time.time() * 1000)
        trace_context = current_trace_context()
        self._last_request_metadata = WebSearchRequestMetadata(
            trace_id=create_trace(
                component="web_search_runtime",
                operation=operation,
                provider=self.provider_name(),
                metadata={"profile": self.profile.name},
            ).trace_id,
            run_id=str(trace_context.get("run_id") or "").strip(),
            parent_trace_id=str(trace_context.get("parent_trace_id") or "").strip(),
            component="web_search_runtime",
            operation=operation,
            provider=self.provider_name(),
            started_at_ms=started_at_ms,
            status="started",
        )
        return started_at_ms

    def _finalize_request_tracking(self, *, status: str) -> None:
        completed_at_ms = int(time.time() * 1000)
        self._last_request_metadata.provider = self.provider_name()
        self._last_request_metadata.completed_at_ms = completed_at_ms
        self._last_request_metadata.latency_ms = max(0, completed_at_ms - int(self._last_request_metadata.started_at_ms or completed_at_ms))
        self._last_request_metadata.status = str(status or "ok")

    def _extract_document_fields(self, html: str, *, url: str, query: str = "") -> tuple[str, str, str, str, str, list[WebEvidenceSentence]]:
        title = ""
        soup = BeautifulSoup(html, "html.parser")
        if soup.title:
            title = soup.title.get_text(" ", strip=True)
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_formatting=False,
            url=url,
            favor_recall=True,
            deduplicate=True,
        )
        if extracted:
            text = extracted.strip()
            summary, excerpt, focus_text, evidence_sentences = self._document_evidence(text, query=query)
            return title, text, summary, excerpt, focus_text, evidence_sentences
        text = soup.get_text("\n", strip=True)
        text = text.strip()
        summary, excerpt, focus_text, evidence_sentences = self._document_evidence(text, query=query)
        return title, text, summary, excerpt, focus_text, evidence_sentences

    def _document_evidence(self, text: str, *, query: str = "") -> tuple[str, str, str, list[WebEvidenceSentence]]:
        sentences = self._meaningful_sentences(text)
        if not sentences:
            return "", "", "", []
        ranked = self._rank_evidence_sentences(sentences, query=query)
        focus_text = ranked[0].text if ranked else ""
        if str(query or "").strip():
            summary = " ".join(item.text for item in ranked[:2]).strip()
            excerpt = focus_text
        else:
            summary = " ".join(item.text for item in ranked[:2]).strip()
            excerpt = self._build_excerpt_from_ranked(ranked)
        return summary, excerpt, focus_text, ranked[:5]

    def _mediawiki_document_from_url(self, url: str, *, query: str = "") -> WebDocument | None:
        parsed = urlparse(str(url or "").strip())
        path = str(parsed.path or "").strip()
        wiki_index = path.find("/wiki/")
        if not parsed.scheme or not parsed.netloc or wiki_index < 0:
            return None
        page_title = unquote(path[wiki_index + len("/wiki/"):]).replace("_", " ").strip()
        if not page_title:
            return None
        prefix = path[:wiki_index]
        base_url = f"{parsed.scheme}://{parsed.netloc}{prefix}".rstrip("/")
        try:
            return self.mediawiki_fetch_document(base_url or f"{parsed.scheme}://{parsed.netloc}", page_title, query=query)
        except Exception:
            return None

    @staticmethod
    def _normalize_terms(text: str) -> list[str]:
        return [
            token
            for token in "".join(ch.lower() if ch.isalnum() else " " for ch in str(text or "")).split()
            if token
        ]

    @staticmethod
    def _document_summary(text: str, *, max_sentences: int = 2) -> str:
        sentences = WebSearchRuntimeClient._meaningful_sentences(text)
        if not sentences:
            return ""
        return " ".join(sentences[:max(1, int(max_sentences))]).strip()

    @staticmethod
    def _document_excerpt(text: str, *, max_chars: int = 320) -> str:
        sentences = WebSearchRuntimeClient._meaningful_sentences(text)
        if not sentences:
            return ""
        excerpt = ""
        for sentence in sentences:
            candidate = f"{excerpt} {sentence}".strip() if excerpt else sentence
            if len(candidate) > max(80, int(max_chars)):
                break
            excerpt = candidate
        return (excerpt or sentences[0]).strip()

    @staticmethod
    def _build_excerpt_from_ranked(ranked: list[WebEvidenceSentence], *, max_chars: int = 320) -> str:
        if not ranked:
            return ""
        excerpt = ""
        for item in ranked:
            candidate = f"{excerpt} {item.text}".strip() if excerpt else item.text
            if len(candidate) > max(80, int(max_chars)):
                break
            excerpt = candidate
        return (excerpt or ranked[0].text).strip()

    @staticmethod
    def _meaningful_sentences(text: str) -> list[str]:
        normalized = str(text or "").replace("\r", "\n")
        normalized = normalized.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n")
        candidates = [
            line.strip()
            for line in normalized.split("\n")
            if line.strip()
        ]
        sentences: list[str] = []
        for line in candidates:
            lowered = line.lower()
            if line.startswith("|") or "|---" in line:
                continue
            if lowered in {"contents", "references", "external links", "see also", "bibliography"}:
                continue
            if len(line) < 24:
                continue
            if line.count("|") >= 2:
                continue
            sentences.append(" ".join(line.split()))
        return sentences

    @staticmethod
    def _rank_evidence_sentences(sentences: list[str], *, query: str = "") -> list[WebEvidenceSentence]:
        query_terms = set(WebSearchRuntimeClient._normalize_terms(query))
        query_lower = str(query or "").lower()
        ranked: list[WebEvidenceSentence] = []
        for sentence in sentences:
            terms = set(WebSearchRuntimeClient._normalize_terms(sentence))
            overlap = len(query_terms & terms) / max(1, len(query_terms)) if query_terms else 0.0
            lowered = sentence.lower()
            creator_bonus = 0.45 if any(token in lowered for token in ("created by", "creator", "creates", "created")) else 0.0
            identity_bonus = 0.15 if any(token in lowered for token in ("is a", "is an", "was a", "was an")) else 0.0
            brevity_bonus = 0.1 if len(sentence) <= 220 else 0.0
            penalty = min(0.2, max(0, len(sentence) - 320) / 1000.0)
            creator_question_penalty = 0.2 if any(token in query_lower for token in ("who created", "creator", "who makes", "who made")) and "fictional character" in lowered else 0.0
            score = overlap + creator_bonus + identity_bonus + brevity_bonus - penalty - creator_question_penalty
            ranked.append(WebEvidenceSentence(text=sentence, score=score, source="document_text"))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    @staticmethod
    def _mediawiki_api_url(base_url: str) -> str:
        normalized = str(base_url or "").strip().rstrip("/")
        parsed = urlparse(normalized)
        path = str(parsed.path or "").rstrip("/")
        origin = f"{parsed.scheme}://{parsed.netloc}".rstrip(":/")
        if path.endswith("/w"):
            return f"{normalized}/api.php"
        wiki_index = path.find("/wiki")
        if wiki_index >= 0:
            prefix = path[:wiki_index]
            return f"{origin}{prefix}/w/api.php"
        if parsed.netloc.endswith("wikipedia.org"):
            return f"{origin}/w/api.php"
        return f"{normalized}/api.php"

    @staticmethod
    def _host_label(base_url: str) -> str:
        normalized = str(base_url or "").replace("https://", "").replace("http://", "").strip("/")
        return normalized or "mediawiki"

    @staticmethod
    def _normalize_duckduckgo_result_url(url: str) -> str:
        parsed = urlparse(str(url or "").strip())
        if parsed.netloc != "duckduckgo.com" or not parsed.path.startswith("/l/"):
            return url
        target = parse_qs(parsed.query).get("uddg") or []
        if not target:
            return url
        return unquote(str(target[0] or "").strip()) or url
