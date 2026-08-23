from pathlib import Path

ROOT = Path.cwd()


def path(name: str) -> Path:
    return ROOT / name


def replace_once(name: str, old: str, new: str) -> None:
    target = path(name)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected patch anchor missing in {name}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(name: str, marker: str, content: str) -> None:
    target = path(name)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")


def write(name: str, content: str) -> None:
    target = path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Reusable Create/video controls wrapper. Keep the legacy composer intact and
# inject only the new reusable video-output controls and honest stage progress.
# ---------------------------------------------------------------------------
write(
    "apps/studio/src/features/create/VideoGenerationControls.jsx",
    r'''
import React, { useEffect, useRef, useState } from 'react';
import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, Sparkles, XCircle } from 'lucide-react';

export const VIDEO_ASPECT_PRESETS = [
  { value: '1:1', label: 'Square' },
  { value: '4:5', label: 'Portrait' },
  { value: '3:4', label: 'Portrait' },
  { value: '2:3', label: 'Tall' },
  { value: '9:16', label: 'Vertical' },
  { value: '5:4', label: 'Classic' },
  { value: '4:3', label: 'Classic' },
  { value: '3:2', label: 'Photo' },
  { value: '16:10', label: 'Wide' },
  { value: '16:9', label: 'Widescreen' },
  { value: '21:9', label: 'Cinematic' },
];

export const VIDEO_FRAME_RATES = [24, 25, 30];

function gcd(a, b) {
  let left = Math.abs(Math.round(Number(a) || 0));
  let right = Math.abs(Math.round(Number(b) || 0));
  while (right) [left, right] = [right, left % right];
  return left || 1;
}

export function referenceAspect(reference) {
  const width = Number(reference?.width) || 0;
  const height = Number(reference?.height) || 0;
  if (!width || !height) return { value: '16:9', ratio: 16 / 9, fromReference: false };
  const divisor = gcd(width, height);
  return {
    value: `${Math.round(width / divisor)}:${Math.round(height / divisor)}`,
    ratio: width / height,
    fromReference: true,
  };
}

function useOutsideDismiss(open, rootRef, close) {
  useEffect(() => {
    if (!open) return undefined;
    const pointer = (event) => {
      if (!rootRef.current?.contains(event.target)) close();
    };
    const key = (event) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
      document.removeEventListener('keydown', key);
    };
  }, [open, rootRef, close]);
}

function CompactPicker({ label, value, options, onChoose, leading }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useOutsideDismiss(open, rootRef, () => setOpen(false));
  return (
    <div className="saga-video-inline-picker" ref={rootRef}>
      <button
        type="button"
        className={`saga-control-pill ${open ? 'active' : ''}`}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {leading}<span>{value}</span><ChevronDown size={13} />
      </button>
      {open && (
        <div className="saga-video-option-menu" role="menu" aria-label={label}>
          {options.map((option) => (
            <button
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              className={option.value === value ? 'selected' : ''}
              key={option.value}
              onClick={() => {
                onChoose(option.value);
                setOpen(false);
              }}
            >
              <span><strong>{option.value}</strong>{option.label && <small>{option.label}</small>}</span>
              {option.value === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function VideoOutputControls({
  autoAspect,
  setAutoAspect,
  manualAspect,
  setManualAspect,
  effectiveAspect,
  referenceInfo,
  frameRate,
  setFrameRate,
}) {
  const aspectValue = autoAspect ? effectiveAspect : manualAspect;
  return (
    <div className="saga-video-extra-controls" aria-label="Video output controls">
      <button
        type="button"
        className={`saga-auto-toggle ${autoAspect ? 'active' : ''}`}
        aria-pressed={autoAspect}
        title={referenceInfo.fromReference ? `Use reference aspect ratio (${referenceInfo.value})` : 'Use reference aspect ratio when an image is attached; otherwise 16:9'}
        onClick={() => setAutoAspect((current) => !current)}
      >
        <Sparkles size={15} /><span>Auto</span>
      </button>
      <CompactPicker
        label="Video aspect ratio"
        value={aspectValue}
        leading={<span className="saga-aspect-icon" style={{ aspectRatio: String(referenceInfo.ratio || 16 / 9) }} />}
        options={VIDEO_ASPECT_PRESETS}
        onChoose={(value) => {
          setManualAspect(value);
          setAutoAspect(false);
        }}
      />
      <CompactPicker
        label="Video frame rate"
        value={`${frameRate} fps`}
        leading={<Gauge size={15} />}
        options={VIDEO_FRAME_RATES.map((fps) => ({ value: `${fps} fps`, raw: fps }))}
        onChoose={(value) => setFrameRate(Number.parseInt(value, 10) || 24)}
      />
    </div>
  );
}

const STATUS_COPY = {
  uploading: ['Uploading reference', 'Preparing the source image for generation.'],
  submitting: ['Submitting generation', 'Sending the video request to the generation service.'],
  queued: ['Queued', 'The request is waiting for an available generation worker.'],
  running: ['Generating video', 'REDGraft LTX 2.5 is rendering the requested frames.'],
  completed: ['Video ready', 'The completed video has been saved to Gallery.'],
  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],
};

export function VideoGenerationProgress({ busy, status }) {
  const [elapsed, setElapsed] = useState(0);
  const [showTerminal, setShowTerminal] = useState(false);

  useEffect(() => {
    if (!busy) return undefined;
    const started = Date.now();
    setElapsed(0);
    setShowTerminal(true);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    if (busy) return undefined;
    if (status !== 'completed' && status !== 'failed') {
      setShowTerminal(false);
      return undefined;
    }
    setShowTerminal(true);
    const timer = window.setTimeout(() => setShowTerminal(false), 5000);
    return () => window.clearTimeout(timer);
  }, [busy, status]);

  if (!busy && !showTerminal) return null;
  const normalized = status || (busy ? 'submitting' : 'completed');
  const [title, detail] = STATUS_COPY[normalized] || STATUS_COPY.running;
  const terminal = normalized === 'completed' || normalized === 'failed';
  return (
    <div className={`saga-generation-progress is-${normalized}`} role="status" aria-live="polite">
      <div className="saga-generation-progress-icon">
        {normalized === 'completed' ? <CheckCircle2 size={17} /> : normalized === 'failed' ? <XCircle size={17} /> : <LoaderCircle className="spin" size={17} />}
      </div>
      <div className="saga-generation-progress-copy">
        <div><strong>{title}</strong>{busy && <span>{elapsed}s elapsed</span>}</div>
        <small>{detail}</small>
        <div className={`saga-generation-progress-track ${terminal ? 'terminal' : 'indeterminate'}`} aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
''',
)

