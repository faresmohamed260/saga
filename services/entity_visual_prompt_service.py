from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from analysis.visual_prompt_schema import (
    DEFAULT_MODEST_CLOTHING,
    compile_character_turnaround_prompt,
    compile_entity_concept_prompt,
    compile_location_concept_prompt,
    normalize_persistent_profile,
)
from sql_store.models import (
    Book,
    CharacterVisualBaseline,
    CreatureVisualBaseline,
    Entity,
    LocationVisualBaseline,
    ObjectVisualBaseline,
    VisualPrompt,
)
from sql_store.persistence import SagaSQLiteStore


@dataclass(slots=True)
class PromptBuildResult:
    book_id: str
    total_entities: int
    prompts_written: int
    prompts_updated: int
    prompts_skipped: int
    prompts_total: int


class EntityVisualPromptService:
    """Build one stored baseline visual prompt per DB entity."""

    PLACEHOLDER_VALUES = {"", "not_explicitly_stated_in_text", "none", "unknown", "n/a"}

    def __init__(self, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()

    def build_book_prompts(self, book_ref: str, *, overwrite: bool = False) -> PromptBuildResult:
        book_id = self._parse_book_ref(book_ref)
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            if book is None:
                raise ValueError(f"Book not found for visual prompt build: {book_ref}")

            entities = session.execute(
                select(Entity).where(Entity.book_id == book.id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
            ).scalars().all()
            prompt_map = {
                (str(row.entity_id or ""), str(row.prompt_type or "").strip().lower()): row
                for row in session.execute(select(VisualPrompt).where(VisualPrompt.book_id == book.id)).scalars().all()
            }
            char_map = {
                row.entity_id: row
                for row in session.execute(select(CharacterVisualBaseline).where(CharacterVisualBaseline.book_id == book.id)).scalars().all()
            }
            creature_map = {
                row.entity_id: row
                for row in session.execute(select(CreatureVisualBaseline).where(CreatureVisualBaseline.book_id == book.id)).scalars().all()
            }
            object_map = {
                row.entity_id: row
                for row in session.execute(select(ObjectVisualBaseline).where(ObjectVisualBaseline.book_id == book.id)).scalars().all()
            }
            location_map = {
                row.entity_id: row
                for row in session.execute(select(LocationVisualBaseline).where(LocationVisualBaseline.book_id == book.id)).scalars().all()
            }

            written = 0
            updated = 0
            skipped = 0
            for entity in entities:
                compiled = self._build_entity_prompt_payload(
                    entity=entity,
                    character_baseline=char_map.get(entity.id),
                    creature_baseline=creature_map.get(entity.id),
                    object_baseline=object_map.get(entity.id),
                    location_baseline=location_map.get(entity.id),
                )
                if not compiled:
                    skipped += 1
                    continue
                prompt_type = str(compiled["prompt_type"]).lower()
                prompt_row = prompt_map.get((entity.id, prompt_type))
                if prompt_row is None:
                    prompt_row = VisualPrompt(
                        book_id=book.id,
                        entity_id=entity.id,
                        entity_name=entity.canonical_name,
                        entity_type=entity.entity_type,
                        prompt_type=compiled["prompt_type"],
                    )
                    session.add(prompt_row)
                    written += 1
                elif not overwrite and str(prompt_row.positive_prompt or "").strip():
                    skipped += 1
                    continue
                else:
                    updated += 1

                prompt_row.visual_bucket = compiled["visual_bucket"]
                prompt_row.positive_prompt = compiled["positive_prompt"]
                prompt_row.negative_prompt = compiled["negative_prompt"]
                prompt_row.source_evidence = compiled["source_evidence"]
                prompt_row.confidence = compiled["confidence"]
                prompt_row.book_index = entity.first_seen_book_index
                prompt_row.chapter_index = entity.first_seen_chapter_index
                prompt_row.scene_index = entity.first_seen_scene_index
                prompt_row.details_json = compiled["details"]
                prompt_row.metadata_json = {"origin": "entity_visual_prompt_service"}
                entity.baseline_visual_prompt = compiled["positive_prompt"]

            session.commit()
            prompts_total = len(session.execute(select(VisualPrompt).where(VisualPrompt.book_id == book.id)).scalars().all())
            return PromptBuildResult(
                book_id=book.id,
                total_entities=len(entities),
                prompts_written=written,
                prompts_updated=updated,
                prompts_skipped=skipped,
                prompts_total=prompts_total,
            )

    def _parse_book_ref(self, book_ref: str) -> str:
        text = str(book_ref or "").strip()
        if text.startswith("db://book/"):
            return text.split("db://book/", 1)[-1].strip()
        return text

    def _build_entity_prompt_payload(
        self,
        *,
        entity: Entity,
        character_baseline: CharacterVisualBaseline | None,
        creature_baseline: CreatureVisualBaseline | None,
        object_baseline: ObjectVisualBaseline | None,
        location_baseline: LocationVisualBaseline | None,
    ) -> dict[str, Any] | None:
        entity_type = str(entity.entity_type or "").strip().lower() or "other"
        if entity_type == "character":
            return self._build_character_prompt(entity, character_baseline)
        if entity_type == "creature":
            return self._build_creature_prompt(entity, creature_baseline)
        if entity_type == "object":
            return self._build_object_prompt(entity, object_baseline)
        if entity_type == "location":
            return self._build_location_prompt(entity, location_baseline)
        return self._build_generic_prompt(entity)

    def _build_character_prompt(self, entity: Entity, baseline: CharacterVisualBaseline | None) -> dict[str, Any] | None:
        traits = (entity.first_appearance_profile or {}).get("persistent_traits") or {}
        source_evidence = self._baseline_description(entity, baseline.evidence_excerpt if baseline else "")
        model_safe_identity = self._join_nonempty(
            self._clean_slot((baseline.gender_presentation if baseline else "") or traits.get("gender_presentation") or ""),
            self._clean_slot((baseline.species_or_race if baseline else "") or traits.get("species_or_race") or ""),
            self._role_line(entity),
        )
        presence_description = self._join_nonempty(
            baseline.apparent_age_group if baseline else "",
            baseline.height_impression if baseline else "",
            baseline.build if baseline else "",
            baseline.facial_features if baseline else "",
            self._role_line(entity),
        ) or self._summarize_character_presence(source_evidence)
        profile = normalize_persistent_profile(
            {
                "gender_presentation": self._clean_slot((baseline.gender_presentation if baseline else "") or traits.get("gender_presentation") or ""),
                "species_or_race": self._clean_slot((baseline.species_or_race if baseline else "") or traits.get("species_or_race") or ""),
                "role_or_archetype": self._role_line(entity),
                "model_safe_identity": model_safe_identity,
                "world_aesthetic_cues": self._clean_slot((baseline.world_genre_cues if baseline else "") or traits.get("world_genre_cues") or ""),
                "presence_description": presence_description,
                "height_description": self._clean_slot((baseline.height_impression if baseline else "") or traits.get("height_impression") or ""),
                "body_type": self._clean_slot((baseline.build if baseline else "") or traits.get("build") or ""),
                "skin_description": self._clean_slot((baseline.skin_tone_or_complexion if baseline else "") or traits.get("skin_tone_or_complexion") or ""),
                "hair_description": self._join_nonempty(
                    baseline.hair_color if baseline else "",
                    baseline.hair_length_or_style if baseline else "",
                    traits.get("hair_color"),
                    traits.get("hair_length_or_style"),
                ),
                "eye_description": self._clean_slot((baseline.eye_color if baseline else "") or traits.get("eye_color") or ""),
                "facial_structure": self._clean_slot((baseline.facial_features if baseline else "") or traits.get("facial_features") or ""),
                "age_appearance": self._clean_slot((baseline.apparent_age_group if baseline else "") or traits.get("apparent_age_group") or ""),
                "expression": "neutral expression",
                "clothing_description": self._clean_slot((baseline.default_clothing_style if baseline else "") or traits.get("default_clothing_style") or DEFAULT_MODEST_CLOTHING),
                "footwear_description": self._clean_slot((baseline.default_footwear if baseline else "") or traits.get("default_footwear") or ""),
                "accessories_description": self._clean_slot((baseline.default_accessories if baseline else "") or traits.get("default_accessories") or ""),
                "distinguishing_marks": self._clean_slot((baseline.distinguishing_marks if baseline else "") or traits.get("distinguishing_marks") or ""),
                "fantasy_features": self._clean_slot((baseline.fantasy_features if baseline else "") or traits.get("fantasy_features") or ""),
                "equipment_or_signature_items": self._clean_slot((baseline.signature_items if baseline else "") or traits.get("signature_items") or ""),
            }
        )
        prompt = compile_character_turnaround_prompt(profile, display_name=entity.canonical_name)
        if not prompt:
            return None
        return {
            "prompt_type": "initial_character_description",
            "visual_bucket": "initial_characters",
            "positive_prompt": prompt,
            "negative_prompt": "",
            "source_evidence": source_evidence,
            "confidence": self._confidence_from_fields(
                [
                    profile.get("presence_description"),
                    profile.get("hair_description"),
                    profile.get("eye_description"),
                    profile.get("body_type"),
                    profile.get("clothing_description"),
                    profile.get("distinguishing_marks"),
                    profile.get("fantasy_features"),
                ]
            ),
            "details": {
                "source_table": "character_visual_baselines" if baseline else "entities",
                "persistent_visual_profile": profile,
                "baseline_description": source_evidence,
            },
        }

    def _build_creature_prompt(self, entity: Entity, baseline: CreatureVisualBaseline | None) -> dict[str, Any] | None:
        baseline_description = self._join_nonempty(
            baseline.species_kind if baseline else "",
            baseline.size_class if baseline else "",
            baseline.body_plan if baseline else "",
            baseline.surface_covering if baseline else "",
            baseline.coloration if baseline else "",
            baseline.head_features if baseline else "",
            baseline.eyes if baseline else "",
            baseline.limbs_appendages if baseline else "",
            baseline.natural_weapons if baseline else "",
            baseline.wings if baseline else "",
            baseline.tail if baseline else "",
            baseline.magical_features if baseline else "",
        )
        if len(baseline_description.split()) < 6:
            baseline_description = self._join_nonempty(
                baseline_description,
                self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            )
        current_state = self._join_nonempty(
            self._latest_state_summary(entity),
            self._recent_visual_change_summary(entity),
        )
        prompt = compile_entity_concept_prompt(
            display_name=entity.canonical_name,
            entity_type="creature",
            baseline_description=baseline_description,
            current_state=current_state,
            owner_or_associated_characters=self._associated_characters(entity),
        )
        if not prompt:
            return None
        return self._noncharacter_payload(
            entity=entity,
            prompt_type="initial_creature_description",
            visual_bucket="objects_creatures",
            prompt=prompt,
            source_table="creature_visual_baselines" if baseline else "entities",
            source_evidence=self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            baseline_description=baseline_description,
            current_state=current_state,
            typed_fields=self._compact_dict(
                {
                    "species_kind": baseline.species_kind if baseline else "",
                    "size_class": baseline.size_class if baseline else "",
                    "body_plan": baseline.body_plan if baseline else "",
                    "surface_covering": baseline.surface_covering if baseline else "",
                    "coloration": baseline.coloration if baseline else "",
                    "head_features": baseline.head_features if baseline else "",
                    "eyes": baseline.eyes if baseline else "",
                    "limbs_appendages": baseline.limbs_appendages if baseline else "",
                    "natural_weapons": baseline.natural_weapons if baseline else "",
                    "wings": baseline.wings if baseline else "",
                    "tail": baseline.tail if baseline else "",
                    "magical_features": baseline.magical_features if baseline else "",
                    "world_genre_cues": baseline.world_genre_cues if baseline else "",
                }
            ),
        )

    def _build_object_prompt(self, entity: Entity, baseline: ObjectVisualBaseline | None) -> dict[str, Any] | None:
        baseline_description = self._join_nonempty(
            baseline.object_class if baseline else "",
            baseline.function if baseline else "",
            baseline.size_scale if baseline else "",
            baseline.shape_form if baseline else "",
            baseline.primary_material if baseline else "",
            baseline.secondary_materials if baseline else "",
            baseline.color_finish if baseline else "",
            baseline.surface_texture if baseline else "",
            baseline.condition_default if baseline else "",
            baseline.symbolic_markings if baseline else "",
            baseline.magical_properties if baseline else "",
        )
        if len(baseline_description.split()) < 5:
            baseline_description = self._join_nonempty(
                baseline_description,
                self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            )
        current_state = self._join_nonempty(
            self._latest_state_summary(entity),
            self._recent_visual_change_summary(entity),
        )
        prompt = compile_entity_concept_prompt(
            display_name=entity.canonical_name,
            entity_type="object",
            baseline_description=baseline_description,
            current_state=current_state,
            owner_or_associated_characters=self._associated_characters(entity),
        )
        if not prompt:
            return None
        return self._noncharacter_payload(
            entity=entity,
            prompt_type="initial_object_description",
            visual_bucket="objects_creatures",
            prompt=prompt,
            source_table="object_visual_baselines" if baseline else "entities",
            source_evidence=self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            baseline_description=baseline_description,
            current_state=current_state,
            typed_fields=self._compact_dict(
                {
                    "object_class": baseline.object_class if baseline else "",
                    "function": baseline.function if baseline else "",
                    "size_scale": baseline.size_scale if baseline else "",
                    "shape_form": baseline.shape_form if baseline else "",
                    "primary_material": baseline.primary_material if baseline else "",
                    "secondary_materials": baseline.secondary_materials if baseline else "",
                    "color_finish": baseline.color_finish if baseline else "",
                    "surface_texture": baseline.surface_texture if baseline else "",
                    "condition_default": baseline.condition_default if baseline else "",
                    "symbolic_markings": baseline.symbolic_markings if baseline else "",
                    "magical_properties": baseline.magical_properties if baseline else "",
                    "world_genre_cues": baseline.world_genre_cues if baseline else "",
                }
            ),
        )

    def _build_location_prompt(self, entity: Entity, baseline: LocationVisualBaseline | None) -> dict[str, Any] | None:
        baseline_description = self._join_nonempty(
            baseline.location_class if baseline else "",
            baseline.indoor_outdoor if baseline else "",
            baseline.environment_type if baseline else "",
            baseline.region_or_domain if baseline else "",
            baseline.architecture_or_terrain_style if baseline else "",
            baseline.dominant_materials if baseline else "",
            baseline.lighting_default if baseline else "",
            baseline.weather_exposure if baseline else "",
            baseline.ambient_mood if baseline else "",
            baseline.notable_features if baseline else "",
            baseline.magic_or_tech_presence if baseline else "",
        )
        if len(baseline_description.split()) < 6:
            baseline_description = self._join_nonempty(
                baseline_description,
                self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            )
        current_description = self._latest_state_summary(entity)
        atmosphere = self._clean_slot((baseline.ambient_mood if baseline else "") or self._recent_visual_change_summary(entity))
        notable_features = self._split_features(baseline.notable_features if baseline else "")
        damage_state = self._latest_damage_summary(entity)
        prompt = compile_location_concept_prompt(
            display_name=entity.canonical_name,
            baseline_description=baseline_description,
            current_description=current_description,
            atmosphere=atmosphere,
            notable_features=notable_features,
            damage_or_restoration_state=damage_state,
        )
        if not prompt:
            return None
        return self._noncharacter_payload(
            entity=entity,
            prompt_type="initial_location_description",
            visual_bucket="locations",
            prompt=prompt,
            source_table="location_visual_baselines" if baseline else "entities",
            source_evidence=self._baseline_description(entity, baseline.evidence_excerpt if baseline else ""),
            baseline_description=baseline_description,
            current_state=current_description,
            typed_fields=self._compact_dict(
                {
                    "location_class": baseline.location_class if baseline else "",
                    "indoor_outdoor": baseline.indoor_outdoor if baseline else "",
                    "environment_type": baseline.environment_type if baseline else "",
                    "region_or_domain": baseline.region_or_domain if baseline else "",
                    "architecture_or_terrain_style": baseline.architecture_or_terrain_style if baseline else "",
                    "dominant_materials": baseline.dominant_materials if baseline else "",
                    "lighting_default": baseline.lighting_default if baseline else "",
                    "weather_exposure": baseline.weather_exposure if baseline else "",
                    "ambient_mood": baseline.ambient_mood if baseline else "",
                    "notable_features": baseline.notable_features if baseline else "",
                    "magic_or_tech_presence": baseline.magic_or_tech_presence if baseline else "",
                    "world_genre_cues": baseline.world_genre_cues if baseline else "",
                }
            ),
        )

    def _build_generic_prompt(self, entity: Entity) -> dict[str, Any] | None:
        entity_type = str(entity.entity_type or "other").strip().lower()
        baseline_description = self._baseline_description(entity, "") or str(entity.entity_context or "").strip()
        current_state = self._join_nonempty(
            self._latest_state_summary(entity),
            self._recent_visual_change_summary(entity),
        )
        prompt = compile_entity_concept_prompt(
            display_name=entity.canonical_name,
            entity_type=entity_type,
            baseline_description=baseline_description,
            current_state=current_state,
            owner_or_associated_characters=self._associated_characters(entity),
        )
        if not prompt:
            return None
        return self._noncharacter_payload(
            entity=entity,
            prompt_type=f"initial_{entity_type}_description",
            visual_bucket=entity_type,
            prompt=prompt,
            source_table="entities",
            source_evidence=baseline_description,
            baseline_description=baseline_description,
            current_state=current_state,
            typed_fields=self._compact_dict(entity.typed_attributes or {}),
        )

    def _noncharacter_payload(
        self,
        *,
        entity: Entity,
        prompt_type: str,
        visual_bucket: str,
        prompt: str,
        source_table: str,
        source_evidence: str,
        baseline_description: str,
        current_state: str,
        typed_fields: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "prompt_type": prompt_type,
            "visual_bucket": visual_bucket,
            "positive_prompt": prompt,
            "negative_prompt": "",
            "source_evidence": source_evidence,
            "confidence": self._confidence_from_fields([baseline_description, typed_fields]),
            "details": {
                "source_table": source_table,
                "baseline_description": baseline_description,
                "current_state": current_state,
                "typed_visual_fields": typed_fields,
            },
        }

    def _baseline_description(self, entity: Entity, evidence_excerpt: str = "") -> str:
        parts = [
            str(evidence_excerpt or "").strip(),
            str(((entity.initial_physical_description or {}).get("description")) or "").strip(),
            str(((entity.first_appearance_profile or {}).get("baseline_description")) or "").strip(),
            str(entity.entity_context or "").strip(),
        ]
        descriptions = entity.descriptions or []
        if isinstance(descriptions, list):
            parts.extend(str(item.get("description") or "").strip() for item in descriptions if isinstance(item, dict))
        return self._join_nonempty(*parts)

    def _role_line(self, entity: Entity) -> str:
        roles = entity.narrative_roles or []
        if isinstance(roles, list):
            return self._join_nonempty(*(str(item) for item in roles[:3]))
        if isinstance(roles, dict):
            return self._join_nonempty(*(str(value) for value in list(roles.values())[:3]))
        return ""

    def _join_nonempty(self, *values: Any) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            lowered = text.lower()
            if not text or lowered in self.PLACEHOLDER_VALUES:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            parts.append(text)
        return ", ".join(parts)

    def _clean_slot(self, value: Any) -> str:
        text = str(value or "").strip()
        lowered = text.lower()
        if lowered in self.PLACEHOLDER_VALUES:
            return ""
        if lowered.startswith("db_") or "agent_v" in lowered:
            return ""
        return text

    def _compact_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key, value in (payload or {}).items():
            if isinstance(value, dict):
                nested = self._compact_dict(value)
                if nested:
                    compact[key] = nested
                continue
            if isinstance(value, list):
                rows = [
                    str(item).strip()
                    for item in value
                    if str(item or "").strip() and str(item).strip().lower() not in self.PLACEHOLDER_VALUES
                ]
                if rows:
                    compact[key] = rows
                continue
            if str(value or "").strip() and str(value).strip().lower() not in self.PLACEHOLDER_VALUES:
                compact[key] = value
        return compact

    def _confidence_from_fields(self, fields: list[Any]) -> str:
        score = sum(1 for value in fields if str(value or "").strip())
        if score >= 5:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _associated_characters(self, entity: Entity) -> list[str]:
        names: list[str] = []
        for row in entity.event_links or []:
            if not isinstance(row, dict):
                continue
            for key in ("characters_involved", "characters", "participants", "entities_involved"):
                value = row.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            candidate = str(item.get("name") or item.get("entity_name") or "").strip()
                        else:
                            candidate = str(item or "").strip()
                        if candidate:
                            names.append(candidate)
        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            lowered = name.lower()
            if lowered in seen or lowered == str(entity.canonical_name or "").strip().lower():
                continue
            seen.add(lowered)
            deduped.append(name)
        return deduped[:4]

    def _latest_state_summary(self, entity: Entity) -> str:
        latest = entity.latest_world_state or {}
        if not isinstance(latest, dict):
            return ""
        parts: list[str] = []
        for value in latest.values():
            if isinstance(value, dict):
                parts.extend(self._clean_slot(item) for item in value.values())
            elif isinstance(value, list):
                parts.extend(self._clean_slot(item) for item in value)
            else:
                parts.append(self._clean_slot(value))
        return self._join_nonempty(*parts)

    def _recent_visual_change_summary(self, entity: Entity) -> str:
        changes = entity.visual_change_log or []
        if not isinstance(changes, list):
            return ""
        parts: list[str] = []
        for row in changes[-4:]:
            if not isinstance(row, dict):
                continue
            parts.extend(
                self._clean_slot(row.get(key))
                for key in (
                    "scene_outfit",
                    "scene_accessories",
                    "scene_footwear",
                    "visible_condition",
                    "injuries",
                    "damage_state",
                    "activation_state",
                    "temporary_setup",
                    "atmosphere_shift",
                    "active_effects",
                )
            )
        return self._join_nonempty(*parts)

    def _latest_damage_summary(self, entity: Entity) -> str:
        changes = entity.visual_change_log or []
        if not isinstance(changes, list):
            return ""
        for row in reversed(changes):
            if not isinstance(row, dict):
                continue
            for key in ("damage_state", "injuries", "visible_condition"):
                value = self._clean_slot(row.get(key))
                if value:
                    return value
        return ""

    def _split_features(self, value: Any) -> list[str]:
        text = str(value or "").strip()
        if not text or text.lower() in self.PLACEHOLDER_VALUES:
            return []
        parts = [chunk.strip() for chunk in text.replace(";", ",").split(",")]
        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            lowered = part.lower()
            if not part or lowered in self.PLACEHOLDER_VALUES or lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(part)
        return deduped[:5]

    def _summarize_character_presence(self, text: str) -> str:
        if not text:
            return ""
        parts = [chunk.strip() for chunk in text.replace(";", ",").split(",")]
        keep: list[str] = []
        blocked = {
            "standing",
            "walking",
            "watching",
            "carrying",
            "looking",
            "saying",
            "grabbing",
            "holding",
            "running",
            "crouching",
            "shouting",
            "knocking",
            "terrified",
            "behind",
            "toward",
        }
        for part in parts:
            lowered = part.lower()
            if not part or any(token in lowered for token in blocked):
                continue
            keep.append(part)
            if len(keep) >= 4:
                break
        return self._join_nonempty(*keep)
