"""Canonical trait taxonomy for structured canon extraction and SQLite storage."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


ENTITY_TYPES = ("character", "creature", "object", "location")
TRAIT_SCOPES = ("persistent", "dynamic")

PRACTICAL_PERSISTENT_FIELDS: dict[str, list[str]] = {
    "character": [
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
        "default_clothing_style",
        "default_accessories",
        "default_footwear",
        "signature_items",
        "fantasy_features",
        "world_genre_cues",
    ],
    "creature": [
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
        "magical_features",
        "world_genre_cues",
    ],
    "object": [
        "object_class",
        "function",
        "size_scale",
        "shape_form",
        "primary_material",
        "secondary_materials",
        "color_finish",
        "surface_texture",
        "condition_default",
        "symbolic_markings",
        "magical_properties",
        "world_genre_cues",
    ],
    "location": [
        "location_class",
        "indoor_outdoor",
        "environment_type",
        "region_or_domain",
        "architecture_or_terrain_style",
        "dominant_materials",
        "lighting_default",
        "weather_exposure",
        "ambient_mood",
        "notable_features",
        "magic_or_tech_presence",
        "world_genre_cues",
    ],
}

PRACTICAL_DYNAMIC_FIELDS: dict[str, list[str]] = {
    "character": [
        "scene_outfit",
        "scene_accessories",
        "scene_footwear",
        "visible_condition",
        "injuries",
        "dirt_blood_markings",
        "body_language",
        "expression",
        "carried_items",
        "temporary_effects",
    ],
    "creature": [
        "visible_condition",
        "injuries",
        "behavior_state",
        "threat_posture",
        "temporary_effects",
    ],
    "object": [
        "owner_or_holder",
        "activation_state",
        "damage_state",
        "location_context",
        "contained_contents",
        "temporary_effects",
    ],
    "location": [
        "lighting_current",
        "weather_current",
        "occupancy_state",
        "damage_state",
        "temporary_setup",
        "atmosphere_shift",
        "active_effects",
    ],
}


# These buckets are already used by the current extraction pipeline.
TYPED_ATTRIBUTE_KEYS: dict[str, list[str]] = {
    "character": [
        "appearance",
        "outfit",
        "condition",
        "body_language",
        "possessions",
        "abilities",
        "titles_or_roles",
        "affiliations",
    ],
    "object": [
        "appearance",
        "materials",
        "abilities",
        "owner_or_holder",
        "current_state",
        "symbolic_role",
    ],
    "location": [
        "appearance",
        "atmosphere",
        "active_features",
        "damage_or_change",
        "occupants",
        "symbolic_role",
    ],
    "creature": [
        "appearance",
        "condition",
        "behavior",
        "abilities",
        "species_or_kind",
        "threat_role",
    ],
}


PERSISTENT_TRAITS: dict[str, dict[str, list[str]]] = {
    "character": {
        "identity": [
            "gender_presentation",
            "species_or_race",
            "role_or_archetype",
            "age_appearance",
            "social_class_signal",
            "world_aesthetic_cues",
        ],
        "appearance": [
            "height_description",
            "body_type",
            "build",
            "skin_description",
            "hair_description",
            "hair_color",
            "hair_style",
            "eye_description",
            "eye_color",
            "facial_structure",
            "facial_hair",
            "distinguishing_marks",
            "default_expression",
            "fantasy_features",
        ],
        "presentation": [
            "signature_clothing",
            "signature_footwear",
            "signature_accessories",
            "signature_equipment",
            "default_posture",
            "core_presence",
        ],
        "social_context": [
            "titles_or_roles",
            "affiliations",
        ],
    },
    "creature": {
        "identity": [
            "species_kind",
            "threat_role",
            "world_aesthetic_cues",
        ],
        "appearance": [
            "body_structure",
            "scale_size",
            "skin_fur_feather_texture",
            "eye_description",
            "limb_structure",
            "teeth_claws_horns",
            "wings_tail_other_features",
            "distinctive_markings",
        ],
        "behavioral_baseline": [
            "default_threat_posture",
            "default_behavior",
            "fantasy_abilities_visible",
        ],
    },
    "object": {
        "identity": [
            "object_kind",
            "symbolic_role",
            "era_or_world_style",
        ],
        "appearance": [
            "material",
            "shape_form",
            "size_scale",
            "color_finish",
            "distinctive_features",
            "craftsmanship_style",
        ],
        "functional_baseline": [
            "magical_properties_visible",
            "default_condition",
        ],
    },
    "location": {
        "identity": [
            "location_kind",
            "environment_type",
            "social_cultural_signal",
            "world_aesthetic_cues",
        ],
        "appearance": [
            "architecture_style",
            "scale",
            "dominant_materials",
            "lighting_baseline",
            "color_palette",
            "signature_features",
        ],
        "atmospheric_baseline": [
            "default_atmosphere",
        ],
    },
}


DYNAMIC_TRAITS: dict[str, dict[str, list[str]]] = {
    "character": {
        "presentation": [
            "current_outfit",
            "current_accessories",
            "current_equipment",
        ],
        "condition": [
            "visible_condition",
            "injuries",
            "fatigue_state",
            "temporary_transformation",
        ],
        "expression_and_motion": [
            "emotional_display",
            "body_language",
        ],
        "context": [
            "current_location",
        ],
    },
    "creature": {
        "condition": [
            "visible_condition",
            "injuries",
            "damage_state",
        ],
        "behavior": [
            "active_behavior",
            "aggression_state",
            "movement_state",
        ],
        "context": [
            "current_location",
            "current_handler_or_target",
        ],
    },
    "object": {
        "state": [
            "owner_or_holder",
            "current_condition",
            "damage_state",
            "activation_state",
            "location_state",
            "contained_contents",
            "visual_effect_state",
        ],
    },
    "location": {
        "state": [
            "current_atmosphere",
            "occupancy_state",
            "weather_state",
            "damage_state",
            "restoration_state",
            "lighting_current",
            "active_objects_or_effects",
        ],
    },
}


def trait_taxonomy() -> dict[str, dict[str, dict[str, list[str]]]]:
    return {
        "persistent": PERSISTENT_TRAITS,
        "dynamic": DYNAMIC_TRAITS,
    }


def iter_trait_definitions() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scope, scope_map in trait_taxonomy().items():
        for entity_type, categories in scope_map.items():
            for category, keys in categories.items():
                for key in keys:
                    rows.append(
                        {
                            "entity_type": entity_type,
                            "trait_scope": scope,
                            "trait_category": category,
                            "trait_key": key,
                        }
                    )
    return rows


def typed_attribute_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entity_type, keys in TYPED_ATTRIBUTE_KEYS.items():
        for key in keys:
            rows.append(
                {
                    "entity_type": entity_type,
                    "typed_attribute_key": key,
                }
            )
    return rows


def validate_trait_taxonomy() -> list[str]:
    errors: list[str] = []
    for entity_type in ENTITY_TYPES:
        if entity_type not in PERSISTENT_TRAITS:
            errors.append(f"missing persistent taxonomy for {entity_type}")
        if entity_type not in DYNAMIC_TRAITS:
            errors.append(f"missing dynamic taxonomy for {entity_type}")
        if entity_type not in TYPED_ATTRIBUTE_KEYS:
            errors.append(f"missing typed-attribute keys for {entity_type}")

    seen: set[tuple[str, str, str, str]] = set()
    for row in iter_trait_definitions():
        key = (
            row["entity_type"],
            row["trait_scope"],
            row["trait_category"],
            row["trait_key"],
        )
        if key in seen:
            errors.append(f"duplicate trait definition: {key}")
        seen.add(key)
    return errors


def practical_persistent_fields(entity_type: str) -> list[str]:
    return PRACTICAL_PERSISTENT_FIELDS.get(str(entity_type or "").strip().lower(), [])


def practical_dynamic_fields(entity_type: str) -> list[str]:
    return PRACTICAL_DYNAMIC_FIELDS.get(str(entity_type or "").strip().lower(), [])


def group_traits_for_entity(entity_type: str, *, scope: str) -> dict[str, list[str]]:
    entity_type = str(entity_type or "").strip().lower()
    scope = str(scope or "").strip().lower()
    if scope == "persistent":
        return PERSISTENT_TRAITS.get(entity_type, {})
    if scope == "dynamic":
        return DYNAMIC_TRAITS.get(entity_type, {})
    return {}


__all__ = [
    "ENTITY_TYPES",
    "TRAIT_SCOPES",
    "TYPED_ATTRIBUTE_KEYS",
    "PERSISTENT_TRAITS",
    "DYNAMIC_TRAITS",
    "trait_taxonomy",
    "iter_trait_definitions",
    "typed_attribute_rows",
    "validate_trait_taxonomy",
    "group_traits_for_entity",
]
