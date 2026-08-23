import React from 'react';
import { ChevronLeft, Folder, LoaderCircle, Pencil, Plus, Trash2 } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function CollectionsView({ collections, selectedCollection, items, loading, error, onCreate, onBack, onOpen, onRename, onDelete, renderCard }) {
  const action = selectedCollection
    ? <button className="secondary-button" onClick={onBack}><ChevronLeft size={18}/> All collections</button>
    : <button className="secondary-button" onClick={onCreate}><Plus size={18}/> New collection</button>;
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title={selectedCollection ? selectedCollection.name : 'Collections'} description={selectedCollection ? `${items.length} saved item${items.length === 1 ? '' : 's'}` : 'Organize persisted generations into reusable groups.'} action={action} />
      {error && <div className="history-state error">{error}</div>}
      {selectedCollection ? (loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collection…</div> : items.length === 0 ? <div className="history-state">This collection is empty. Add items from History or Favorites.</div> : <section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true, true))}</section>) : (loading && collections.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collections…</div> : collections.length === 0 ? <div className="history-state">No collections yet.</div> : <div className="collection-grid">{collections.map((collection) => <article className="collection-card" key={collection.id}><button className="collection-cover" style={collection.coverUrl ? { backgroundImage: `url(${collection.coverUrl})` } : undefined} onClick={() => onOpen(collection)}>{!collection.coverUrl && <Folder size={34}/>}</button><div className="collection-copy"><button className="collection-title" onClick={() => onOpen(collection)}>{collection.name}</button><span>{collection.itemCount || 0} items</span></div><div className="collection-actions"><button onClick={() => onRename(collection)}><Pencil size={16}/></button><button onClick={() => onDelete(collection)}><Trash2 size={16}/></button></div></article>)}</div>)}
    </section>
  );
}
