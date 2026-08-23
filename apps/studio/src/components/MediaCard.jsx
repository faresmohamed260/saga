import React, { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Download, Folder, Heart, Maximize2, MoreHorizontal, Pencil, RefreshCcw, Sparkles, Trash2, Video } from 'lucide-react';

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
  const moreRef = useRef(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const favorite = favorites.has(item.id);
  const videoSource = item.originalUrl || item.url || '';
  const itemLabel = item.title || 'media';
  const openOrSelect = () => selectable ? onSelect?.(item) : onOpen(item);
  const action = (callback) => (event) => {
    event.stopPropagation();
    callback?.(item);
  };
  const menuAction = (callback) => (event) => {
    event.stopPropagation();
    setMoreOpen(false);
    callback?.(item);
  };

  useEffect(() => {
    if (!moreOpen) return undefined;

    const handlePointerDown = (event) => {
      if (!moreRef.current?.contains(event.target)) setMoreOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      setMoreOpen(false);
      moreRef.current?.querySelector('.media-more-trigger')?.focus();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [moreOpen]);

  useEffect(() => {
    if (selectable && moreOpen) setMoreOpen(false);
  }, [selectable, moreOpen]);

  const favoriteLabel = favorite ? 'Remove from favorites' : 'Add to favorites';
  const collectionLabel = inCollection ? 'Remove from collection' : 'Add to collection';
  const primaryLabel = selectable
    ? `${selected ? 'Deselect' : 'Select'} ${itemLabel}`
    : `Open ${itemLabel}`;

  const galleryActions = (
    <div className="card-actions media-actions-overlay" aria-label="Media actions">
      <button
        type="button"
        title={favoriteLabel}
        aria-label={favoriteLabel}
        className={`media-action-primary favorite ${favorite ? 'active' : ''}`}
        onClick={action(onToggleFavorite)}
      >
        <Heart size={17} fill={favorite ? 'currentColor' : 'none'}/>
      </button>
      <button
        type="button"
        title="Download original"
        aria-label="Download original"
        className="media-action-primary media-action-desktop-download"
        onClick={action(onDownload)}
      >
        <Download size={16}/>
      </button>
      <button
        type="button"
        title="Open full media"
        aria-label="Open full media"
        className="media-action-primary"
        onClick={action(onOpen)}
      >
        <ArrowUpRight size={17}/>
      </button>
      <div className="media-actions-menu" ref={moreRef}>
        <button
          type="button"
          title="More actions"
          aria-label="More actions"
          aria-haspopup="menu"
          aria-expanded={moreOpen}
          className="media-action-primary media-more-trigger"
          onClick={(event) => {
            event.stopPropagation();
            setMoreOpen((value) => !value);
          }}
        >
          <MoreHorizontal size={18}/>
        </button>
        {moreOpen && (
          <div className="media-actions-popover" role="menu" aria-label="More media actions" onClick={(event) => event.stopPropagation()}>
            <button type="button" role="menuitem" onClick={menuAction(onReuseSettings)}><RefreshCcw size={15}/><span>Reuse settings</span></button>
            <button type="button" role="menuitem" onClick={menuAction(onEdit)}><Pencil size={15}/><span>Edit</span></button>
            <button type="button" role="menuitem" className="media-overflow-download" onClick={menuAction(onDownload)}><Download size={15}/><span>Download original</span></button>
            <button type="button" role="menuitem" onClick={menuAction(inCollection ? onRemoveFromCollection : onAddToCollection)}><Folder size={15}/><span>{collectionLabel}</span></button>
            <div className="media-actions-menu-divider" role="separator"/>
            <button type="button" role="menuitem" className="danger" onClick={menuAction(onDelete)}><Trash2 size={15}/><span>Delete permanently</span></button>
          </div>
        )}
      </div>
    </div>
  );

  const standardActions = (
    <div className="card-actions">
      <button type="button" title={favoriteLabel} aria-label={favoriteLabel} className={favorite ? 'favorite active' : 'favorite'} onClick={action(onToggleFavorite)}><Heart size={17} fill={favorite ? 'currentColor' : 'none'}/></button>
      <button type="button" title="Reuse settings" aria-label="Reuse settings" onClick={action(onReuseSettings)}><RefreshCcw size={16}/></button>
      <button type="button" title="Edit this" aria-label="Edit this" onClick={action(onEdit)}><Pencil size={16}/></button>
      <button type="button" title="Download original" aria-label="Download original" onClick={action(onDownload)}><Download size={16}/></button>
      <button type="button" title="Open full media" aria-label="Open full media" onClick={action(onOpen)}><ArrowUpRight size={17}/></button>
      <button type="button" title={collectionLabel} aria-label={collectionLabel} onClick={action(inCollection ? onRemoveFromCollection : onAddToCollection)}><Folder size={16}/></button>
      <button type="button" title="Delete permanently" aria-label="Delete permanently" onClick={action(onDelete)}><Trash2 size={16}/></button>
    </div>
  );

  return (
    <article className={`media-card ${history ? 'history-card' : ''} ${selected ? 'selected' : ''} ${selectable ? 'selectable' : ''}`}>
      <div
        className={`media-frame ${!item.url && !videoSource ? 'media-frame-empty' : ''}`}
        style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined}
        onMouseEnter={() => {
          if (history && !selectable && videoRef.current) videoRef.current.play().catch(() => {});
        }}
        onMouseLeave={() => {
          if (videoRef.current) videoRef.current.pause();
        }}
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
            preload={item.thumbnailUrl ? 'none' : 'metadata'}
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              if (!item.thumbnailUrl && Number.isFinite(video.duration) && video.duration > 0.1 && video.currentTime === 0) {
                try { video.currentTime = Math.min(0.08, Math.max(0, video.duration - 0.02)); } catch {}
              }
            }}
          />
        ) : null}
        {!item.url && !videoSource && <div className="media-placeholder"><Video size={28}/><span>Preview unavailable</span></div>}

        <button
          type="button"
          className="media-frame-primary"
          aria-label={primaryLabel}
          aria-pressed={selectable ? selected : undefined}
          onClick={openOrSelect}
        >
          <span className="sr-only">{primaryLabel}</span>
        </button>

        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? `${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}${history ? '' : ' · Klein 9B'}` : '1024 × 1024'}</div>
        {selectable && (
          <span
            className={`media-select-toggle ${selected ? 'selected' : ''}`}
            aria-hidden="true"
          >
            {selected && <Check size={14}/>}<span className="sr-only">{selected ? 'Selected' : 'Not selected'}</span>
          </span>
        )}
        {!history && <div className="media-hover" aria-hidden="true"><span className="media-hover-icon"><Maximize2 size={18}/></span></div>}
        {history && !selectable && galleryActions}
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
      {!history && standardActions}
    </article>
  );
}
