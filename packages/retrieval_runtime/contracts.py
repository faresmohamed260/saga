"""Portable contracts and payload models for generic retrieval-capable clients."""

from __future__ import annotations

from typing import Any, Iterable, Protocol

from pydantic import AliasChoices, BaseModel, Field
from packages.runtime_common import RuntimeRequestMetadata


class RetrievalDocumentInput(BaseModel):
    document_id: str = Field(min_length=1)
    text: str = ""
    summary: str = ""
    source_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalDocumentMetadata(BaseModel):
    characters: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class RetrievalDocument(BaseModel):
    document_id: str = Field(min_length=1)
    text: str = ""
    summary: str = ""
    source_type: str = ""
    metadata: RetrievalDocumentMetadata = Field(default_factory=RetrievalDocumentMetadata)


class RetrievalIndexRef(BaseModel):
    index_id: str = ""
    series_id: str = Field(min_length=1)
    scope_key: str = Field(min_length=1)
    fingerprint: str = ""
    namespace: str = ""


class RetrievalIndexPayload(BaseModel):
    index_id: str = ""
    series_id: str = Field(min_length=1)
    scope_key: str = Field(min_length=1)
    namespace: str = ""
    embedding_model: str = ""
    fingerprint: str = ""
    documents: list[RetrievalDocument] = Field(default_factory=list)
    vectors: list[list[float]] = Field(default_factory=list)


class RetrievalRequestMetadata(RuntimeRequestMetadata):
    series_id: str = ""
    scope_key: str = ""
    namespace: str = ""
    index_id: str = ""
    fingerprint: str = ""
    document_count: int = 0
    query_text: str = ""
    top_k: int = 0


class RetrievalQueryResult(BaseModel):
    document_id: str = Field(min_length=1)
    source_type: str = ""
    summary: str = ""
    excerpt: str = ""
    metadata: RetrievalDocumentMetadata = Field(default_factory=RetrievalDocumentMetadata)
    score: float = 0.0


class RetrievalIndexToolPayload(BaseModel):
    index_id: str = ""
    series_id: str = ""
    scope_key: str = ""
    document_count: int = 0
    embedding_model: str = ""
    fingerprint: str = ""
    index_ref: RetrievalIndexRef
    request_metadata: RetrievalRequestMetadata = Field(
        default_factory=RetrievalRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class RetrievalQueryToolPayload(BaseModel):
    query_text: str = ""
    result_count: int = 0
    results: list[RetrievalQueryResult] = Field(default_factory=list)
    request_metadata: RetrievalRequestMetadata = Field(
        default_factory=RetrievalRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class DocumentRetrievalTool(Protocol):
    def ensure_document_index(self, *, series_id: str, scope_key: str, documents: list[dict[str, Any]] | list[RetrievalDocumentInput]) -> dict[str, Any]:
        ...

    def query_documents(
        self,
        *,
        index_ref: dict[str, Any] | RetrievalIndexRef,
        query_text: str,
        top_k: int = 6,
        allowed_types: Iterable[str] | None = None,
        character_bias: Iterable[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | list[RetrievalQueryResult]:
        ...