write(
    "apps/studio/src/features/create/CreateWorkspace.jsx",
    r'''
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import LegacyCreateWorkspace from '../../create-controls.jsx';
import {
  VideoGenerationProgress,
  VideoOutputControls,
  referenceAspect,
} from './VideoGenerationControls.jsx';

const VIDEO_OUTPUT_STORAGE_KEY = 'saga-studio:video-output:v1';

function loadVideoOutputSettings() {
  if (typeof window === 'undefined') return { autoAspect: true, manualAspect: '16:9', frameRate: 24 };
  try {
    const saved = JSON.parse(window.localStorage.getItem(VIDEO_OUTPUT_STORAGE_KEY) || '{}');
    return {
      autoAspect: saved.autoAspect !== false,
      manualAspect: typeof saved.manualAspect === 'string' ? saved.manualAspect : '16:9',
      frameRate: [24, 25, 30].includes(Number(saved.frameRate)) ? Number(saved.frameRate) : 24,
    };
  } catch {
    return { autoAspect: true, manualAspect: '16:9', frameRate: 24 };
  }
}

export default function CreateWorkspace(props) {
  const { mode, references = [], busy, jobStatus, onGenerate } = props;
  const initial = useMemo(loadVideoOutputSettings, []);
  const [autoAspect, setAutoAspect] = useState(initial.autoAspect);
  const [manualAspect, setManualAspect] = useState(initial.manualAspect);
  const [frameRate, setFrameRate] = useState(initial.frameRate);
  const [toolbarHost, setToolbarHost] = useState(null);
  const [composerHost, setComposerHost] = useState(null);
  const referenceInfo = useMemo(() => referenceAspect(references[0]), [references]);
  const effectiveAspect = autoAspect ? referenceInfo.value : manualAspect;

  useEffect(() => {
    if (mode !== 'Video') {
      setToolbarHost(null);
      setComposerHost(null);
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      setToolbarHost(document.querySelector('.saga-composer.is-video .saga-toolbar-left'));
      setComposerHost(document.querySelector('.saga-composer.is-video'));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [mode]);

  useEffect(() => {
    try {
      window.localStorage.setItem(VIDEO_OUTPUT_STORAGE_KEY, JSON.stringify({ autoAspect, manualAspect, frameRate }));
    } catch {
      // Storage can be unavailable in hardened browser contexts; controls still work for the session.
    }
  }, [autoAspect, manualAspect, frameRate]);

  const handleGenerate = useCallback((legacyOptions = {}) => onGenerate({
    ...legacyOptions,
    videoAspect: effectiveAspect,
    videoAspectMode: autoAspect ? 'auto' : 'manual',
    videoFrameRate: frameRate,
  }), [onGenerate, effectiveAspect, autoAspect, frameRate]);

  return (
    <>
      <LegacyCreateWorkspace {...props} onGenerate={handleGenerate} />
      {mode === 'Video' && toolbarHost && createPortal(
        <VideoOutputControls
          autoAspect={autoAspect}
          setAutoAspect={setAutoAspect}
          manualAspect={manualAspect}
          setManualAspect={setManualAspect}
          effectiveAspect={effectiveAspect}
          referenceInfo={referenceInfo}
          frameRate={frameRate}
          setFrameRate={setFrameRate}
        />,
        toolbarHost,
      )}
      {mode === 'Video' && composerHost && createPortal(
        <VideoGenerationProgress busy={busy} status={jobStatus} />,
        composerHost,
      )}
    </>
  );
}
''',
)

