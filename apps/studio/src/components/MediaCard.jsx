import React, { useRef } from 'react';
import { ArrowUpRight, Check, Download, Folder, Heart, Maximize2, Pencil, RefreshCcw, Sparkles, Trash2, Video } from 'lucide-react';

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
  selectable = false,
  selected = false,
  onSelect,
}) {
  const videoRef = useRef(null);
  const favorite = favorites.has(item.id);
  const videoSource = item.originalUrl || item.url || '';
  const openOrSelect = () => selectable ? onSelect?.(item) : onOpen(item);
  const action = (callback) => (event) => {
    event.stopPropagation();
    callback?.(item);
  };

  const actions = (
    <div className={`card-actions ${history ? 'media-actions-overlay' : ''}`}>
      <button title="Favorite" aria-label="Favorite" className={favorite ? 'favorite active' : 'favorite'} onClick={action(onToggleFavorite)}><Heart size={17} fill={favorite ? 'currentColor' : 'none'}/></button>
      <button title="Reuse settings" aria-label="Reuse settings" onClick={action(onReuseSettings)}><RefreshCcw size={16}/></button>
      <button title="Edit this" aria-label="Edit this" onClick={action(onEdit)}><Pencil size={16}/></button>
      <button title="Download original" aria-label="Download original" onClick={action(onDownload)}><Download size={16}/></button>
      <button title="Open full media" aria-label="Open full media" onClick={action(onOpen)}><ArrowUpRight size={17}/></button>
      <button title={inCollection ? 'Remove from collection' : 'Add to collection'} aria-label={inCollection ? 'Remove from collection' : 'Add to collection'} onClick={action(inCollection ? onRemoveFromCollection : onAddToCollection)}><Folder size={16}/></button>
      <button title="Delete permanently" aria-label="Delete permanently" onClick={action(onDelete)}><Trash2 size={16}/></button>
    </div>
  );

  return (
    <article className={`media-card ${history ? 'history-card' : ''} ${selected ? 'selected' : ''}`}>
      <div
        className={`media-frame ${!item.url && !videoSource ? 'media-frame-empty' : ''}`}
        style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined}
        onClick={openOrSelect}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openOrSelect();
          }
        }}
        onMouseEnter={() => {
          if (history && videoRef.current) videoRef.current.play().catch(() => {});
        }}
        onMouseLeave={() => {
          if (videoRef.current) videoRef.current.pause();
        }}
        role="button"
        aria-label={selectable ? `${selected ? 'Deselect' : 'Select'} ${item.title || 'media'}` : `Open ${item.title || 'media'}`}
        tabIndex={0}
      >
        {item.kind === 'video' && videoSource ? (
          <video
            ref={videoRef}
            className="media-video-preview"
            src={videoSource}
            poster={item.thumbnailUrl || undefined}
            muted
            playsInline
            loop
            preload="metadata"
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              if (!item.thumbnailUrl && Number.isFinite(video.duration) && video.duration > 0.1 && video.currentTime === 0) {
                try { video.currentTime = Math.min(0.08, Math.max(0, video.duration - 0.02)); } catch {}
              }
            }}
          />
        ) : null}
        {!item.url && !videoSource && <div className="media-placeholder"><Video size={28}/><span>Preview unavailable</span></div>}
        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? `${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}${history ? '' : ' · Klein 9B'}` : '1024 × 1024'}</div>
        {selectable && (
          <button
            type="button"
            className={`media-select-toggle ${selected ? 'selected' : ''}`}
            aria-label={selected ? 'Deselect media' : 'Select media'}
            aria-pressed={selected}
            onClick={action(onSelect)}
          >
            {selected && <Check size={14}/>}<span className="sr-only">{selected ? 'Selected' : 'Not selected'}</span>
          </button>
        )}
        {!history && <div className="media-hover"><button aria-label="Open full media" onClick={action(onOpen)}><Maximize2 size={18}/></button></div>}
        {history && actions}
      </div>
      {history && (
        <div className="history-copy">
          <div className="history-prompt">{item.title}</div>
          <div className="history-meta">
            <span>{item.model || 'Unknown model'}</span>
            <span>{[
              item.aspectRatio,
              item.frameRate ? `${item.frameRate} fps` : null,
              item.seed != null ? `Seed ${item.seed}` : null,
            ].filter(Boolean).join(' · ')}</span>
          </div>
        </div>
      )}
      {!history && actions}
    </article>
  );
}
