"""Provider-neutral positive and negative prompt policy by visual target type."""

from __future__ import annotations


CHARACTER_PREFIX = (
    "Create a photorealistic studio character-sheet photograph. Use a three-view layout on a pure white seamless background. "
    "Show the same person front, side profile, and back, full body head to toe. Keep face, body, hairstyle, clothing, and proportions identical across views."
)
CHARACTER_SUFFIX = (
    "Real human skin texture, realistic anatomy, natural hair and fabric detail, neutral diffuse studio light, sharp focus, "
    "clean production-reference photography, no cropping, no stylization."
)
CHARACTER_NEGATIVE = (
    "illustration, painting, anime, cartoon, CGI, 3D render, game character, plastic skin, cel shading, exaggerated proportions, "
    "dramatic shadows, fantasy glow, environment, scenery, extra characters, duplicate person, inconsistent face, cropped body, "
    "modern clothing, text, logo, watermark, blurry, malformed anatomy"
)

ENTITY_PREFIX = {
    "location": "Create a photorealistic empty environment production-reference image. The location is the only subject; show no people, creatures, silhouettes, or narrative action.",
    "creature": "Create a photorealistic creature production-reference image. Show one complete creature with a clear silhouette, believable anatomy, and no people, riders, handlers, or action scene.",
    "object": "Create a photorealistic isolated prop production-reference image. Show one complete object with readable construction and no people, hands, creatures, or display clutter.",
}
ENTITY_SUFFIX = {
    "location": "Wide readable composition, coherent architecture, believable scale, stable layout, naturalistic light, physically plausible textures, sharp focus, documentary production-design reference.",
    "creature": "Full-subject composition, grounded material detail, stable proportions, naturalistic light, sharp focus, documentary creature reference.",
    "object": "Clean readable composition, stable proportions, believable construction and materials, naturalistic light, sharp focus, documentary prop reference.",
}
ENTITY_NEGATIVE = {
    "location": "people, characters, creatures, silhouettes, body parts, action scene, battle, movie still, theme park, replica, generic fantasy architecture, modern signs, barriers, vehicles, anime, illustration, painting, CGI, text, logo, watermark, blurry",
    "creature": "people, handlers, riders, crowds, battle, attack pose, duplicate creature, extra heads, extra limbs, malformed anatomy, mascot, toy, anime, illustration, painting, CGI, text, logo, watermark, blurry",
    "object": "people, hands, fingers, characters, creatures, duplicate objects, product ad, pedestal, clutter, floating parts, broken perspective, anime, illustration, painting, CGI, text, logo, watermark, blurry",
}
SCENE_PREFIX = "Create a photorealistic narrative scene image faithful to the supplied production references and story moment."
SCENE_SUFFIX = "Cinematic but physically plausible composition, coherent spatial layout, realistic anatomy and materials, natural detail, sharp subject readability, no text or watermark."
SCENE_NEGATIVE = "anime, illustration, painting, cartoon, CGI, 3D render, duplicate characters, extra people, background people, crowds, silhouettes, reflections of people, portraits, inconsistent faces, extra limbs, malformed hands, broken anatomy, incoherent architecture, unrelated people, text, logo, watermark, blurry, low detail, black image"


def compile_prompt(*, target_type: str, body: str, scene_character_names: list[str] | None = None) -> tuple[str, str, str]:
    normalized = str(target_type or "").strip().lower()
    clean_body = " ".join(str(body or "").split())
    if normalized == "character":
        return f"{CHARACTER_PREFIX}\n{clean_body}\n{CHARACTER_SUFFIX}", CHARACTER_NEGATIVE, "character_sheet"
    if normalized == "scene":
        cast = list(dict.fromkeys(name.strip() for name in (scene_character_names or []) if name.strip()))
        if cast:
            cast_constraint = (
                f"HARD CAST LIMIT: Show EXACTLY {len(cast)} PEOPLE TOTAL in the entire image: {', '.join(cast)}. "
                "Show each named person exactly once. Do not add any other person, duplicate, background figure, "
                "silhouette, human reflection, or human portrait."
            )
        else:
            cast_constraint = (
                "HARD CAST LIMIT: Show ZERO PEOPLE in the entire image. Do not add a person, background figure, "
                "silhouette, human reflection, or human portrait."
            )
        return f"{SCENE_PREFIX}\n{cast_constraint}\n{clean_body}\n{SCENE_SUFFIX}", SCENE_NEGATIVE, "entity_generation"
    if normalized not in ENTITY_PREFIX:
        raise ValueError(f"Unsupported visual target type '{target_type}'.")
    return f"{ENTITY_PREFIX[normalized]}\n{clean_body}\n{ENTITY_SUFFIX[normalized]}", ENTITY_NEGATIVE[normalized], "entity_generation"