append_once(
    "apps/studio/src/create-workspace-v2.css",
    ".saga-video-extra-controls",
    r'''
/* Reusable video output controls + generation lifecycle feedback. */
.workspace .saga-video-extra-controls{display:flex;align-items:center;gap:7px;min-width:0}
.workspace .saga-video-inline-picker{position:relative;display:inline-flex}
.workspace .saga-video-option-menu{
  position:absolute;left:0;bottom:calc(100% + 8px);z-index:1800;min-width:184px;padding:6px;border:1px solid #303743;border-radius:12px;background:rgba(18,22,28,.985);box-shadow:0 18px 48px rgba(0,0,0,.48);backdrop-filter:blur(18px)
}
.workspace .saga-video-option-menu button{
  width:100%;min-height:36px;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 9px;border:0;border-radius:8px;background:transparent;color:#cbd0d8;text-align:left;cursor:pointer
}
.workspace .saga-video-option-menu button:hover,.workspace .saga-video-option-menu button.selected{background:#252a33;color:#fff}
.workspace .saga-video-option-menu button>span{display:flex;align-items:baseline;gap:7px;min-width:0}
.workspace .saga-video-option-menu strong{font-size:10px;white-space:nowrap}
.workspace .saga-video-option-menu small{font-size:9px;color:#778292;white-space:nowrap}
.workspace .saga-generation-progress{
  display:flex;align-items:flex-start;gap:10px;margin:0 12px 11px;padding:10px 12px;border:1px solid #29313c;border-radius:12px;background:#10151c;color:#dfe4eb
}
.workspace .saga-generation-progress-icon{width:28px;height:28px;display:grid;place-items:center;flex:0 0 28px;border-radius:9px;background:#1d2330;color:#a998ff}
.workspace .saga-generation-progress-copy{min-width:0;flex:1}
.workspace .saga-generation-progress-copy>div:first-child{display:flex;align-items:center;justify-content:space-between;gap:12px}
.workspace .saga-generation-progress-copy strong{font-size:11px}
.workspace .saga-generation-progress-copy>div:first-child span{font-size:9px;color:#758195;white-space:nowrap}
.workspace .saga-generation-progress-copy small{display:block;margin-top:2px;color:#7e899a;font-size:9px;line-height:1.4}
.workspace .saga-generation-progress-track{position:relative;height:3px;margin-top:8px;overflow:hidden;border-radius:999px;background:#242b35}
.workspace .saga-generation-progress-track span{position:absolute;inset:0 auto 0 0;border-radius:inherit;background:#8c76ff}
.workspace .saga-generation-progress-track.indeterminate span{width:38%;animation:saga-progress-slide 1.25s ease-in-out infinite}
.workspace .saga-generation-progress-track.terminal span{width:100%}
.workspace .saga-generation-progress.is-completed{border-color:rgba(94,190,140,.24)}
.workspace .saga-generation-progress.is-completed .saga-generation-progress-icon{color:#73d7a4;background:rgba(43,113,76,.18)}
.workspace .saga-generation-progress.is-failed{border-color:rgba(238,97,116,.28)}
.workspace .saga-generation-progress.is-failed .saga-generation-progress-icon{color:#ff9dac;background:rgba(116,39,51,.22)}
@keyframes saga-progress-slide{0%{transform:translateX(-115%)}50%{transform:translateX(110%)}100%{transform:translateX(280%)}}
@media(max-width:760px){.workspace .saga-video-extra-controls{flex-wrap:wrap}.workspace .saga-video-option-menu{bottom:auto;top:calc(100% + 8px)}}
@media(prefers-reduced-motion:reduce){.workspace .saga-generation-progress-track.indeterminate span{animation:none;width:100%;opacity:.55}}
''',
)

# ---------------------------------------------------------------------------
# Gallery: reusable MediaCard selection mode, hover actions, and manager bar.
# ---------------------------------------------------------------------------
write(
    "apps/studio/src/components/MediaCard.jsx",
    r'''
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
''',
)

write(
    "apps/studio/src/features/library/HistoryView.jsx",
    r'''
import React, { useEffect, useMemo, useState } from 'react';
import { Check, Download, Heart, LoaderCircle, Plus, RefreshCcw, Trash2, X } from 'lucide-react';
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
      if (name === 'delete' && result !== false) setSelected(new Set());
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
        <div className="gallery-manager" role="toolbar" aria-label="Selected media actions">
          <strong>{selected.size} selected</strong>
          <button onClick={() => setSelected(new Set(items.map((item) => item.id)))} disabled={!items.length}>Select all</button>
          <button onClick={() => setSelected(new Set())} disabled={!selected.size}>Clear</button>
          <span className="gallery-manager-spacer" />
          <button onClick={() => runBulk('favorite', onBulkFavorite)} disabled={!selected.size || Boolean(actionBusy)}><Heart size={15}/> Favorite</button>
          <button onClick={() => runBulk('download', onBulkDownload)} disabled={!selected.size || Boolean(actionBusy)}><Download size={15}/> Download</button>
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
''',
)

write(
    "apps/studio/src/components/Sidebar.jsx",
    r'''
import React from 'react';
import { Box, ChevronDown, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, Sparkles, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, mode, mobileOpen, onCloseMobile, onSectionChange, onModeChange, onClearError }) {
  const chooseSection = (label) => {
    onSectionChange(label);
    if (label === 'Create' && mode === 'More') onModeChange('Image');
    onCloseMobile();
  };

  return (
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button className="mobile-close" onClick={onCloseMobile}><ChevronLeft size={19}/></button></div>
      <nav className="nav-group primary-nav">
        {primary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label && (label !== 'Create' || mode !== 'More')} onClick={() => chooseSection(label)} />)}
        <NavItem icon={Sparkles} label="More" active={section === 'Create' && mode === 'More'} onClick={() => { onSectionChange('Create'); onModeChange('More'); onClearError(); onCloseMobile(); }} />
      </nav>
      <div className="nav-divider" />
      <nav className="nav-group">{secondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}</nav>
      <div className="nav-divider" />
      <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => onSectionChange('Settings')} />
      <div className="profile-card"><div className="avatar-orb"/><div className="profile-copy"><div className="profile-name">Saga Creator <span className="pro-badge">Studio</span></div><div className="profile-email">FLUX.2 online</div></div><ChevronDown size={16}/></div>
    </aside>
  );
}
''',
)

