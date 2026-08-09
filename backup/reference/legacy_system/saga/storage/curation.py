from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from .models import (
    Book,
    CharacterVisualBaseline,
    CharacterVisualSceneState,
    CreatureVisualBaseline,
    Entity,
    LocationVisualBaseline,
    LocationSceneState,
    ObjectVisualBaseline,
    ObjectSceneState,
    CharacterProfile,
    StableCharacterState,
)
from .persistence import SagaSQLiteStore


PLACEHOLDER_VALUES = {
    "",
    "n/a",
    "none",
    "null",
    "unknown",
    "not_explicitly_stated_in_text",
}

GENERIC_LOCATION_NAMES = {
    "bakery",
    "back door",
    "classroom",
    "clearing",
    "corridor",
    "cupboard",
    "fireplace",
    "front door",
    "harbor",
    "kitchen",
    "lake",
    "number",
    "privet",
    "rock",
    "second bedroom",
    "staffroom",
    "unused",
    "various",
}

CHARACTER_TO_TYPE_REMAP = {
    "hogwarts": ("Hogwarts", "organization"),
    "hufflepuff": ("Hufflepuff", "organization"),
    "slytherin": ("Slytherin", "organization"),
    "quidditch": ("Quidditch", "other"),
    "add norbert": ("Norbert", "creature"),
    "the gryffindor": ("Gryffindor", "organization"),
}

CHARACTER_MERGES = {
    "mr dursley": "Vernon Dursley",
    "uncle vernon": "Vernon Dursley",
}


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in PLACEHOLDER_VALUES else text


def _unique_parts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _string_list(values: list[str], *, limit: int = 8) -> str:
    parts = _unique_parts(values)
    return ", ".join(parts[:limit])


def _typed_list_map(raw: dict[str, Any], groups: dict[str, list[str]]) -> dict[str, list[str]]:
    payload: dict[str, list[str]] = {}
    for label, keys in groups.items():
        parts = _unique_parts([raw.get(key) for key in keys])
        if parts:
            payload[label] = parts
    return payload


def _status_for(parts_count: int) -> str:
    if parts_count >= 5:
        return "grounded"
    if parts_count >= 2:
        return "partial"
    if parts_count >= 1:
        return "minimal"
    return "empty"


@dataclass
class CurationStats:
    books_processed: int = 0
    entities_curated: int = 0
    entities_deleted: int = 0
    entities_merged: int = 0
    entities_retyped: int = 0


