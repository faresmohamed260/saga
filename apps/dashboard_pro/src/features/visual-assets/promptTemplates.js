export const CHARACTER_NEGATIVE_PROMPT = "illustration, painterly style, anime, CGI, 3D render, game character, plastic or overly smooth skin, no toon shading, no cel shading, exaggerated proportions, cinematic lighting, dramatic shadows, fantasy glow, magical effects, environment or scenery, extra characters or duplicates, modern clothing, denim, t-shirt, hoodie, sneakers, zipper, plastic accessories, modern jewelry, futuristic materials, contemporary streetwear.";

const CHARACTER_PROMPT_PREFIX_LINES = [
  "Create a photorealistic studio character-sheet photograph.",
  "Use a three-view layout with a pure white seamless background.",
  "Show the same person three times side by side: front view full body, side profile full body, and back view full body.",
  "Keep the face, body, hairstyle, and proportions identical across all views.",
  "Place the subject in a T-pose with arms relaxed at the sides, legs straight, feet shoulder-width apart, and the full body visible head to toe with no cropping.",
];

const CHARACTER_PROMPT_SUFFIX_LINES = [
  "Photorealistic, real human skin texture, visible pores, and natural skin tone variation.",
  "Subtle facial asymmetry, realistic anatomy and proportions, natural hair strand detail, and physically accurate fabric texture.",
  "Neutral studio lighting with soft diffuse even light, no dramatic contrast, and no rim light.",
  "Sharp focus across the entire image, no depth-of-field blur, no stylization, clean controlled studio documentation photo, RAW photo, shot on Canon EOS R5, 8k UHD.",
];

const CREATURE_NEGATIVE_PROMPT = "people, characters, handlers, riders, saddles, reins, crowds, battle scene, attack pose, narrative action, motion blur, cinematic scene, movie still, illustration, painting, cartoon, anime, CGI, toy-like proportions, mascot look, generic monster design, duplicate limbs, extra heads, malformed anatomy, floating accessories, stylized fantasy glow, oversaturated colors";
const OBJECT_NEGATIVE_PROMPT = "people, hands, fingers, characters, creatures, mannequins, product ad, display pedestal, shop display, cluttered background, movie still, action scene, illustration, painting, cartoon, anime, CGI, oversized ornamentation, generic fantasy trinket design, duplicate objects, broken perspective, floating parts, unreadable silhouette, stylized glow, oversaturated colors";
const LOCATION_NEGATIVE_PROMPT = "people, person, human figure, character, student, wizard, witch, crowd, portrait, close-up face, silhouette, hands, feet, body part, creature, animal, staged action, duel, battle, chase, movie still, cinematic blocking, dramatic hero shot, over-the-shoulder shot, point-of-view shot, Dutch angle, theme park, amusement park, tourist attraction, castle replica, polished courtyard, clean modern paving, multicolored decorative stone, artificial rock facade, oversized fantasy ornament, generic fantasy castle, generic fantasy tavern, generic medieval village, random background extras, modern props, signs, information boards, railings, ropes, barriers, bins, speakers, security equipment, sci-fi elements, visible spells, glowing runes, magical portal, stylized concept art, painterly brushwork, anime, illustration, matte painting look, text, logo, watermark";

const LOCATION_PROMPT_PREFIX_MATCHERS = [
  { type: "startsWith", value: "Create a photorealistic empty environment reference image of " },
  { type: "exact", value: "The location itself is the only subject." },
  { type: "exact", value: "Show no people, no characters, no creatures, no silhouettes, no body parts, and no active figure of any kind." },
  { type: "exact", value: "Treat this as a worldbuilding reference plate for a canon location, not a movie still, not a staged action scene, and not a narrative moment." },
];

const LOCATION_PROMPT_SUFFIX_MATCHERS = [
  { type: "exact", value: "Use a wide, readable environmental composition with coherent architecture, believable scale, and stable physical layout." },
  { type: "exact", value: "Keep the framing observational and documentary, as if cataloging the place for production design reference." },
  { type: "exact", value: "The scene must read as a permanent, believable place with coherent architecture, stable layout, realistic scale, and no decorative fantasy exaggeration." },
  { type: "exact", value: "The scene is completely empty. No people, characters, creatures, silhouettes, statues resembling living figures, vehicles, signs, barriers, ropes, bins, or temporary objects." },
  { type: "exact", value: "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects." },
];

