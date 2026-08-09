"""Standalone retrieval runtime that can be embedded in any project."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any, Callable, Iterable

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    build_retrieval_namespace,
    create_persistence_client,
)
from packages.retrieval_runtime.contracts import (
    RetrievalDocument,
    RetrievalDocumentInput,
    RetrievalDocumentMetadata,
    RetrievalIndexPayload,
    RetrievalIndexRef,
    RetrievalIndexToolPayload,
    RetrievalQueryResult,
    RetrievalQueryToolPayload,
    RetrievalRequestMetadata,
)
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig
from packages.runtime_common import build_structured_runtime_tool, create_trace, current_trace_context


Embedder = Callable[[list[str]], list[list[float]]]


class RetrievalRuntimeClient:
    MODE_DOCUMENT_INDEX = "document_index"

    def __init__(
        self,
        *,
        profile: RetrievalProfile,
        config: RetrievalRuntimeConfig,
        embedder: Embedder | None = None,
        persistence_client=None,
    ) -> None:
        self.profile = profile
        self.config = config
        self.mode = str(profile.mode or self.MODE_DOCUMENT_INDEX).strip().lower() or self.MODE_DOCUMENT_INDEX
        self.embedding_model = str(profile.embedding_model or "").strip() or "nomic-embed-text:latest"
        self.ollama_embed_url = str(profile.ollama_embed_url or "").strip() or "http://localhost:11434/api/embed"
        self.batch_size = max(1, int(profile.batch_size))
        self.vector_namespace_prefix = str(profile.vector_namespace_prefix or "retrieval").strip() or "retrieval"
        self.embedder = embedder
        self.persistence_client = persistence_client or self._build_persistence_client(config)
        self.persistence_client.initialize()
        self._last_request_metadata = RetrievalRequestMetadata()

    def ensure_document_index(
        self,
        *,
        series_id: str,
        scope_key: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started_at_ms = self._begin_request_tracking(operation="ensure_document_index")
        normalized_documents = [RetrievalDocumentInput.model_validate(document) for document in documents]
        fingerprint = self._fingerprint(normalized_documents)
        index_id = self._index_id(series_id=series_id, scope_key=scope_key, fingerprint=fingerprint)
        namespace = self._vector_namespace(series_id=series_id, scope_key=scope_key)
        existing = self._load_index_ref(
            RetrievalIndexRef(
                index_id=index_id,
                series_id=series_id,
                scope_key=scope_key,
                fingerprint=fingerprint,
                namespace=namespace,
            ),
            strict=False,
        )
        if existing and existing.fingerprint == fingerprint and existing.index_id == index_id:
            self._last_request_metadata.series_id = series_id
            self._last_request_metadata.scope_key = scope_key
            self._last_request_metadata.namespace = namespace
            self._last_request_metadata.index_id = index_id
            self._last_request_metadata.fingerprint = fingerprint
            self._last_request_metadata.document_count = len(existing.documents or [])
            self._finalize_request_tracking(status="ok")
            return existing.model_dump()

        vectors = self._embed_texts([document.text for document in normalized_documents])
        stored_documents = [
            self._stored_document_payload(
                document,
                embedding=vector,
                series_id=series_id,
                scope_key=scope_key,
                fingerprint=fingerprint,
                index_id=index_id,
                position=position,
            )
            for position, (document, vector) in enumerate(zip(normalized_documents, vectors))
        ]
        self.persistence_client.vectors.delete_documents(namespace)
        self.persistence_client.vectors.upsert_documents(namespace, stored_documents)
        self._last_request_metadata = RetrievalRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="retrieval_runtime",
            operation="ensure_document_index",
            provider=self.provider_name(),
            series_id=series_id,
            scope_key=scope_key,
            namespace=namespace,
            index_id=index_id,
            fingerprint=fingerprint,
            document_count=len(normalized_documents),
            started_at_ms=started_at_ms,
        )
        self._finalize_request_tracking(status="ok")
        payload = RetrievalIndexPayload(
            index_id=index_id,
            series_id=series_id,
            scope_key=scope_key,
            namespace=namespace,
            embedding_model=self.embedding_model,
            fingerprint=fingerprint,
            documents=[
                RetrievalDocument(
                    document_id=document.document_id,
                    text=document.text,
                    summary=document.summary,
                    source_type=document.source_type,
                    metadata=self._public_metadata(dict(document.metadata or {})),
                )
                for document in normalized_documents
            ],
            vectors=vectors,
        )
        return payload.model_dump()

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
        started_at_ms = self._begin_request_tracking(operation="query_documents")
        index_payload = self._load_index_ref(index_ref)
        documents = list(index_payload.documents or [])
        vectors = list(index_payload.vectors or [])
        self._last_request_metadata = RetrievalRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="retrieval_runtime",
            operation="query_documents",
            provider=self.provider_name(),
            series_id=index_payload.series_id,
            scope_key=index_payload.scope_key,
            namespace=index_payload.namespace,
            index_id=index_payload.index_id,
            fingerprint=index_payload.fingerprint,
            document_count=len(documents),
            query_text=str(query_text or ""),
            top_k=max(1, int(top_k)),
            started_at_ms=started_at_ms,
        )
        if not str(query_text or "").strip() or not documents or not vectors:
            self._finalize_request_tracking(status="ok")
            return []

        query_vector = self._embed_texts([str(query_text or "")])[0]
        query_terms = self._tokenize(query_text)
        allowed = {item for item in (allowed_types or []) if item}
        biased_characters = {str(name).strip().lower() for name in (character_bias or []) if str(name).strip()}
        filters = metadata_filters or {}

        document_frequency = self._document_frequency(documents)
        candidate_rows: list[dict[str, Any]] = []
        for doc, vector in zip(documents, vectors):
            if allowed and str(doc.source_type or "") not in allowed:
                continue
            public_metadata = doc.metadata if isinstance(doc.metadata, RetrievalDocumentMetadata) else RetrievalDocumentMetadata.model_validate(doc.metadata or {})
            public_metadata_dict = self._metadata_for_matching(public_metadata)
            if not self._matches_filters(public_metadata_dict, filters):
                continue
            dense_score = self._cosine_similarity(query_vector, vector)
            lexical_score = self._lexical_score(query_terms, doc.model_dump(), len(documents), document_frequency)
            if not dense_score and not lexical_score:
                continue
            names = {str(name).strip().lower() for name in (public_metadata.characters or []) if str(name).strip()}
            if biased_characters and names:
                overlap = len(names & biased_characters)
                if overlap:
                    dense_score *= 1.0 + min(0.35, 0.12 * overlap)
                    lexical_score *= 1.0 + min(0.35, 0.12 * overlap)
            candidate_rows.append(
                {
                    "document_id": doc.document_id,
                    "source_type": doc.source_type,
                    "summary": doc.summary,
                    "metadata": public_metadata,
                    "dense_score": float(dense_score),
                    "lexical_score": float(lexical_score),
                    "text": doc.text,
                }
            )
        if not candidate_rows:
            self._finalize_request_tracking(status="ok")
            return []

        fused = self._fuse_rankings(candidate_rows)
        reranked = self._rerank_candidates(
            fused[: max(max(1, int(top_k)) * 3, 8)],
            query_terms=query_terms,
            character_bias=biased_characters,
        )
        results = [
            RetrievalQueryResult(
                document_id=row["document_id"],
                source_type=row["source_type"],
                summary=row["summary"],
                excerpt=self._excerpt_text(str(row.get("text") or row.get("summary") or "")),
                metadata=RetrievalDocumentMetadata.model_validate(row["metadata"]),
                score=round(float(row["score"]), 6),
            ).model_dump()
            for row in reranked[: max(1, int(top_k))]
        ]
        self._finalize_request_tracking(status="ok")
        return results

    def provider_name(self) -> str:
        return self.mode

    def last_request_metadata(self) -> dict[str, Any]:
        return self._last_request_metadata.model_dump()

    def as_langgraph_tools(self) -> list[StructuredTool]:
        client = self

        class EnsureDocumentIndexArgs(BaseModel):
            series_id: str = Field(description="Series identifier used as the retrieval namespace.")
            scope_key: str = Field(description="Stable key for the document collection within the series.")
            documents: list[RetrievalDocumentInput] = Field(description="Documents to index. Each item should include text and metadata.")

        class QueryDocumentsArgs(BaseModel):
            index_ref: RetrievalIndexRef = Field(description="Opaque index reference returned by ensure_document_index.")
            query_text: str = Field(description="Natural language search query.")
            top_k: int = Field(default=6, ge=1, description="Maximum number of ranked results to return.")
            allowed_types: list[str] = Field(default_factory=list, description="Optional allowed source types.")
            character_bias: list[str] = Field(default_factory=list, description="Optional character names to bias retrieval toward.")
            metadata_filters: dict[str, Any] = Field(default_factory=dict, description="Optional exact-match metadata filters.")

        def ensure_document_index_tool(series_id: str, scope_key: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
            payload = client.ensure_document_index(series_id=series_id, scope_key=scope_key, documents=documents)
            return RetrievalIndexToolPayload(
                index_id=str(payload.get("index_id") or ""),
                series_id=str(payload.get("series_id") or ""),
                scope_key=str(payload.get("scope_key") or ""),
                document_count=len(payload.get("documents") or []),
                embedding_model=str(payload.get("embedding_model") or ""),
                fingerprint=str(payload.get("fingerprint") or ""),
                index_ref=RetrievalIndexRef(
                    index_id=str(payload.get("index_id") or ""),
                    series_id=str(payload.get("series_id") or ""),
                    scope_key=str(payload.get("scope_key") or ""),
                    fingerprint=str(payload.get("fingerprint") or ""),
                    namespace=str(payload.get("namespace") or ""),
                ),
                request_metadata=RetrievalRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        def query_documents_tool(
            index_ref: dict[str, Any],
            query_text: str,
            top_k: int = 6,
            allowed_types: list[str] | None = None,
            character_bias: list[str] | None = None,
            metadata_filters: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            results = client.query_documents(
                index_ref=index_ref,
                query_text=query_text,
                top_k=top_k,
                allowed_types=allowed_types,
                character_bias=character_bias,
                metadata_filters=metadata_filters,
            )
            return RetrievalQueryToolPayload(
                query_text=query_text,
                result_count=len(results),
                results=[RetrievalQueryResult.model_validate(row) for row in results],
                request_metadata=RetrievalRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        return [
            build_structured_runtime_tool(
                func=ensure_document_index_tool,
                name="retrieval_ensure_document_index",
                description="Create or refresh a portable document index and return the index payload for later queries.",
                args_schema=EnsureDocumentIndexArgs,
                component="retrieval_runtime",
                operation="ensure_document_index",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name},
                response_model=RetrievalIndexToolPayload,
                error_code="retrieval_ensure_document_index_failed",
                error_details=lambda **kwargs: {"series_id": kwargs.get("series_id", ""), "scope_key": kwargs.get("scope_key", "")},
            ),
            build_structured_runtime_tool(
                func=query_documents_tool,
                name="retrieval_query_documents",
                description="Query a portable document index and return ranked retrieval results.",
                args_schema=QueryDocumentsArgs,
                component="retrieval_runtime",
                operation="query_documents",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name},
                response_model=RetrievalQueryToolPayload,
                error_code="retrieval_query_documents_failed",
                error_details=lambda **kwargs: {"query_text": kwargs.get("query_text", ""), "top_k": int(kwargs.get("top_k", 6) or 6)},
            ),
        ]

    def _load_index_ref(self, index_ref: dict[str, Any] | RetrievalIndexRef, *, strict: bool = True) -> RetrievalIndexPayload | None:
        index = RetrievalIndexRef.model_validate(index_ref)
        series_id = index.series_id
        scope_key = index.scope_key
        fingerprint = index.fingerprint
        index_id = index.index_id
        namespace = index.namespace or self._vector_namespace(series_id=series_id, scope_key=scope_key)
        if not series_id or not scope_key:
            raise ValueError("Index reference must include series_id and scope_key.")
        rows = self.persistence_client.vectors.list_documents(namespace, limit=10000)
        if not rows:
            if strict:
                raise FileNotFoundError(f"Retrieval index not found for series='{series_id}' scope='{scope_key}'.")
            return None
        payload = self._index_payload_from_rows(
            series_id=series_id,
            scope_key=scope_key,
            namespace=namespace,
            rows=rows,
        )
        if fingerprint and str(payload.fingerprint or "").strip() != fingerprint:
            if strict:
                raise ValueError("Retrieval index fingerprint mismatch.")
            return None
        if index_id and str(payload.index_id or "").strip() != index_id:
            if strict:
                raise ValueError("Retrieval index id mismatch.")
            return None
        self._last_request_metadata = RetrievalRequestMetadata(
            trace_id=self._last_request_metadata.trace_id,
            run_id=self._last_request_metadata.run_id,
            parent_trace_id=self._last_request_metadata.parent_trace_id,
            component="retrieval_runtime",
            operation="load_index_ref",
            provider=self.provider_name(),
            series_id=series_id,
            scope_key=scope_key,
            namespace=namespace,
            index_id=str(payload.index_id or ""),
            fingerprint=str(payload.fingerprint or ""),
            document_count=len(payload.documents or []),
        )
        return payload

    def _begin_request_tracking(self, *, operation: str) -> int:
        started_at_ms = int(time.time() * 1000)
        trace_context = current_trace_context()
        self._last_request_metadata = RetrievalRequestMetadata(
            trace_id=create_trace(
                component="retrieval_runtime",
                operation=operation,
                provider=self.provider_name(),
                metadata={"profile": self.profile.name},
            ).trace_id,
            run_id=str(trace_context.get("run_id") or "").strip(),
            parent_trace_id=str(trace_context.get("parent_trace_id") or "").strip(),
            component="retrieval_runtime",
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

    def _build_persistence_client(self, config: RetrievalRuntimeConfig):
        profile = config.persistence_profile or PersistenceProfile(
            name="retrieval-runtime",
            provider="supabase",
            mode="supabase_postgres",
            application_name="saga-retrieval-runtime",
        )
        runtime_config = config.persistence_config or PersistenceRuntimeConfig(profile=profile)
        return create_persistence_client(config=runtime_config, profile=profile)

    def _vector_namespace(self, *, series_id: str, scope_key: str) -> str:
        return build_retrieval_namespace(series_id=series_id, scope_key=scope_key, prefix=self.vector_namespace_prefix)

    def _stored_document_payload(
        self,
        document: RetrievalDocumentInput,
        *,
        embedding: list[float],
        series_id: str,
        scope_key: str,
        fingerprint: str,
        index_id: str,
        position: int,
    ) -> dict[str, Any]:
        metadata = dict(document.metadata or {})
        metadata.update(
            {
                "series_id": series_id,
                "source_scope": scope_key,
                "scope_key": scope_key,
                "content_version": fingerprint,
                "index_id": index_id,
                "embedding_model": self.embedding_model,
                "document_position": int(position),
            }
        )
        if document.source_type:
            metadata["source_type"] = str(document.source_type or "")
        return {
            "document_id": str(document.document_id or "").strip(),
            "content": str(document.text or ""),
            "summary": str(document.summary or ""),
            "metadata": metadata,
            "embedding": [float(value) for value in embedding],
        }

    def _index_payload_from_rows(
        self,
        *,
        series_id: str,
        scope_key: str,
        namespace: str,
        rows: list[dict[str, Any]],
    ) -> RetrievalIndexPayload:
        ordered_rows = sorted(rows, key=lambda row: int((row.get("metadata") or {}).get("document_position") or 0))
        first_metadata = dict((ordered_rows[0].get("metadata") or {})) if ordered_rows else {}
        fingerprint = str(first_metadata.get("content_version") or "").strip()
        index_id = str(first_metadata.get("index_id") or "").strip()
        embedding_model = str(first_metadata.get("embedding_model") or self.embedding_model).strip() or self.embedding_model
        documents: list[RetrievalDocument] = []
        vectors: list[list[float]] = []
        for row in ordered_rows:
            metadata = dict(row.get("metadata") or {})
            documents.append(
                RetrievalDocument(
                    document_id=str(row.get("document_id", "")),
                    source_type=str(metadata.pop("source_type", "")),
                    summary=str(row.get("summary", "") or ""),
                    text=str(row.get("content", "") or ""),
                    metadata=self._public_metadata(metadata),
                )
            )
            vectors.append([float(value) for value in (row.get("embedding") or [])])
        return RetrievalIndexPayload(
            index_id=index_id,
            series_id=series_id,
            scope_key=scope_key,
            namespace=namespace,
            embedding_model=embedding_model,
            fingerprint=fingerprint,
            documents=documents,
            vectors=vectors,
        )

    @staticmethod
    def _public_metadata(metadata: dict[str, Any]) -> RetrievalDocumentMetadata:
        cleaned = dict(metadata or {})
        for key in ("series_id", "source_scope", "scope_key", "content_version", "index_id", "embedding_model", "document_position"):
            cleaned.pop(key, None)
        raw_characters = cleaned.pop("characters", [])
        characters = [
            str(value or "").strip()
            for value in (raw_characters if isinstance(raw_characters, list) else [])
            if str(value or "").strip()
        ]
        return RetrievalDocumentMetadata(
            characters=characters,
            attributes=cleaned,
        )

    @staticmethod
    def _metadata_for_matching(metadata: RetrievalDocumentMetadata) -> dict[str, Any]:
        return {
            "characters": list(metadata.characters or []),
            **dict(metadata.attributes or {}),
        }

    def _fingerprint(self, documents: list[RetrievalDocumentInput]) -> str:
        normalized = json.dumps(
            [
                {
                    "document_id": doc.document_id,
                    "source_type": doc.source_type,
                    "summary": doc.summary,
                    "text": doc.text,
                    "metadata": doc.metadata,
                }
                for doc in documents
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _index_id(self, *, series_id: str, scope_key: str, fingerprint: str) -> str:
        raw = f"{self._slug(series_id)}:{self._slug(scope_key)}:{fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.embedder is not None:
            return self.embedder(texts)

        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset: offset + self.batch_size]
            response = requests.post(
                self.ollama_embed_url,
                json={"model": self.embedding_model, "input": batch},
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json() or {}
            embeddings = payload.get("embeddings") or []
            if len(embeddings) != len(batch):
                raise RuntimeError(
                    f"Embedding service returned {len(embeddings)} vectors for batch of {len(batch)} texts."
                )
            vectors.extend([[float(value) for value in vector] for vector in embeddings])
        return vectors

    @staticmethod
    def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            actual = metadata.get(key)
            if expected in (None, "", []):
                continue
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "default"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", str(text or "").lower()) if token]

    def _document_frequency(self, documents: list[RetrievalDocument] | list[dict[str, Any]]) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for doc in documents:
            if isinstance(doc, RetrievalDocument):
                summary = doc.summary
                text = doc.text
            else:
                summary = str(doc.get("summary") or "")
                text = str(doc.get("text") or "")
            terms = set(self._tokenize(f"{summary} {text}"))
            for term in terms:
                frequencies[term] = frequencies.get(term, 0) + 1
        return frequencies

    def _lexical_score(
        self,
        query_terms: list[str],
        doc: dict[str, Any],
        document_count: int,
        document_frequency: dict[str, int],
    ) -> float:
        if not query_terms:
            return 0.0
        doc_terms = self._tokenize(f"{doc.get('summary') or ''} {doc.get('text') or ''}")
        if not doc_terms:
            return 0.0
        doc_length = max(1, len(doc_terms))
        avg_doc_length = max(1.0, float(doc_length))
        term_counts: dict[str, int] = {}
        for term in doc_terms:
            term_counts[term] = term_counts.get(term, 0) + 1
        score = 0.0
        for term in query_terms:
            frequency = term_counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(1.0 + ((document_count - df + 0.5) / (df + 0.5))) if df else math.log(1.0 + document_count)
            numerator = frequency * (1.2 + 1.0)
            denominator = frequency + 1.2 * (1.0 - 0.75 + 0.75 * (doc_length / avg_doc_length))
            score += idf * (numerator / denominator)
        return score

    @staticmethod
    def _fuse_rankings(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dense_order = sorted(candidates, key=lambda item: item["dense_score"], reverse=True)
        lexical_order = sorted(candidates, key=lambda item: item["lexical_score"], reverse=True)
        dense_rank = {row["document_id"]: index + 1 for index, row in enumerate(dense_order)}
        lexical_rank = {row["document_id"]: index + 1 for index, row in enumerate(lexical_order)}
        fused: list[dict[str, Any]] = []
        for row in candidates:
            fused_score = (1.0 / (60 + dense_rank[row["document_id"]])) + (1.0 / (60 + lexical_rank[row["document_id"]]))
            payload = dict(row)
            payload["score"] = fused_score
            fused.append(payload)
        fused.sort(key=lambda item: item["score"], reverse=True)
        return fused

    @staticmethod
    def _excerpt_text(text: str, *, limit: int = 220) -> str:
        collapsed = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[: max(0, limit - 3)].rstrip() + "..."

    def _rerank_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        query_terms: list[str],
        character_bias: set[str],
    ) -> list[dict[str, Any]]:
        reranked: list[dict[str, Any]] = []
        query_term_set = set(query_terms)
        for row in candidates:
            text_terms = set(self._tokenize(f"{row.get('summary') or ''} {row.get('text') or ''}"))
            coverage = (len(query_term_set & text_terms) / max(1, len(query_term_set))) if query_term_set else 0.0
            metadata = row.get("metadata")
            typed_metadata = metadata if isinstance(metadata, RetrievalDocumentMetadata) else RetrievalDocumentMetadata.model_validate(metadata or {})
            names = {str(name).strip().lower() for name in (typed_metadata.characters or []) if str(name).strip()}
            bias_bonus = 0.08 if character_bias and names & character_bias else 0.0
            payload = dict(row)
            payload["score"] = float(row.get("score") or 0.0) + (coverage * 0.2) + bias_bonus
            reranked.append(payload)
        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked
