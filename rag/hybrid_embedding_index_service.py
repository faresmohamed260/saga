"""Persisted local embedding index for focused narrative retrieval."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests


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

    def ensure_index(
        self,
        *,
        series_id: str,
        scope_key: str,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        runtime_dir = self._runtime_dir(series_id=series_id, scope_key=scope_key)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        index_path = runtime_dir / "index.json"
        fingerprint = self._fingerprint(documents)
        existing = self._load_index(index_path)
        if existing and existing.get("fingerprint") == fingerprint:
            return existing

        vectors = self._embed_texts([str(doc.get("text") or "") for doc in documents])
        payload = {
            "series_id": series_id,
            "scope_key": scope_key,
            "embedding_model": self.embedding_model,
            "fingerprint": fingerprint,
            "documents": documents,
            "vectors": vectors,
        }
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def query(
        self,
        *,
        index_payload: Dict[str, Any],
        query_text: str,
        top_k: int = 6,
        allowed_types: Optional[Iterable[str]] = None,
        character_bias: Optional[Iterable[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        documents = list(index_payload.get("documents") or [])
        vectors = list(index_payload.get("vectors") or [])
        if not query_text.strip() or not documents or not vectors:
            return []

        query_vector = self._embed_texts([query_text])[0]
        allowed = {item for item in (allowed_types or []) if item}
        biased_characters = {str(name).strip().lower() for name in (character_bias or []) if str(name).strip()}
        filters = metadata_filters or {}

        ranked: List[Dict[str, Any]] = []
        for doc, vector in zip(documents, vectors):
            if allowed and str(doc.get("source_type") or "") not in allowed:
                continue
            if not self._matches_filters(doc.get("metadata") or {}, filters):
                continue
            score = self._cosine_similarity(query_vector, vector)
            if not score:
                continue
            names = {str(name).strip().lower() for name in (doc.get("metadata", {}).get("characters") or []) if str(name).strip()}
            if biased_characters and names:
                overlap = len(names & biased_characters)
                if overlap:
                    score *= 1.0 + min(0.35, 0.12 * overlap)
            ranked.append({
                "document_id": doc.get("document_id", ""),
                "source_type": doc.get("source_type", ""),
                "summary": doc.get("summary", ""),
                "metadata": doc.get("metadata", {}) or {},
                "score": round(float(score), 6),
            })

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[: max(1, int(top_k))]

    def _runtime_dir(self, *, series_id: str, scope_key: str) -> Path:
        safe_series = self._slug(series_id or "standalone")
        safe_scope = self._slug(scope_key or "default")
        return self.base_dir / safe_series / safe_scope

    def _load_index(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _fingerprint(self, documents: List[Dict[str, Any]]) -> str:
        normalized = json.dumps(
            [
                {
                    "document_id": doc.get("document_id"),
                    "source_type": doc.get("source_type"),
                    "summary": doc.get("summary"),
                    "text": doc.get("text"),
                    "metadata": doc.get("metadata"),
                }
                for doc in documents
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.embedder is not None:
            return self.embedder(texts)

        vectors: List[List[float]] = []
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

    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
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

    def _cosine_similarity(self, left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _slug(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "default"