append_once(
    "apps/studio/src/history-controls.css",
    ".gallery-manager",
    r'''
/* Gallery manager + dense media cards. */
.gallery-toolbar-actions{display:flex;align-items:center;gap:10px}
.gallery-manage-trigger{min-height:42px!important;padding:0 14px!important}
.gallery-manage-trigger.active{border-color:rgba(122,92,255,.52);background:rgba(100,78,222,.16)}
.gallery-manager{
  position:sticky;top:12px;z-index:18;display:flex;align-items:center;gap:7px;margin:-4px 0 14px;padding:8px 10px;border:1px solid rgba(255,255,255,.13);border-radius:12px;background:rgba(14,18,25,.94);box-shadow:0 12px 34px rgba(0,0,0,.28);backdrop-filter:blur(14px)
}
.gallery-manager strong{min-width:82px;font-size:11px;color:#eef0f5}
.gallery-manager button{height:32px;display:flex;align-items:center;justify-content:center;gap:6px;padding:0 10px;border:1px solid rgba(255,255,255,.10);border-radius:8px;background:#171c24;color:#cbd1da;font-size:10px;cursor:pointer}
.gallery-manager button:hover:not(:disabled){background:#202630;color:#fff}
.gallery-manager button:disabled{opacity:.4;cursor:not-allowed}
.gallery-manager button.danger{color:#ffb2be;border-color:rgba(255,103,125,.22)}
.gallery-manager-spacer{flex:1}
.history-view .history-grid{grid-template-columns:repeat(auto-fill,minmax(180px,220px));justify-content:start;gap:12px}
.history-view .history-card{width:100%;transition:border-color .16s ease,transform .16s ease,box-shadow .16s ease}
.history-view .history-card.selected{border-color:rgba(129,102,255,.82);box-shadow:0 0 0 1px rgba(129,102,255,.22),0 8px 28px rgba(0,0,0,.22)}
.history-view .history-card .media-frame{aspect-ratio:1;background:#0b0f15}
.media-video-preview{width:100%;height:100%;display:block;object-fit:cover;background:#080b10}
.history-card .media-actions-overlay{
  position:absolute;left:7px;right:7px;bottom:7px;z-index:5;height:38px;display:grid;grid-template-columns:repeat(7,1fr);align-items:center;border:1px solid rgba(255,255,255,.14);border-radius:10px;background:rgba(10,13,18,.88);box-shadow:0 8px 24px rgba(0,0,0,.34);backdrop-filter:blur(12px);opacity:0;transform:translateY(5px);pointer-events:none;transition:opacity .16s ease,transform .16s ease
}
.history-card .media-frame:hover .media-actions-overlay,.history-card .media-frame:focus-within .media-actions-overlay{opacity:1;transform:none;pointer-events:auto}
.history-card .media-actions-overlay button{height:100%;border:0;background:transparent;color:#d5dae3;display:grid;place-items:center;cursor:pointer}
.history-card .media-actions-overlay button:hover{background:rgba(255,255,255,.07);color:#fff}
.history-card .media-actions-overlay .favorite.active{color:#a98fff}
.media-select-toggle{position:absolute;right:9px;top:9px;z-index:7;width:25px;height:25px;display:grid;place-items:center;border:1px solid rgba(255,255,255,.34);border-radius:8px;background:rgba(9,12,17,.78);color:#fff;cursor:pointer;box-shadow:0 3px 12px rgba(0,0,0,.22)}
.media-select-toggle.selected{border-color:#9f8cff;background:#7157df}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(hover:none){.history-card .media-actions-overlay{opacity:1;transform:none;pointer-events:auto}}
@media(max-width:760px){.gallery-toolbar-actions{width:100%;justify-content:space-between}.gallery-manager{flex-wrap:wrap;top:8px}.gallery-manager-spacer{display:none}.history-view .history-grid{grid-template-columns:repeat(2,minmax(0,1fr));justify-content:stretch}.history-card .media-actions-overlay{height:34px}}
''',
)

