from __future__ import annotations

from typing import Any, Iterable, Protocol


class BookRetrievalTool(Protocol):
    def ensure_book_index(self, *, book_id: str, source_types: Iterable[str] | None = None) -> dict[str, Any]:
        ...

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
        ...
