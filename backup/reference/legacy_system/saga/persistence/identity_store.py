from __future__ import annotations

from typing import Any

from saga.storage.persistence import SagaRelationalStore


class IdentityStore:
    """Identity persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def persist_identity_bundle(
        self,
        *,
        series_id: str,
        source_path: str,
        series_payload: dict[str, Any],
        book_summaries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.relational_store.persist_identity_bundle(
            series_id=series_id,
            source_path=source_path,
            series_payload=series_payload,
            book_summaries=book_summaries,
        )

    def get_identity_series_payload(self, series_id: str) -> dict[str, Any] | None:
        return self.relational_store.get_identity_series_payload(series_id)


SQLiteIdentityStore = IdentityStore