# ---------------------------------------------------------------------------
# App shell: route Gallery, pass video aspect/FPS, fix video preview fallback,
# and expose bulk operations through the same action functions used by cards.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/app/App.jsx",
    "const SECTION_HASHES = { Create: 'create', Jobs: 'jobs', History: 'history', Favorites: 'favorites', Collections: 'collections', Models: 'models', Workflows: 'workflows', Settings: 'settings' };\nconst HASH_SECTIONS = Object.fromEntries(Object.entries(SECTION_HASHES).map(([section, hash]) => [hash, section]));",
    "const SECTION_HASHES = { Create: 'create', Jobs: 'jobs', Gallery: 'gallery', Favorites: 'favorites', Collections: 'collections', Models: 'models', Workflows: 'workflows', Settings: 'settings' };\nconst HASH_SECTIONS = { ...Object.fromEntries(Object.entries(SECTION_HASHES).map(([section, hash]) => [hash, section])), history: 'Gallery' };",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "  const previewUrl = row.thumbnail_url || (row.kind === 'image' ? row.media_url : '');",
    "  const previewUrl = row.thumbnail_url || row.media_url || '';",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "    createdAt: row.created_at,\n  };",
    "    createdAt: row.created_at,\n    aspectRatio: row.metadata?.execution?.aspectRatio || null,\n    frameRate: row.metadata?.execution?.frameRate || null,\n  };",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "    if (section === 'History') loadHistory({ append: false, kind: historyKind, model: historyModel });",
    "    if (section === 'Gallery') loadHistory({ append: false, kind: historyKind, model: historyModel });",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "      setHistoryError(err instanceof Error ? err.message : 'Unable to load generation history.');",
    "      setHistoryError(err instanceof Error ? err.message : 'Unable to load Gallery.');",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "    if (section === 'History') loadHistory({ append: false });",
    "    if (section === 'Gallery') loadHistory({ append: false });",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "    const videoAudio = videoOptions.videoAudio !== false;\n    const sourceFile = references[0]?.file || null;",
    "    const videoAudio = videoOptions.videoAudio !== false;\n    const videoAspect = String(videoOptions.videoAspect || '16:9');\n    const requestedFrameRate = Number(videoOptions.videoFrameRate);\n    const videoFrameRate = [24, 25, 30].includes(requestedFrameRate) ? requestedFrameRate : 24;\n    const sourceFile = references[0]?.file || null;",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "      durationSeconds: videoDuration,\n      audioEnabled: videoAudio,\n      seed: effectiveSeed,",
    "      durationSeconds: videoDuration,\n      audioEnabled: videoAudio,\n      aspectRatio: videoAspect,\n      frameRate: videoFrameRate,\n      seed: effectiveSeed,",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "      model: 'LTX-Video 2.3 · 22B Distilled',",
    "      model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',",
)
replace_once(
    "apps/studio/src/app/App.jsx",
    "      audioEnabled: videoAudio,\n    };",
    "      audioEnabled: videoAudio,\n      aspectRatio: videoAspect,\n      frameRate: videoFrameRate,\n    };",
)
# The second History refresh belongs to the video path.
replace_once(
    "apps/studio/src/app/App.jsx",
    "    if (section === 'History') loadHistory({ append: false });",
    "    if (section === 'Gallery') loadHistory({ append: false });",
)

bulk_anchor = "  const openMedia = (item) => setSelectedMedia(item);\n"
bulk_code = r'''  const bulkFavorite = async (selectedItems) => {
    const candidates = selectedItems.filter(Boolean);
    if (!candidates.length) return false;
    setFavorites((current) => {
      const next = new Set(current);
      candidates.forEach((item) => next.add(item.id));
      return next;
    });
    const persisted = candidates.filter((item) => item.persisted && isUuid(item.id));
    try {
      await Promise.all(persisted.map(async (item) => {
        const response = await fetch('/api/favorites', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: item.id, isFavorite: true }) });
        if (!response.ok) throw new Error(`Favorite update failed (${response.status})`);
      }));
      setHistoryItems((current) => current.map((entry) => candidates.some((item) => item.id === entry.id) ? { ...entry, favorite: true } : entry));
      return true;
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not favorite selected media.');
      await loadHistory({ append: false });
      return false;
    }
  };

  const bulkDownload = async (selectedItems) => {
    selectedItems.forEach((item) => downloadItem(item));
    return true;
  };

  const bulkDelete = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item.persisted && isUuid(item.id));
    if (!candidates.length) return false;
    if (!window.confirm(`Permanently delete ${candidates.length} selected generation${candidates.length === 1 ? '' : 's'}? This removes originals, favorites, collection memberships, and retained source references.`)) return false;
    try {
      await Promise.all(candidates.map(async (item) => {
        const response = await fetch(`/api/generations?id=${encodeURIComponent(item.id)}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`Delete failed for one or more items (${response.status})`);
      }));
      const ids = new Set(candidates.map((item) => item.id));
      setSelectedMedia((current) => current && ids.has(current.id) ? null : current);
      setHistoryItems((current) => current.filter((entry) => !ids.has(entry.id)));
      setFavoriteItems((current) => current.filter((entry) => !ids.has(entry.id)));
      setCollectionItems((current) => current.filter((entry) => !ids.has(entry.id)));
      setItems((current) => current.filter((entry) => !ids.has(entry.id)));
      setFavorites((current) => {
        const next = new Set(current);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      await loadCollections();
      return true;
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not delete selected media.');
      await loadHistory({ append: false });
      return false;
    }
  };

  const openMedia = (item) => setSelectedMedia(item);
'''
replace_once("apps/studio/src/app/App.jsx", bulk_anchor, bulk_code)
replace_once(
    "apps/studio/src/app/App.jsx",
    ": section === 'History' ? <HistoryView items={historyItems} kind={historyKind} model={historyModel} models={historyModels} page={historyPage} loading={historyLoading} appending={historyAppending} error={historyError} onKindChange={setHistoryKind} onModelChange={setHistoryModel} onRefresh={() => loadHistory({ append: false })} onLoadMore={() => loadHistory({ append: true })} renderCard={renderCard} />",
    ": section === 'Gallery' ? <HistoryView items={historyItems} kind={historyKind} model={historyModel} models={historyModels} page={historyPage} loading={historyLoading} appending={historyAppending} error={historyError} onKindChange={setHistoryKind} onModelChange={setHistoryModel} onRefresh={() => loadHistory({ append: false })} onLoadMore={() => loadHistory({ append: true })} renderCard={renderCard} onBulkFavorite={bulkFavorite} onBulkDownload={bulkDownload} onBulkDelete={bulkDelete} />",
)

