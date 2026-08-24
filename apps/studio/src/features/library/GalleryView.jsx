import React from 'react';
import useGallerySelection from '../../hooks/useGallerySelection.js';
import { Check, Download, FolderPlus, Heart, LoaderCircle, Plus, RefreshCcw, Trash2, X } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';
import { modelDisplayName } from '../../model-labels.js';

const DENSITY_STORAGE_KEY = 'saga.galleryDensity';

export default function GalleryView({
  items,
  kind,
  model,
  models,
  search,
  sort,
  page,
  loading,
  appending,
  error,
  onKindChange,
  onModelChange,
  onSearchChange,
  onSortChange,
  onRefresh,
  onLoadMore,
  renderCard,
  onBulkFavorite,
  onBulkAddToCollection,
  onBulkDownload,
  onBulkDelete,
}) {
  const { managing, setManaging, selected, setSelected, actionBusy, toggle, finishManaging, runBulk } = useGallerySelection(items);
  const [density, setDensity] = React.useState(() => {
    if (typeof window === 'undefined') return 'compact';
    return window.localStorage.getItem(DENSITY_STORAGE_KEY) === 'comfortable' ? 'comfortable' : 'compact';
  });

  const changeDensity = (nextDensity) => {
    setDensity(nextDensity);
    try { window.localStorage.setItem(DENSITY_STORAGE_KEY, nextDensity); } catch {}
  };

  return (
    <section className={`gallery-view gallery-density-${density}`}>
      <LibraryHeader
        eyebrow="Library"
        title="Gallery"
        description="Browse, preview, select, and manage your generated media."
        action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>}
      />
      <div className="gallery-toolbar">
        <div className="gallery-kind-tabs" role="group" aria-label="Media type filter">
          {[['all', 'All'], ['image', 'Images'], ['video', 'Videos']].map(([value, label]) => <button key={value} className={kind === value ? 'selected' : ''} onClick={() => onKindChange(value)}>{label}</button>)}
        </div>
        <div className="gallery-toolbar-actions">
          <label className="gallery-search"><span className="sr-only">Search prompts</span><input type="search" value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search prompts" aria-label="Search prompts" /></label>
          <label className="gallery-sort"><span>Sort</span><select value={sort} onChange={(event) => onSortChange(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
          <label className="gallery-model-filter"><span>Model</span><select value={model} onChange={(event) => onModelChange(event.target.value)}><option value="all">All models</option>{models.map((modelName) => <option key={modelName} value={modelName}>{modelDisplayName(modelName)}</option>)}</select></label>
          <div className="gallery-density-control" role="group" aria-label="Gallery density">
            <button type="button" className={density === 'compact' ? 'selected' : ''} aria-pressed={density === 'compact'} onClick={() => changeDensity('compact')}>Compact</button>
            <button type="button" className={density === 'comfortable' ? 'selected' : ''} aria-pressed={density === 'comfortable'} onClick={() => changeDensity('comfortable')}>Comfortable</button>
          </div>
          <button className={`secondary-button gallery-manage-trigger ${managing ? 'active' : ''}`} onClick={() => managing ? finishManaging() : setManaging(true)}>{managing ? <X size={17}/> : <Check size={17}/>} {managing ? 'Done' : 'Manage'}</button>
        </div>
      </div>

      {managing && (
        <div className="gallery-manager" role="toolbar" aria-label="Selected media actions" data-mobile-bottom-bar="true">
          <strong>{selected.size} selected</strong>
          <button onClick={() => setSelected(new Set(items.map((item) => item.id)))} disabled={!items.length} title="Select every media item currently loaded in Gallery">Select visible</button>
          <button onClick={() => setSelected(new Set())} disabled={!selected.size}>Clear</button>
          <span className="gallery-manager-spacer" />
          <button onClick={() => runBulk('favorite', onBulkFavorite)} disabled={!selected.size || Boolean(actionBusy)}><Heart size={15}/> Favorite</button>
          <button onClick={() => runBulk('collection', onBulkAddToCollection)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'collection' ? <LoaderCircle className="spin" size={15}/> : <FolderPlus size={15}/>} Add to Collection</button>
          <button onClick={() => runBulk('download', onBulkDownload)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'download' ? <LoaderCircle className="spin" size={15}/> : <Download size={15}/>} Download ZIP</button>
          <button className="danger" onClick={() => runBulk('delete', onBulkDelete)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'delete' ? <LoaderCircle className="spin" size={15}/> : <Trash2 size={15}/>} Delete</button>
        </div>
      )}

      {error && <div className="gallery-state error">{error}</div>}
      {loading && items.length === 0 ? (
        <div className="gallery-state"><LoaderCircle className="spin" size={22}/> Loading Gallery…</div>
      ) : items.length === 0 ? (
        <div className="gallery-state">No media matches these filters.</div>
      ) : (
        <>
          <section className="gallery-grid" data-density={density}>
            {items.map((item) => React.cloneElement(renderCard(item, true), {
              selectable: managing,
              selected: selected.has(item.id),
              onSelect: toggle,
            }))}
          </section>
          {page.hasMore && <div className="gallery-load-more"><button className="secondary-button" onClick={onLoadMore} disabled={appending}>{appending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {appending ? 'Loading…' : 'Load more'}</button></div>}
        </>
      )}
    </section>
  );
}
