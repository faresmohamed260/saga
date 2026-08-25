import React from 'react';
import useGallerySelection from '../../hooks/useGallerySelection.js';
import {
  ArrowDownUp,
  Check,
  ChevronDown,
  Download,
  Folder,
  FolderPlus,
  Heart,
  LayoutGrid,
  ListFilter,
  LoaderCircle,
  Search,
  Shapes,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';
import { modelDisplayName } from '../../model-labels.js';
import UploadsView from './UploadsView.jsx';

const DENSITY_STORAGE_KEY = 'saga.galleryDensity';

export default function GalleryView({
  items,
  kind,
  model,
  models,
  search,
  sort,
  date,
  favoritesOnly,
  collections = [],
  page,
  loading,
  appending,
  error,
  onKindChange,
  onModelChange,
  onSearchChange,
  onSortChange,
  onDateChange,
  onFavoritesOnlyChange,
  onOpenCollection,
  onOpenCollections,
  onLoadMore,
  renderCard,
  onBulkFavorite,
  onBulkAddToCollection,
  onBulkDownload,
  onBulkDelete,
  onUseUploadReference,
}) {
  const { managing, setManaging, selected, setSelected, actionBusy, toggle, finishManaging, runBulk } = useGallerySelection(items);
  const [libraryTab, setLibraryTab] = React.useState('creatives');
  const [uploadSearch, setUploadSearch] = React.useState('');
  const [density, setDensity] = React.useState(() => {
    if (typeof window === 'undefined') return 'compact';
    try { return window.localStorage.getItem(DENSITY_STORAGE_KEY) === 'comfortable' ? 'comfortable' : 'compact'; }
    catch { return 'compact'; }
  });
  const [collectionsOpen, setCollectionsOpen] = React.useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = React.useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = React.useState(false);

  const changeDensity = (nextDensity) => {
    setDensity(nextDensity);
    try { window.localStorage.setItem(DENSITY_STORAGE_KEY, nextDensity); } catch {}
  };

  const hasActiveFilters = kind !== 'all' || model !== 'all' || date !== 'any' || favoritesOnly;
  const resetFilters = () => {
    onKindChange('all');
    onModelChange('all');
    onDateChange('any');
    onFavoritesOnlyChange(false);
  };
  const toggleManaging = () => managing ? finishManaging() : setManaging(true);
  const activeSearch = libraryTab === 'uploads' ? uploadSearch : search;
  const updateActiveSearch = (value) => libraryTab === 'uploads' ? setUploadSearch(value) : onSearchChange(value);
  const activeSearchLabel = libraryTab === 'uploads' ? 'Search uploads' : 'Search prompts';

  const switchLibrary = (nextTab) => {
    if (nextTab === libraryTab) return;
    if (managing) finishManaging();
    setCollectionsOpen(false);
    setMobileFiltersOpen(false);
    setMobileSearchOpen(false);
    setLibraryTab(nextTab);
  };

  return (
    <section className={`gallery-view gallery-density-${density}`}>
      <LibraryHeader
        eyebrow="Library"
        title="Gallery"
        description="Browse, preview, select, and manage generated media and reusable uploaded assets."
      />

      <div className="gallery-library-nav" aria-label="Asset library navigation">
        <div className="gallery-primary-tabs" role="tablist" aria-label="Asset libraries">
          <button type="button" role="tab" aria-selected={libraryTab === 'creatives'} className={libraryTab === 'creatives' ? 'selected' : ''} onClick={() => switchLibrary('creatives')}><Sparkles size={16}/><span>Creatives</span></button>
          <button type="button" role="tab" aria-selected={libraryTab === 'uploads'} className={libraryTab === 'uploads' ? 'selected' : ''} onClick={() => switchLibrary('uploads')}><Upload size={16}/><span>Uploads</span></button>
          <button type="button" role="tab" aria-selected="false" aria-disabled="true" disabled title="Reusable Elements are not available yet"><Shapes size={16}/><span>Elements</span></button>
        </div>

        <label className="gallery-search gallery-search-desktop">
          <Search size={16}/>
          <span className="sr-only">{activeSearchLabel}</span>
          <input type="search" value={activeSearch} onChange={(event) => updateActiveSearch(event.target.value)} placeholder="Search" aria-label={activeSearchLabel} />
        </label>
        <button type="button" className={`gallery-mobile-search-trigger ${mobileSearchOpen ? 'active' : ''}`} aria-label={`Search ${libraryTab === 'uploads' ? 'Uploads' : 'Gallery'}`} aria-pressed={mobileSearchOpen} onClick={() => setMobileSearchOpen((value) => !value)}><Search size={20}/></button>
      </div>

      {mobileSearchOpen && (
        <label className="gallery-search gallery-search-mobile">
          <Search size={16}/>
          <span className="sr-only">{activeSearchLabel}</span>
          <input autoFocus type="search" value={activeSearch} onChange={(event) => updateActiveSearch(event.target.value)} placeholder={libraryTab === 'uploads' ? 'Search uploads' : 'Search prompts'} aria-label={activeSearchLabel} />
        </label>
      )}

      {libraryTab === 'uploads' ? (
        <UploadsView search={uploadSearch} onSearchChange={setUploadSearch} onUseReference={onUseUploadReference}/>
      ) : (
        <>
          <div className="gallery-desktop-controls">
            <div className="gallery-filter-strip">
              <button type="button" className={`gallery-reset-filter ${hasActiveFilters ? '' : 'selected'}`} onClick={resetFilters}>All creations</button>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <label className="gallery-kind-filter gallery-inline-select">
                <span className="sr-only">Type</span>
                <select value={kind} onChange={(event) => onKindChange(event.target.value)} aria-label="Type">
                  <option value="all">All types</option>
                  <option value="image">Images</option>
                  <option value="video">Videos</option>
                </select>
              </label>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <label className="gallery-model-filter gallery-inline-select">
                <span className="sr-only">Model</span>
                <select value={model} onChange={(event) => onModelChange(event.target.value)} aria-label="Model">
                  <option value="all">All models</option>
                  {models.map((modelName) => <option key={modelName} value={modelName}>{modelDisplayName(modelName)}</option>)}
                </select>
              </label>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <label className="gallery-date-filter gallery-inline-select">
                <span className="sr-only">Date</span>
                <select value={date} onChange={(event) => onDateChange(event.target.value)} aria-label="Date">
                  <option value="any">Any date</option>
                  <option value="today">Today</option>
                  <option value="week">This week</option>
                  <option value="month">This month</option>
                </select>
              </label>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <label className="gallery-favorites-filter">
                <input type="checkbox" checked={favoritesOnly} onChange={(event) => onFavoritesOnlyChange(event.target.checked)} />
                <Heart size={15} fill={favoritesOnly ? 'currentColor' : 'none'}/>
                <span>Favorites</span>
              </label>
            </div>

            <div className="gallery-view-strip">
              <button className={`gallery-manage-trigger ${managing ? 'active' : ''}`} aria-label={managing ? 'Done' : 'Manage'} aria-pressed={managing} onClick={toggleManaging}>
                {managing ? <X size={16}/> : <Check size={16}/>}<span>{managing ? 'Exit Batch Selection' : 'Batch Actions'}</span>
              </button>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <label className="gallery-sort gallery-inline-select">
                <ArrowDownUp size={15}/><span className="sr-only">Sort</span>
                <select value={sort} onChange={(event) => onSortChange(event.target.value)} aria-label="Sort"><option value="newest">Newest</option><option value="oldest">Oldest</option></select>
              </label>
              <span className="gallery-control-divider" aria-hidden="true"/>
              <div className="gallery-density-control" role="group" aria-label="Gallery density">
                <LayoutGrid size={15}/>
                <button type="button" className={density === 'compact' ? 'selected' : ''} aria-pressed={density === 'compact'} onClick={() => changeDensity('compact')}>Compact</button>
                <button type="button" className={density === 'comfortable' ? 'selected' : ''} aria-pressed={density === 'comfortable'} onClick={() => changeDensity('comfortable')}>Comfortable</button>
              </div>
            </div>
          </div>

          <div className="gallery-mobile-controls" aria-label="Gallery controls">
            <button type="button" className={collectionsOpen ? 'active' : ''} aria-expanded={collectionsOpen} onClick={() => setCollectionsOpen((value) => !value)}><Folder size={19}/><span>Collections</span></button>
            <button type="button" className={mobileFiltersOpen || hasActiveFilters ? 'active' : ''} aria-expanded={mobileFiltersOpen} onClick={() => setMobileFiltersOpen((value) => !value)}><SlidersHorizontal size={19}/><span>Filter{hasActiveFilters ? ' •' : ''}</span></button>
            <label className="gallery-mobile-select"><ArrowDownUp size={19}/><span>Sort</span><select value={sort} onChange={(event) => onSortChange(event.target.value)} aria-label="Mobile sort"><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
            <button type="button" onClick={() => changeDensity(density === 'compact' ? 'comfortable' : 'compact')} aria-label={`Gallery layout: ${density}`}><LayoutGrid size={19}/><span>Layout</span></button>
            <button type="button" className={managing ? 'active' : ''} aria-label={managing ? 'Done' : 'Manage'} aria-pressed={managing} onClick={toggleManaging}>{managing ? <X size={19}/> : <Check size={19}/>}<span>{managing ? 'Done' : 'Manage'}</span></button>
          </div>

          {mobileFiltersOpen && (
            <div className="gallery-mobile-filter-panel" role="group" aria-label="Gallery filters">
              <label><span>Type</span><select value={kind} onChange={(event) => onKindChange(event.target.value)}><option value="all">All types</option><option value="image">Images</option><option value="video">Videos</option></select></label>
              <label className="gallery-model-filter"><span>Model</span><select value={model} onChange={(event) => onModelChange(event.target.value)}><option value="all">All models</option>{models.map((modelName) => <option key={modelName} value={modelName}>{modelDisplayName(modelName)}</option>)}</select></label>
              <label><span>Date</span><select value={date} onChange={(event) => onDateChange(event.target.value)}><option value="any">Any date</option><option value="today">Today</option><option value="week">This week</option><option value="month">This month</option></select></label>
              <label className="gallery-mobile-favorite"><input type="checkbox" checked={favoritesOnly} onChange={(event) => onFavoritesOnlyChange(event.target.checked)} /><Heart size={16} fill={favoritesOnly ? 'currentColor' : 'none'}/><span>Favorites only</span></label>
              {hasActiveFilters && <button type="button" className="gallery-clear-filters" onClick={resetFilters}>Clear filters</button>}
            </div>
          )}

          <div className="gallery-collections-row">
            <button type="button" className="gallery-collections-trigger" aria-expanded={collectionsOpen} onClick={() => setCollectionsOpen((value) => !value)}><ListFilter size={17}/><Folder size={17}/><span>Collections</span><span className="gallery-collections-count">({collections.length})</span><ChevronDown size={15} className={collectionsOpen ? 'open' : ''}/></button>
          </div>
          {collectionsOpen && (
            <div className="gallery-collections-panel">
              <button type="button" className="gallery-collection-all" onClick={onOpenCollections}><Folder size={16}/><span>View all collections</span></button>
              {collections.length ? collections.map((collection) => (
                <button type="button" key={collection.id} onClick={() => onOpenCollection?.(collection)}>
                  <span className="gallery-collection-thumb" style={collection.coverUrl ? { backgroundImage: `url(${collection.coverUrl})` } : undefined}><Folder size={15}/></span>
                  <span className="gallery-collection-name">{collection.name}</span>
                  <span className="gallery-collection-count">{collection.itemCount ?? 0}</span>
                </button>
              )) : <span className="gallery-collections-empty">No collections yet.</span>}
            </div>
          )}

          <div className="gallery-content-heading">Creations</div>

          {managing && (
            <div className="gallery-manager" role="toolbar" aria-label="Selected media actions" data-mobile-bottom-bar="true">
              <button className="gallery-select-all" onClick={() => setSelected(new Set(items.map((item) => item.id)))} disabled={!items.length} title="Select every media item currently loaded in Gallery"><Check size={15}/><span>Select All</span><strong>({selected.size} selected)</strong></button>
              <span className="gallery-manager-divider" aria-hidden="true"/>
              <button onClick={() => runBulk('favorite', onBulkFavorite)} disabled={!selected.size || Boolean(actionBusy)}><Heart size={16}/> <span>Favorite</span></button>
              <button onClick={() => runBulk('download', onBulkDownload)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'download' ? <LoaderCircle className="spin" size={16}/> : <Download size={16}/>} <span>Download</span></button>
              <button onClick={() => runBulk('collection', onBulkAddToCollection)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'collection' ? <LoaderCircle className="spin" size={16}/> : <FolderPlus size={16}/>} <span>Add to</span></button>
              <button className="danger" onClick={() => runBulk('delete', onBulkDelete)} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'delete' ? <LoaderCircle className="spin" size={16}/> : <Trash2 size={16}/>} <span>Delete</span></button>
              <button className="gallery-manager-close" onClick={finishManaging} aria-label="Close batch actions"><X size={17}/></button>
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
              {page.hasMore && <div className="gallery-load-more"><button className="secondary-button" onClick={onLoadMore} disabled={appending}>{appending ? <LoaderCircle className="spin" size={18}/> : <span aria-hidden="true">+</span>} {appending ? 'Loading…' : 'Load more'}</button></div>}
            </>
          )}
        </>
      )}
    </section>
  );
}