# ---------------------------------------------------------------------------
# Client/API video contract: carry aspect ratio and frame rate end to end.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/generation-client.js",
    "  audioEnabled = true,\n  seed = 42,\n}) {",
    "  audioEnabled = true,\n  aspectRatio = '16:9',\n  frameRate = 24,\n  seed = 42,\n}) {",
)
replace_once(
    "apps/studio/src/generation-client.js",
    "      durationSeconds,\n      audioEnabled,\n      seed,",
    "      durationSeconds,\n      audioEnabled,\n      aspectRatio,\n      frameRate,\n      seed,",
)

replace_once(
    "apps/studio/api/_workflows.js",
    "      durationSeconds: 5,\n      audioEnabled: true,",
    "      durationSeconds: 5,\n      audioEnabled: true,\n      aspectRatio: '16:9',\n      frameRate: 24,",
)
replace_once(
    "apps/studio/api/_workflows.js",
    "      resolutions: ['480p', '720p', '1080p', '2K'],",
    "      resolutions: ['480p', '720p', '1080p', '2K'],\n      frameRates: [24, 25, 30],",
)
replace_once(
    "apps/studio/api/_workflows.js",
    "      imageToVideo: true,\n    } : undefined,",
    "      imageToVideo: true,\n      aspectRatios: ['1:1', '4:5', '3:4', '2:3', '9:16', '5:4', '4:3', '3:2', '16:10', '16:9', '21:9'],\n      frameRates: workflow.limits.frameRates,\n      autoReferenceAspect: true,\n    } : undefined,",
)

replace_once(
    "apps/studio/api/generate.js",
    "    const audioEnabled = parseBoolean(\n      jsonMode ? body.audioEnabled : req.headers['x-saga-audio-enabled'],\n      workflow.defaults.audioEnabled,\n    );",
    "    const audioEnabled = parseBoolean(\n      jsonMode ? body.audioEnabled : req.headers['x-saga-audio-enabled'],\n      workflow.defaults.audioEnabled,\n    );\n    const aspectRatio = String(\n      jsonMode ? body.aspectRatio ?? workflow.defaults.aspectRatio : decodeHeader(req.headers['x-saga-aspect-ratio']) || workflow.defaults.aspectRatio || '16:9',\n    ).trim().slice(0, 32);\n    const frameRate = parseNumber(\n      jsonMode ? body.frameRate : req.headers['x-saga-frame-rate'],\n      workflow.defaults.frameRate || 24,\n    );",
)
replace_once(
    "apps/studio/api/generate.js",
    "          ...(workflow.kind === 'video' ? { durationSeconds, audioEnabled, resolution } : {}),",
    "          ...(workflow.kind === 'video' ? { durationSeconds, audioEnabled, resolution, aspectRatio, frameRate } : {}),",
)
replace_once(
    "apps/studio/api/generate.js",
    "      durationSeconds,\n      audioEnabled,\n    });",
    "      durationSeconds,\n      audioEnabled,\n      aspectRatio,\n      frameRate,\n    });",
)

replace_once(
    "apps/studio/api/_providers.js",
    "function getModalGatewayUrl() {",
    r'''function normalizeAspectRatio(value, fallback = '16:9') {
  const text = String(value || fallback).trim();
  const match = text.match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) {
    const error = new Error(`Unsupported video aspect ratio: ${text || 'empty'}`);
    error.statusCode = 400;
    throw error;
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  const ratio = width / height;
  if (!Number.isFinite(ratio) || ratio < 0.4 || ratio > 2.5) {
    const error = new Error(`Video aspect ratio is outside the supported range: ${text}`);
    error.statusCode = 400;
    throw error;
  }
  return `${width}:${height}`;
}

function getModalGatewayUrl() {''',
)
replace_once(
    "apps/studio/api/_providers.js",
    "  form.append('audio_enabled', String(input.audioEnabled));\n  return form;",
    "  form.append('audio_enabled', String(input.audioEnabled));\n  form.append('aspect_ratio', input.aspectRatio);\n  form.append('frame_rate', String(input.frameRate));\n  return form;",
)
replace_once(
    "apps/studio/api/_providers.js",
    "    normalized.audioEnabled = safeBoolean(rawInput.audioEnabled, workflow.defaults.audioEnabled);",
    "    normalized.audioEnabled = safeBoolean(rawInput.audioEnabled, workflow.defaults.audioEnabled);\n    normalized.aspectRatio = normalizeAspectRatio(rawInput.aspectRatio, workflow.defaults.aspectRatio);\n    const requestedFrameRate = Math.round(safeNumber(rawInput.frameRate, workflow.defaults.frameRate));\n    if (!(workflow.limits.frameRates || []).includes(requestedFrameRate)) {\n      const error = new Error(`Unsupported video frame rate: ${requestedFrameRate}`);\n      error.statusCode = 400;\n      throw error;\n    }\n    normalized.frameRate = requestedFrameRate;",
)

