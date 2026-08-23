import React from 'react';
import { LoaderCircle, RefreshCcw } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function FavoritesView({ items, loading, error, onRefresh, renderCard }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title="Favorites" description="Saved generations persist across refreshes and devices using the Studio database." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading favorites…</div> : items.length === 0 ? <div className="history-state">No favorites yet. Tap the heart on any persisted generation.</div> : <section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true))}</section>}
    </section>
  );
}