class SagaAnalysisCurator:
    """Curate noisy SQLite analysis rows into cleaner dashboard-ready output."""

    def __init__(self, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()

    def curate_all_books(self) -> CurationStats:
        stats = CurationStats()
        with self.sqlite_store.session_factory() as session:
            books = session.execute(select(Book).order_by(Book.created_at.asc())).scalars().all()
            for book in books:
                self._curate_book(session, book, stats)
            session.commit()
        return stats

    def curate_book(self, book_id: str) -> CurationStats:
        stats = CurationStats()
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            if book is None:
                return stats
            self._curate_book(session, book, stats)
            session.commit()
        return stats

    def _curate_book(self, session, book: Book, stats: CurationStats) -> None:
        stats.books_processed += 1
        entities = session.execute(select(Entity).where(Entity.book_id == book.id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())).scalars().all()
        entity_map = {(str(row.canonical_name or "").strip().lower(), str(row.entity_type or "").strip().lower()): row for row in entities}

        for row in list(entities):
            if str(row.entity_type or "").strip().lower() != "character":
                continue
            lowered = str(row.canonical_name or "").strip().lower()
            if lowered in CHARACTER_MERGES:
                target_name = CHARACTER_MERGES[lowered]
                target = entity_map.get((target_name.lower(), "character"))
                if target is not None and target.id != row.id:
                    self._merge_entities(target, row)
                    self._reassign_entity_references(session, source_id=row.id, target_id=target.id)
                    session.delete(row)
                    stats.entities_deleted += 1
                    stats.entities_merged += 1
                    continue
            if lowered in CHARACTER_TO_TYPE_REMAP:
                new_name, new_type = CHARACTER_TO_TYPE_REMAP[lowered]
                target = entity_map.get((new_name.lower(), new_type))
                if target is not None and target.id != row.id:
                    self._merge_entities(target, row)
                    self._reassign_entity_references(session, source_id=row.id, target_id=target.id)
                    session.delete(row)
                    stats.entities_deleted += 1
                    stats.entities_merged += 1
                    continue
                row.canonical_name = new_name
                row.entity_type = new_type
                stats.entities_retyped += 1

        session.flush()
        entities = session.execute(select(Entity).where(Entity.book_id == book.id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())).scalars().all()
        baseline_lookup = self._load_baseline_lookup(session, book.id)

        for row in list(entities):
            if self._should_drop_generic_row(row):
                session.delete(row)
                stats.entities_deleted += 1
                continue
            self._hydrate_entity_summaries(row, baseline_lookup.get(row.id))
            stats.entities_curated += 1

    def _load_baseline_lookup(self, session, book_id: str) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for model, kind in [
            (CharacterVisualBaseline, "character"),
            (CreatureVisualBaseline, "creature"),
            (ObjectVisualBaseline, "object"),
            (LocationVisualBaseline, "location"),
        ]:
            for row in session.execute(select(model).where(model.book_id == book_id)).scalars().all():
                data = {key: value for key, value in row.__dict__.items() if not key.startswith("_")}
                data["_kind"] = kind
                lookup[str(row.entity_id)] = data
        return lookup

    def _should_drop_generic_row(self, row: Entity) -> bool:
        name = str(row.canonical_name or "").strip().lower()
        entity_type = str(row.entity_type or "").strip().lower()
        mentions = int(row.mention_count or 0)
        if entity_type == "location" and mentions <= 1 and name in GENERIC_LOCATION_NAMES:
            return True
        return False

    def _merge_entities(self, target: Entity, source: Entity) -> None:
        target.mention_count = int(target.mention_count or 0) + int(source.mention_count or 0)
        target.entity_context = _string_list([target.entity_context, source.entity_context], limit=3)
        target.descriptions = self._merge_lists(target.descriptions, source.descriptions)
        target.state_changes = self._merge_lists(target.state_changes, source.state_changes)
        target.event_links = self._merge_lists(target.event_links, source.event_links)
        target.visual_change_log = self._merge_lists(target.visual_change_log, source.visual_change_log)
        if self._scene_sort_key(source) < self._scene_sort_key(target):
            target.first_seen_book_index = source.first_seen_book_index
            target.first_seen_chapter_index = source.first_seen_chapter_index
            target.first_seen_scene_index = source.first_seen_scene_index
        if not isinstance(target.initial_physical_description, dict) and isinstance(source.initial_physical_description, dict):
            target.initial_physical_description = source.initial_physical_description
        if not isinstance(target.first_appearance_profile, dict) and isinstance(source.first_appearance_profile, dict):
            target.first_appearance_profile = source.first_appearance_profile
        if not isinstance(target.typed_attributes, dict) and isinstance(source.typed_attributes, dict):
            target.typed_attributes = source.typed_attributes

    def _scene_sort_key(self, row: Entity) -> tuple[int, int, int]:
        return (
            int(row.first_seen_book_index or 999999),
            int(row.first_seen_chapter_index or 999999),
            int(row.first_seen_scene_index or 999999),
        )

    def _merge_lists(self, left: Any, right: Any) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for bucket in [left, right]:
            if not isinstance(bucket, list):
                continue
            for item in bucket:
                key = repr(item)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        return merged

    def _hydrate_entity_summaries(self, row: Entity, baseline: dict[str, Any] | None) -> None:
        entity_type = str(row.entity_type or "").strip().lower()
        if entity_type == "character":
            self._hydrate_character(row, baseline or {})
            return
        if entity_type == "creature":
            self._hydrate_creature(row, baseline or {})
            return
        if entity_type == "object":
            self._hydrate_object(row, baseline or {})
            return
        if entity_type == "location":
            self._hydrate_location(row, baseline or {})
            return
        row.initial_physical_description = {"status": "n/a", "description": _clean_text(row.entity_context)}
        row.first_appearance_profile = {"status": "n/a", "baseline_description": _clean_text(row.entity_context)}

    def _hydrate_character(self, row: Entity, baseline: dict[str, Any]) -> None:
        seed = dict((row.first_appearance_profile or {}).get("persistent_traits") or {})
        seed.update(dict((row.initial_physical_description or {}).get("baseline_visual_fields") or {}))
        raw = {
            "gender_presentation": baseline.get("gender_presentation") or seed.get("gender_presentation"),
            "species_or_race": baseline.get("species_or_race") or seed.get("species_or_race"),
            "apparent_age_group": baseline.get("apparent_age_group") or seed.get("apparent_age_group"),
            "height_impression": baseline.get("height_impression") or seed.get("height_impression"),
            "build": baseline.get("build") or seed.get("build"),
            "skin_tone_or_complexion": baseline.get("skin_tone_or_complexion") or seed.get("skin_tone_or_complexion"),
            "hair_color": baseline.get("hair_color") or seed.get("hair_color"),
            "hair_length_or_style": baseline.get("hair_length_or_style") or seed.get("hair_length_or_style"),
            "eye_color": baseline.get("eye_color") or seed.get("eye_color"),
            "facial_features": baseline.get("facial_features") or seed.get("facial_features"),
            "distinguishing_marks": baseline.get("distinguishing_marks") or seed.get("distinguishing_marks"),
            "default_clothing_style": baseline.get("default_clothing_style") or seed.get("default_clothing_style"),
            "default_accessories": baseline.get("default_accessories") or seed.get("default_accessories"),
            "default_footwear": baseline.get("default_footwear") or seed.get("default_footwear"),
            "signature_items": baseline.get("signature_items") or seed.get("signature_items"),
            "fantasy_features": baseline.get("fantasy_features") or seed.get("fantasy_features"),
            "world_genre_cues": baseline.get("world_genre_cues") or seed.get("world_genre_cues"),
        }
        description = _string_list([
            raw["gender_presentation"],
            raw["species_or_race"],
            raw["apparent_age_group"],
            raw["height_impression"],
            raw["build"],
            raw["skin_tone_or_complexion"],
            raw["hair_color"],
            raw["hair_length_or_style"],
            raw["eye_color"],
            raw["facial_features"],
            raw["distinguishing_marks"],
        ], limit=7)
        baseline_description = _string_list([
            description,
            raw["default_clothing_style"],
            raw["default_accessories"],
            raw["default_footwear"],
            raw["signature_items"],
            raw["fantasy_features"],
            raw["world_genre_cues"],
        ], limit=9)
        typed = _typed_list_map(raw, {
            "appearance": [
                "gender_presentation",
                "species_or_race",
                "apparent_age_group",
                "height_impression",
                "build",
                "skin_tone_or_complexion",
                "hair_color",
                "hair_length_or_style",
                "eye_color",
                "facial_features",
                "distinguishing_marks",
            ],
            "outfit": [
                "default_clothing_style",
                "default_accessories",
                "default_footwear",
                "signature_items",
            ],
            "fantasy_features": [
                "fantasy_features",
                "world_genre_cues",
            ],
        })
        status = _status_for(sum(len(values) for values in typed.values()))
        row.initial_physical_description = {
            "status": status,
            "description": description,
            "baseline_visual_fields": raw,
            "evidence_excerpt": _clean_text(baseline.get("evidence_excerpt")),
        }
        row.first_appearance_profile = {
            "status": status,
            "baseline_description": baseline_description or description,
            "persistent_traits": raw,
            "typed_attributes": typed,
            "source": baseline.get("source_scene_json") or [],
        }
        row.typed_attributes = typed
        row.metadata_json = self._clean_scene_state_metadata(row.metadata_json)

    def _hydrate_creature(self, row: Entity, baseline: dict[str, Any]) -> None:
        seed = dict((row.first_appearance_profile or {}).get("persistent_traits") or {})
        seed.update(dict((row.initial_physical_description or {}).get("baseline_visual_fields") or {}))
        raw = {
            "species_kind": baseline.get("species_kind") or seed.get("species_kind") or seed.get("species_or_race"),
            "size_class": baseline.get("size_class") or seed.get("size_class") or seed.get("height_impression"),
            "body_plan": baseline.get("body_plan") or seed.get("body_plan") or seed.get("build"),
            "surface_covering": baseline.get("surface_covering") or seed.get("surface_covering"),
            "coloration": baseline.get("coloration") or seed.get("coloration") or seed.get("skin_tone_or_complexion"),
            "head_features": baseline.get("head_features") or seed.get("head_features") or seed.get("facial_features"),
            "eyes": baseline.get("eyes") or seed.get("eyes") or seed.get("eye_color"),
            "limbs_appendages": baseline.get("limbs_appendages") or seed.get("limbs_appendages"),
            "natural_weapons": baseline.get("natural_weapons") or seed.get("natural_weapons"),
            "wings": baseline.get("wings") or seed.get("wings"),
            "tail": baseline.get("tail") or seed.get("tail"),
            "magical_features": baseline.get("magical_features") or seed.get("magical_features") or seed.get("fantasy_features"),
            "world_genre_cues": baseline.get("world_genre_cues") or seed.get("world_genre_cues"),
        }
        description = _string_list([
            raw["species_kind"],
            raw["size_class"],
            raw["body_plan"],
            raw["surface_covering"],
            raw["coloration"],
            raw["head_features"],
            raw["eyes"],
            raw["natural_weapons"],
            raw["magical_features"],
        ], limit=8)
        typed = _typed_list_map(raw, {
            "appearance": [
                "species_kind",
                "size_class",
                "body_plan",
                "surface_covering",
                "coloration",
                "head_features",
                "eyes",
                "limbs_appendages",
                "natural_weapons",
                "wings",
                "tail",
            ],
            "fantasy_features": ["magical_features", "world_genre_cues"],
        })
        status = _status_for(sum(len(values) for values in typed.values()))
        row.initial_physical_description = {
            "status": status,
            "description": description,
            "baseline_visual_fields": raw,
            "evidence_excerpt": _clean_text(baseline.get("evidence_excerpt")),
        }
        row.first_appearance_profile = {
            "status": status,
            "baseline_description": description,
            "persistent_traits": raw,
            "typed_attributes": typed,
            "source": baseline.get("source_scene_json") or [],
        }
        row.typed_attributes = typed

    def _hydrate_object(self, row: Entity, baseline: dict[str, Any]) -> None:
        seed = dict((row.first_appearance_profile or {}).get("persistent_traits") or {})
        seed.update(dict((row.initial_physical_description or {}).get("baseline_visual_fields") or {}))
        raw = {
            "object_class": baseline.get("object_class") or seed.get("object_class"),
            "function": baseline.get("function") or seed.get("function"),
            "size_scale": baseline.get("size_scale") or seed.get("size_scale"),
            "shape_form": baseline.get("shape_form") or seed.get("shape_form"),
            "primary_material": baseline.get("primary_material") or seed.get("primary_material"),
            "secondary_materials": baseline.get("secondary_materials") or seed.get("secondary_materials"),
            "color_finish": baseline.get("color_finish") or seed.get("color_finish"),
            "surface_texture": baseline.get("surface_texture") or seed.get("surface_texture"),
            "condition_default": baseline.get("condition_default") or seed.get("condition_default"),
            "symbolic_markings": baseline.get("symbolic_markings") or seed.get("symbolic_markings"),
            "magical_properties": baseline.get("magical_properties") or seed.get("magical_properties"),
            "world_genre_cues": baseline.get("world_genre_cues") or seed.get("world_genre_cues"),
        }
        description = _string_list([
            raw["object_class"],
            raw["function"],
            raw["size_scale"],
            raw["shape_form"],
            raw["primary_material"],
            raw["color_finish"],
            raw["surface_texture"],
            raw["magical_properties"],
        ], limit=8)
        typed = _typed_list_map(raw, {
            "appearance": [
                "object_class",
                "size_scale",
                "shape_form",
                "primary_material",
                "secondary_materials",
                "color_finish",
                "surface_texture",
                "condition_default",
                "symbolic_markings",
            ],
            "function": ["function", "magical_properties", "world_genre_cues"],
        })
        status = _status_for(sum(len(values) for values in typed.values()))
        row.initial_physical_description = {
            "status": status,
            "description": description,
            "baseline_visual_fields": raw,
            "evidence_excerpt": _clean_text(baseline.get("evidence_excerpt")),
        }
        row.first_appearance_profile = {
            "status": status,
            "baseline_description": description,
            "persistent_traits": raw,
            "typed_attributes": typed,
            "source": baseline.get("source_scene_json") or [],
        }
        row.typed_attributes = typed

    def _hydrate_location(self, row: Entity, baseline: dict[str, Any]) -> None:
        seed = dict((row.first_appearance_profile or {}).get("persistent_traits") or {})
        seed.update(dict((row.initial_physical_description or {}).get("baseline_visual_fields") or {}))
        raw = {
            "location_class": baseline.get("location_class") or seed.get("location_class"),
            "indoor_outdoor": baseline.get("indoor_outdoor") or seed.get("indoor_outdoor"),
            "environment_type": baseline.get("environment_type") or seed.get("environment_type"),
            "region_or_domain": baseline.get("region_or_domain") or seed.get("region_or_domain"),
            "architecture_or_terrain_style": baseline.get("architecture_or_terrain_style") or seed.get("architecture_or_terrain_style"),
            "dominant_materials": baseline.get("dominant_materials") or seed.get("dominant_materials"),
            "lighting_default": baseline.get("lighting_default") or seed.get("lighting_default"),
            "weather_exposure": baseline.get("weather_exposure") or seed.get("weather_exposure"),
            "ambient_mood": baseline.get("ambient_mood") or seed.get("ambient_mood"),
            "notable_features": baseline.get("notable_features") or seed.get("notable_features"),
            "magic_or_tech_presence": baseline.get("magic_or_tech_presence") or seed.get("magic_or_tech_presence"),
            "world_genre_cues": baseline.get("world_genre_cues") or seed.get("world_genre_cues"),
        }
        description = _string_list([
            raw["location_class"],
            raw["indoor_outdoor"],
            raw["environment_type"],
            raw["region_or_domain"],
            raw["architecture_or_terrain_style"],
            raw["ambient_mood"],
            raw["notable_features"],
        ], limit=8)
        typed = _typed_list_map(raw, {
            "setting": [
                "location_class",
                "indoor_outdoor",
                "environment_type",
                "region_or_domain",
                "architecture_or_terrain_style",
                "dominant_materials",
            ],
            "atmosphere": [
                "lighting_default",
                "weather_exposure",
                "ambient_mood",
                "notable_features",
                "magic_or_tech_presence",
                "world_genre_cues",
            ],
        })
        status = _status_for(sum(len(values) for values in typed.values()))
        row.initial_physical_description = {
            "status": status,
            "description": description,
            "baseline_visual_fields": raw,
            "evidence_excerpt": _clean_text(baseline.get("evidence_excerpt")),
        }
        row.first_appearance_profile = {
            "status": status,
            "baseline_description": description,
            "persistent_traits": raw,
            "typed_attributes": typed,
            "source": baseline.get("source_scene_json") or [],
        }
        row.typed_attributes = typed

    def _clean_scene_state_metadata(self, metadata: Any) -> dict[str, Any]:
        payload = dict(metadata or {}) if isinstance(metadata, dict) else {}
        rows = payload.get("scene_visual_states")
        if not isinstance(rows, list):
            return payload
        cleaned_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cleaned = {}
            for key, value in row.items():
                if key in {"chapter_index", "scene_index", "scene_id"}:
                    cleaned[key] = value
                    continue
                if _clean_text(value):
                    cleaned[key] = value
            if len(cleaned) > 3:
                cleaned_rows.append(cleaned)
        payload["scene_visual_states"] = cleaned_rows
        return payload

    def _reassign_entity_references(self, session, *, source_id: str, target_id: str) -> None:
        for model in [CharacterVisualBaseline, CreatureVisualBaseline, ObjectVisualBaseline, LocationVisualBaseline]:
            row = session.execute(select(model).where(model.entity_id == source_id)).scalars().first()
            if row is not None:
                session.delete(row)
        for model in [CharacterVisualSceneState, ObjectSceneState, LocationSceneState]:
            rows = session.execute(select(model).where(model.entity_id == source_id)).scalars().all()
            for row in rows:
                row.entity_id = target_id
        for model in [CharacterProfile, StableCharacterState]:
            rows = session.execute(select(model).where(model.entity_id == source_id)).scalars().all()
            for row in rows:
                row.entity_id = target_id
