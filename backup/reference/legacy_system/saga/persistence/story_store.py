from __future__ import annotations

from typing import Any

from saga.storage.persistence import SagaRelationalStore


class StoryStore:
    """Generated-story persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def store_generated_story(self, **kwargs: Any) -> dict[str, Any]:
        return self.relational_store.store_generated_story(**kwargs)

    def get_generated_stories(self, *, book_id: str | None = None) -> list[dict[str, Any]]:
        return self.relational_store.get_generated_stories(book_id=book_id)

    def get_generated_story(self, story_id: str) -> dict[str, Any] | None:
        return self.relational_store.get_generated_story(story_id)

    def get_generated_stories_for_series(self, series_id: str) -> list[dict[str, Any]]:
        return self.relational_store.get_generated_stories_for_series(series_id)


SQLiteStoryStore = StoryStore
