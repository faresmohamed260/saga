import React from 'react';
import { ArrowUpRight, Download, Folder, Heart, Maximize2, Pencil, RefreshCcw, Sparkles, Trash2, Video } from 'lucide-react';

export default function MediaCard({
  item,
  history = false,
  inCollection = false,
  favorites,
  onToggleFavorite,
  onReuseSettings,
  onEdit,
  onDownload,
  onOpen,
  onAddToCollection,
  onRemoveFromCollection,
  onDelete,
}) {
  const favorite = favorites.has(item.id);
  return (
    <article className={`media-card ${history ? 'history-card' : ''}`}>
      <div
        className={`media-frame ${!item.url ? 'media-frame-empty' : ''}`}
        style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined}
        onClick={() => onOpen(item)}
        role="button"
        tabIndex={0}
      >
        {item.kind === 'video' && item.url ? <video className="media-video-preview" src={item.originalUrl || item.url} muted playsInline preload="metadata" /> : null}
        {!item.url && <div className="media-placeholder"><Video size={28}/><span>Video preview</span></div>}
        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? `${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}${history ? '' : ' · Klein 9B'}` : '1024 × 1024'}</div>
        <div className="media-hover"><button aria-label="Open full media"><Maximize2 size={18}/></button></div>
      </div>
      {history && <div className="history-copy"><div className="history-prompt">{item.title}</div><div className="history-meta"><span>{item.model || 'Unknown model'}</span>{item.seed != null && <span>Seed {item.seed}</span>}</div></div>}
      <div className="card-actions" style={{ gridTemplateColumns: 'repeat(7,1fr)' }}>
        <button title="Favorite" className={favorite ? 'favorite active' : 'favorite'} onClick={() => onToggleFavorite(item)}><Heart size={19} fill={favorite ? 'currentColor' : 'none'}/></button>
        <button title="Reuse settings" onClick={() => onReuseSettings(item)}><RefreshCcw size={18}/></button>
        <button title="Edit this" onClick={() => onEdit(item)}><Pencil size={18}/></button>
        <button title="Download original" onClick={() => onDownload(item)}><Download size={18}/></button>
        <button title="Open full media" onClick={() => onOpen(item)}><ArrowUpRight size={19}/></button>
        <button title={inCollection ? 'Remove from collection' : 'Add to collection'} onClick={() => inCollection ? onRemoveFromCollection(item) : onAddToCollection(item)}><Folder size={18}/></button>
        <button title="Delete permanently" onClick={() => onDelete(item)}><Trash2 size={18}/></button>
      </div>
    </article>
  );
}
