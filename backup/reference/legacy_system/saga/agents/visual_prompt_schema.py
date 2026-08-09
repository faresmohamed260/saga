"""Shared schema helpers for character-first visual prompt generation."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


TURNAROUND_PREFIX_LINES = [
    "studio photograph, three-view layout,",
    "pure white seamless background,",
    "same person shown three times side by side,",
    "front view full body, side profile full body, back view full body,",
    "identical face, body, proportions across all views,",
    "",
    "T-pose, arms relaxed at sides, legs straight, feet shoulder-width apart,",
    "full body visible head to toe, no cropping,",
    "",
]

TURNAROUND_SUFFIX_LINES = [
    "photorealistic, real human skin texture, visible pores,",
    "natural skin tone variation, subtle facial asymmetry,",
    "realistic anatomy and proportions,",
    "natural hair strand detail,",
    "physically accurate fabric texture,",
    "",
    "neutral studio lighting, soft diffuse light, evenly lit,",
    "no dramatic contrast, no rim light,",
    "",
    "sharp focus across entire image,",
    "no depth of field blur, no stylization,",
    "studio documentation photo, clean controlled realistic,",
    "RAW photo, shot on Canon EOS R5, 8k uhd",
]

WORLD_AESTHETIC_DEFAULTS = [
    "setting-appropriate visual aesthetic grounded in the source text,",
    "materials, tailoring, and construction should match the implied world and time period,",
    "no off-setting design drift, no genre-inappropriate styling, no unsupported modern or futuristic details,",
    "",
]

SETTING_FANTASY_TOKENS = {
    "fae", "fairy", "elf", "court", "lord", "lady", "priestess", "mage", "sorcerer", "spell", "magic",
    "enchanted", "dragon", "kingdom", "castle", "sword", "blade", "warrior", "armor", "armour", "cloak",
    "robe", "tunic", "winged fantasy humanoid", "temple attendant", "horns", "pointed ears",
}
SETTING_HISTORICAL_TOKENS = {
    "victorian", "regency", "edwardian", "period", "corset", "bonnet", "carriage", "musket", "empire waist",
    "gown", "waistcoat", "cravat", "manor", "duke", "duchess", "countess", "count", "medieval", "renaissance",
}
SETTING_MODERN_TOKENS = {
    "jeans", "hoodie", "t-shirt", "sneakers", "suit", "blazer", "apartment", "office", "phone", "car", "train",
    "urban", "modern", "contemporary", "school uniform", "subway", "jacket", "denim",
}
SETTING_SCI_FI_TOKENS = {
    "spaceship", "starship", "android", "cybernetic", "plasma", "laser", "spacesuit", "futuristic", "hologram",
    "space station", "mech", "synthetic", "powered armor", "helmet visor", "alien", "orbit", "galactic",
}

PERSISTENT_PROFILE_KEYS = [
    "gender_presentation",
    "species_or_race",
    "role_or_archetype",
    "model_safe_identity",
    "world_aesthetic_cues",
    "presence_description",
    "height_description",
    "body_type",
    "skin_description",
    "hair_description",
    "eye_description",
    "facial_structure",
    "age_appearance",
    "expression",
    "clothing_description",
    "footwear_description",
    "accessories_description",
    "distinguishing_marks",
    "fantasy_features",
    "equipment_or_signature_items",
    "lore_terms",
]

CHANGE_KEYS = [
    "change_label",
    "change_summary",
    "outfit_change",
    "visible_condition_change",
    "body_language_change",
    "fantasy_feature_change",
    "equipment_change",
    "scene_context",
    "source_evidence",
    "confidence",
    "image_edit_prompt",
]

PHYSICAL_SPECIFICITY_KEYS = [
    "world_aesthetic_cues",
    "height_description",
    "body_type",
    "skin_description",
    "hair_description",
    "eye_description",
    "facial_structure",
    "age_appearance",
    "clothing_description",
    "footwear_description",
    "accessories_description",
    "distinguishing_marks",
    "fantasy_features",
    "equipment_or_signature_items",
]

SCENE_CONTEXT_MARKERS = {
    "standing in",
    "standing near",
    "standing by",
    "standing beside",
    "seated near",
    "seated by",
    "watching",
    "confronting",
    "inside the",
    "outside the",
    "in the cottage",
    "near the table",
    "at the table",
    "by the hearth",
    "in a dim",
    "with a deer carcass",
    "during the",
    "after the",
    "before the",
}

HAIR_HINTS = {"hair", "braid", "braided", "shaved", "curly", "wavy", "straight-haired", "dark-haired", "golden-haired", "coppery"}
EYE_HINTS = {"eyes", "eyed", "violet", "hazel", "gray-blue", "teal", "amber", "brown-eyed", "blue-eyed", "green-eyed"}
BODY_HINTS = {"tall", "short", "lean", "slender", "muscular", "broad-shouldered", "thin", "lithe", "stocky", "athletic", "gaunt"}
SKIN_HINTS = {"skin", "pale", "tan", "bronze", "brown", "golden", "freckled", "scarred", "scar", "tattoo"}
FACE_HINTS = {"face", "jaw", "cheekbones", "mouth", "nose", "brow", "fine-boned", "aristocratic", "handsome", "beautiful"}
FANTASY_HINTS = {"wings", "winged", "fangs", "claws", "tail", "horns", "pointed ears", "siphon", "tattoo", "markings"}
CLOTHING_HINTS = {"cloak", "dress", "gown", "armor", "armour", "leathers", "boots", "jacket", "tunic", "shirt", "sweater", "robe", "robes", "leggings", "gloves"}
EXPRESSION_HINTS = {"neutral", "stern", "composed", "calm", "wary", "watchful", "determined", "solemn", "grim", "smiling", "smile", "frown"}
INVALID_TRAIT_MARKERS = {
    "unseen in text",
    "not described",
    "unknown",
    "unspecified",
    "not visible",
    "unclear",
}
WEAK_QUALIFIER_MARKERS = {
    "implied",
    "not mentioned",
    "mentioned",
    "described in the scene",
    "described",
    "visible",
    "remaining",
}
SCENE_CONTAMINATION_MARKERS = {
    "carrying",
    "watching",
    "standing",
    "crouched",
    "slow smile",
    "rippling into darkness",
    "later dissolves",
    "as he",
    "as she",
    "in the cell",
    "in the room",
}
ROLE_NOISE_MARKERS = {
    "love interest",
    "former craftsman",
    "protector",
    "bitter",
    "sister",
    "father",
    "mother",
    "younger sister",
    "elder sister",
}

ROLE_TRANSLATIONS = {
    "illyrian": "winged fantasy humanoid",
    "high fae": "fantasy humanoid",
    "fae": "fantasy humanoid",
    "high lord": "noble fantasy leader",
    "high lady": "noble fantasy leader",
    "priestess": "temple attendant",
}

DEFAULT_MODEST_CLOTHING = "fully clothed in modest, non-revealing garments appropriate to the setting"


def clean_text(value: Any, *, limit: int = 700) -> str:
    text = str(value or "")
    text = (
        text.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return " ".join(text.strip().split())[:limit]


def normalize_string_list(values: Iterable[Any]) -> List[str]:
    rows: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = clean_text(value)
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        rows.append(cleaned)
    return rows


def empty_persistent_profile() -> Dict[str, Any]:
    return {key: ([] if key == "lore_terms" else "") for key in PERSISTENT_PROFILE_KEYS}


def normalize_persistent_profile(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized = empty_persistent_profile()
    if not isinstance(raw, dict):
        return normalized
    for key in PERSISTENT_PROFILE_KEYS:
        if key == "lore_terms":
            normalized[key] = normalize_string_list(raw.get(key) or [])
        else:
            normalized[key] = clean_text(raw.get(key))
    normalized = enrich_persistent_profile_from_legacy_fields(normalized)
    normalized["model_safe_identity"] = _model_safe_identity(normalized)
    return normalized


def enrich_persistent_profile_from_legacy_fields(
    profile: Dict[str, Any] | None,
    *,
    physical_description: str = "",
    outfit: str = "",
    body_language: str = "",
) -> Dict[str, Any]:
    normalized = empty_persistent_profile()
    if isinstance(profile, dict):
        normalized.update({key: profile.get(key, normalized.get(key)) for key in normalized.keys()})

    if outfit and not clean_text(normalized.get("clothing_description")):
        normalized["clothing_description"] = clean_text(outfit)
    if body_language and not clean_text(normalized.get("expression")):
        maybe_expression = _maybe_expression(body_language)
        if maybe_expression:
            normalized["expression"] = maybe_expression

    description = clean_text(physical_description)
    if description:
        chunks = _split_trait_chunks(description)
        for chunk in chunks:
            category = _classify_trait_chunk(chunk)
            if category == "hair" and not clean_text(normalized.get("hair_description")):
                normalized["hair_description"] = chunk
            elif category == "eyes" and not clean_text(normalized.get("eye_description")):
                normalized["eye_description"] = chunk
            elif category == "body" and not clean_text(normalized.get("body_type")):
                normalized["body_type"] = chunk
            elif category == "skin" and not clean_text(normalized.get("skin_description")):
                normalized["skin_description"] = chunk
            elif category == "face" and not clean_text(normalized.get("facial_structure")):
                normalized["facial_structure"] = chunk
            elif category == "fantasy" and not clean_text(normalized.get("fantasy_features")):
                normalized["fantasy_features"] = chunk
            elif category == "clothing" and not clean_text(normalized.get("clothing_description")):
                normalized["clothing_description"] = chunk
            elif category == "expression" and not clean_text(normalized.get("expression")):
                normalized["expression"] = chunk
        if not clean_text(normalized.get("presence_description")):
            residual = _presence_candidate_from_chunks(chunks)
            if residual:
                normalized["presence_description"] = residual

    normalized["presence_description"] = _scrub_scene_context(normalized.get("presence_description", ""))
    if clean_text(normalized.get("presence_description")) and _looks_overly_contextual(normalized["presence_description"]):
        normalized["presence_description"] = ""
    for key in PHYSICAL_SPECIFICITY_KEYS:
        normalized[key] = _scrub_scene_context(normalized.get(key, ""), allow_context=False)
    normalized["expression"] = _scrub_scene_context(normalized.get("expression", ""), allow_context=False)
    normalized["role_or_archetype"] = _sanitize_role_text(normalized.get("role_or_archetype", ""))
    normalized["gender_presentation"] = _sanitize_gender_text(normalized.get("gender_presentation", ""))
    _promote_identity_line_into_slots(normalized)
    _sanitize_profile_fields(normalized)
    normalized["model_safe_identity"] = _model_safe_identity(normalized)
    return normalized


def promote_persistent_profile_from_visual_changes(
    profile: Dict[str, Any] | None,
    changes: Iterable[Dict[str, Any]] | None,
) -> Dict[str, Any]:
    normalized = enrich_persistent_profile_from_legacy_fields(profile or {})
    for row in changes or []:
        if not isinstance(row, dict):
            continue
        confidence = clean_text(row.get("confidence")).lower()
        if confidence and confidence not in {"high", "medium"}:
            continue
        visible = _stable_excerpt_from_change(row.get("visible_condition_change"))
        outfit = _stable_excerpt_from_change(row.get("outfit_change"))
        fantasy = _stable_excerpt_from_change(row.get("fantasy_feature_change"))
        equipment = _stable_excerpt_from_change(row.get("equipment_change"))
        augmented = enrich_persistent_profile_from_legacy_fields(
            normalized,
            physical_description=", ".join(part for part in [visible, fantasy] if part),
            outfit=outfit,
        )
        if equipment and not clean_text(augmented.get("equipment_or_signature_items")):
            augmented["equipment_or_signature_items"] = equipment
        normalized = augmented
        if profile_specificity_score(normalized) >= 4:
            break
    _sanitize_profile_fields(normalized)
    normalized["model_safe_identity"] = _model_safe_identity(normalized)
    return normalized


def normalize_dynamic_visual_changes(rows: Iterable[Dict[str, Any]] | None, *, display_name: str = "") -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {key: clean_text(row.get(key)) for key in CHANGE_KEYS if key != "confidence"}
        item["confidence"] = _confidence(row.get("confidence"))
        if not item["image_edit_prompt"]:
            item["image_edit_prompt"] = compile_character_edit_prompt(display_name=display_name, change=item)
        summary = item["change_summary"] or " ".join(
            part
            for part in [
                item["outfit_change"],
                item["visible_condition_change"],
                item["body_language_change"],
                item["fantasy_feature_change"],
                item["equipment_change"],
            ]
            if part
        )
        item["change_summary"] = clean_text(summary)
        if not item["change_summary"] and not item["image_edit_prompt"]:
            continue
        key = (item["change_label"].lower(), item["change_summary"].lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized[:12]


def compile_character_turnaround_prompt(profile: Dict[str, Any] | None, *, display_name: str = "") -> str:
    normalized = normalize_persistent_profile(profile)
    if profile_specificity_score(normalized) <= 0:
        return ""
    clothing_line = normalized["clothing_description"] or _default_clothing_description(normalized)
    footwear_line = normalized["footwear_description"] or _default_footwear_description(normalized)
    accessories_line = normalized["accessories_description"]
    distinguishing_line = normalized["distinguishing_marks"]
    fantasy_line = normalized["fantasy_features"]
    equipment_line = normalized["equipment_or_signature_items"]
    identity_line = normalized["model_safe_identity"] or clean_text(display_name) or "humanoid character"
    presence_line = normalized["presence_description"] or _presence_fallback(normalized)
    if presence_line.lower() == identity_line.lower():
        presence_line = ""
    world_cues = normalized.get("world_aesthetic_cues") or _default_world_aesthetic_cues(normalized)

    appearance_bits = _dedupe_preserve_order(
        [
            normalized["height_description"],
            normalized["body_type"],
            normalized["skin_description"],
            normalized["hair_description"],
            normalized["eye_description"],
            normalized["facial_structure"],
            normalized["age_appearance"],
            normalized["expression"] or "neutral expression",
        ]
    )
    equipment_bits = _dedupe_preserve_order(
        [
            accessories_line,
            distinguishing_line,
            fantasy_line,
            equipment_line,
        ]
    )

    subject_name = clean_text(display_name) or "the subject"
    lines = [
        "Create a photorealistic studio character-sheet photograph.",
        "Use a three-view layout with a pure white seamless background.",
        "Show the same person three times side by side: front view full body, side profile full body, and back view full body.",
        "Keep the face, body, hairstyle, and proportions identical across all views.",
        "Place the subject in a T-pose with arms relaxed at the sides, legs straight, feet shoulder-width apart, and the full body visible head to toe with no cropping.",
        _sentence(f"Depict {subject_name} as {identity_line}"),
    ]
    if presence_line:
        lines.append(_sentence(f"Overall presence: {presence_line}"))
    appearance_sentence = _appearance_sentence(appearance_bits)
    if appearance_sentence:
        lines.append(_sentence(appearance_sentence))
    if clothing_line:
        outfit_sentence = f"The subject should wear {clothing_line}"
        if footwear_line:
            outfit_sentence += f", with {footwear_line}"
        lines.append(_sentence(outfit_sentence))
    elif footwear_line:
        lines.append(_sentence(f"The subject should wear {footwear_line}"))
    if equipment_bits:
        lines.append(_sentence(_equipment_sentence(equipment_bits)))
    lines.append(_sentence(f"The design language should reflect {world_cues}"))
    lines.append(_sentence(_setting_aesthetic_sentence(normalized)))
    lines.extend(
        [
            "Photorealistic, real human skin texture, visible pores, and natural skin tone variation.",
            "Subtle facial asymmetry, realistic anatomy and proportions, natural hair strand detail, and physically accurate fabric texture.",
            "Neutral studio lighting with soft diffuse even light, no dramatic contrast, and no rim light.",
            "Sharp focus across the entire image, no depth-of-field blur, no stylization, clean controlled studio documentation photo, RAW photo, shot on Canon EOS R5, 8k UHD.",
        ]
    )
    return "\n".join(line for line in lines if line).strip()


def compile_character_edit_prompt(*, display_name: str, change: Dict[str, Any] | None) -> str:
    row = change or {}
    updates = [
        clean_text(row.get("change_summary")),
        clean_text(row.get("outfit_change")),
        clean_text(row.get("visible_condition_change")),
        clean_text(row.get("body_language_change")),
        clean_text(row.get("fantasy_feature_change")),
        clean_text(row.get("equipment_change")),
    ]
    updates = normalize_string_list(updates)
    context = clean_text(row.get("scene_context"))
    if not updates:
        return ""
    pieces = [
        f"Edit the existing reference image of {clean_text(display_name) or 'the character'}.",
        "Keep the same face, body proportions, hair, eyes, skin tone, and persistent identity traits unchanged.",
        "Update only the scene-specific visual state:",
        "; ".join(updates) + ".",
    ]
    if context:
        pieces.append(f"Context: {context}.")
    return " ".join(piece for piece in pieces if piece).strip()


def compile_entity_concept_prompt(
    *,
    display_name: str,
    entity_type: str,
    baseline_description: str = "",
    current_state: str = "",
    owner_or_associated_characters: Iterable[str] | None = None,
) -> str:
    name = clean_text(display_name) or "the entity"
    baseline = clean_text(baseline_description, limit=1200)
    state = clean_text(current_state, limit=900)
    associated = normalize_string_list(owner_or_associated_characters or [])
    identity = {
        "object": "a story-significant object or artifact",
        "weapon": "a story-significant weapon",
        "magical_artifact": "a story-significant magical artifact",
        "creature": "a non-human fantasy creature",
    }.get(clean_text(entity_type).lower(), "a story-significant entity")
    lines = [
        f"Create a photorealistic concept image of {name}.",
        f"Depict it as {identity}.",
    ]
    if baseline:
        lines.append(_sentence(f"Persistent physical description: {baseline}"))
    if state:
        lines.append(_sentence(f"Current visible state: {state}"))
    if associated:
        lines.append(_sentence(f"Associated with {', '.join(associated[:4])}"))
    lines.extend(
        [
            "Keep the design grounded in the source setting and material culture, with believable texture, scale, wear, and construction details.",
            "Photorealistic rendering, sharp focus, natural lighting, and no stylized illustration look.",
        ]
    )
    return "\n".join(line for line in lines if line).strip()


def compile_location_concept_prompt(
    *,
    display_name: str,
    view_archetype: str = "",
    location_class: str = "",
    indoor_outdoor: str = "",
    environment_type: str = "",
    region_or_domain: str = "",
    architecture_or_terrain_style: str = "",
    dominant_materials: str = "",
    lighting_default: str = "",
    weather_exposure: str = "",
    baseline_description: str = "",
    current_description: str = "",
    atmosphere: str = "",
    notable_features: Iterable[str] | None = None,
    damage_or_restoration_state: str = "",
    magic_or_tech_presence: str = "",
    world_genre_cues: str = "",
) -> str:
    name = clean_text(display_name) or "the location"
    archetype = clean_text(view_archetype, limit=80) or "establishing_exterior"
    location_identity = clean_text(location_class, limit=180)
    indoor = clean_text(indoor_outdoor, limit=120)
    environment = clean_text(environment_type, limit=220)
    region = clean_text(region_or_domain, limit=220)
    architecture = clean_text(architecture_or_terrain_style, limit=260)
    materials = clean_text(dominant_materials, limit=240)
    lighting = clean_text(lighting_default, limit=220)
    weather = clean_text(weather_exposure, limit=180)
    baseline = clean_text(baseline_description, limit=1200)
    current = clean_text(current_description, limit=1200)
    mood = clean_text(atmosphere, limit=400)
    damage = clean_text(damage_or_restoration_state, limit=300)
    magic_presence = clean_text(magic_or_tech_presence, limit=240)
    world_cues = clean_text(world_genre_cues, limit=260)
    features = normalize_string_list(notable_features or [])
    location_noun = _location_subject_noun(location_identity, architecture, environment)
    lines = [
        f"Create a photorealistic empty environment reference image of {_location_view_title(name, archetype)}.",
        "Empty environment reference plate focused entirely on the location itself.",
        "Neutral worldbuilding reference for a canon location, presented as observational production design documentation.",
    ]
    lines.append(_location_view_opening(archetype, location_noun))
    structure_line = _location_structure_line(
        archetype=archetype,
        architecture=architecture,
        location_identity=location_identity,
        environment=environment,
        region=region,
    )
    if structure_line:
        lines.append(structure_line)
    material_line = _location_material_line(materials, lighting, weather, damage)
    if material_line:
        lines.append(material_line)
    feature_line = _location_feature_line(archetype, features)
    if feature_line:
        lines.append(feature_line)
    baseline_line = _location_baseline_line(archetype, baseline, features)
    if baseline_line:
        lines.append(baseline_line)
    if mood and not (
        archetype in {"establishing_exterior", "main_approach", "grounds"}
        and any(token in mood.lower() for token in ("christmas", "holiday", "festive", "celebration"))
    ):
        lines.append(_sentence(f"Let the place feel {mood} without turning it into a dramatic story beat"))
    magic_line = _location_magic_line(magic_presence)
    if magic_line:
        lines.append(magic_line)
    if world_cues:
        lines.append(_sentence(f"Keep the design language faithful to {world_cues} and avoid screen-inspired replicas, generic fantasy drift, or theme-park presentation"))
    elif region:
        lines.append(_sentence(f"Keep the architecture and surface treatment grounded in the material culture of {region}, with no generic fantasy set dressing"))
    lines.extend(
        [
            _location_composition_line(archetype),
            "Observational documentary framing suitable for production design reference.",
            "The scene must read as a permanent, believable place with coherent architecture, stable layout, and realistic scale.",
            "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
        ]
    )
    return "\n".join(line for line in lines if line).strip()


def compile_creature_concept_prompt(
    *,
    display_name: str,
    species_kind: str = "",
    size_class: str = "",
    body_plan: str = "",
    surface_covering: str = "",
    coloration: str = "",
    head_features: str = "",
    eyes: str = "",
    limbs_appendages: str = "",
    natural_weapons: str = "",
    wings: str = "",
    tail: str = "",
    magical_features: str = "",
    baseline_description: str = "",
    current_description: str = "",
    world_genre_cues: str = "",
) -> str:
    name = clean_text(display_name) or "the creature"
    subject_identity = clean_text(species_kind, limit=180) or "a canon creature"
    anatomy_bits = normalize_string_list(
        [
            clean_text(size_class, limit=140),
            clean_text(body_plan, limit=220),
            clean_text(surface_covering, limit=180),
            clean_text(coloration, limit=180),
            clean_text(head_features, limit=180),
            clean_text(eyes, limit=140),
            clean_text(limbs_appendages, limit=180),
            clean_text(natural_weapons, limit=180),
            clean_text(wings, limit=160),
            clean_text(tail, limit=140),
        ]
    )
    magic = clean_text(magical_features, limit=220)
    baseline = clean_text(baseline_description, limit=1200)
    current = clean_text(current_description, limit=700)
    world = clean_text(world_genre_cues, limit=220)
    lines = [
        f"Create a photorealistic creature reference image of {name}.",
        "Single-subject creature reference plate focused entirely on the creature.",
        "Neutral worldbuilding reference for a canon creature, presented as design documentation rather than narrative action.",
        _sentence(f"Depict {name} as {subject_identity}"),
    ]
    if anatomy_bits:
        lines.append(_sentence(f"Primary anatomy and visible structure: {', '.join(anatomy_bits)}"))
    if magic:
        lines.append(_sentence(f"Supernatural or special-world traits should appear as {magic}"))
    if baseline:
        lines.append(_sentence(f"Persistent visual description: {baseline}"))
    if current:
        lines.append(_sentence(f"Current visible condition only if canon-relevant: {current}"))
    if world:
        lines.append(_sentence(f"Keep the design language faithful to {world} and avoid generic monster design drift"))
    lines.extend(
        [
            "Use a clear full-subject composition with readable silhouette, believable anatomy, grounded material detail, and stable proportions.",
            "Observational documentary framing suitable for a production design reference library.",
            "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
        ]
    )
    return "\n".join(line for line in lines if line).strip()


def compile_creature_negative_prompt() -> str:
    return (
        "people, characters, handlers, riders, saddles, reins, crowds, battle scene, attack pose, narrative action, motion blur, cinematic scene, "
        "movie still, illustration, painting, cartoon, anime, CGI, toy-like proportions, mascot look, generic monster design, duplicate limbs, "
        "extra heads, malformed anatomy, floating accessories, stylized fantasy glow, oversaturated colors"
    )


def compile_object_concept_prompt(
    *,
    display_name: str,
    object_class: str = "",
    function: str = "",
    size_scale: str = "",
    shape_form: str = "",
    primary_material: str = "",
    secondary_materials: str = "",
    color_finish: str = "",
    surface_texture: str = "",
    condition_default: str = "",
    symbolic_markings: str = "",
    magical_properties: str = "",
    baseline_description: str = "",
    current_description: str = "",
    world_genre_cues: str = "",
) -> str:
    name = clean_text(display_name) or "the object"
    object_identity = clean_text(object_class, limit=180) or "a canon prop or artifact"
    function_text = clean_text(function, limit=220)
    structure_bits = normalize_string_list(
        [
            clean_text(size_scale, limit=140),
            clean_text(shape_form, limit=220),
            clean_text(primary_material, limit=180),
            clean_text(secondary_materials, limit=180),
            clean_text(color_finish, limit=180),
            clean_text(surface_texture, limit=180),
            clean_text(condition_default, limit=180),
            clean_text(symbolic_markings, limit=200),
        ]
    )
    magic = clean_text(magical_properties, limit=220)
    baseline = clean_text(baseline_description, limit=1200)
    current = clean_text(current_description, limit=700)
    world = clean_text(world_genre_cues, limit=220)
    lines = [
        f"Create a photorealistic isolated prop reference image of {name}.",
        "Single-subject prop reference plate with the object fully visible and clearly readable.",
        "Neutral worldbuilding reference for a canon object, presented as production design documentation.",
        _sentence(f"Depict {name} as {object_identity}"),
    ]
    if function_text:
        lines.append(_sentence(f"Primary function or use: {function_text}"))
    if structure_bits:
        lines.append(_sentence(f"Fixed visual structure, materials, and finish: {', '.join(structure_bits)}"))
    if magic:
        lines.append(_sentence(f"Special-world properties should appear as {magic}"))
    if baseline:
        lines.append(_sentence(f"Persistent visual description: {baseline}"))
    if current:
        lines.append(_sentence(f"Current visible condition only if canon-relevant: {current}"))
    if world:
        lines.append(_sentence(f"Keep the design language faithful to {world} and avoid generic fantasy prop styling or modern product drift"))
    lines.extend(
        [
            "Use a clean readable composition with the full object clearly visible, stable proportions, believable construction, and grounded material detail.",
            "Observational documentary framing suitable for production design reference.",
            "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
        ]
    )
    return "\n".join(line for line in lines if line).strip()


def compile_object_negative_prompt() -> str:
    return (
        "people, hands, fingers, characters, creatures, mannequins, product ad, display pedestal, shop display, cluttered background, movie still, "
        "action scene, illustration, painting, cartoon, anime, CGI, oversized ornamentation, generic fantasy trinket design, duplicate objects, "
        "broken perspective, floating parts, unreadable silhouette, stylized glow, oversaturated colors"
    )


def compile_location_negative_prompt() -> str:
    return (
        "people, person, human figure, character, student, wizard, witch, crowd, portrait, close-up face, silhouette, "
        "hands, feet, body part, creature, animal, staged action, duel, battle, chase, movie still, cinematic blocking, "
        "dramatic hero shot, over-the-shoulder shot, point-of-view shot, Dutch angle, theme park, amusement park, tourist attraction, "
        "castle replica, polished courtyard, clean modern paving, multicolored decorative stone, artificial rock facade, oversized fantasy ornament, "
        "generic fantasy castle, generic fantasy tavern, generic medieval village, random background extras, modern props, signs, information boards, "
        "railings, ropes, barriers, bins, speakers, security equipment, sci-fi elements, visible spells, glowing runes, magical portal, stylized concept art, "
        "painterly brushwork, anime, illustration, matte painting look, text, logo, watermark"
    )


def _location_view_title(name: str, archetype: str) -> str:
    mapping = {
        "establishing_exterior": f"a distant exterior establishing view of {name}",
        "main_approach": f"the main exterior approach to {name}",
        "courtyard": f"the central courtyard of {name}",
        "grounds": f"the surrounding grounds of {name}",
        "interior_hall": f"the main interior hall of {name}",
        "corridor_passage": f"a corridor or passage within {name}",
        "chamber_room": f"a key interior room within {name}",
        "hidden_entry": f"a concealed entry point within {name}",
    }
    return mapping.get(archetype, name)


def _location_subject_noun(location_identity: str, architecture: str, environment: str) -> str:
    for value in (location_identity, architecture, environment):
        lowered = value.lower()
        if "castle" in lowered:
            return "castle"
        if "street" in lowered or "road" in lowered or "drive" in lowered:
            return "street"
        if "forest" in lowered:
            return "forest edge"
        if "hall" in lowered:
            return "hall"
        if "corridor" in lowered or "passage" in lowered or "tunnel" in lowered:
            return "passage"
        if "courtroom" in lowered:
            return "courtroom"
        if "house" in lowered or "home" in lowered:
            return "house"
    return "location"


def _location_view_opening(archetype: str, location_noun: str) -> str:
    mapping = {
        "establishing_exterior": f"Show a wide establishing view where the full scale and silhouette of the {location_noun} are clearly readable.",
        "main_approach": f"Show a wide eye-level approach view where the entrance sequence and the larger mass of the {location_noun} remain the visual focus.",
        "courtyard": "Show a broad enclosed open-air view where the surrounding walls and permanent architectural edges define the space clearly.",
        "grounds": "Show a wide environmental view that makes the surrounding terrain, pathways, and permanent structures easy to read at a glance.",
        "interior_hall": "Show a wide interior reference view with the room volume, circulation paths, and major architectural anchors clearly visible.",
        "corridor_passage": "Show a grounded linear view through the passage so the corridor depth, walls, thresholds, and circulation path read clearly.",
        "chamber_room": "Show a wide documentary interior view with the room layout, fixed furnishings, and architectural structure clearly readable.",
        "hidden_entry": "Show a close-to-mid environmental reference view centered on a concealed architectural access point that still feels embedded in the larger structure.",
    }
    return mapping.get(archetype, "Show a coherent, readable environmental reference view with a clear spatial hierarchy.")


def _location_structure_line(*, archetype: str, architecture: str, location_identity: str, environment: str, region: str) -> str:
    subject = clean_text(architecture or location_identity or environment or region, limit=220)
    if not subject:
        return ""
    if archetype == "establishing_exterior":
        return _sentence(f"Depict an immense, permanent {subject} with believable massing, layered depth, and a stable real-world construction logic")
    if archetype == "main_approach":
        return _sentence(f"Use enclosing walls, entry structures, arches, or doors to define a clear arrival sequence into {subject}")
    if archetype == "courtyard":
        return _sentence(f"Let the courtyard be framed by surrounding architecture so the space feels enclosed, functional, and permanently built into {subject}")
    if archetype == "grounds":
        return _sentence(f"Let the landforms, pathways, vegetation, and built structures feel native to {subject} rather than decorative or staged")
    if archetype == "hidden_entry":
        return _sentence(f"The concealed access point should read as part of the original structure of {subject}, not as a theatrical set piece")
    return _sentence(f"Keep the architecture and layout grounded in {subject} with believable scale, circulation, and material logic")


def _location_material_line(materials: str, lighting: str, weather: str, damage: str) -> str:
    parts = []
    if materials:
        parts.append(f"Use {materials} as the dominant visible materials and surface textures")
    if lighting:
        parts.append(f"Let the default lighting read as {lighting}")
    if weather:
        parts.append(f"Show the surfaces as shaped by {weather}")
    if damage:
        parts.append(f"Let any visible wear read as {damage}")
    if not parts:
        return ""
    return _sentence(", ".join(parts))


def _location_feature_line(archetype: str, features: List[str]) -> str:
    if not features:
        return ""
    if archetype == "hidden_entry":
        feature = clean_text(features[0], limit=180).lower()
        if any(token in feature for token in ("hidden", "secret", "concealed", "tunnel", "passage", "trapdoor")):
            return (
                "Include a concealed entrance integrated into old masonry or structure, easy to overlook rather than presented as a dramatic focal attraction."
            )
    if archetype == "main_approach":
        return _sentence(f"Anchor the composition with fixed approach details such as {', '.join(features[:2])}")
    if archetype in {"interior_hall", "corridor_passage", "chamber_room"}:
        return _sentence(f"Keep permanent interior reference points clearly visible, including {', '.join(features[:3])}")
    return _sentence(f"Keep fixed architectural details visible, including {', '.join(features[:3])}")


def _location_baseline_line(archetype: str, baseline: str, features: List[str]) -> str:
    if not baseline:
        return ""
    lowered = baseline.lower()
    blocked = ("where ", "when ", "after ", "before ", "during ", "location of ", "referenced as", "allegedly", "encounter")
    if any(marker in lowered for marker in blocked):
        return ""
    if archetype in {"establishing_exterior", "main_approach", "grounds"} and any(
        token in lowered
        for token in (
            "hidden", "secret", "concealed", "tunnel", "passage", "trapdoor",
            "both", "corridor", "common room", "dungeon", "dormitor", "classroom", "courtroom", "kitchen", "library", "bedroom",
        )
    ):
        return ""
    if features and all(feature.lower() in lowered for feature in features[:2]):
        return ""
    return _sentence(f"Keep the persistent visual identity grounded in {baseline}")


def _location_magic_line(magic_presence: str) -> str:
    if not magic_presence:
        return ""
    return _sentence(
        f"Convey the special-world quality of the place subtly through built-in environmental cues such as practical lighting, atmosphere, impossible-but-grounded details, or architectural logic related to {magic_presence}, not through visible spell effects"
    )


def _location_composition_line(archetype: str) -> str:
    mapping = {
        "establishing_exterior": "Use a wide documentary composition with the structure occupying most of the frame, restrained foreground, readable skyline, and minimal empty paving.",
        "main_approach": "Use a wide eye-level composition with the entrance path and main structure dominant in frame, restrained foreground, and clear human scale.",
        "courtyard": "Use a balanced documentary composition that keeps the open space readable without letting empty foreground overwhelm the architecture.",
        "grounds": "Use a wide environmental composition with clear terrain depth and enough surrounding structure to keep the place specific rather than generic.",
        "interior_hall": "Use a wide interior composition with clear volume, strong architectural anchors, and no extreme lens distortion.",
        "corridor_passage": "Use a linear perspective composition that emphasizes depth and thresholds without turning the passage into a dramatic chase shot.",
        "chamber_room": "Use a wide room-level composition with clear layout, stable perspective, and enough surrounding context to read as a permanent functional space.",
        "hidden_entry": "Use a restrained close-to-mid composition with the concealed access point visible but not oversized, keeping it embedded in the surrounding structure.",
    }
    return mapping.get(archetype, "Use a readable documentary composition with coherent scale, restrained foreground, and stable perspective.")


def _confidence(value: Any) -> str:
    cleaned = clean_text(value).lower()
    return cleaned if cleaned in {"high", "medium", "low"} else "medium"


def _model_safe_identity(profile: Dict[str, Any]) -> str:
    explicit = clean_text(profile.get("model_safe_identity"))
    if explicit:
        sanitized = _sanitize_identity_text(_replace_lore_terms(explicit))
        if sanitized and "humanoidrie" not in sanitized.lower():
            return sanitized
    pieces = [
        clean_text(profile.get("gender_presentation")),
        _replace_lore_terms(clean_text(profile.get("species_or_race"))),
        _replace_lore_terms(clean_text(profile.get("role_or_archetype"))),
    ]
    return _sanitize_identity_text(" ".join(piece for piece in pieces if piece))


def _replace_lore_terms(text: str) -> str:
    lowered = text.lower()
    result = text
    for source, replacement in sorted(ROLE_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        if source in lowered:
            result = _replace_case_insensitive(result, source, replacement)
            lowered = result.lower()
    return clean_text(result)


def _replace_case_insensitive(text: str, needle: str, replacement: str) -> str:
    pattern = re.compile(rf"(?i)\b{re.escape(needle)}\b")
    return pattern.sub(replacement, text)


def _default_clothing_description(profile: Dict[str, Any]) -> str:
    role = clean_text(profile.get("role_or_archetype")).lower()
    species = clean_text(profile.get("species_or_race")).lower()
    fantasy = clean_text(profile.get("fantasy_features")).lower()
    setting = _infer_setting_family(profile)
    if any(token in role for token in {"warrior", "guard", "soldier", "hunter", "fighter"}):
        if setting == "sci_fi":
            return "fully covering practical combat gear with durable technical materials and a functional silhouette appropriate to the setting"
        if setting in {"fantasy", "historical"}:
            return "layered practical combat or hunting clothing built from rough cloth, leather, and other hand-crafted materials appropriate to the setting"
        return "fully covering practical fitted clothing appropriate to the setting"
    if any(token in role for token in {"lord", "lady", "noble", "court", "queen", "king"}):
        return "layered formal attire with refined tailoring and high-status materials appropriate to the setting"
    if any(token in role for token in {"servant", "acolyte", "priestess", "attendant", "maid"}):
        return "simple fully covering work or ceremonial garments appropriate to the setting"
    if any(token in role for token in {"beast", "monster", "creature"}):
        return ""
    if any(token in species for token in {"beast", "monster", "creature", "animal"}):
        return ""
    if any(token in fantasy for token in {"fur", "scales", "hide", "claws", "fangs"}) and not any(token in role for token in {"warrior", "guard"}):
        return ""
    if setting == "fantasy":
        return "fully covering layered clothing made from natural fibers and hand-crafted materials appropriate to the fantasy setting"
    if setting == "historical":
        return "fully covering layered garments with period-appropriate tailoring and materials"
    return DEFAULT_MODEST_CLOTHING


def _default_footwear_description(profile: Dict[str, Any]) -> str:
    if clean_text(profile.get("clothing_description")) or _default_clothing_description(profile):
        role = clean_text(profile.get("role_or_archetype")).lower()
        if any(token in role for token in {"noble", "lord", "lady", "court", "queen", "king"}):
            return "closed formal footwear appropriate to the setting"
        if any(token in role for token in {"servant", "acolyte", "priestess", "attendant"}):
            return "simple practical closed footwear"
        return "practical sturdy closed footwear"
    return ""


def _comma_line(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith(",") else f"{cleaned},"


def _presence_fallback(profile: Dict[str, Any]) -> str:
    pieces = _dedupe_preserve_order(
        [
            clean_text(profile.get("gender_presentation")),
            _replace_lore_terms(clean_text(profile.get("species_or_race"))),
            _sanitize_role_text(clean_text(profile.get("role_or_archetype"))),
        ]
    )
    return " ".join(piece for piece in pieces if piece)


def _merge_fantasy_world_cues(fantasy_features: str, world_cues: str) -> str:
    fantasy = clean_text(fantasy_features)
    world = clean_text(world_cues)
    if fantasy and world:
        return f"{fantasy}, {world}"
    return fantasy or world


def _setting_aesthetic_lines(profile: Dict[str, Any]) -> List[str]:
    setting = _infer_setting_family(profile)
    if setting == "fantasy":
        return [
            "fantasy-world aesthetic grounded in the source text, with period-appropriate hand-crafted materials and silhouettes,",
            "natural fabrics, leather, metalwork, embroidery, and setting-appropriate ceremonial or martial detailing,",
            "no modern fashion cuts, no plastics, no zippers, no streetwear, unless explicitly supported by the text,",
            "",
        ]
    if setting == "historical":
        return [
            "historical or period-inspired aesthetic grounded in the source text and social setting,",
            "era-appropriate tailoring, fabrics, closures, footwear, and hand-crafted material details,",
            "no modern fashion drift, no synthetic materials, no contemporary styling unless explicitly supported by the text,",
            "",
        ]
    if setting == "modern":
        return [
            "contemporary or near-contemporary aesthetic grounded in the source text,",
            "modern-ready materials, tailoring, and everyday construction details appropriate to the setting,",
            "no fantasy armor, no medieval styling, no futuristic techwear unless explicitly supported by the text,",
            "",
        ]
    if setting == "sci_fi":
        return [
            "science-fiction or futuristic aesthetic grounded in the source text,",
            "setting-appropriate advanced materials, technical construction, and functional design language,",
            "no medieval fantasy styling, no anachronistic historical garments, no unsupported contemporary fashion drift,",
            "",
        ]
    return WORLD_AESTHETIC_DEFAULTS


def _setting_aesthetic_sentence(profile: Dict[str, Any]) -> str:
    setting = _infer_setting_family(profile)
    if setting == "fantasy":
        return (
            "Keep the overall styling grounded in a hand-crafted fantasy world, using natural fabrics, leather, metalwork, fur, embroidery, "
            "and silhouettes that feel native to the source setting rather than modern fashion."
        )
    if setting == "historical":
        return (
            "Keep the styling grounded in the source period, with era-appropriate tailoring, closures, fabrics, and footwear rather than modern design shortcuts."
        )
    if setting == "modern":
        return (
            "Keep the styling grounded in the source's contemporary world, with believable modern construction and no fantasy or futuristic drift."
        )
    if setting == "sci_fi":
        return (
            "Keep the styling grounded in the source's futuristic world, with advanced materials and functional design language rather than fantasy or historical clothing cues."
        )
    return "Keep the styling grounded in the source setting and time period, with materials and construction details that match the world."


def _default_world_aesthetic_cues(profile: Dict[str, Any]) -> str:
    role = clean_text(profile.get("role_or_archetype")).lower()
    setting = _infer_setting_family(profile)
    if setting == "fantasy":
        if any(token in role for token in {"hunter", "fighter", "warrior", "guard", "soldier"}):
            return "a grounded fantasy world with practical layered garments, worn leather, natural fibers, and hand-made martial or hunting gear"
        if any(token in role for token in {"lord", "lady", "noble", "court", "queen", "king"}):
            return "a high-status fantasy world with refined tailoring, layered formal garments, metal fastenings, embroidery, and hand-crafted luxury materials"
        return "a grounded fantasy world with hand-crafted materials, layered garments, leather, wool, linen, fur, metal details, and no modern construction cues"
    if setting == "historical":
        return "a period setting with era-appropriate tailoring, closures, fabrics, and hand-crafted material culture"
    if setting == "modern":
        return "a contemporary setting with believable modern clothing construction and everyday materials"
    if setting == "sci_fi":
        return "a futuristic setting with advanced materials, functional technical construction, and world-appropriate visual design"
    return "the source setting's time period, material culture, and social class cues"


def _appearance_sentence(bits: List[str]) -> str:
    if not bits:
        return ""
    if len(bits) == 1:
        return f"Key persistent appearance traits: {bits[0]}"
    if len(bits) == 2:
        return f"Key persistent appearance traits: {bits[0]} and {bits[1]}"
    return f"Key persistent appearance traits: {', '.join(bits[:-1])}, and {bits[-1]}"


def _equipment_sentence(bits: List[str]) -> str:
    if not bits:
        return ""
    if len(bits) == 1:
        return f"Visible persistent identifying details should include {bits[0]}"
    return f"Visible persistent identifying details should include {', '.join(bits[:-1])}, and {bits[-1]}"


def _sentence(text: str) -> str:
    cleaned = clean_text(text, limit=1200)
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _infer_setting_family(profile: Dict[str, Any]) -> str:
    haystack = " ".join(
        clean_text(profile.get(key))
        for key in [
            "species_or_race",
            "role_or_archetype",
            "model_safe_identity",
            "fantasy_features",
            "clothing_description",
            "equipment_or_signature_items",
        ]
    ).lower()
    lore_terms = [clean_text(term).lower() for term in profile.get("lore_terms") or []]
    combined = " ".join([haystack, *lore_terms]).strip()
    if not combined:
        return "neutral"

    scores = {
        "fantasy": sum(1 for token in SETTING_FANTASY_TOKENS if token in combined),
        "historical": sum(1 for token in SETTING_HISTORICAL_TOKENS if token in combined),
        "modern": sum(1 for token in SETTING_MODERN_TOKENS if token in combined),
        "sci_fi": sum(1 for token in SETTING_SCI_FI_TOKENS if token in combined),
    }
    winner = max(scores, key=scores.get)
    return winner if scores[winner] > 0 else "neutral"


def _promote_identity_line_into_slots(profile: Dict[str, Any]) -> None:
    identity_line = clean_text(profile.get("model_safe_identity"))
    if not identity_line:
        return
    chunks = _split_trait_chunks(identity_line)
    for chunk in chunks:
        category = _classify_trait_chunk(chunk)
        if category == "hair" and not clean_text(profile.get("hair_description")):
            profile["hair_description"] = _strip_identity_prefix(chunk)
        elif category == "eyes" and not clean_text(profile.get("eye_description")):
            profile["eye_description"] = _strip_identity_prefix(chunk)
        elif category == "body" and not clean_text(profile.get("body_type")):
            profile["body_type"] = _strip_identity_prefix(chunk)
        elif category == "skin" and not clean_text(profile.get("skin_description")):
            profile["skin_description"] = _strip_identity_prefix(chunk)
        elif category == "face" and not clean_text(profile.get("facial_structure")):
            profile["facial_structure"] = _strip_identity_prefix(chunk)
        elif category == "fantasy" and not clean_text(profile.get("fantasy_features")):
            profile["fantasy_features"] = _strip_identity_prefix(chunk)


def profile_specificity_score(profile: Dict[str, Any] | None) -> int:
    if not isinstance(profile, dict):
        return 0
    score = 0
    for key in PHYSICAL_SPECIFICITY_KEYS:
        if clean_text(profile.get(key)):
            score += 2
    if clean_text(profile.get("presence_description")):
        score += 1
    if clean_text(profile.get("model_safe_identity")):
        score += 1
    return score


def _looks_overly_contextual(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(marker in lowered for marker in SCENE_CONTEXT_MARKERS)


def _scrub_scene_context(text: Any, *, allow_context: bool = True) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    if any(marker in cleaned.lower() for marker in INVALID_TRAIT_MARKERS):
        return ""
    if allow_context:
        return cleaned
    if _looks_overly_contextual(cleaned):
        return ""
    return cleaned


def _maybe_expression(text: str) -> str:
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    if any(term in lowered for term in EXPRESSION_HINTS):
        return cleaned
    return ""


def _split_trait_chunks(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    parts = re.split(r",|;|\band\b", cleaned)
    rows = []
    for part in parts:
        chunk = clean_text(part, limit=220)
        if not chunk:
            continue
        if any(marker in chunk.lower() for marker in INVALID_TRAIT_MARKERS):
            continue
        rows.append(chunk)
    return _dedupe_preserve_order(rows)


def _classify_trait_chunk(chunk: str) -> str:
    lowered = chunk.lower()
    if any(term in lowered for term in HAIR_HINTS):
        return "hair"
    if any(term in lowered for term in EYE_HINTS):
        return "eyes"
    if any(term in lowered for term in FANTASY_HINTS):
        return "fantasy"
    if any(term in lowered for term in CLOTHING_HINTS):
        return "clothing"
    if any(term in lowered for term in SKIN_HINTS):
        return "skin"
    if any(term in lowered for term in FACE_HINTS):
        return "face"
    if any(term in lowered for term in EXPRESSION_HINTS):
        return "expression"
    if any(term in lowered for term in BODY_HINTS):
        return "body"
    return "other"


def _presence_candidate_from_chunks(chunks: List[str]) -> str:
    residual = [
        chunk
        for chunk in chunks
        if _classify_trait_chunk(chunk) == "other" and not _looks_overly_contextual(chunk)
    ]
    return residual[0] if residual else ""


def _sanitize_role_text(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    parts = [piece.strip() for piece in cleaned.split(",")]
    kept = [piece for piece in parts if piece and piece.lower() not in ROLE_NOISE_MARKERS]
    return clean_text(", ".join(kept) if kept else parts[0])


def _sanitize_gender_text(text: str) -> str:
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    if lowered in {"young woman", "woman", "female", "girl"}:
        return "female"
    if lowered in {"young man", "man", "male", "boy"}:
        return "male"
    return cleaned


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    rows: List[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_text(value)
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        rows.append(cleaned)
    return rows


def _strip_identity_prefix(text: str) -> str:
    cleaned = clean_text(text)
    if " with " in cleaned.lower():
        prefix, suffix = re.split(r"\bwith\b", cleaned, maxsplit=1, flags=re.IGNORECASE)
        if any(token in prefix.lower() for token in {"woman", "man", "female", "male", "human", "fae", "faerie", "humanoid"}):
            cleaned = suffix.strip()
    cleaned = re.sub(
        r"^(young|older|middle-aged)\s+(woman|man|female|male)\s+with\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(woman|man|female|male)\s+with\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return clean_text(cleaned)


def _sanitize_profile_fields(profile: Dict[str, Any]) -> None:
    for key in [
        "world_aesthetic_cues",
        "presence_description",
        "height_description",
        "body_type",
        "skin_description",
        "hair_description",
        "eye_description",
        "facial_structure",
        "age_appearance",
        "expression",
        "clothing_description",
        "footwear_description",
        "accessories_description",
        "distinguishing_marks",
        "fantasy_features",
        "equipment_or_signature_items",
    ]:
        profile[key] = _sanitize_visual_field(key, profile.get(key, ""))
    profile["model_safe_identity"] = _sanitize_identity_text(profile.get("model_safe_identity", ""))


def _sanitize_visual_field(key: str, value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if any(marker in lowered for marker in INVALID_TRAIT_MARKERS):
        return ""
    if any(marker in lowered for marker in SCENE_CONTAMINATION_MARKERS) and key in {
        "presence_description",
        "body_type",
        "expression",
    }:
        return ""
    cleaned = re.sub(r"\b(?:human-sized|man-sized|woman-sized)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:visible|remaining)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:under skin)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:gaunt features implied)\b", "gaunt features", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:metal eye mentioned)\b", "metal eye", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:armor not mentioned|armour not mentioned)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:described in the scene|described|mentioned|implied)\b", "", cleaned, flags=re.IGNORECASE)
    if key == "world_aesthetic_cues":
        cleaned = re.sub(r"\b(?:standing|watching|carrying|bleeding|crying|trembling)\b", "", cleaned, flags=re.IGNORECASE)
    if key == "clothing_description":
        cleaned = re.sub(r"\brevealing toned physique\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bcut close to body\b", "fitted", cleaned, flags=re.IGNORECASE)
    if key == "equipment_or_signature_items":
        cleaned = re.sub(r"\bknees knives\b", "knives", cleaned, flags=re.IGNORECASE)
    if key in {"hair_description", "eye_description", "skin_description", "facial_structure", "fantasy_features"}:
        cleaned = _strip_identity_prefix(cleaned)
    cleaned = re.sub(r"\s*[,;]\s*[,;]\s*", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"^[,;:\-\s]+|[,;:\-\s]+$", "", cleaned)
    return clean_text(cleaned)


def _stable_excerpt_from_change(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    parts = _split_trait_chunks(cleaned)
    kept = []
    for part in parts:
        lowered = part.lower()
        if any(marker in lowered for marker in SCENE_CONTAMINATION_MARKERS):
            continue
        if any(term in lowered for term in {"radiating light", "later dissolves", "moving", "gripping", "crouched", "slow smile"}):
            continue
        kept.append(part)
    return ", ".join(_dedupe_preserve_order(kept[:4]))


def _sanitize_identity_text(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    cleaned = cleaned.replace("fantasy humanoidrie", "fantasy humanoid")
    cleaned = cleaned.replace("fantasy humanoidry", "fantasy humanoid")
    cleaned = re.sub(r"\bfaerie\b", "fantasy humanoid", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh\s+faerie\b", "fantasy humanoid", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh\s+fae\b", "fantasy humanoid", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfae\b", "fantasy humanoid", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh lord of\b", "noble fantasy leader of", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh lady of\b", "noble fantasy leader of", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh lord\b", "noble fantasy leader", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhigh lady\b", "noble fantasy leader", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\bnoble fantasy leader of of\b", "noble fantasy leader of", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned)
