"""Portable contracts and payload models for web-search capable clients."""

from __future__ import annotations

from typing import Any, Protocol
from pydantic import AliasChoices, BaseModel, Field
from packages.runtime_common import RuntimeRequestMetadata


class WebSearchResultMetadata(BaseModel):
    page_title: str = ""
    page_id: int = 0
    source_type: str = ""


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    rank: int = 0
    metadata: WebSearchResultMetadata = Field(default_factory=WebSearchResultMetadata)


class WebEvidenceSentence(BaseModel):
    text: str
    score: float = 0.0
    source: str = ""


class WebDocumentMetadata(BaseModel):
    status_code: int = 0
    source_type: str = ""
    page_title: str = ""
    page_id: int = 0
    categories: list[str] = Field(default_factory=list)


class WebDocument(BaseModel):
    url: str
    title: str = ""
    summary: str = ""
    excerpt: str = ""
    focus_text: str = ""
    query: str = ""
    evidence_sentences: list[WebEvidenceSentence] = Field(default_factory=list)
    text: str = ""
    html: str = ""
    metadata: WebDocumentMetadata = Field(default_factory=WebDocumentMetadata)


class WebSearchRequestMetadata(RuntimeRequestMetadata):
    query: str = ""
    site: str = ""
    url: str = ""
    base_url: str = ""
    api_url: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    status_code: int = 0
    content_length: int = 0
    result_count: int = 0


class WebSearchResultsPayload(BaseModel):
    query: str = ""
    site: str = ""
    result_count: int = 0
    results: list[SearchResult] = Field(default_factory=list)
    request_metadata: WebSearchRequestMetadata = Field(
        default_factory=WebSearchRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class WebDocumentPayload(BaseModel):
    url: str
    title: str = ""
    summary: str = ""
    excerpt: str = ""
    focus_text: str = ""
    query: str = ""
    evidence_sentences: list[WebEvidenceSentence] = Field(default_factory=list)
    text: str = ""
    html: str = ""
    metadata: WebDocumentMetadata = Field(default_factory=WebDocumentMetadata)
    request_metadata: WebSearchRequestMetadata = Field(default_factory=WebSearchRequestMetadata)


class MediaWikiSearchPayload(BaseModel):
    base_url: str
    query: str
    result_count: int = 0
    results: list[SearchResult] = Field(default_factory=list)
    request_metadata: WebSearchRequestMetadata = Field(
        default_factory=WebSearchRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class WebSearchClient(Protocol):
    mode: str

    def search(self, query: str, *, max_results: int = 8, site: str = "") -> list[SearchResult]:
        ...

    def fetch_document(self, url: str) -> WebDocument:
        ...

    def mediawiki_search(self, base_url: str, query: str, *, max_results: int = 5) -> list[SearchResult]:
        ...

    def mediawiki_get(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        ...

    def mediawiki_page_categories(self, base_url: str, page_title: str) -> list[str]:
        ...

    def mediawiki_parse_html(self, base_url: str, page_title: str) -> str:
        ...

    def provider_name(self) -> str:
        ...

    def last_request_metadata(self) -> dict[str, Any]:
        ...
