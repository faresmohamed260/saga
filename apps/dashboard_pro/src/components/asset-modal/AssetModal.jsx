import { useEffect, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, StatusBanner } from "../primitives";
import {
  CHARACTER_NEGATIVE_PROMPT,
  composeNegativePrompt,
  composePrompt,
  negativePromptBaseForEntity,
  negativePromptSegments,
  positivePromptSegments,
  promptKey,
  splitNegativePrompt,
  splitPositivePrompt,
} from "../../features/visual-assets/promptTemplates";
import { assetImageUrl } from "./assetImageUrl";
import { PromptTab } from "./PromptTab";
import { StructuredPromptEditor } from "./StructuredPromptEditor";

export function AssetModal({ entityId, payload, loading, onSaved, onDeleted, onClose }) {
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
    imageRef: null,
    thumbnailRef: null,
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
  const fullImageRef =
    activeImage.output_artifact ||
    activeImage.generated_image ||
    entity.generated_image ||
    entity.generated_image_artifact;
  const displayedImageRef = previewState.imageRef || fullImageRef;

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
    setBaselineEditorState({
      positivePrefix: positive.lockedPrefix,
      positiveBody: positive.editableBody,
      positiveSuffix: positive.lockedSuffix,
      negativeBase: negative.lockedBase,
      negativeTail: negative.editableTail,
    });
    setBaselinePromptState({
      positive: baselinePositive,
      negative: baselineNegative,
    });
    setPreviewState({
      imageRef: null,
      thumbnailRef: null,
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
  const canSave = !!previewState.imageRef && previewState.promptKey === currentPromptKey && !previewState.rendering && !previewState.saving;
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
        imageRef: result.preview_image || result.preview_image_artifact || null,
        thumbnailRef: result.preview_thumbnail || result.preview_thumbnail_artifact || null,
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
        preview_image: previewState.imageRef,
      });
      setPreviewState((current) => ({
        ...current,
        imageRef: null,
        thumbnailRef: null,
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
      <div className="max-h-[92vh] w-full max-w-7xl overflow-hidden rounded-lg border border-white/10 bg-[#050816] shadow-2xl shadow-black/50">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
          <div>
            <h3 className="text-2xl font-black text-white">{entity.name || "Loading asset"}</h3>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {displayedImageRef ? (
              <a
                href={assetImageUrl(displayedImageRef)}
                download
                className="rounded-lg border border-emerald-400/50 bg-emerald-400/10 px-4 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-400/20"
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

        <div className="grid max-h-[calc(92vh-5rem)] gap-0 overflow-auto xl:grid-cols-[minmax(0,1.02fr)_minmax(0,.98fr)]">
          <div className="border-b border-white/10 bg-black/40 xl:border-b-0 xl:border-r">
            {loading ? (
              <div className="flex min-h-[32rem] items-center justify-center p-8 text-slate-400">Loading full asset details...</div>
            ) : displayedImageRef ? (
              <div className="flex min-h-[32rem] items-center justify-center p-6">
                <img
                  src={assetImageUrl(displayedImageRef)}
                  alt={entity.name || entityId}
                  className="max-h-[78vh] w-full rounded-lg object-contain"
                />
              </div>
            ) : (
              <div className="flex min-h-[32rem] items-center justify-center p-8">
                <EmptyState title="No rendered image yet">This entity has no active full-size image stored.</EmptyState>
              </div>
            )}
          </div>

          <div className="space-y-4 p-5">
            <div className="rounded-lg border border-white/10 bg-black/25 p-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Entity name</p>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  value={renameDraft}
                  onChange={(event) => setRenameDraft(event.target.value)}
                  placeholder="Rename entity..."
                  className="min-w-0 flex-1 rounded-lg border border-white/10 bg-slate-950/85 px-4 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400/55 focus:ring-1 focus:ring-cyan-400/35"
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
            {previewState.imageRef && previewState.promptKey !== currentPromptKey ? (
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