# ---------------------------------------------------------------------------
# Modal gateway/runtime: fix the half-resolution regression, support arbitrary
# reference aspect ratios, requested FPS, and deliver exact standard dimensions.
# ---------------------------------------------------------------------------
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    "import os\n\nimport modal",
    "import os\nimport re\n\nimport modal",
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    "        audio_enabled: bool = Form(True),\n        image_file: UploadFile | None = File(None),",
    "        audio_enabled: bool = Form(True),\n        aspect_ratio: str = Form(\"16:9\"),\n        frame_rate: int = Form(24),\n        image_file: UploadFile | None = File(None),",
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    "        if not 5 <= int(duration_seconds) <= 30:\n            raise HTTPException(status_code=400, detail=\"duration_seconds must be between 5 and 30\")",
    "        if not 5 <= int(duration_seconds) <= 30:\n            raise HTTPException(status_code=400, detail=\"duration_seconds must be between 5 and 30\")\n        ratio_match = re.fullmatch(r\"(\\d+(?:\\.\\d+)?):(\\d+(?:\\.\\d+)?)\", str(aspect_ratio).strip())\n        if not ratio_match:\n            raise HTTPException(status_code=400, detail=\"aspect_ratio must be W:H\")\n        ratio_value = float(ratio_match.group(1)) / float(ratio_match.group(2))\n        if not 0.4 <= ratio_value <= 2.5:\n            raise HTTPException(status_code=400, detail=\"aspect_ratio is outside the supported range\")\n        if int(frame_rate) not in {24, 25, 30}:\n            raise HTTPException(status_code=400, detail=\"frame_rate must be 24, 25, or 30\")",
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    "                audio_enabled=bool(audio_enabled),\n                source_image=image_bytes,",
    "                audio_enabled=bool(audio_enabled),\n                aspect_ratio=str(aspect_ratio),\n                frame_rate=int(frame_rate),\n                source_image=image_bytes,",
)

replace_once(
    "integrations/comfyui/ltx23_app.py",
    "import json\nimport os",
    "import json\nimport math\nimport os",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "FPS = 24\nGPU_TYPE",
    "DEFAULT_FPS = 24\nFRAME_RATES = {24, 25, 30}\nGPU_TYPE",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "ENABLED_RESOLUTIONS = {\"480p\", \"720p\", \"1080p\", \"2K\"}",
    "ENABLED_RESOLUTIONS = {\"480p\", \"720p\", \"1080p\", \"2K\"}\nRESOLUTION_SHORT_EDGES = {\"480p\": 480, \"720p\": 720, \"1080p\": 1080, \"2K\": 1152, \"4K\": 2160}",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    r'''def _frame_count(duration_seconds: int) -> int:
    return int(duration_seconds) * FPS + 1


def _workflow(
    *,
    prompt: str,
    seed: int,
    resolution: str,
    duration_seconds: int,
    audio_enabled: bool,
    source_name: str | None,
    output_token: str,
) -> dict[str, Any]:
    target_width, target_height = RESOLUTIONS[resolution]
    low_width, low_height = target_width // 2, target_height // 2
    frames = _frame_count(duration_seconds)
''',
    r'''def _parse_aspect_ratio(value: str) -> float:
    left, separator, right = str(value or "16:9").strip().partition(":")
    if not separator:
        raise ValueError("aspect_ratio must be W:H")
    width = float(left)
    height = float(right)
    ratio = width / height
    if not math.isfinite(ratio) or ratio < 0.4 or ratio > 2.5:
        raise ValueError("aspect_ratio is outside the supported range")
    return ratio


def _even(value: float) -> int:
    return max(2, int(round(float(value) / 2.0)) * 2)


def _align64(value: int) -> int:
    return max(64, int(math.ceil(int(value) / 64.0)) * 64)


def _delivery_dimensions(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    ratio = _parse_aspect_ratio(aspect_ratio)
    short_edge = RESOLUTION_SHORT_EDGES[resolution]
    if ratio >= 1:
        height = short_edge
        width = _even(height * ratio)
    else:
        width = short_edge
        height = _even(width / ratio)
    return width, height


def _internal_dimensions(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    width, height = _delivery_dimensions(resolution, aspect_ratio)
    return _align64(width), _align64(height)


def _frame_count(duration_seconds: int, frame_rate: int) -> int:
    return int(duration_seconds) * int(frame_rate) + 1


def _workflow(
    *,
    prompt: str,
    seed: int,
    resolution: str,
    duration_seconds: int,
    audio_enabled: bool,
    aspect_ratio: str,
    frame_rate: int,
    source_name: str | None,
    output_token: str,
) -> dict[str, Any]:
    target_width, target_height = _internal_dimensions(resolution, aspect_ratio)
    low_width, low_height = target_width // 2, target_height // 2
    frames = _frame_count(duration_seconds, frame_rate)
''',
)
# Every LTX conditioning/audio/video node now uses the chosen frame rate.
text_path = path("integrations/comfyui/ltx23_app.py")
text = text_path.read_text(encoding="utf-8")
if '"frame_rate": FPS' not in text or '"fps": FPS' not in text:
    raise RuntimeError("Expected FPS anchors are missing in ltx23_app.py")
