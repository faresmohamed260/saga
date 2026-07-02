import { Badge, Button, EmptyState, Panel, SearchBox, StatusBanner, toneFor } from "../../../components/ui/primitives";

const ENTITY_FILTERS = ["all", "character", "location", "creature", "object", "organization"];
const STANDARD_ASSET_RATIO_CLASS = "aspect-[47/32]";

function assetImageUrl(path) {
  return path ? `/runtime/file?path=${encodeURIComponent(path)}` : "";
}

export function AssetSeriesPanel({ seriesCards, selectedSeriesId, onSelectSeries }) {
  return (
    <Panel
      title="Visual Asset Browser"
      subtitle="Browse by series first, then load lightweight thumbnail pages instead of the full asset library at once."
    >
      {seriesCards.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {seriesCards.map((item) => (
            <SeriesCard key={item.seriesId} item={item} selected={item.seriesId === selectedSeriesId} onSelect={() => onSelectSeries(item.seriesId)} />
          ))}
        </div>
      ) : (
        <EmptyState title="No series with visual assets found">Run visual generation first, then the browser will group assets by series.</EmptyState>
      )}
    </Panel>
  );
}

function SeriesCard({ item, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "rounded-2xl border p-4 text-left transition",
        selected
          ? "border-cyan-300/60 bg-cyan-300/10 shadow-lg shadow-cyan-950/30"
          : "border-white/10 bg-slate-950/45 hover:border-cyan-300/40 hover:bg-cyan-300/5",
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
}

export function AssetFiltersPanel({ selectedSeriesId, entityType, onEntityTypeChange, query, onQueryChange }) {
  return (
    <Panel
      title={selectedSeriesId ? `Assets for ${selectedSeriesId}` : "Asset inventory"}
      subtitle="The grid loads paged thumbnails only. Full prompts and original images open on demand."
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {ENTITY_FILTERS.map((item) => (
          <Button
            key={item}
            onClick={() => onEntityTypeChange(item)}
            variant={entityType === item ? "primary" : "secondary"}
          >
            {item}
          </Button>
        ))}
      </div>
      <SearchBox value={query} onChange={onQueryChange} placeholder="Search entity name..." />
    </Panel>
  );
}

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
        <div className="flex items-center gap-2">
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

function AssetCard({ entity, selected, onToggleSelect, onOpen }) {
  const thumbnailPath = entity.generated_thumbnail_path || entity.generated_image_path;
  const hasImage = !!thumbnailPath;

  return (
    <div
      className={[
        "overflow-hidden rounded-2xl border bg-slate-950/55 text-left shadow-lg shadow-black/10 transition",
        selected
          ? "border-emerald-300/55 shadow-emerald-950/20"
          : "border-white/10 hover:border-cyan-300/50 hover:bg-cyan-300/5",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
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

      <button type="button" onClick={onOpen} className="block w-full text-left">
        <div className={`${STANDARD_ASSET_RATIO_CLASS} border-b border-white/10 bg-black/40`}>
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
