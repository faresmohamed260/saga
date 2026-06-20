from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from typing import Any, Callable, Iterable

import requests
from sqlalchemy import select

from saga.storage.models import Event, Scene, SemanticDocumentEmbedding
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


Embedder = Callable[[list[str]], list[list[float]]]


class SQLiteHybridRetrievalService:
    """
    Drop-in retrieval backend with the same public shape as SQLiteSemanticRetrievalService.

    It keeps the same SQLite embedding index, then combines:
    - dense cosine retrieval
    - lightweight BM25-style lexical retrieval
    - reciprocal-rank fusion
    """

    SUPPORTED_SOURCE_TYPES = ("scene", "event")

    def __init__(
        self,
        *,
        sqlite_store: SagaSQLiteStore | None = None,
        embedding_model: str = "nomic-embed-text:latest",
        ollama_embed_url: str = "http://localhost:11434/api/embed",
        batch_size: int = 24,
        embedder: Embedder | None = None,
        rrf_k: int = 60,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        reranker_top_n: int = 24,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.embedding_model = embedding_model
        self.ollama_embed_url = ollama_embed_url
        self.batch_size = max(1, int(batch_size))
        self.embedder = embedder
        self.rrf_k = max(1, int(rrf_k))
        self.reranker_model = reranker_model
        self.reranker_top_n = max(1, int(reranker_top_n))
        self._reranker = None
        self._reranker_unavailable = False
        self.last_debug: dict[str, Any] = {}

    def ensure_book_index(
        self,
        *,
        book_id: str,
        source_types: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        requested_types = [
            source_type
            for source_type in (source_types or self.SUPPORTED_SOURCE_TYPES)
            if str(source_type).strip().lower() in self.SUPPORTED_SOURCE_TYPES
        ]
        documents = self._collect_documents(book_id=book_id, source_types=requested_types)
        created = 0
        updated = 0
        removed = 0
        with self.sqlite_store.session_factory() as session:
            existing_rows = session.execute(
                select(SemanticDocumentEmbedding).where(
                    SemanticDocumentEmbedding.book_id == book_id,
                    SemanticDocumentEmbedding.embedding_model == self.embedding_model,
                )
            ).scalars().all()
            existing_map = {(row.source_type, row.source_id): row for row in existing_rows}
            seen_keys: set[tuple[str, str]] = set()
            to_embed: list[dict[str, Any]] = []
            for document in documents:
                key = (document["source_type"], document["source_id"])
                seen_keys.add(key)
                row = existing_map.get(key)
                if row is None or str(row.content_hash or "") != document["content_hash"]:
                    to_embed.append(document)
            if to_embed:
                vectors = self._embed_texts([doc["content_text"] for doc in to_embed])
                for document, vector in zip(to_embed, vectors):
                    key = (document["source_type"], document["source_id"])
                    row = existing_map.get(key)
                    if row is None:
                        row = SemanticDocumentEmbedding(
                            book_id=book_id,
                            source_type=document["source_type"],
                            source_id=document["source_id"],
                            embedding_model=self.embedding_model,
                        )
                        session.add(row)
                        created += 1
                    else:
                        updated += 1
                    row.chapter_index = document.get("chapter_index")
                    row.scene_index = document.get("scene_index")
                    row.summary = document.get("summary")
                    row.content_text = document["content_text"]
                    row.content_hash = document["content_hash"]
                    row.embedding_json = vector
                    row.metadata_json = document.get("metadata_json") or {}
            stale_rows = [row for key, row in existing_map.items() if key not in seen_keys]
            for stale_row in stale_rows:
                session.delete(stale_row)
            removed = len(stale_rows)
            session.commit()
        LOGGER.info(
            "SQLite hybrid retrieval index ready | book=%s model=%s docs=%s created=%s updated=%s removed=%s",
            book_id,
            self.embedding_model,
            len(documents),
            created,
            updated,
            removed,
        )
        return {
            "book_id": book_id,
            "embedding_model": self.embedding_model,
            "document_count": len(documents),
            "created": created,
            "updated": updated,
            "removed": removed,
        }

    def query(
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
        text = str(query_text or "").strip()
        if not text:
            return []
        requested_types = {
            str(source_type).strip().lower()
            for source_type in (source_types or self.SUPPORTED_SOURCE_TYPES)
            if str(source_type).strip().lower() in self.SUPPORTED_SOURCE_TYPES
        }
        filters = metadata_filters or {}
        entity_bias_keys = {
            self._normalize_text(item)
            for item in (entity_bias or [])
            if self._normalize_text(item)
        }
        planned_queries = self._plan_queries(query_text=text, entity_bias=entity_bias)
        query_vectors = self._embed_texts(planned_queries)
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(SemanticDocumentEmbedding).where(
                    SemanticDocumentEmbedding.book_id == book_id,
                    SemanticDocumentEmbedding.embedding_model == self.embedding_model,
                )
            ).scalars().all()

        candidates: list[dict[str, Any]] = []
        for row in rows:
            if requested_types and str(row.source_type or "").lower() not in requested_types:
                continue
            metadata = dict(row.metadata_json or {}) if isinstance(row.metadata_json, dict) else {}
            if chapter_bias is not None and int(metadata.get("chapter_index") or -1) != int(chapter_bias):
                continue
            if not self._matches_filters(metadata=metadata, filters=filters):
                continue
            names = {
                self._normalize_text(item)
                for item in (metadata.get("entity_names") or [])
                if self._normalize_text(item)
            }
            bias_multiplier = 1.0
            if entity_bias_keys and names:
                overlap = len(names & entity_bias_keys)
                if overlap:
                    bias_multiplier += min(0.45, 0.15 * overlap)
            dense_score, lexical_score = self._score_document_against_queries(
                planned_queries=planned_queries,
                query_vectors=query_vectors,
                text=str(row.content_text or ""),
                vector=self._coerce_vector(row.embedding_json),
            )
            if dense_score <= 0.0 and lexical_score <= 0.0:
                continue
            candidates.append(
                {
                    "source_type": row.source_type,
                    "source_id": row.source_id,
                    "chapter_index": row.chapter_index,
                    "scene_index": row.scene_index,
                    "summary": row.summary or "",
                    "excerpt": row.content_text,
                    "metadata": metadata,
                    "dense_score": dense_score * bias_multiplier,
                    "lexical_score": lexical_score * bias_multiplier,
                }
            )

        dense_ranked = [row for row in sorted(candidates, key=lambda item: item["dense_score"], reverse=True) if row["dense_score"] > 0.0]
        lexical_ranked = [row for row in sorted(candidates, key=lambda item: item["lexical_score"], reverse=True) if row["lexical_score"] > 0.0]

        fused: dict[tuple[str, str], dict[str, Any]] = {}
        for rank, row in enumerate(lexical_ranked, start=1):
            key = (str(row["source_type"]), str(row["source_id"]))
            item = fused.setdefault(key, dict(row))
            item["score"] = item.get("score", 0.0) + (1.0 / (self.rrf_k + rank))
        for rank, row in enumerate(dense_ranked, start=1):
            key = (str(row["source_type"]), str(row["source_id"]))
            item = fused.setdefault(key, dict(row))
            item["score"] = item.get("score", 0.0) + (1.0 / (self.rrf_k + rank))

        ranked = sorted(fused.values(), key=lambda item: item.get("score", 0.0), reverse=True)
        reranked = self._rerank(query_text=text, rows=ranked)
        self.last_debug = {
            "query_text": text,
            "planned_queries": planned_queries,
            "candidate_count": len(candidates),
            "dense_top": self._debug_preview(dense_ranked),
            "lexical_top": self._debug_preview(lexical_ranked),
            "fused_top": self._debug_preview(ranked),
            "final_top": self._debug_preview(reranked),
        }
        return [
            {
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "chapter_index": row["chapter_index"],
                "scene_index": row["scene_index"],
                "summary": row["summary"],
                "excerpt": row["excerpt"],
                "metadata": row["metadata"],
                "score": round(float(row.get("score") or 0.0), 6),
            }
            for row in reranked[: max(1, int(top_k))]
        ]

    def _plan_queries(self, *, query_text: str, entity_bias: Iterable[str] | None) -> list[str]:
        base = " ".join(str(query_text or "").strip().split())
        if not base:
            return []
        aliases = [" ".join(str(item or "").strip().split()) for item in (entity_bias or []) if str(item or "").strip()]
        alias_text = " / ".join(aliases[:3])
        queries: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            cleaned = " ".join(str(value or "").strip().split())
            key = cleaned.lower()
            if not cleaned or key in seen:
                return
            seen.add(key)
            queries.append(cleaned)

        add(base)
        if alias_text:
            add(f"{base} {alias_text}")
        add(f"{base} appearance description physical traits")
        add(f"{base} visual details anatomy clothing features")
        for alias in aliases[:2]:
            add(f"{alias} appearance")
            add(f"{alias} description")
        return queries[:6]

    def _score_document_against_queries(
        self,
        *,
        planned_queries: list[str],
        query_vectors: list[list[float]],
        text: str,
        vector: list[float],
    ) -> tuple[float, float]:
        best_dense = 0.0
        best_lexical = 0.0
        for query_text, query_vector in zip(planned_queries, query_vectors):
            best_dense = max(best_dense, self._cosine_similarity(query_vector, vector))
            best_lexical = max(best_lexical, self._bm25_like_score(self._tokenize(query_text), text))
        return best_dense, best_lexical

    def _rerank(self, *, query_text: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        reranker = self._get_reranker()
        if reranker is None:
            return rows
        limit = min(len(rows), self.reranker_top_n)
        pairs = [(query_text, str(row.get("excerpt") or "")) for row in rows[:limit]]
        try:
            scores = reranker.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            LOGGER.warning("Hybrid retrieval reranker failed, falling back to fused ranking: %s", exc)
            return rows
        reranked_head: list[dict[str, Any]] = []
        for row, rerank_score in zip(rows[:limit], scores):
            item = dict(row)
            item["score"] = float(rerank_score)
            reranked_head.append(item)
        reranked_head.sort(key=lambda item: item["score"], reverse=True)
        return reranked_head + rows[limit:]

    def _get_reranker(self):
        if self._reranker_unavailable:
            return None
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
        except Exception:
            LOGGER.info("sentence-transformers not available; hybrid retriever reranker disabled")
            self._reranker_unavailable = True
            return None
        try:
            self._reranker = CrossEncoder(self.reranker_model)
        except Exception as exc:
            LOGGER.warning("Could not load hybrid retrieval reranker '%s': %s", self.reranker_model, exc)
            self._reranker_unavailable = True
            return None
        return self._reranker

    def _debug_preview(self, rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        preview: list[dict[str, Any]] = []
        for row in rows[:limit]:
            preview.append(
                {
                    "source_type": row.get("source_type"),
                    "source_id": row.get("source_id"),
                    "score": round(float(row.get("score") or row.get("dense_score") or row.get("lexical_score") or 0.0), 6),
                }
            )
        return preview

    def _collect_documents(self, *, book_id: str, source_types: list[str]) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        with self.sqlite_store.session_factory() as session:
            if "scene" in source_types:
                scenes = session.execute(
                    select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
                ).scalars().all()
                for scene in scenes:
                    text = str(scene.text or "").strip()
                    if not text:
                        continue
                    metadata = dict(scene.payload_json or {}) if isinstance(scene.payload_json, dict) else {}
                    entity_names = self._scene_entity_names(metadata)
                    documents.append(
                        self._document_row(
                            source_type="scene",
                            source_id=str(scene.id),
                            chapter_index=scene.chapter_index,
                            scene_index=scene.scene_index,
                            summary=str(scene.summary or "").strip(),
                            content_text=text,
                            metadata_json={
                                "chapter_index": scene.chapter_index,
                                "scene_index": scene.scene_index,
                                "location_name": str(scene.location_name or "").strip(),
                                "entity_names": entity_names,
                                "source": "scene",
                            },
                        )
                    )
            if "event" in source_types:
                events = session.execute(
                    select(Event).where(Event.book_id == book_id).order_by(Event.chapter_index.asc(), Event.scene_index.asc(), Event.created_at.asc())
                ).scalars().all()
                for event in events:
                    payload = dict(event.payload_json or {}) if isinstance(event.payload_json, dict) else {}
                    parts = [
                        str(event.description or "").strip(),
                        str(event.reason or "").strip(),
                        str(event.outcome or "").strip(),
                    ]
                    text = " ".join(part for part in parts if part).strip()
                    if not text:
                        continue
                    documents.append(
                        self._document_row(
                            source_type="event",
                            source_id=str(event.id),
                            chapter_index=event.chapter_index,
                            scene_index=event.scene_index,
                            summary=str(event.description or "").strip(),
                            content_text=text,
                            metadata_json={
                                "chapter_index": event.chapter_index,
                                "scene_index": event.scene_index,
                                "event_type": str(event.event_type or "").strip(),
                                "entity_names": self._event_entity_names(event=event, payload=payload),
                                "event_location": str(payload.get("event_location") or "").strip(),
                                "source": "event",
                            },
                        )
                    )
        return documents

    def _document_row(
        self,
        *,
        source_type: str,
        source_id: str,
        chapter_index: int | None,
        scene_index: int | None,
        summary: str,
        content_text: str,
        metadata_json: dict[str, Any],
    ) -> dict[str, Any]:
        fingerprint_payload = {
            "summary": summary,
            "content_text": content_text,
            "metadata_json": metadata_json,
        }
        content_hash = hashlib.sha256(json_dumps(fingerprint_payload).encode("utf-8")).hexdigest()
        return {
            "source_type": source_type,
            "source_id": source_id,
            "chapter_index": chapter_index,
            "scene_index": scene_index,
            "summary": summary,
            "content_text": content_text,
            "content_hash": content_hash,
            "metadata_json": metadata_json,
        }

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

    def _scene_entity_names(self, payload: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for row in payload.get("entities_present") or []:
            if isinstance(row, dict):
                value = str(row.get("name") or "").strip()
                if value:
                    names.append(value)
        for row in payload.get("canonical_characters") or []:
            if isinstance(row, dict):
                value = str(row.get("name") or "").strip()
            else:
                value = str(row or "").strip()
            if value:
                names.append(value)
        return self._dedupe_strings(names)

    def _event_entity_names(self, *, event: Event, payload: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for value in event.entities_involved or []:
            item = str(value or "").strip()
            if item:
                names.append(item)
        for key in (
            "characters",
            "characters_involved",
            "objects_involved",
            "creatures_involved",
            "locations_involved",
            "organizations_involved",
        ):
            for value in payload.get(key) or []:
                item = str(value or "").strip()
                if item:
                    names.append(item)
        location_name = str(payload.get("event_location") or payload.get("location_name") or "").strip()
        if location_name:
            names.append(location_name)
        return self._dedupe_strings(names)

    def _matches_filters(self, *, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if expected in (None, "", []):
                continue
            actual = metadata.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def _coerce_vector(self, value: Any) -> list[float]:
        if not isinstance(value, list):
            return []
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return []

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _bm25_like_score(self, query_tokens: list[str], text: str) -> float:
        doc_tokens = self._tokenize(text)
        if not query_tokens or not doc_tokens:
            return 0.0
        doc_counts = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        avg_doc_len = 120.0
        k1 = 1.5
        b = 0.75
        score = 0.0
        for token in query_tokens:
            tf = doc_counts.get(token, 0)
            if tf <= 0:
                continue
            idf = 1.0 + math.log1p(len(token))
            denom = tf + k1 * (1.0 - b + b * (doc_len / avg_doc_len))
            score += idf * ((tf * (k1 + 1.0)) / denom)
        return score

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b\w+\b", str(text or "").lower())

    def _dedupe_strings(self, values: Iterable[str]) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = " ".join(str(value or "").strip().split())
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            rows.append(cleaned)
        return rows

    def _normalize_text(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or ""))
        return " ".join(cleaned.split())


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)
