from __future__ import annotations

from typing import Any, Iterable

from packages.retrieval_runtime.contracts import DocumentRetrievalTool
from saga.contracts.retrieval import BookRetrievalTool
from saga.providers.retrieval_runtime_adapter import create_runtime_retrieval_client
from saga.storage.persistence import SagaRelationalStore
from saga.storage.hybrid_retrieval import RelationalHybridRetrievalService


class RetrievalService:
    """Saga-facing adapter over book-native and portable document retrieval."""

    def __init__(
        self,
        *,
        relational_store: SagaRelationalStore | None = None,
        sqlite_store: SagaRelationalStore | None = None,
        book_retriever: BookRetrievalTool | None = None,
        document_retriever: DocumentRetrievalTool | None = None,
        embedding_model: str = "nomic-embed-text:latest",
        ollama_embed_url: str = "http://localhost:11434/api/embed",
        batch_size: int = 24,
        embedder=None,
    ) -> None:
        self.relational_store = relational_store or sqlite_store or SagaRelationalStore()
        self.book_retriever = book_retriever or self._build_book_retriever(
            embedding_model=embedding_model,
            ollama_embed_url=ollama_embed_url,
            batch_size=batch_size,
            embedder=embedder,
        )
        self.document_retriever = document_retriever or create_runtime_retrieval_client(
            embedding_model=embedding_model,
            ollama_embed_url=ollama_embed_url,
            batch_size=batch_size,
            embedder=embedder,
        )

    def ensure_book_index(self, *, book_id: str, source_types: Iterable[str] | None = None) -> dict[str, Any]:
        return self.book_retriever.ensure_book_index(book_id=book_id, source_types=source_types)

    def query_book(
        self,
        *,
        book_id: str,
        query_text: str,
        top_k: int = 8,
        source_types: Iterable[str] | None = None,
        entity_bias: Iterable[str] | None = None,
        chapter_bias: int | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.book_retriever.query_book(
            book_id=book_id,
            query_text=query_text,
            top_k=top_k,
            source_types=source_types,
            entity_bias=entity_bias,
            chapter_bias=chapter_bias,
            metadata_filters=metadata_filters,
        )

    def ensure_document_index(self, *, series_id: str, scope_key: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        return self.document_retriever.ensure_document_index(series_id=series_id, scope_key=scope_key, documents=documents)

    def query_documents(
        self,
        *,
        index_ref: dict[str, Any],
        query_text: str,
        top_k: int = 6,
        allowed_types: Iterable[str] | None = None,
        character_bias: Iterable[str] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.document_retriever.query_documents(
            index_ref=index_ref,
            query_text=query_text,
            top_k=top_k,
            allowed_types=allowed_types,
            character_bias=character_bias,
            metadata_filters=metadata_filters,
        )

    def _build_book_retriever(self, *, embedding_model: str, ollama_embed_url: str, batch_size: int, embedder):
        return RelationalHybridRetrievalService(
            sqlite_store=self.relational_store,
            embedding_model=embedding_model,
            ollama_embed_url=ollama_embed_url,
            batch_size=batch_size,
            embedder=embedder,
        )
