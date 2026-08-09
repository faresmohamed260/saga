from __future__ import annotations

from saga.storage.persistence import SagaRelationalStore


class AudiobookStore:
    """Audiobook persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def create_audiobook_run(self, payload: dict) -> dict:
        return self.relational_store.create_audiobook_run(payload)

    def upsert_audiobook_chapter(self, payload: dict) -> dict:
        return self.relational_store.upsert_audiobook_chapter(payload)

    def get_audiobook_runs(self, *, series_id: str | None = None, book_id: str | None = None, limit: int = 100) -> list[dict]:
        return self.relational_store.get_audiobook_runs(series_id=series_id, book_id=book_id, limit=limit)

    def get_audiobook_run(self, run_id: str) -> dict | None:
        return self.relational_store.get_audiobook_run(run_id)

    def update_audiobook_run(self, run_id: str, payload: dict) -> dict | None:
        return self.relational_store.update_audiobook_run(run_id, payload)


SQLiteAudiobookStore = AudiobookStore
