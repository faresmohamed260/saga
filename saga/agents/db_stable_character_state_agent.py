from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select

from saga.domain.stable_character_state import StableCharacterStateBuilder
from saga.storage.models import CharacterProfile, Entity, Scene, StableCharacterState
from saga.storage.persistence import SagaSQLiteStore
from saga.domain.canon_state_service import CanonStateService
from saga.domain.state_transition_service import StateTransitionService


LOGGER = logging.getLogger(__name__)


class DatabaseStableCharacterStateAgent:
    VERSION = "db_stable_character_state_agent_v1"

    def __init__(self, *, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.transition_service = StateTransitionService()
        self.canon_service = CanonStateService()
        self.builder = StableCharacterStateBuilder()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
        replace_existing: bool = True,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        scene_rows, profile_rows, identity_result = self._load_inputs(book_id=book_id, chapter_limit=chapter_limit, chapter_indices=chapter_indices)
        state_result = self.transition_service.build(scene_rows)
        canon_snapshot = self.canon_service.snapshot_at(
            state_result.get("transitions") or [],
            scene_ref=self._last_scene_ref(scene_rows),
        )
        stable_rows = self.builder.build(
            character_profiles=profile_rows,
            identity_result=identity_result,
            canon_snapshot=canon_snapshot,
            state_result=state_result,
        )
        stable_rows = self._merge_profile_fallback_states(stable_rows=stable_rows, profile_rows=profile_rows)
        with self.sqlite_store.session_factory() as session:
            if replace_existing:
                session.execute(delete(StableCharacterState).where(StableCharacterState.book_id == book_id))
            entity_rows = session.execute(select(Entity).where(Entity.book_id == book_id)).scalars().all()
            entity_by_name = {str(row.canonical_name or "").strip().lower(): row for row in entity_rows}
            latest_by_name = {
                str(row.get("entity_name") or "").strip().lower(): row
                for row in (state_result.get("latest_state") or [])
                if str(row.get("entity_type") or "").strip().lower() == "character"
            }
            for row in stable_rows:
                character_name = str(row.get("entity_name") or "").strip()
                entity = entity_by_name.get(character_name.lower())
                payload = {
                    "character_name": character_name,
                    "attributes": dict(row.get("attributes") or {}),
                    "latest_state": dict((latest_by_name.get(character_name.lower()) or {}).get("attributes") or {}),
                    "agent_metadata": {"source": self.VERSION},
                }
                session.add(
                    StableCharacterState(
                        book_id=book_id,
                        entity_id=entity.id if entity else None,
                        character_name=character_name,
                        payload_json=payload,
                    )
                )
                if entity is not None:
                    world_state = dict(entity.latest_world_state or {}) if isinstance(entity.latest_world_state, dict) else {}
                    world_state["stable_character_state"] = payload["attributes"]
                    if payload["latest_state"]:
                        world_state["latest_character_state"] = payload["latest_state"]
                    entity.latest_world_state = world_state
            session.commit()
        LOGGER.info("DB stable state agent complete | book=%s scenes=%s transitions=%s stable_rows=%s", book_id, len(scene_rows), len(state_result.get("transitions") or []), len(stable_rows))
        return {
            "book_id": book_id,
            "scene_count": len(scene_rows),
            "transition_count": len(state_result.get("transitions") or []),
            "stable_state_count": len(stable_rows),
            "stable_states": stable_rows,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_inputs(
        self,
        *,
        book_id: str,
        chapter_limit: int | None,
        chapter_indices: list[int] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        selected = {int(value) for value in (chapter_indices or [])}
        with self.sqlite_store.session_factory() as session:
            scenes = session.execute(
                select(Scene)
                .where(Scene.book_id == book_id)
                .order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            profiles = session.execute(
                select(CharacterProfile).where(CharacterProfile.book_id == book_id).order_by(CharacterProfile.character_name.asc())
            ).scalars().all()
            entities = session.execute(
                select(Entity).where(Entity.book_id == book_id, Entity.entity_type == "character").order_by(Entity.canonical_name.asc())
            ).scalars().all()
        scene_rows: list[dict[str, Any]] = []
        for scene in scenes:
            chapter_index = int(scene.chapter_index or 0)
            if chapter_limit is not None and chapter_index > int(chapter_limit):
                continue
            if selected and chapter_index not in selected:
                continue
            payload = dict(scene.payload_json or {}) if isinstance(scene.payload_json, dict) else {}
            scene_rows.append(
                {
                    "book_index": 1,
                    "chapter_index": chapter_index,
                    "scene_index": int(scene.scene_index or 0),
                    "state_changes": list(payload.get("state_changes") or []),
                }
            )
        profile_rows: list[dict[str, Any]] = []
        for row in profiles:
            payload = dict(row.payload_json or {}) if isinstance(row.payload_json, dict) else {}
            profile_rows.append(
                {
                    "canonical_name": str(row.character_name or "").strip(),
                    "core_description": str(payload.get("profile_summary") or "").strip(),
                    "traits": list(payload.get("core_traits") or []),
                    "relationship_refs": list(payload.get("relationship_refs") or []),
                    "state_at_latest": dict(payload.get("state_at_latest") or {}),
                }
            )
        alias_map = {
            str(row.canonical_name or "").strip(): [str(item).strip() for item in ((row.metadata_json or {}).get("aliases") or []) if str(item).strip()]
            for row in entities
            if str(row.canonical_name or "").strip()
        }
        return scene_rows, profile_rows, {"alias_map": alias_map}

    def _merge_profile_fallback_states(self, *, stable_rows: list[dict[str, Any]], profile_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_name: dict[str, dict[str, Any]] = {
            str(row.get("entity_name") or "").strip().lower(): {
                "entity_name": str(row.get("entity_name") or "").strip(),
                "attributes": dict(row.get("attributes") or {}),
            }
            for row in stable_rows
            if str(row.get("entity_name") or "").strip()
        }
        for profile in profile_rows:
            name = str(profile.get("canonical_name") or "").strip()
            if not name:
                continue
            inferred = self._infer_profile_fallback_attributes(profile)
            if not inferred:
                continue
            entry = by_name.setdefault(name.lower(), {"entity_name": name, "attributes": {}})
            for key, value in inferred.items():
                if value and not str(entry["attributes"].get(key) or "").strip():
                    entry["attributes"][key] = value
        rows = [row for row in by_name.values() if row.get("attributes")]
        rows.sort(key=lambda item: str(item.get("entity_name") or "").lower())
        return rows

    def _infer_profile_fallback_attributes(self, profile: dict[str, Any]) -> dict[str, str]:
        attrs: dict[str, str] = {}
        payload = dict(profile or {})
        titles = [str(item).strip() for item in (payload.get("titles_or_roles") or []) if str(item).strip()]
        affiliations = [str(item).strip() for item in (payload.get("affiliations") or []) if str(item).strip()]
        summary = " ".join(
            item
            for item in [
                str(payload.get("core_description") or "").strip(),
                " ".join(str(item).strip() for item in (payload.get("traits") or []) if str(item).strip()),
                " ".join(titles),
                " ".join(affiliations),
            ]
            if item
        ).lower()
        if "not_explicitly_stated_in_text" in summary and len(summary.split()) <= 4:
            summary = ""

        for value in titles:
            lowered = value.lower()
            if "professor" in lowered:
                attrs.setdefault("title", "Professor")
                attrs.setdefault("role", "teacher")
            if "headmaster" in lowered:
                attrs.setdefault("title", "Headmaster")
                attrs.setdefault("role", "headmaster")
            if "caretaker" in lowered:
                attrs.setdefault("role", "caretaker")
            if "student" in lowered:
                attrs.setdefault("role", "student")
            if "gamekeeper" in lowered:
                attrs.setdefault("role", "gamekeeper")
            if "chaser" in lowered:
                attrs.setdefault("role", "chaser")
            if lowered in {"aunt", "uncle", "mother", "father", "son", "daughter", "wife", "husband"}:
                attrs.setdefault("family_role", lowered)
            if "wife of" in lowered:
                attrs.setdefault("family_role", "wife")
            if "mother of" in lowered:
                attrs.setdefault("family_role", "mother")

        if not attrs.get("family_role"):
            name = str(profile.get("canonical_name") or "").strip().lower()
            if name.startswith("aunt "):
                attrs["family_role"] = "aunt"
            elif name.startswith("uncle "):
                attrs["family_role"] = "uncle"
            elif name.startswith("professor "):
                attrs.setdefault("title", "Professor")
                attrs.setdefault("role", "teacher")
            elif name.startswith("mr "):
                attrs.setdefault("title", "Mr")
            elif name.startswith("mrs "):
                attrs.setdefault("title", "Mrs")

        for value in affiliations:
            cleaned = str(value or "").strip()
            lowered = cleaned.lower()
            if not cleaned or lowered == "not_explicitly_stated_in_text":
                continue
            attrs.setdefault("allegiance", cleaned)
            break

        if "hostile to harry" in summary and not attrs.get("relationship_status"):
            attrs["relationship_status"] = "hostile toward Harry Potter"
        if "protective of her family" in summary and not attrs.get("family_role"):
            attrs["family_role"] = "family member"
        return attrs

    def _last_scene_ref(self, scene_rows: list[dict[str, Any]]) -> tuple[int, int, int] | None:
        if not scene_rows:
            return None
        last = sorted(scene_rows, key=lambda item: (item.get("book_index", 0), item.get("chapter_index", 0), item.get("scene_index", 0)))[-1]
        return (
            int(last.get("book_index") or 1),
            int(last.get("chapter_index") or 0),
            int(last.get("scene_index") or 0),
        )
