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

PERSISTENT_PROFILE_KEYS = [
    "gender_presentation",
    "species_or_race",
    "role_or_archetype",
    "model_safe_identity",
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


def clean_text(value: Any, *, limit: int = 700) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


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
    identity_line = normalized["model_safe_identity"] or clean_text(display_name)
    expression = normalized["expression"] or "neutral expression"
    body_lines = _dedupe_preserve_order([
        identity_line,
        normalized["presence_description"],
        normalized["height_description"],
        normalized["body_type"],
        normalized["skin_description"],
        normalized["hair_description"],
        normalized["eye_description"],
        normalized["facial_structure"],
        normalized["age_appearance"],
        expression,
        normalized["clothing_description"],
        normalized["footwear_description"],
        normalized["accessories_description"],
        normalized["distinguishing_marks"],
        normalized["fantasy_features"],
        normalized["equipment_or_signature_items"],
    ])
    lines = list(TURNAROUND_PREFIX_LINES)
    lines.extend(f"{line}," for line in body_lines if line)
    lines.append("")
    lines.extend(TURNAROUND_SUFFIX_LINES)
    return "\n".join(line for line in lines if line is not None).strip()


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


def _confidence(value: Any) -> str:
    cleaned = clean_text(value).lower()
    return cleaned if cleaned in {"high", "medium", "low"} else "medium"


def _model_safe_identity(profile: Dict[str, Any]) -> str:
    explicit = clean_text(profile.get("model_safe_identity"))
    if explicit:
        return _replace_lore_terms(explicit)
    pieces = [
        clean_text(profile.get("gender_presentation")),
        _replace_lore_terms(clean_text(profile.get("species_or_race"))),
        _replace_lore_terms(clean_text(profile.get("role_or_archetype"))),
    ]
    return clean_text(" ".join(piece for piece in pieces if piece))


def _replace_lore_terms(text: str) -> str:
    lowered = text.lower()
    result = text
    for source, replacement in sorted(ROLE_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        if source in lowered:
            result = _replace_case_insensitive(result, source, replacement)
            lowered = result.lower()
    return clean_text(result)


def _replace_case_insensitive(text: str, needle: str, replacement: str) -> str:
    lowered = text.lower()
    index = lowered.find(needle.lower())
    while index >= 0:
        text = text[:index] + replacement + text[index + len(needle):]
        lowered = text.lower()
        index = lowered.find(needle.lower(), index + len(replacement))
    return text


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
