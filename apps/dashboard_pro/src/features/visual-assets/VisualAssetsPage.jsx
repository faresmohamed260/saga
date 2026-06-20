import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Panel, SearchBox, text, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";

const ENTITY_FILTERS = ["all", "character", "location", "creature", "object", "organization"];
const PAGE_SIZE = 48;
const STANDARD_ASSET_RATIO_CLASS = "aspect-[47/32]";
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
const CHARACTER_NEGATIVE_PROMPT = "illustration, painterly style, anime, CGI, 3D render, game character, plastic or overly smooth skin, no toon shading, no cel shading, exaggerated proportions, cinematic lighting, dramatic shadows, fantasy glow, magical effects, environment or scenery, extra characters or duplicates, modern clothing, denim, t-shirt, hoodie, sneakers, zipper, plastic accessories, modern jewelry, futuristic materials, contemporary streetwear.";
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

function assetImageUrl(path) {
  return path ? `/runtime/file?path=${encodeURIComponent(path)}` : "";
}

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

function splitPositivePrompt(prompt, entityType = "") {
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

function negativePromptBaseForEntity(entityType = "") {
  const normalizedEntityType = String(entityType || "").trim().toLowerCase();
  if (normalizedEntityType === "location") return LOCATION_NEGATIVE_PROMPT;
  if (normalizedEntityType === "creature") return CREATURE_NEGATIVE_PROMPT;
  if (normalizedEntityType === "object") return OBJECT_NEGATIVE_PROMPT;
  return CHARACTER_NEGATIVE_PROMPT;
}

function splitNegativePrompt(prompt, entityType = "") {
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

function composePrompt(prefix, body, suffix) {
  return [prefix, body, suffix].map((value) => String(value || "").trim()).filter(Boolean).join("\n");
}

function composeNegativePrompt(lockedBase, editableTail) {
  const base = String(lockedBase || "").trim();
  const tail = String(editableTail || "").trim();
  if (!tail) return base;
  return `${base}, ${tail}`;
}

function promptKey(positive, negative) {
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

function positivePromptSegments(editorState, entityType = "") {
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

function negativePromptSegments(editorState, entityType = "") {
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

function segmentLineCount(value) {
  return Math.max(
    1,
    String(value || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean).length,
  );
}

export function VisualAssetsPage() {
  const [entityType, setEntityType] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedSeriesId, setSelectedSeriesId] = useState("");
  const [page, setPage] = useState(1);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkState, setBulkState] = useState({
    rendering: false,
    deleting: false,
    message: "",
    error: "",
  });
  const seriesSummary = useAsync(() => runtimeApi.assetSeriesSummary(), []);

  const seriesCards = useMemo(
    () => (seriesSummary.value?.series || []).map((item) => ({
      seriesId: item.series_id || "unassigned",
      seriesTitle: item.series_title || item.series_id || "Unassigned",
      assetCount: Number(item.asset_count || 0),
      renderedCount: Number(item.rendered_count || 0),
    })),
    [seriesSummary.value],
  );

  useEffect(() => {
    if (!seriesCards.length) {
      if (selectedSeriesId) setSelectedSeriesId("");
      return;
    }
    const stillExists = seriesCards.some((item) => item.seriesId === selectedSeriesId);
    if (!selectedSeriesId || !stillExists) {
      setSelectedSeriesId(seriesCards[0].seriesId);
    }
  }, [selectedSeriesId, seriesCards]);

  useEffect(() => {
    setPage(1);
  }, [selectedSeriesId, entityType, query]);

  useEffect(() => {
    setSelectedIds([]);
    setBulkState({ rendering: false, deleting: false, message: "", error: "" });
  }, [selectedSeriesId]);

  const assets = useAsync(
    () =>
      runtimeApi.assets({
        series_id: selectedSeriesId,
        entity_type: entityType === "all" ? "" : entityType,
        q: query.trim(),
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    [selectedSeriesId, entityType, query, page],
  );

  const selectedAsset = useAsync(
    () => (selectedAssetId ? runtimeApi.asset(selectedAssetId) : Promise.resolve(null)),
    [selectedAssetId],
    { initialData: null },
  );

  const filteredAssets = assets.value?.entities || [];
  const totalAssets = Number(assets.value?.total || 0);
  const totalPages = Math.max(1, Math.ceil(totalAssets / PAGE_SIZE));
  const selectedCount = selectedIds.length;
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  function toggleSelectedAsset(entityId) {
    setSelectedIds((current) => (
      current.includes(entityId)
        ? current.filter((item) => item !== entityId)
        : [...current, entityId]
    ));
  }

  async function handleRenderSelected() {
    if (!selectedIds.length) return;
    const idsToRender = [...selectedIds];
    setSelectedIds([]);
    setBulkState({ rendering: true, deleting: false, message: "", error: "" });
    try {
      await runtimeApi.renderBatch({ entity_ids: idsToRender });
      setBulkState({
        rendering: false,
        deleting: false,
        message: `Queued saved renders for ${idsToRender.length} selected asset${idsToRender.length === 1 ? "" : "s"}.`,
        error: "",
      });
    } catch (exc) {
      setBulkState({
        rendering: false,
        deleting: false,
        message: "",
        error: exc.message || String(exc),
      });
    }
    assets.reload();
    seriesSummary.reload();
  }

  async function handleDeleteSelected() {
    if (!selectedIds.length) return;
    const confirmed = window.confirm(`Delete ${selectedIds.length} selected asset${selectedIds.length === 1 ? "" : "s"} from the system? This removes each entity and its saved prompts/images.`);
    if (!confirmed) return;
    const idsToDelete = [...selectedIds];
    setSelectedIds([]);
    setBulkState({ rendering: false, deleting: true, message: "", error: "" });
    const results = await Promise.allSettled(idsToDelete.map((entityId) => runtimeApi.deleteAssetEntity(entityId)));
    const succeededIds = idsToDelete.filter((_, index) => results[index]?.status === "fulfilled");
    const failed = results.length - succeededIds.length;
    if (selectedAssetId && succeededIds.includes(selectedAssetId)) {
      setSelectedAssetId("");
    }
    setBulkState({
      rendering: false,
      deleting: false,
      message: succeededIds.length ? `Deleted ${succeededIds.length} selected asset${succeededIds.length === 1 ? "" : "s"}.` : "",
      error: failed ? `Failed to delete ${failed} selected asset${failed === 1 ? "" : "s"}.` : "",
    });
    assets.reload();
    seriesSummary.reload();
  }

  return (
    <div className="space-y-5">
      <Panel
        title="Visual Asset Browser"
        subtitle="Browse by series first, then load lightweight thumbnail pages instead of the full asset library at once."
      >
        {seriesCards.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {seriesCards.map((item) => {
              const selected = item.seriesId === selectedSeriesId;
              return (
                <button
                  key={item.seriesId}
                  type="button"
                  onClick={() => setSelectedSeriesId(item.seriesId)}
                  className={[
                    "rounded-2xl border p-4 text-left transition",
                    selected
                      ? "border-sky-500/70 bg-sky-500/10 shadow-lg shadow-sky-950/30"
                      : "border-slate-800 bg-slate-950/45 hover:border-sky-500/40 hover:bg-sky-500/5",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold uppercase tracking-[0.2em] text-slate-500">{item.seriesId}</p>
                      <h3 className="mt-2 text-xl font-black text-white">{item.seriesTitle}</h3>
                    </div>
                    <Badge tone={selected ? "blue" : "slate"}>{item.assetCount} assets</Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Badge tone="green">{item.renderedCount} rendered</Badge>
                    <Badge>{Math.max(item.assetCount - item.renderedCount, 0)} pending</Badge>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No series with visual assets found">Run visual generation first, then the browser will group assets by series.</EmptyState>
        )}
      </Panel>

      <Panel
        title={selectedSeriesId ? `Assets for ${selectedSeriesId}` : "Asset inventory"}
        subtitle="The grid loads paged thumbnails only. Full prompts and original images open on demand."
      >
        <div className="mb-4 flex flex-wrap gap-2">
          {ENTITY_FILTERS.map((item) => (
            <Button
              key={item}
              onClick={() => setEntityType(item)}
              variant={entityType === item ? "primary" : "secondary"}
            >
              {item}
            </Button>
          ))}
        </div>
        <SearchBox value={query} onChange={setQuery} placeholder="Search entity name..." />
      </Panel>

      <Panel
        title={`${totalAssets} asset${totalAssets === 1 ? "" : "s"}`}
        subtitle="Thumbnail-first browsing keeps initial load fast. Select a card to inspect the full asset and prompt details."
        action={filteredAssets.length ? (
          <div className="flex items-center gap-2">
            {selectedCount ? (
              <>
                <Badge tone="blue">{`${selectedCount} selected`}</Badge>
                <Button onClick={handleRenderSelected} variant="secondary" disabled={bulkState.rendering || bulkState.deleting}>
                  {bulkState.rendering ? "Rendering..." : "Render selected"}
                </Button>
                <Button onClick={handleDeleteSelected} variant="danger" disabled={bulkState.rendering || bulkState.deleting}>
                  {bulkState.deleting ? "Deleting..." : "Delete selected"}
                </Button>
              </>
            ) : null}
            <Button onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>
              Previous
            </Button>
            <Badge tone="blue">{`Page ${page}/${totalPages}`}</Badge>
            <Button onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page >= totalPages}>
              Next
            </Button>
          </div>
        ) : null}
      >
        {bulkState.error ? <StatusBanner tone="red" message={bulkState.error} /> : null}
        {bulkState.message ? <div className="mb-4"><StatusBanner tone="green" message={bulkState.message} /></div> : null}
        {filteredAssets.length ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {filteredAssets.map((entity) => (
              <AssetCard
                key={entity.id}
                entity={entity}
                selected={selectedIdSet.has(entity.id)}
                onToggleSelect={() => toggleSelectedAsset(entity.id)}
                onOpen={() => setSelectedAssetId(entity.id)}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No assets match the current filters">Try another series, entity type, or character/location name.</EmptyState>
        )}
      </Panel>

      {selectedAssetId ? (
        <AssetModal
          entityId={selectedAssetId}
          payload={selectedAsset.value}
          loading={selectedAsset.loading}
          onSaved={(assetPayload) => {
            if (assetPayload) {
              selectedAsset.setData(assetPayload);
            }
            assets.reload();
            seriesSummary.reload();
          }}
          onDeleted={() => {
            setSelectedAssetId("");
            setSelectedIds((current) => current.filter((item) => item !== selectedAssetId));
            assets.reload();
            seriesSummary.reload();
          }}
          onClose={() => setSelectedAssetId("")}
        />
      ) : null}
    </div>
  );
}

function AssetCard({ entity, selected, onToggleSelect, onOpen }) {
  const thumbnailPath = entity.generated_thumbnail_path || entity.generated_image_path;
  const hasImage = !!thumbnailPath;

  return (
    <div
      className={[
        "overflow-hidden rounded-3xl border bg-slate-950/55 text-left transition",
        selected
          ? "border-emerald-400/55 shadow-lg shadow-emerald-950/20"
          : "border-slate-800 hover:border-sky-500/50 hover:bg-sky-500/5",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <label className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-emerald-400 focus:ring-emerald-400"
          />
          Select
        </label>
        <Badge tone={selected ? "green" : toneFor(entity.render_status)}>{selected ? "selected" : (entity.render_status || "not rendered")}</Badge>
      </div>

      <button
        type="button"
        onClick={onOpen}
        className="block w-full text-left"
      >
        <div className={`${STANDARD_ASSET_RATIO_CLASS} border-b border-slate-800 bg-black/40`}>
        {hasImage ? (
          <img
            src={assetImageUrl(thumbnailPath)}
            alt={entity.name}
            loading="lazy"
            decoding="async"
            className="h-full w-full bg-[#050816] object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <EmptyState title="No image">Render pending</EmptyState>
          </div>
        )}
        </div>

        <div className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-black text-white">{entity.name}</h3>
              <p className="mt-1 text-sm text-slate-400">{entity.book_title || entity.series_title || entity.series_id || entity.book_id}</p>
            </div>
            <Badge tone={toneFor(entity.render_status)}>{entity.render_status || "not rendered"}</Badge>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone="blue">{entity.entity_type}</Badge>
            <Badge>{entity.prompt_count || 0} prompts</Badge>
            <Badge tone={entity.image_count ? "green" : "amber"}>{entity.image_count || 0} images</Badge>
          </div>
        </div>
      </button>
    </div>
  );
}

function AssetModal({ entityId, payload, loading, onSaved, onDeleted, onClose }) {
  const entity = payload?.entity || {};
  const prompts = payload?.prompts || [];
  const images = payload?.images || [];
  const promptEditor = payload?.prompt_editor || null;
  const latestPrompt = prompts[0] || {};
  const activeImage = images[0] || {};
  const [editorState, setEditorState] = useState(() => ({
    positivePrefix: "",
    positiveBody: "",
    positiveSuffix: "",
    negativeBase: CHARACTER_NEGATIVE_PROMPT,
    negativeTail: "",
  }));
  const [baselineEditorState, setBaselineEditorState] = useState(() => ({
    positivePrefix: "",
    positiveBody: "",
    positiveSuffix: "",
    negativeBase: CHARACTER_NEGATIVE_PROMPT,
    negativeTail: "",
  }));
  const [baselinePromptState, setBaselinePromptState] = useState({ positive: "", negative: "" });
  const [previewState, setPreviewState] = useState({
    imagePath: "",
    thumbnailPath: "",
    promptKey: "",
    rendering: false,
    saving: false,
    deleting: false,
    error: "",
    message: "",
  });
  const [activePromptTab, setActivePromptTab] = useState("positive");
  const [renameDraft, setRenameDraft] = useState("");
  const [renaming, setRenaming] = useState(false);
  const fullImagePath = activeImage.output_path || entity.generated_image_path;
  const displayedImagePath = previewState.imagePath || fullImagePath;

  useEffect(() => {
    const positive = promptEditor?.positive
      ? {
          lockedPrefix: promptEditor.positive.locked_prefix || "",
          editableBody: promptEditor.positive.editable_body || "",
          lockedSuffix: promptEditor.positive.locked_suffix || "",
        }
      : splitPositivePrompt(latestPrompt.positive_prompt || entity.baseline_visual_prompt, entity.entity_type);
    const negative = promptEditor?.negative
      ? {
          lockedBase: promptEditor.negative.locked_base || negativePromptBaseForEntity(entity.entity_type),
          editableTail: promptEditor.negative.editable_tail || "",
        }
      : splitNegativePrompt(latestPrompt.negative_prompt, entity.entity_type);
    const baselinePositive = promptEditor?.compiled_positive || composePrompt(positive.lockedPrefix, positive.editableBody, positive.lockedSuffix);
    const baselineNegative = promptEditor?.compiled_negative || composeNegativePrompt(negative.lockedBase, negative.editableTail);
    setEditorState({
      positivePrefix: positive.lockedPrefix,
      positiveBody: positive.editableBody,
      positiveSuffix: positive.lockedSuffix,
      negativeBase: negative.lockedBase,
      negativeTail: negative.editableTail,
    });
    const nextBaselineEditorState = {
      positivePrefix: positive.lockedPrefix,
      positiveBody: positive.editableBody,
      positiveSuffix: positive.lockedSuffix,
      negativeBase: negative.lockedBase,
      negativeTail: negative.editableTail,
    };
    setBaselineEditorState(nextBaselineEditorState);
    setBaselinePromptState({
      positive: baselinePositive,
      negative: baselineNegative,
    });
    setPreviewState({
      imagePath: "",
      thumbnailPath: "",
      promptKey: "",
      rendering: false,
      saving: false,
      deleting: false,
      error: "",
      message: "",
    });
    setActivePromptTab("positive");
    setRenameDraft(entity.name || "");
    setRenaming(false);
  }, [entity.id, entity.name, entity.entity_type, latestPrompt.positive_prompt, latestPrompt.negative_prompt, entity.baseline_visual_prompt, promptEditor]);

  const resolvedPositivePrompt = composePrompt(editorState.positivePrefix, editorState.positiveBody, editorState.positiveSuffix);
  const resolvedNegativePrompt = composeNegativePrompt(editorState.negativeBase, editorState.negativeTail);
  const currentPromptKey = promptKey(resolvedPositivePrompt, resolvedNegativePrompt);
  const canSave = !!previewState.imagePath && previewState.promptKey === currentPromptKey && !previewState.rendering && !previewState.saving;
  const positiveDirty =
    String(editorState.positivePrefix || "") !== String(baselineEditorState.positivePrefix || "") ||
    String(editorState.positiveBody || "") !== String(baselineEditorState.positiveBody || "") ||
    String(editorState.positiveSuffix || "") !== String(baselineEditorState.positiveSuffix || "");
  const negativeDirty =
    String(editorState.negativeBase || "") !== String(baselineEditorState.negativeBase || "") ||
    String(editorState.negativeTail || "") !== String(baselineEditorState.negativeTail || "");
  const activeSegments = activePromptTab === "positive"
    ? positivePromptSegments(editorState, entity.entity_type)
    : negativePromptSegments(editorState, entity.entity_type);
  const compiledPrompt = activePromptTab === "positive" ? resolvedPositivePrompt : resolvedNegativePrompt;
  const renameDirty = String(renameDraft || "").trim() && String(renameDraft || "").trim() !== String(entity.name || "").trim();

  async function handleRender() {
    setPreviewState((current) => ({ ...current, rendering: true, saving: false, error: "", message: "" }));
    try {
      const result = await runtimeApi.previewRenderEntity(entityId, {
        positive_prompt: resolvedPositivePrompt,
        negative_prompt: resolvedNegativePrompt,
      });
      setPreviewState({
        imagePath: result.preview_image_path || "",
        thumbnailPath: result.preview_thumbnail_path || "",
        promptKey: currentPromptKey,
        rendering: false,
        saving: false,
        deleting: false,
        error: "",
        message: "Preview render ready. Save will commit this prompt/image pair.",
      });
    } catch (exc) {
      setPreviewState((current) => ({
        ...current,
        rendering: false,
        error: exc.message || String(exc),
        message: "",
      }));
    }
  }

  async function handleSave() {
    if (!canSave) return;
    setPreviewState((current) => ({ ...current, saving: true, error: "", message: "" }));
    try {
      const result = await runtimeApi.saveRenderedEntity(entityId, {
        positive_prompt: resolvedPositivePrompt,
        negative_prompt: resolvedNegativePrompt,
        preview_image_path: previewState.imagePath,
      });
      setPreviewState((current) => ({
        ...current,
        imagePath: "",
        thumbnailPath: "",
        promptKey: "",
        rendering: false,
        saving: false,
        deleting: false,
        error: "",
        message: "Saved updated prompts and rendered image.",
      }));
      onSaved?.(result.asset || null);
    } catch (exc) {
      setPreviewState((current) => ({
        ...current,
        saving: false,
        error: exc.message || String(exc),
        message: "",
      }));
    }
  }

  async function handleDelete() {
    const entityName = String(entity.name || "this entity").trim();
    const confirmed = window.confirm(`Delete ${entityName} from the system? This will remove the entity and its saved prompts/images for manual cleanup.`);
    if (!confirmed) return;
    setPreviewState((current) => ({ ...current, rendering: false, saving: false, deleting: true, error: "", message: "" }));
    try {
      await runtimeApi.deleteAssetEntity(entityId);
      onDeleted?.();
    } catch (exc) {
      setPreviewState((current) => ({
        ...current,
        deleting: false,
        error: exc.message || String(exc),
        message: "",
      }));
    }
  }

  async function handleRename() {
    const nextName = String(renameDraft || "").trim();
    if (!nextName || nextName === String(entity.name || "").trim()) return;
    setRenaming(true);
    setPreviewState((current) => ({ ...current, error: "", message: "" }));
    try {
      const result = await runtimeApi.renameAssetEntity(entityId, { name: nextName });
      setRenameDraft(result.new_name || nextName);
      setPreviewState((current) => ({
        ...current,
        error: "",
        message: "Entity renamed across the system.",
      }));
      onSaved?.(result.asset || null);
    } catch (exc) {
      setPreviewState((current) => ({
        ...current,
        error: exc.message || String(exc),
        message: "",
      }));
    } finally {
      setRenaming(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-7xl overflow-hidden rounded-3xl border border-slate-800 bg-[#050816] shadow-2xl shadow-black/50">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-4">
          <div>
            <h3 className="text-2xl font-black text-white">{entity.name || "Loading asset"}</h3>
          </div>
          <div className="flex items-center gap-2">
            {displayedImagePath ? (
              <a
                href={assetImageUrl(displayedImagePath)}
                download
                className="rounded-xl border border-emerald-400/50 bg-emerald-500/15 px-4 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-500/25"
              >
                Download
              </a>
            ) : null}
            <Button onClick={handleDelete} variant="danger" disabled={previewState.rendering || previewState.saving || previewState.deleting || renaming}>
              {previewState.deleting ? "Deleting..." : "Delete"}
            </Button>
            <Button onClick={handleRender} variant="secondary" disabled={previewState.rendering || previewState.saving || previewState.deleting || renaming}>
              {previewState.rendering ? "Rendering..." : "Render"}
            </Button>
            <Button onClick={handleSave} variant="primary" disabled={!canSave || previewState.deleting || renaming}>
              {previewState.saving ? "Saving..." : "Save"}
            </Button>
            <Button onClick={onClose} disabled={previewState.deleting || renaming}>Close</Button>
          </div>
        </div>

        <div className="grid max-h-[calc(92vh-5rem)] gap-0 overflow-auto xl:grid-cols-[minmax(0,1.02fr)_minmax(460px,.98fr)]">
          <div className="border-b border-slate-800 bg-black/40 xl:border-b-0 xl:border-r">
            {loading ? (
              <div className="flex min-h-[32rem] items-center justify-center p-8 text-slate-400">Loading full asset details...</div>
            ) : displayedImagePath ? (
              <div className="flex min-h-[32rem] items-center justify-center p-6">
                <img
                  src={assetImageUrl(displayedImagePath)}
                  alt={entity.name || entityId}
                  className="max-h-[78vh] w-full rounded-2xl object-contain"
                />
              </div>
            ) : (
              <div className="flex min-h-[32rem] items-center justify-center p-8">
                <EmptyState title="No rendered image yet">This entity has no active full-size image stored.</EmptyState>
              </div>
            )}
          </div>

          <div className="space-y-4 p-5">
            <div className="rounded-2xl border border-slate-800 bg-black/25 p-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Entity name</p>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  value={renameDraft}
                  onChange={(event) => setRenameDraft(event.target.value)}
                  placeholder="Rename entity..."
                  className="min-w-[18rem] flex-1 rounded-xl border border-slate-700/80 bg-slate-950/85 px-4 py-2.5 text-sm text-slate-100 outline-none transition focus:border-sky-500/55 focus:ring-1 focus:ring-sky-500/35 placeholder:text-slate-600"
                />
                <Button onClick={handleRename} variant="secondary" disabled={!renameDirty || renaming || previewState.deleting}>
                  {renaming ? "Renaming..." : "Rename"}
                </Button>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">This updates the canonical entity name and the stored visual/analysis references linked to it.</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge tone="blue">{entity.entity_type || "entity"}</Badge>
              <Badge>{prompts.length} prompts</Badge>
              <Badge tone={images.length ? "green" : "amber"}>{images.length} images</Badge>
            </div>

            {previewState.error ? <StatusBanner tone="red" message={previewState.error} /> : null}
            {previewState.message ? <StatusBanner tone="green" message={previewState.message} /> : null}
            {previewState.imagePath && previewState.promptKey !== currentPromptKey ? (
              <StatusBanner tone="amber" message="The prompt changed after the last render. Render again before saving." />
            ) : null}

            <div className="flex flex-wrap gap-2">
              <PromptTab
                active={activePromptTab === "positive"}
                dirty={positiveDirty}
                onClick={() => setActivePromptTab("positive")}
              >
                Positive prompt
              </PromptTab>
              <PromptTab
                active={activePromptTab === "negative"}
                dirty={negativeDirty}
                onClick={() => setActivePromptTab("negative")}
              >
                Negative prompt
              </PromptTab>
            </div>

            <StructuredPromptEditor
              label={activePromptTab === "positive" ? "Positive prompt" : "Negative prompt"}
              helper={
                activePromptTab === "positive"
                  ? "Your text is combined with locked instructions before and after it before rendering."
                  : "Your text is combined with the locked base negative template before rendering."
              }
              compiledPrompt={compiledPrompt}
              segments={activeSegments}
              onChangeSegment={(segmentId, value) => {
                if (segmentId === "positive-body") {
                  setEditorState((current) => ({ ...current, positiveBody: value }));
                }
                if (segmentId === "negative-tail") {
                  setEditorState((current) => ({ ...current, negativeTail: value }));
                }
              }}
              large={activePromptTab === "positive"}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function PromptTab({ active, dirty, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition",
        active ? "border-sky-500/60 bg-sky-500/12 text-white" : "border-slate-800 bg-slate-950/55 text-slate-300 hover:border-sky-500/35",
      ].join(" ")}
    >
      <span>{children}</span>
      {dirty ? <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-amber-200">Edited</span> : null}
    </button>
  );
}

function StructuredPromptEditor({ label, helper = "", compiledPrompt, segments, onChangeSegment, large = false }) {
  const [showCompiled, setShowCompiled] = useState(false);

  useEffect(() => {
    setShowCompiled(false);
  }, [label]);

  return (
    <div className={large ? "rounded-2xl border border-slate-800 bg-black/25 p-5" : "rounded-2xl border border-slate-800 bg-black/25 p-4"}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
        <button
          type="button"
          onClick={() => setShowCompiled((current) => !current)}
          className="text-[11px] font-medium text-sky-300 transition hover:text-sky-200"
        >
          {showCompiled ? "Hide compiled prompt" : "View compiled prompt"}
        </button>
      </div>
      {helper ? <p className="mb-3 text-[11px] leading-5 text-slate-500">{helper}</p> : null}
      {showCompiled ? (
        <div className="mb-3 rounded-xl border border-slate-800 bg-slate-950/75 px-3 py-3">
          <p className="mb-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">Compiled prompt</p>
          <pre className="whitespace-pre-wrap break-words text-[12px] leading-[1.55] text-slate-300">{compiledPrompt || "No prompt compiled yet."}</pre>
        </div>
      ) : null}
      <div className="rounded-2xl border border-slate-800/90 bg-slate-950/80 transition focus-within:border-sky-500/45 focus-within:ring-1 focus-within:ring-sky-500/35">
        <div className="space-y-2 p-3">
          {segments.map((segment) => (
            segment.kind === "locked" ? (
              <LockedPromptToken key={segment.id} title={segment.title} value={segment.value} />
            ) : (
              <EditablePromptRegion
                key={segment.id}
                label={segment.title}
                value={segment.value}
                onChange={(value) => onChangeSegment(segment.id, value)}
                placeholder={segment.placeholder}
                large={large}
              />
            )
          ))}
        </div>
      </div>
    </div>
  );
}

function LockedPromptToken({ title, value }) {
  const lines = String(value || "").split("\n").filter(Boolean);
  const isLong = lines.length > 6;
  const [expanded, setExpanded] = useState(false);
  const preview = isLong && !expanded ? `${lines.slice(0, 2).join(" ")}` : value;

  return (
    <div className="rounded-md bg-slate-900/40 px-3 py-2 text-slate-300">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-[10px] text-slate-500">
          <span aria-hidden="true" className="inline-flex h-3.5 w-3.5 items-center justify-center text-slate-500">
              <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
                <path d="M5.5 7V5.75a2.5 2.5 0 1 1 5 0V7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <rect x="3.5" y="7" width="9" height="6" rx="1.6" stroke="currentColor" strokeWidth="1.2" />
              </svg>
          </span>
          <span className="truncate font-medium uppercase tracking-[0.14em]">{title || "Locked template"}</span>
          <span className="whitespace-nowrap">{segmentLineCount(value)} lines</span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="shrink-0 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500 transition hover:text-slate-300"
        >
          {expanded ? "Hide" : "Preview"}
        </button>
      </div>
      {expanded ? (
        <div className="mt-2 border-l-2 border-slate-700/60 pl-3">
          <p className="whitespace-pre-wrap break-words text-[12.5px] leading-[1.55] text-slate-300">{text(value, "No locked template.")}</p>
        </div>
      ) : isLong ? null : (
        <div className="mt-1.5 border-l-2 border-slate-700/60 pl-3">
          <p className="truncate text-[12px] leading-[1.55] text-slate-400">{preview}</p>
        </div>
      )}
    </div>
  );
}

function EditablePromptRegion({ label, value, onChange, placeholder = "", large = false }) {
  return (
    <div className="rounded-md bg-slate-950/55 px-3 py-2.5">
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={[
          "w-full resize-none overflow-y-auto rounded-md border border-slate-700/80 bg-slate-900/85 px-3 py-2.5 text-[12.5px] leading-[1.55] text-slate-100 outline-none transition focus:border-sky-500/55 focus:ring-1 focus:ring-sky-500/35 placeholder:text-slate-600",
          large ? "h-64" : "h-36",
        ].join(" ")}
      />
    </div>
  );
}

function StatusBanner({ tone = "slate", message }) {
  const classes = {
    slate: "border-slate-700 bg-slate-900/80 text-slate-300",
    green: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
    amber: "border-amber-500/40 bg-amber-500/10 text-amber-100",
    red: "border-red-500/40 bg-red-500/10 text-red-100",
  };
  return <div className={`rounded-xl border px-4 py-3 text-sm ${classes[tone]}`}>{message}</div>;
}
