import React from 'react';
import { LoaderCircle } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function FavoritesView({ items, loading, error, renderCard }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title="Favorites" description="Saved generations sync automatically across devices using the Studio database." />
      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading favorites…</div> : items.length === 0 ? <div className="history-state">No favorites yet. Tap the heart on any persisted generation.</div> : <section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true))}</section>}
    </section>
  );
}
