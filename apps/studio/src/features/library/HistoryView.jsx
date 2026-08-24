import React, { useEffect, useMemo, useState } from 'react';
import { Check, Download, FolderPlus, Heart, LoaderCircle, Plus, RefreshCcw, Trash2, X } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function HistoryView({
  items,
  kind,
  model,
  models,
  page,
  loading,
  appending,
  error,
  onKindChange,
  onModelChange,
  onRefresh,
  onLoadMore,
  renderCard,
  onBulkFavorite,
  onBulkAddToCollection,
  onBulkDownload,
  onBulkDelete,
}) {
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [actionBusy, setActionBusy] = useState('');
  const itemIds = useMemo(() => new Set(items.map((item) => item.id)), [items]);

  useEffect(() => {
    setSelected((current) => {
      const next = new Set([...current].filter((id) => itemIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [itemIds]);

  const selectedItems = useMemo(() => items.filter((item) => selected.has(item.id)), [items, selected]);
  const toggle = (item) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(item.id)) next.delete(item.id);
    else next.add(item.id);
    return next;
  });
  const finishManaging = () => {
    setManaging(false);
    setSelected(new Set());
  };
  const runBulk = async (name, callback) => {
    if (!selectedItems.length || actionBusy) return;
    setActionBusy(name);
    try {
      const result = await callback?.(selectedItems);
      if (result && Array.isArray(result.failedIds)) {
        setSelected(new Set(result.failedIds));
      } else if ((name === 'delete' || name === 'collection') && result !== false) {
        setSelected(new Set());
      }
    } finally {
      setActionBusy('');
    }
  };

  return (
    <section className="history-view gallery-view">
      <LibraryHeader
        eyebrow="Library"
        title="Gallery"
        description="Browse, preview, select, and manage your generated media."
        action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>}
      />
      <div className="history-toolbar">
        <div className="history-kind-tabs" role="group" aria-label="Media type filter">
          {[['all', 'All'], ['image', 'Images'], ['video', 'Videos']].map(([value, label]) => <button key={value} className={kind === value ? 'selected' : ''} onClick={() => onKindChange(value)}>{label}</button>)}
        </div>
        <div className="gallery-toolbar-actions">
          <label className="history-model-filter"><span>Model</span><select value={model} onChange={(event) => onModelChange(event.target.value)}><option value="all">All models</option>{models.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}</select></label>
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

      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? (
        <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading Gallery…</div>
      ) : items.length === 0 ? (
        <div className="history-state">No media matches these filters.</div>
      ) : (
        <>
          <section className="gallery-grid history-grid">
            {items.map((item) => React.cloneElement(renderCard(item, true), {
              selectable: managing,
              selected: selected.has(item.id),
              onSelect: toggle,
            }))}
          </section>
          {page.hasMore && <div className="history-load-more"><button className="secondary-button" onClick={onLoadMore} disabled={appending}>{appending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {appending ? 'Loading…' : 'Load more'}</button></div>}
        </>
      )}
    </section>
  );
}
