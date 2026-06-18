from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from saga.domain.builders.relationship_profile_builder import RelationshipProfileBuilder
from saga.storage.models import Book, Scene
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


class DatabaseRelationshipAgent:
    VERSION = "db_relationship_agent_v1"

    def __init__(self, *, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.builder = RelationshipProfileBuilder()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        scene_rows = self._load_scene_rows(book_id=book_id, chapter_limit=chapter_limit, chapter_indices=chapter_indices)
        profiles = self.builder.build(scene_analyses=scene_rows)
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            if book is not None:
                metadata = dict(book.metadata_json or {})
                metadata["relationship_profiles"] = profiles
                metadata["relationship_agent"] = {
                    "source": self.VERSION,
                    "scene_count": len(scene_rows),
                    "relationship_profile_count": len(profiles),
                }
                book.metadata_json = metadata
                session.commit()
        LOGGER.info("DB relationship agent complete | book=%s scenes=%s profiles=%s", book_id, len(scene_rows), len(profiles))
        return {
            "book_id": book_id,
            "scene_count": len(scene_rows),
            "relationship_profile_count": len(profiles),
            "relationship_profiles": profiles,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_scene_rows(self, *, book_id: str, chapter_limit: int | None, chapter_indices: list[int] | None) -> list[dict[str, Any]]:
        selected = {int(value) for value in (chapter_indices or [])}
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            payload: list[dict[str, Any]] = []
            for row in rows:
                chapter_index = int(row.chapter_index or 0)
                if chapter_limit is not None and chapter_index > int(chapter_limit):
                    continue
                if selected and chapter_index not in selected:
                    continue
                scene_payload = dict(row.payload_json or {}) if isinstance(row.payload_json, dict) else {}
                payload.append(
                    {
                        "book_index": int(scene_payload.get("book_index") or 1),
                        "chapter_index": chapter_index,
                        "scene_index": int(row.scene_index or 0),
                        "relationship_changes": list(scene_payload.get("relationship_changes") or []),
                    }
                )
            return payload
