from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from saga.storage.models import (
    CharacterVisualBaseline,
    CharacterVisualSceneState,
    CreatureVisualBaseline,
    Entity,
    LocationSceneState,
    LocationVisualBaseline,
    ObjectSceneState,
    ObjectVisualBaseline,
)
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)

UNKNOWN_TEXT = "not_explicitly_stated_in_text"


class DatabaseWorldStateConsolidationAgent:
    VERSION = "db_world_state_consolidation_agent_v1"

    def __init__(self, *, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        selected = {int(value) for value in (chapter_indices or [])}
        updated = 0
        with self.sqlite_store.session_factory() as session:
            entities = session.execute(
                select(Entity).where(Entity.book_id == book_id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
            ).scalars().all()
            char_baselines = {
                row.entity_id: row
                for row in session.execute(select(CharacterVisualBaseline).where(CharacterVisualBaseline.book_id == book_id)).scalars().all()
            }
            creature_baselines = {
                row.entity_id: row
                for row in session.execute(select(CreatureVisualBaseline).where(CreatureVisualBaseline.book_id == book_id)).scalars().all()
            }
            object_baselines = {
                row.entity_id: row
                for row in session.execute(select(ObjectVisualBaseline).where(ObjectVisualBaseline.book_id == book_id)).scalars().all()
            }
            location_baselines = {
                row.entity_id: row
                for row in session.execute(select(LocationVisualBaseline).where(LocationVisualBaseline.book_id == book_id)).scalars().all()
            }
            char_states = session.execute(
                select(CharacterVisualSceneState).where(CharacterVisualSceneState.book_id == book_id).order_by(CharacterVisualSceneState.chapter_index.asc(), CharacterVisualSceneState.scene_index.asc())
            ).scalars().all()
            object_states = session.execute(
                select(ObjectSceneState).where(ObjectSceneState.book_id == book_id).order_by(ObjectSceneState.chapter_index.asc(), ObjectSceneState.scene_index.asc())
            ).scalars().all()
            location_states = session.execute(
                select(LocationSceneState).where(LocationSceneState.book_id == book_id).order_by(LocationSceneState.chapter_index.asc(), LocationSceneState.scene_index.asc())
            ).scalars().all()
            char_state_map: dict[str, list[CharacterVisualSceneState]] = {}
            object_state_map: dict[str, list[ObjectSceneState]] = {}
            location_state_map: dict[str, list[LocationSceneState]] = {}
            for row in char_states:
                if chapter_limit is not None and int(row.chapter_index or 0) > int(chapter_limit):
                    continue
                if selected and int(row.chapter_index or 0) not in selected:
                    continue
                char_state_map.setdefault(str(row.entity_id), []).append(row)
            for row in object_states:
                if chapter_limit is not None and int(row.chapter_index or 0) > int(chapter_limit):
                    continue
                if selected and int(row.chapter_index or 0) not in selected:
                    continue
                object_state_map.setdefault(str(row.entity_id), []).append(row)
            for row in location_states:
                if chapter_limit is not None and int(row.chapter_index or 0) > int(chapter_limit):
                    continue
                if selected and int(row.chapter_index or 0) not in selected:
                    continue
                location_state_map.setdefault(str(row.entity_id), []).append(row)

            for entity in entities:
                entity_type = str(entity.entity_type or "").strip().lower()
                if entity_type == "character":
                    baseline = char_baselines.get(entity.id)
                    states = char_state_map.get(entity.id, [])
                    self._apply_character(entity=entity, baseline=baseline, states=states)
                    updated += 1
                elif entity_type == "creature":
                    baseline = creature_baselines.get(entity.id)
                    self._apply_noncharacter(entity=entity, baseline=baseline, states=[])
                    updated += 1
                elif entity_type == "object":
                    baseline = object_baselines.get(entity.id)
                    states = object_state_map.get(entity.id, [])
                    self._apply_object(entity=entity, baseline=baseline, states=states)
                    updated += 1
                elif entity_type == "location":
                    baseline = location_baselines.get(entity.id)
                    states = location_state_map.get(entity.id, [])
                    self._apply_location(entity=entity, baseline=baseline, states=states)
                    updated += 1
            session.commit()
        LOGGER.info("DB world-state consolidation complete | book=%s updated_entities=%s", book_id, updated)
        return {"book_id": book_id, "updated_entities": updated, "agent_version": self.VERSION}

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _apply_character(self, *, entity: Entity, baseline: CharacterVisualBaseline | None, states: list[CharacterVisualSceneState]) -> None:
        persistent_traits = {}
        if baseline is not None:
            persistent_traits = {
                "gender_presentation": self._clean(baseline.gender_presentation),
                "species_or_race": self._clean(baseline.species_or_race),
                "apparent_age_group": self._clean(baseline.apparent_age_group),
                "height_impression": self._clean(baseline.height_impression),
                "build": self._clean(baseline.build),
                "skin_tone_or_complexion": self._clean(baseline.skin_tone_or_complexion),
                "hair_color": self._clean(baseline.hair_color),
                "hair_length_or_style": self._clean(baseline.hair_length_or_style),
                "eye_color": self._clean(baseline.eye_color),
                "facial_features": self._clean(baseline.facial_features),
                "distinguishing_marks": self._clean(baseline.distinguishing_marks),
                "default_clothing_style": self._clean(baseline.default_clothing_style),
                "default_accessories": self._clean(baseline.default_accessories),
                "default_footwear": self._clean(baseline.default_footwear),
                "signature_items": self._clean(baseline.signature_items),
                "fantasy_features": self._clean(baseline.fantasy_features),
                "world_genre_cues": self._clean(baseline.world_genre_cues),
            }
        state_rows = []
        latest_state = {}
        for row in states:
            payload = {
                "chapter_index": int(row.chapter_index or 0),
                "scene_index": int(row.scene_index or 0),
                "scene_id": str(row.scene_id or "").strip(),
                "scene_outfit": self._clean(row.scene_outfit),
                "scene_accessories": self._clean(row.scene_accessories),
                "scene_footwear": self._clean(row.scene_footwear),
                "visible_condition": self._clean(row.visible_condition),
                "injuries": self._clean(row.injuries),
                "dirt_blood_markings": self._clean(row.dirt_blood_markings),
                "body_language": self._clean(row.body_language),
                "expression": self._clean(row.expression),
                "carried_items": self._clean(row.carried_items),
                "temporary_effects": self._clean(row.temporary_effects),
            }
            state_rows.append(payload)
            latest_state = {key: value for key, value in payload.items() if value and key not in {"chapter_index", "scene_index", "scene_id"}}
        entity.first_appearance_profile = {
            **(dict(entity.first_appearance_profile or {}) if isinstance(entity.first_appearance_profile, dict) else {}),
            "persistent_traits": persistent_traits,
            "status": "captured" if any(value != UNKNOWN_TEXT for value in persistent_traits.values()) else "sparse",
            "agent_version": self.VERSION,
        }
        entity.latest_world_state = {
            **(dict(entity.latest_world_state or {}) if isinstance(entity.latest_world_state, dict) else {}),
            "persistent_traits": persistent_traits,
            "current_visual_state": latest_state,
            "scene_visual_state_count": len(state_rows),
            "agent_version": self.VERSION,
        }
        entity.visual_change_log = state_rows
        metadata = dict(entity.metadata_json or {})
        metadata["scene_visual_states"] = [{"chapter_index": row["chapter_index"], "scene_index": row["scene_index"], "scene_id": row["scene_id"], "state": row} for row in state_rows]
        metadata["world_state_consolidation"] = {"source": self.VERSION}
        entity.metadata_json = metadata

    def _apply_noncharacter(self, *, entity: Entity, baseline: Any, states: list[Any]) -> None:
        persistent_traits = {}
        if baseline is not None:
            for key in baseline.__table__.columns.keys():
                if key in {"id", "book_id", "entity_id", "created_at", "updated_at", "evidence_excerpt", "source_scene_json"}:
                    continue
                persistent_traits[key] = self._clean(getattr(baseline, key))
        entity.first_appearance_profile = {
            **(dict(entity.first_appearance_profile or {}) if isinstance(entity.first_appearance_profile, dict) else {}),
            "persistent_traits": persistent_traits,
            "status": "captured" if any(value != UNKNOWN_TEXT for value in persistent_traits.values()) else "sparse",
            "agent_version": self.VERSION,
        }
        entity.latest_world_state = {
            **(dict(entity.latest_world_state or {}) if isinstance(entity.latest_world_state, dict) else {}),
            "persistent_traits": persistent_traits,
            "agent_version": self.VERSION,
        }

    def _apply_object(self, *, entity: Entity, baseline: ObjectVisualBaseline | None, states: list[ObjectSceneState]) -> None:
        self._apply_noncharacter(entity=entity, baseline=baseline, states=states)
        state_rows = []
        latest_state = {}
        for row in states:
            payload = {
                "chapter_index": int(row.chapter_index or 0),
                "scene_index": int(row.scene_index or 0),
                "scene_id": str(row.scene_id or "").strip(),
                "owner_or_holder": self._clean(row.owner_or_holder),
                "activation_state": self._clean(row.activation_state),
                "damage_state": self._clean(row.damage_state),
                "location_context": self._clean(row.location_context),
                "contained_contents": self._clean(row.contained_contents),
                "temporary_effects": self._clean(row.temporary_effects),
            }
            state_rows.append(payload)
            latest_state = {key: value for key, value in payload.items() if value and key not in {"chapter_index", "scene_index", "scene_id"}}
        world_state = dict(entity.latest_world_state or {}) if isinstance(entity.latest_world_state, dict) else {}
        world_state["current_object_state"] = latest_state
        world_state["scene_state_count"] = len(state_rows)
        entity.latest_world_state = world_state
        entity.visual_change_log = state_rows
        metadata = dict(entity.metadata_json or {})
        metadata["scene_visual_states"] = [{"chapter_index": row["chapter_index"], "scene_index": row["scene_index"], "scene_id": row["scene_id"], "state": row} for row in state_rows]
        entity.metadata_json = metadata

    def _apply_location(self, *, entity: Entity, baseline: LocationVisualBaseline | None, states: list[LocationSceneState]) -> None:
        self._apply_noncharacter(entity=entity, baseline=baseline, states=states)
        state_rows = []
        latest_state = {}
        for row in states:
            payload = {
                "chapter_index": int(row.chapter_index or 0),
                "scene_index": int(row.scene_index or 0),
                "scene_id": str(row.scene_id or "").strip(),
                "lighting_current": self._clean(row.lighting_current),
                "weather_current": self._clean(row.weather_current),
                "occupancy_state": self._clean(row.occupancy_state),
                "damage_state": self._clean(row.damage_state),
                "temporary_setup": self._clean(row.temporary_setup),
                "atmosphere_shift": self._clean(row.atmosphere_shift),
                "active_effects": self._clean(row.active_effects),
            }
            state_rows.append(payload)
            latest_state = {key: value for key, value in payload.items() if value and key not in {"chapter_index", "scene_index", "scene_id"}}
        world_state = dict(entity.latest_world_state or {}) if isinstance(entity.latest_world_state, dict) else {}
        world_state["current_location_state"] = latest_state
        world_state["scene_state_count"] = len(state_rows)
        entity.latest_world_state = world_state
        entity.visual_change_log = state_rows
        metadata = dict(entity.metadata_json or {})
        metadata["scene_visual_states"] = [{"chapter_index": row["chapter_index"], "scene_index": row["scene_index"], "scene_id": row["scene_id"], "state": row} for row in state_rows]
        entity.metadata_json = metadata

    def _clean(self, value: Any) -> str:
        cleaned = " ".join(str(value or "").strip().split())
        return cleaned or UNKNOWN_TEXT
