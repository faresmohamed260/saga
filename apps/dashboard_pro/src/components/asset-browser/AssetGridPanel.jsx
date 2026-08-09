import { Badge, Button, EmptyState, Panel, StatusBanner } from "../primitives";
import { AssetCard } from "./AssetCard";

export function AssetGridPanel({
  totalAssets,
  filteredAssets,
  page,
  totalPages,
  selectedCount,
  bulkState,
  selectedIdSet,
  onRenderSelected,
  onDeleteSelected,
  onPreviousPage,
  onNextPage,
  onToggleSelect,
  onOpen,
}) {
  return (
    <Panel
      title={`${totalAssets} asset${totalAssets === 1 ? "" : "s"}`}
      subtitle="Thumbnail-first browsing keeps initial load fast. Select a card to inspect the full asset and prompt details."
      action={filteredAssets.length ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {selectedCount ? (
            <>
              <Badge tone="blue">{`${selectedCount} selected`}</Badge>
              <Button onClick={onRenderSelected} variant="secondary" disabled={bulkState.rendering || bulkState.deleting}>
                {bulkState.rendering ? "Rendering..." : "Render selected"}
              </Button>
              <Button onClick={onDeleteSelected} variant="danger" disabled={bulkState.rendering || bulkState.deleting}>
                {bulkState.deleting ? "Deleting..." : "Delete selected"}
              </Button>
            </>
          ) : null}
          <Button onClick={onPreviousPage} disabled={page <= 1}>
            Previous
          </Button>
          <Badge tone="blue">{`Page ${page}/${totalPages}`}</Badge>
          <Button onClick={onNextPage} disabled={page >= totalPages}>
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
              onToggleSelect={() => onToggleSelect(entity.id)}
              onOpen={() => onOpen(entity.id)}
            />
          ))}
        </div>
      ) : (
        <EmptyState title="No assets match the current filters">Try another series, entity type, or character/location name.</EmptyState>
      )}
    </Panel>
  );
}
