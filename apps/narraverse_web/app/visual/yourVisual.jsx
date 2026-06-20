"use client";

import { useEffect, useMemo, useState } from "react";
import LeftBox from "./boxes/leftBox";
import RightBox from "./boxes/rightbox";
import { runtimeApi, runtimeFileUrl } from "@/lib/runtimeApi";

function composePositivePrompt(editor, draft) {
  const prefix = String(editor?.positive?.locked_prefix || "").trim();
  const body = String(draft || "").trim();
  const suffix = String(editor?.positive?.locked_suffix || "").trim();
  return [prefix, body, suffix].filter(Boolean).join("\n");
}

function composeNegativePrompt(editor) {
  const base = String(editor?.negative?.locked_base || "").trim();
  const tail = String(editor?.negative?.editable_tail || "").trim();
  return [base, tail].filter(Boolean).join(", ");
}

export default function YourVisual() {
  const [seriesOptions, setSeriesOptions] = useState([]);
  const [selectedSeriesId, setSelectedSeriesId] = useState("");
  const [entityType, setEntityType] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [entityOptions, setEntityOptions] = useState([]);
  const [selectedEntityId, setSelectedEntityId] = useState("");
  const [assetDetail, setAssetDetail] = useState(null);
  const [promptDraft, setPromptDraft] = useState("");
  const [previewState, setPreviewState] = useState({
    imagePath: "",
    thumbnailPath: "",
    fingerprint: "",
  });
  const [loadingState, setLoadingState] = useState({
    series: true,
    entities: false,
    asset: false,
    generating: false,
    saving: false,
  });
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [selectedGalleryId, setSelectedGalleryId] = useState("");

  useEffect(() => {
    let active = true;
    setLoadingState((current) => ({ ...current, series: true }));
    runtimeApi
      .assetSeriesSummary()
      .then((payload) => {
        if (!active) return;
        const series = payload?.series || [];
        setSeriesOptions(series);
        setSelectedSeriesId((current) => current || series[0]?.series_id || "");
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load backend series.");
      })
      .finally(() => {
        if (!active) return;
        setLoadingState((current) => ({ ...current, series: false }));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedSeriesId) {
      setEntityOptions([]);
      setSelectedEntityId("");
      return;
    }
    let active = true;
    setLoadingState((current) => ({ ...current, entities: true }));
    runtimeApi
      .assets({
        series_id: selectedSeriesId,
        entity_type: entityType,
        q: searchQuery,
        limit: 24,
      })
      .then((payload) => {
        if (!active) return;
        const entities = payload?.entities || [];
        setEntityOptions(entities);
        setSelectedEntityId((current) => {
          if (entities.some((item) => item.id === current)) {
            return current;
          }
          return entities[0]?.id || "";
        });
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load backend assets.");
      })
      .finally(() => {
        if (!active) return;
        setLoadingState((current) => ({ ...current, entities: false }));
      });
    return () => {
      active = false;
    };
  }, [selectedSeriesId, entityType, searchQuery]);

  useEffect(() => {
    if (!selectedEntityId) {
      setAssetDetail(null);
      setPromptDraft("");
      setPreviewState({ imagePath: "", thumbnailPath: "", fingerprint: "" });
      return;
    }
    let active = true;
    setLoadingState((current) => ({ ...current, asset: true }));
    runtimeApi
      .asset(selectedEntityId)
      .then((payload) => {
        if (!active) return;
        setAssetDetail(payload);
        const editor = payload?.prompt_editor;
        setPromptDraft(
          String(
            editor?.positive?.editable_body ||
              payload?.prompts?.[0]?.positive_prompt ||
              "",
          ).trim(),
        );
        setPreviewState({ imagePath: "", thumbnailPath: "", fingerprint: "" });
        setSelectedGalleryId(payload?.images?.[0]?.id || "");
        setStatus("");
        setError("");
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load asset details.");
      })
      .finally(() => {
        if (!active) return;
        setLoadingState((current) => ({ ...current, asset: false }));
      });
    return () => {
      active = false;
    };
  }, [selectedEntityId]);

  const entity = assetDetail?.entity || null;
  const promptEditor = assetDetail?.prompt_editor || null;
  const compiledPositivePrompt = useMemo(
    () => composePositivePrompt(promptEditor, promptDraft),
    [promptEditor, promptDraft],
  );
  const compiledNegativePrompt = useMemo(
    () => composeNegativePrompt(promptEditor),
    [promptEditor],
  );

  const galleryItems = useMemo(
    () =>
      (assetDetail?.images || []).map((image) => ({
        id: image.id,
        label: image.render_status || "rendered image",
        imageUrl: runtimeFileUrl(image.output_path),
        thumbnailUrl: runtimeFileUrl(image.thumbnail_path),
      })),
    [assetDetail],
  );

  const selectedGalleryItem =
    galleryItems.find((item) => item.id === selectedGalleryId) || galleryItems[0];

  const displayImageUrl = previewState.imagePath
    ? runtimeFileUrl(previewState.imagePath)
    : selectedGalleryItem?.imageUrl || "";

  async function handleGenerate() {
    if (!selectedEntityId || !compiledPositivePrompt) {
      return;
    }
    setError("");
    setStatus("");
    setLoadingState((current) => ({ ...current, generating: true }));
    try {
      const result = await runtimeApi.previewRenderEntity(selectedEntityId, {
        positive_prompt: compiledPositivePrompt,
        negative_prompt: compiledNegativePrompt,
      });
      setPreviewState({
        imagePath: result.preview_image_path || "",
        thumbnailPath: result.preview_thumbnail_path || "",
        fingerprint: result.fingerprint || "",
      });
      setStatus(
        "Preview render ready from the Dashboard Pro backend. Save to commit it into the visual library.",
      );
    } catch (err) {
      setError(err.message || "Preview render failed.");
    } finally {
      setLoadingState((current) => ({ ...current, generating: false }));
    }
  }

  async function handleSave() {
    if (!selectedEntityId || !previewState.imagePath) {
      return;
    }
    setError("");
    setStatus("");
    setLoadingState((current) => ({ ...current, saving: true }));
    try {
      const result = await runtimeApi.saveRenderedEntity(selectedEntityId, {
        positive_prompt: compiledPositivePrompt,
        negative_prompt: compiledNegativePrompt,
        preview_image_path: previewState.imagePath,
      });
      setAssetDetail(result);
      const firstImage = result?.images?.[0];
      setSelectedGalleryId(firstImage?.id || "");
      setPreviewState({ imagePath: "", thumbnailPath: "", fingerprint: "" });
      setStatus("Saved the rendered visual back into the shared S.A.G.A. library.");
    } catch (err) {
      setError(err.message || "Saving the rendered visual failed.");
    } finally {
      setLoadingState((current) => ({ ...current, saving: false }));
    }
  }

  const helperText = error
    ? error
    : loadingState.series
      ? "Loading story universes from the existing S.A.G.A. backend..."
      : "This page now uses the same visual asset backend as Dashboard Pro. Select an existing analyzed asset, adjust the prompt, and render a preview here.";

  const entityDescription = entity
    ? `${entity.entity_type} - ${entity.book_title}`
    : "Your AI-generated visuals will appear here.";

  return (
    <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pb-24 pt-6 lg:flex-row lg:items-start lg:px-8">
      <LeftBox
        num="1"
        seriesOptions={seriesOptions}
        selectedSeriesId={selectedSeriesId}
        onSeriesChange={setSelectedSeriesId}
        entityType={entityType}
        onEntityTypeChange={setEntityType}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        entityOptions={entityOptions}
        selectedEntityId={selectedEntityId}
        onEntityChange={setSelectedEntityId}
        promptDraft={promptDraft}
        onPromptDraftChange={setPromptDraft}
        bookTitle={entity?.book_title || ""}
        loadingSeries={loadingState.series}
        loadingEntities={loadingState.entities}
        loadingAsset={loadingState.asset}
        onGenerate={handleGenerate}
        generating={loadingState.generating}
        disabled={!selectedEntityId || loadingState.asset || loadingState.entities}
        helperText={helperText}
      />

      <RightBox
        num1="2"
        num2="3"
        imageUrl={displayImageUrl}
        title={entity?.name || ""}
        description={entityDescription}
        status={status || error}
        onSave={handleSave}
        canSave={Boolean(previewState.imagePath)}
        saving={loadingState.saving}
        galleryItems={galleryItems}
        selectedGalleryId={selectedGalleryId}
        onSelectGallery={setSelectedGalleryId}
        renderStatus={previewState.imagePath ? "preview rendered" : entity?.render_status}
      />
    </div>
  );
}