text = text.replace('"frame_rate": FPS', '"frame_rate": frame_rate')
text = text.replace('"fps": FPS', '"fps": frame_rate')
text_path.write_text(text, encoding="utf-8")
replace_once(
    "integrations/comfyui/ltx23_app.py",
    '"inputs": {"samples": ["20", 0], "upscale_method": "bicubic", "scale_by": 0.5}',
    '"inputs": {"samples": ["20", 0], "upscale_method": "bicubic", "scale_by": 1.0}',
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "            \"fps\": FPS,",
    "            \"default_fps\": DEFAULT_FPS,\n            \"frame_rates\": sorted(FRAME_RATES),",
)

finalize_code = r'''
def _finalize_video(video_path: Path, *, width: int, height: int, frame_rate: int) -> Path:
    final_path = video_path.with_name(f"{video_path.stem}-delivery.mp4")
    video_filter = (
        f"scale={int(width)}:{int(height)}:force_original_aspect_ratio=increase,"
        f"crop={int(width)}:{int(height)},fps={int(frame_rate)},setsar=1"
    )
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", video_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not final_path.is_file() or final_path.stat().st_size <= 0:
        raise RuntimeError(f"ffmpeg delivery encode failed: {result.stderr[-3000:]}")
    return final_path


'''
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "\n\n@app.function(\n    image=image,\n    timeout=7200,",
    "\n\n" + finalize_code + "@app.function(\n    image=image,\n    timeout=7200,",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "        audio_enabled: bool = True,\n        source_image: bytes | None = None,",
    "        audio_enabled: bool = True,\n        aspect_ratio: str = \"16:9\",\n        frame_rate: int = DEFAULT_FPS,\n        source_image: bytes | None = None,",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "        if not 5 <= int(duration_seconds) <= 30:\n            raise ValueError(\"duration_seconds must be between 5 and 30\")",
    "        if not 5 <= int(duration_seconds) <= 30:\n            raise ValueError(\"duration_seconds must be between 5 and 30\")\n        _parse_aspect_ratio(aspect_ratio)\n        if int(frame_rate) not in FRAME_RATES:\n            raise ValueError(\"frame_rate must be 24, 25, or 30\")",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "            audio_enabled=bool(audio_enabled),\n            source_name=source_name,",
    "            audio_enabled=bool(audio_enabled),\n            aspect_ratio=str(aspect_ratio),\n            frame_rate=int(frame_rate),\n            source_name=source_name,",
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    "                    video_path = _find_new_video(started_at, item)\n                    return video_path.read_bytes()",
    "                    video_path = _find_new_video(started_at, item)\n                    delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)\n                    final_path = _finalize_video(\n                        video_path,\n                        width=delivery_width,\n                        height=delivery_height,\n                        frame_rate=int(frame_rate),\n                    )\n                    _log(\n                        \"ltx25_delivery_ready\",\n                        resolution=resolution,\n                        aspect_ratio=aspect_ratio,\n                        frame_rate=int(frame_rate),\n                        width=delivery_width,\n                        height=delivery_height,\n                        bytes=final_path.stat().st_size,\n                    )\n                    return final_path.read_bytes()",
)

# ---------------------------------------------------------------------------
# R2 media endpoint: video tags need byte ranges for metadata, first-frame
# previews, hover playback, and seeking without downloading the whole object.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/api/media.js",
    r'''      const object = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
      res.setHeader('Content-Type', object.ContentType || 'application/octet-stream');
      res.setHeader('Cache-Control', 'private, max-age=86400');
      if (req.query?.download === '1') {
        const filename = key.split('/').pop() || 'saga-media';
        res.setHeader('Content-Disposition', `attachment; filename="${filename.replace(/["\\]/g, '_')}"`);
      }
      if (object.ContentLength != null) res.setHeader('Content-Length', String(object.ContentLength));
      for await (const chunk of object.Body) res.write(chunk);
      res.end();
''',
    r'''      const rawRange = String(req.headers.range || '').trim();
      const range = /^bytes=\d*-\d*$/.test(rawRange) && rawRange !== 'bytes=-' ? rawRange : '';
      const object = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key, ...(range ? { Range: range } : {}) }));
      res.setHeader('Content-Type', object.ContentType || 'application/octet-stream');
      res.setHeader('Cache-Control', 'private, max-age=86400');
      res.setHeader('Accept-Ranges', 'bytes');
      if (range && object.ContentRange) {
        res.statusCode = 206;
        res.setHeader('Content-Range', object.ContentRange);
      }
      if (req.query?.download === '1') {
        const filename = key.split('/').pop() || 'saga-media';
        res.setHeader('Content-Disposition', `attachment; filename="${filename.replace(/["\\]/g, '_')}"`);
      }
      if (object.ContentLength != null) res.setHeader('Content-Length', String(object.ContentLength));
      for await (const chunk of object.Body) res.write(chunk);
      res.end();
''',
)

# Basic source-level regression checks run before the actual project build.
app_source = path("integrations/comfyui/ltx23_app.py").read_text(encoding="utf-8")
assert '"scale_by": 1.0' in app_source
assert "def _delivery_dimensions" in app_source
assert "frame_rate: int = DEFAULT_FPS" in app_source
provider_source = path("apps/studio/api/_providers.js").read_text(encoding="utf-8")
assert "form.append('aspect_ratio'" in provider_source
assert "form.append('frame_rate'" in provider_source
print("Applied reusable video controls, exact output geometry, FPS, Gallery manager, and range-preview patches.")