const CREATURE_PROMPT_PREFIX_MATCHERS = [
  { type: "startsWith", value: "Create a photorealistic creature reference image of " },
  { type: "exact", value: "The creature itself is the only subject." },
  { type: "exact", value: "Show no people, no characters, no handlers, no riders, no extra creatures, and no environmental storytelling action." },
  { type: "exact", value: "Treat this as a worldbuilding reference plate for a canon creature, not a battle scene, not a movie still, and not a dramatic narrative moment." },
];

const CREATURE_PROMPT_SUFFIX_MATCHERS = [
  { type: "exact", value: "Use a clear full-subject composition with readable silhouette, believable anatomy, grounded material detail, and stable proportions." },
  { type: "exact", value: "Keep the framing observational and documentary, as if cataloging the creature for a production design reference library." },
  { type: "exact", value: "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects." },
];

const OBJECT_PROMPT_PREFIX_MATCHERS = [
  { type: "startsWith", value: "Create a photorealistic isolated prop reference image of " },
  { type: "exact", value: "The object itself is the only subject." },
  { type: "exact", value: "Show no people, no hands, no characters, no creatures, no shelves full of props, and no environmental storytelling clutter." },
  { type: "exact", value: "Treat this as a worldbuilding reference plate for a canon object, not a product ad, not a movie still, and not a staged action scene." },
];

const OBJECT_PROMPT_SUFFIX_MATCHERS = [
  { type: "exact", value: "Use a clean readable composition with the full object clearly visible, stable proportions, believable construction, and grounded material detail." },
  { type: "exact", value: "Keep the framing observational and documentary, as if cataloging the prop for production design reference." },
  { type: "exact", value: "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects." },
];

function lineMatchesTemplateRule(line, rule) {
  const normalizedLine = String(line || "").trim();
  if (!normalizedLine) return false;
  if (rule.type === "startsWith") {
    return normalizedLine.startsWith(rule.value);
  }
  return normalizedLine === rule.value;
}

function splitPromptWithTemplateMatchers(prompt, prefixMatchers = [], suffixMatchers = []) {
  const lines = String(prompt || "").split("\n").map((line) => line.trim()).filter(Boolean);
  if (!lines.length) {
    return {
      lockedPrefix: "",
      editableBody: "",
      lockedSuffix: "",
    };
  }

  let prefixCount = 0;
  while (prefixCount < prefixMatchers.length && prefixCount < lines.length && lineMatchesTemplateRule(lines[prefixCount], prefixMatchers[prefixCount])) {
    prefixCount += 1;
  }

  let suffixCount = 0;
  while (
    suffixCount < suffixMatchers.length &&
    lines.length - 1 - suffixCount >= prefixCount &&
    lineMatchesTemplateRule(lines[lines.length - 1 - suffixCount], suffixMatchers[suffixMatchers.length - 1 - suffixCount])
  ) {
    suffixCount += 1;
  }

  if (!prefixCount && !suffixCount) {
    return {
      lockedPrefix: "",
      editableBody: String(prompt || "").trim(),
      lockedSuffix: "",
    };
  }

  return {
    lockedPrefix: lines.slice(0, prefixCount).join("\n"),
    editableBody: lines.slice(prefixCount, lines.length - suffixCount).join("\n"),
    lockedSuffix: suffixCount ? lines.slice(lines.length - suffixCount).join("\n") : "",
  };
}

