import React from 'react';
import { LoaderCircle, Plus, RefreshCcw } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function HistoryView({ items, kind, model, models, page, loading, appending, error, onKindChange, onModelChange, onRefresh, onLoadMore, renderCard }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title="Generation history" description="Thumbnail-first previews. Originals load only when you open an item." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Media type filter">{[['all', 'All'], ['image', 'Images'], ['video', 'Videos']].map(([value, label]) => <button key={value} className={kind === value ? 'selected' : ''} onClick={() => onKindChange(value)}>{label}</button>)}</div><label className="history-model-filter"><span>Model</span><select value={model} onChange={(event) => onModelChange(event.target.value)}><option value="all">All models</option>{models.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}</select></label></div>
      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading history…</div> : items.length === 0 ? <div className="history-state">No generations match these filters.</div> : <><section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true))}</section>{page.hasMore && <div className="history-load-more"><button className="secondary-button" onClick={onLoadMore} disabled={appending}>{appending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {appending ? 'Loading…' : 'Load more'}</button></div>}</>}
    </section>
  );
}
