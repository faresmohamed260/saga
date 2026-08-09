"""Compatibility wrapper over the portable retrieval runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from saga.providers.retrieval_runtime_adapter import create_runtime_retrieval_client


class HybridEmbeddingIndexService:
    """Build and query a small persisted local embedding index."""

    def __init__(
        self,
        *,
        base_dir: str | Path = "analysis_outputs/vector_indices",
        embedding_model: str = "nomic-embed-text:latest",
        ollama_embed_url: str = "http://localhost:11434/api/embed",
        batch_size: int = 24,
        embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.embedding_model = embedding_model
        self.ollama_embed_url = ollama_embed_url
        self.batch_size = max(1, int(batch_size))
        self.embedder = embedder
        self.runtime = create_runtime_retrieval_client(
            base_dir=str(self.base_dir),
            embedding_model=self.embedding_model,
            ollama_embed_url=self.ollama_embed_url,
            batch_size=self.batch_size,
            embedder=self.embedder,
        )

    def ensure_index(
        self,
        *,
        series_id: str,
        scope_key: str,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self.ensure_document_index(series_id=series_id, scope_key=scope_key, documents=documents)

    def ensure_document_index(
        self,
        *,
        series_id: str,
        scope_key: str,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self.runtime.ensure_document_index(series_id=series_id, scope_key=scope_key, documents=documents)

    def query(
        self,
        *,
        index_ref: Dict[str, Any],
        query_text: str,
        top_k: int = 6,
        allowed_types: Optional[Iterable[str]] = None,
        character_bias: Optional[Iterable[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.query_documents(
            index_ref=index_ref,
            query_text=query_text,
            top_k=top_k,
            allowed_types=allowed_types,
            character_bias=character_bias,
            metadata_filters=metadata_filters,
        )

    def query_documents(
        self,
        *,
        index_ref: Dict[str, Any],
        query_text: str,
        top_k: int = 6,
        allowed_types: Optional[Iterable[str]] = None,
        character_bias: Optional[Iterable[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.runtime.query_documents(
            index_ref=index_ref,
            query_text=query_text,
            top_k=top_k,
            allowed_types=allowed_types,
            character_bias=character_bias,
            metadata_filters=metadata_filters,
        )
