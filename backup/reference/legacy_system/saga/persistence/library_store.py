from __future__ import annotations

from pathlib import Path
from typing import Any

from saga.storage.persistence import SagaRelationalStore


class LibraryStore:
    """Structured-library persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def persist_contract(self, contract: dict[str, Any], *, contract_path: str | Path | None = None) -> dict[str, Any]:
        return self.relational_store.persist_contract(contract, contract_path=contract_path)

    def persist_render_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return self.relational_store.persist_render_manifest(manifest)

    def resplit_book_scenes(self, *, book_ref: str, target_scene_words: int = 700) -> dict[str, Any]:
        return self.relational_store.resplit_book_scenes(book_ref=book_ref, target_scene_words=target_scene_words)

    def register_uploaded_source(
        self,
        *,
        original_name: str,
        stored_path: str,
        size_bytes: int | None = None,
        mime_type: str | None = None,
        sha256: str | None = None,
        source_kind: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.relational_store.register_uploaded_source(
            original_name=original_name,
            stored_path=stored_path,
            size_bytes=size_bytes,
            mime_type=mime_type,
            sha256=sha256,
            source_kind=source_kind,
            metadata=metadata,
        )

    def get_uploaded_sources(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.relational_store.get_uploaded_sources(limit=limit)

    def get_series_books(self, series_id: str) -> list[dict[str, Any]]:
        return self.relational_store.get_series_books(series_id)


SQLiteLibraryStore = LibraryStore
