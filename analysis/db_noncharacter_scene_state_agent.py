from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select

from sql_store.models import Entity, LocationSceneState, ObjectSceneState, Scene
from sql_store.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)

UNKNOWN_TEXT = "not_explicitly_stated_in_text"


class DatabaseNonCharacterSceneStateAgent:
    VERSION = "db_noncharacter_scene_state_agent_v1"

    def __init__(self, *, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
        replace_existing: bool = True,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        selected = {int(value) for value in (chapter_indices or [])}
        object_rows = 0
        location_rows = 0
        with self.sqlite_store.session_factory() as session:
            scene_rows = session.execute(
                select(Scene)
                .where(Scene.book_id == book_id)
                .order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            entity_rows = session.execute(
                select(Entity)
                .where(Entity.book_id == book_id, Entity.entity_type.in_(["object", "location"]))
                .order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
            ).scalars().all()
            entity_lookup = {
                (str(row.canonical_name or "").strip().lower(), str(row.entity_type or "").strip().lower()): row
                for row in entity_rows
                if str(row.canonical_name or "").strip()
            }
            if replace_existing:
                session.execute(delete(ObjectSceneState).where(ObjectSceneState.book_id == book_id))
                session.execute(delete(LocationSceneState).where(LocationSceneState.book_id == book_id))

            for scene in scene_rows:
                chapter_index = int(scene.chapter_index or 0)
                if chapter_limit is not None and chapter_index > int(chapter_limit):
                    continue
                if selected and chapter_index not in selected:
                    continue

                payload = dict(scene.payload_json or {}) if isinstance(scene.payload_json, dict) else {}
                world_state = dict(payload.get("entity_world_state") or {})
                world_entities = list(world_state.get("entities") or [])

                for row in world_entities:
                    if not isinstance(row, dict):
                        continue
                    entity_name = str(row.get("entity_name") or "").strip()
                    entity_type = str(row.get("entity_type") or "").strip().lower()
                    if entity_type != "object" or not entity_name:
                        continue
                    entity = entity_lookup.get((entity_name.lower(), "object"))
                    if entity is None:
                        continue
                    current_state = self._text(row.get("current_state"))
                    state_changes = self._state_change_text(row.get("state_changes"))
                    session.add(
                        ObjectSceneState(
                            book_id=book_id,
                            entity_id=entity.id,
                            scene_id=scene.id,
                            chapter_index=chapter_index,
                            scene_index=int(scene.scene_index or 0),
                            owner_or_holder=UNKNOWN_TEXT,
                            activation_state=current_state,
                            damage_state=self._infer_damage_state(current_state=current_state, state_changes=state_changes),
                            location_context=self._text(scene.location_name) or UNKNOWN_TEXT,
                            contained_contents=UNKNOWN_TEXT,
                            temporary_effects=state_changes or current_state or UNKNOWN_TEXT,
                            source_scene_json=row,
                        )
                    )
                    object_rows += 1

                location_name = self._text(scene.location_name)
                if location_name:
                    entity = entity_lookup.get((location_name.lower(), "location"))
                    if entity is not None:
                        entities_present = list(payload.get("entities_present") or [])
                        occupants = [
                            str(item.get("name") or "").strip()
                            for item in entities_present
                            if isinstance(item, dict) and str(item.get("name") or "").strip()
                        ]
                        location_payload = dict(payload.get("location") or {})
                        session.add(
                            LocationSceneState(
                                book_id=book_id,
                                entity_id=entity.id,
                                scene_id=scene.id,
                                chapter_index=chapter_index,
                                scene_index=int(scene.scene_index or 0),
                                lighting_current=UNKNOWN_TEXT,
                                weather_current=UNKNOWN_TEXT,
                                occupancy_state=", ".join(occupants[:12]) if occupants else UNKNOWN_TEXT,
                                damage_state=self._infer_damage_state(
                                    current_state=self._text(location_payload.get("description")),
                                    state_changes=self._text(location_payload.get("atmosphere")),
                                ),
                                temporary_setup=self._text(location_payload.get("description")) or UNKNOWN_TEXT,
                                atmosphere_shift=self._text(location_payload.get("atmosphere")) or UNKNOWN_TEXT,
                                active_effects=self._active_effects_text(world_entities),
                                source_scene_json={
                                    "location": location_payload,
                                    "entities_present": entities_present,
                                },
                            )
                        )
                        location_rows += 1

            session.commit()

        LOGGER.info(
            "DB non-character scene-state agent complete | book=%s object_rows=%s location_rows=%s",
            book_id,
            object_rows,
            location_rows,
        )
        return {
            "book_id": book_id,
            "object_scene_state_rows": object_rows,
            "location_scene_state_rows": location_rows,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _text(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _state_change_text(self, value: Any) -> str:
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    detail = " ".join(
                        piece
                        for piece in [
                            self._text(item.get("attribute")),
                            self._text(item.get("new_state")),
                            self._text(item.get("detail")),
                        ]
                        if piece
                    )
                    if detail:
                        parts.append(detail)
                else:
                    cleaned = self._text(item)
                    if cleaned:
                        parts.append(cleaned)
            return " | ".join(parts)
        return self._text(value)

    def _infer_damage_state(self, *, current_state: str, state_changes: str) -> str:
        source = f"{current_state} {state_changes}".lower()
        for token in ("broken", "damaged", "destroyed", "burned", "burnt", "missing", "cracked", "shattered"):
            if token in source:
                return token
        return UNKNOWN_TEXT

    def _active_effects_text(self, world_entities: list[dict[str, Any]]) -> str:
        effects: list[str] = []
        for item in world_entities:
            if not isinstance(item, dict):
                continue
            entity_type = str(item.get("entity_type") or "").strip().lower()
            if entity_type not in {"object", "creature"}:
                continue
            current_state = self._text(item.get("current_state"))
            if current_state:
                effects.append(f"{self._text(item.get('entity_name'))}: {current_state}")
        return " | ".join(effects[:8]) if effects else UNKNOWN_TEXT