export function splitPositivePrompt(prompt, entityType = "") {
  const normalizedEntityType = String(entityType || "").trim().toLowerCase();
  if (normalizedEntityType === "location") {
    return splitPromptWithTemplateMatchers(prompt, LOCATION_PROMPT_PREFIX_MATCHERS, LOCATION_PROMPT_SUFFIX_MATCHERS);
  }
  if (normalizedEntityType === "creature") {
    return splitPromptWithTemplateMatchers(prompt, CREATURE_PROMPT_PREFIX_MATCHERS, CREATURE_PROMPT_SUFFIX_MATCHERS);
  }
  if (normalizedEntityType === "object") {
    return splitPromptWithTemplateMatchers(prompt, OBJECT_PROMPT_PREFIX_MATCHERS, OBJECT_PROMPT_SUFFIX_MATCHERS);
  }
  const lines = String(prompt || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const matchesCharacterTemplate =
    lines.length >= CHARACTER_PROMPT_PREFIX_LINES.length + CHARACTER_PROMPT_SUFFIX_LINES.length &&
    CHARACTER_PROMPT_PREFIX_LINES.every((line, index) => lines[index] === line) &&
    CHARACTER_PROMPT_SUFFIX_LINES.every((line, index) => lines[lines.length - CHARACTER_PROMPT_SUFFIX_LINES.length + index] === line);
  if (!matchesCharacterTemplate) {
    return {
      lockedPrefix: "",
      editableBody: String(prompt || "").trim(),
      lockedSuffix: "",
    };
  }
  return {
    lockedPrefix: CHARACTER_PROMPT_PREFIX_LINES.join("\n"),
    editableBody: lines.slice(CHARACTER_PROMPT_PREFIX_LINES.length, lines.length - CHARACTER_PROMPT_SUFFIX_LINES.length).join("\n"),
    lockedSuffix: CHARACTER_PROMPT_SUFFIX_LINES.join("\n"),
  };
}

export function negativePromptBaseForEntity(entityType = "") {
  const normalizedEntityType = String(entityType || "").trim().toLowerCase();
  if (normalizedEntityType === "location") return LOCATION_NEGATIVE_PROMPT;
  if (normalizedEntityType === "creature") return CREATURE_NEGATIVE_PROMPT;
  if (normalizedEntityType === "object") return OBJECT_NEGATIVE_PROMPT;
  return CHARACTER_NEGATIVE_PROMPT;
}

export function splitNegativePrompt(prompt, entityType = "") {
  const lockedBase = negativePromptBaseForEntity(entityType);
  const value = String(prompt || "").trim();
  if (!value) {
    return { lockedBase, editableTail: "" };
  }
  if (value.startsWith(lockedBase)) {
    const tail = value.slice(lockedBase.length).replace(/^[,\s]+/, "");
    return { lockedBase, editableTail: tail };
  }
  return { lockedBase, editableTail: value };
}

export function composePrompt(prefix, body, suffix) {
  return [prefix, body, suffix].map((value) => String(value || "").trim()).filter(Boolean).join("\n");
}

export function composeNegativePrompt(lockedBase, editableTail) {
  const base = String(lockedBase || "").trim();
  const tail = String(editableTail || "").trim();
  if (!tail) return base;
  return `${base}, ${tail}`;
}

export function promptKey(positive, negative) {
  return JSON.stringify([String(positive || "").trim(), String(negative || "").trim()]);
}

function positivePromptLabelsForEntity(entityType = "") {
  const normalizedEntityType = String(entityType || "").trim().toLowerCase();
  if (normalizedEntityType === "location") {
    return { prefix: "Location reference rules", suffix: "Documentary render constraints" };
  }
  if (normalizedEntityType === "creature") {
    return { prefix: "Creature reference rules", suffix: "Render constraints" };
  }
  if (normalizedEntityType === "object") {
    return { prefix: "Object reference rules", suffix: "Render constraints" };
  }
  return { prefix: "Character-sheet rules", suffix: "Photorealism constraints" };
}

export function positivePromptSegments(editorState, entityType = "") {
  const labels = positivePromptLabelsForEntity(entityType);
  return [
    editorState.positivePrefix
      ? {
          id: "positive-prefix",
          kind: "locked",
          title: labels.prefix,
          value: editorState.positivePrefix,
        }
      : null,
    {
      id: "positive-body",
      kind: "editable",
      title: "Your prompt",
      value: editorState.positiveBody,
      placeholder: "Add or refine the story-specific part of the positive prompt...",
    },
    editorState.positiveSuffix
      ? {
          id: "positive-suffix",
          kind: "locked",
          title: labels.suffix,
          value: editorState.positiveSuffix,
        }
      : null,
  ].filter(Boolean);
}

export function negativePromptSegments(editorState, entityType = "") {
  const normalizedEntityType = String(entityType || "").trim().toLowerCase();
  const title = normalizedEntityType === "location"
    ? "Location negative template"
    : normalizedEntityType === "creature"
      ? "Creature negative template"
      : normalizedEntityType === "object"
        ? "Object negative template"
        : "Base negative template";
  return [
    editorState.negativeBase
      ? {
          id: "negative-base",
          kind: "locked",
          title,
          value: editorState.negativeBase,
        }
      : null,
    {
      id: "negative-tail",
      kind: "editable",
      title: "Your prompt",
      value: editorState.negativeTail,
      placeholder: "Add extra negative tokens or leave this empty...",
    },
  ].filter(Boolean);
}

export function segmentLineCount(value) {
  return Math.max(
    1,
    String(value || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean).length,
  );
}
