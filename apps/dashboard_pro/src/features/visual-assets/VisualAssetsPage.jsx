import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { useAsync } from "../../hooks/useAsync";
import { AssetFiltersPanel, AssetGridPanel, AssetSeriesPanel } from "../../components/AssetBrowserPanels";
import { AssetModal } from "../../components/AssetModal";

const PAGE_SIZE = 48;

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
      <AssetSeriesPanel seriesCards={seriesCards} selectedSeriesId={selectedSeriesId} onSelectSeries={setSelectedSeriesId} />
      <AssetFiltersPanel
        selectedSeriesId={selectedSeriesId}
        entityType={entityType}
        onEntityTypeChange={setEntityType}
        query={query}
        onQueryChange={setQuery}
      />
      <AssetGridPanel
        totalAssets={totalAssets}
        filteredAssets={filteredAssets}
        page={page}
        totalPages={totalPages}
        selectedCount={selectedCount}
        bulkState={bulkState}
        selectedIdSet={selectedIdSet}
        onRenderSelected={handleRenderSelected}
        onDeleteSelected={handleDeleteSelected}
        onPreviousPage={() => setPage((current) => Math.max(1, current - 1))}
        onNextPage={() => setPage((current) => Math.min(totalPages, current + 1))}
        onToggleSelect={toggleSelectedAsset}
        onOpen={setSelectedAssetId}
      />

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
