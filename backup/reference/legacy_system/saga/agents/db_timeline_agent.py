from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select

from saga.storage.models import Event, Scene, TimelineRow
from saga.storage.persistence import SagaSQLiteStore
from saga.domain.timeline.timeline_service import TimelineService


LOGGER = logging.getLogger(__name__)


class DatabaseTimelineAgent:
    VERSION = "db_timeline_agent_v1"

    def __init__(self, *, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.service = TimelineService()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
        replace_existing: bool = True,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        scene_rows, event_rows = self._load_rows(book_id=book_id, chapter_limit=chapter_limit, chapter_indices=chapter_indices)
        timeline = self.service.build_from_scene_analyses(scene_rows)
        with self.sqlite_store.session_factory() as session:
            if replace_existing:
                session.execute(delete(TimelineRow).where(TimelineRow.book_id == book_id))
            event_by_external = {
                str(row.event_id_external or "").strip(): row
                for row in session.execute(select(Event).where(Event.book_id == book_id)).scalars().all()
                if str(row.event_id_external or "").strip()
            }
            for idx, row in enumerate(timeline, start=1):
                event = event_by_external.get(str(row.get("event_id") or "").strip())
                session.add(
                    TimelineRow(
                        book_id=book_id,
                        event_id=event.id if event else None,
                        row_index=idx,
                        payload_json={**row, "agent_metadata": {"source": self.VERSION}},
                    )
                )
            session.commit()
        LOGGER.info("DB timeline agent complete | book=%s scenes=%s events=%s timeline_rows=%s", book_id, len(scene_rows), len(event_rows), len(timeline))
        return {
            "book_id": book_id,
            "scene_count": len(scene_rows),
            "event_count": len(event_rows),
            "timeline_row_count": len(timeline),
            "timeline_preview": timeline[:10],
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_rows(
        self,
        *,
        book_id: str,
        chapter_limit: int | None,
        chapter_indices: list[int] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        selected = {int(value) for value in (chapter_indices or [])}
        with self.sqlite_store.session_factory() as session:
            scene_models = session.execute(
                select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            event_models = session.execute(
                select(Event).where(Event.book_id == book_id).order_by(Event.chapter_index.asc(), Event.scene_index.asc(), Event.created_at.asc())
            ).scalars().all()
        filtered_scenes: list[dict[str, Any]] = []
        for scene in scene_models:
            chapter_index = int(scene.chapter_index or 0)
            if chapter_limit is not None and chapter_index > int(chapter_limit):
                continue
            if selected and chapter_index not in selected:
                continue
            filtered_scenes.append(
                {
                    "book_index": 1,
                    "chapter_index": chapter_index,
                    "scene_index": int(scene.scene_index or 0),
                    "events": [],
                }
            )
        scene_lookup = {(row["chapter_index"], row["scene_index"]): row for row in filtered_scenes}
        filtered_events: list[dict[str, Any]] = []
        for event in event_models:
            chapter_index = int(event.chapter_index or 0)
            if chapter_limit is not None and chapter_index > int(chapter_limit):
                continue
            if selected and chapter_index not in selected:
                continue
            row = {
                "event_id": str(event.event_id_external or "").strip(),
                "description": str(event.description or "").strip(),
                "event_type": str(event.event_type or "").strip(),
                "type": str(event.event_type or "").strip(),
                "characters": list((dict(event.payload_json or {}).get("characters") or [])),
                "entities_involved": list(event.entities_involved or []),
                "reason": str(event.reason or "").strip(),
                "outcome": str(event.outcome or "").strip(),
            }
            filtered_events.append(row)
            scene_payload = scene_lookup.get((chapter_index, int(event.scene_index or 0)))
            if scene_payload is not None:
                scene_payload["events"].append(row)
        return filtered_scenes, filtered_events
