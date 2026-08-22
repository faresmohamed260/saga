import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  WandSparkles, History, Heart, Folder, Box, Workflow, Settings,
  Plus, X, SlidersHorizontal, Sparkles, RefreshCcw, Pencil,
  ArrowUpRight, ChevronDown, RotateCcw, Menu, ChevronLeft,
  Maximize2, LoaderCircle, Trash2, Download, Video
} from 'lucide-react';
import { runImageEdit } from './generation-client.js';
import CreateWorkspace from './create-controls.jsx';
import './styles.css';
import './create-controls.css';

const HISTORY_PAGE_SIZE = 24;
const SECTION_HASHES = { Create: 'create', Jobs: 'jobs', History: 'history', Favorites: 'favorites', Collections: 'collections', Models: 'models', Workflows: 'workflows', Settings: 'settings' };
const HASH_SECTIONS = Object.fromEntries(Object.entries(SECTION_HASHES).map(([section, hash]) => [hash, section]));

function sectionFromLocation() {
  if (typeof window === 'undefined') return 'Create';
  const hash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
  return HASH_SECTIONS[hash] || 'Create';
}

const samples = [
  { id: 1, title: 'Forest refuge', url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=85' },
  { id: 2, title: 'Orbital horizon', url: 'https://images.unsplash.com/photo-1446776877081-d282a0f896e2?auto=format&fit=crop&w=1200&q=85' },
  { id: 3, title: 'Neon portrait', url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1200&q=85' },
  { id: 4, title: 'Future city', url: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1200&q=85' },
];

const navPrimary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [History, 'History'], [Heart, 'Favorites'], [Folder, 'Collections']];
const navSecondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function isUuid(value) { return /^[0-9a-f-]{36}$/i.test(String(value || '')); }
function formatJobTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function toHistoryItem(row) {
  const previewUrl = row.thumbnail_url || (row.kind === 'image' ? row.media_url : '');
  return {
    id: row.id,
    title: row.prompt || 'Untitled generation',
    url: previewUrl,
    originalUrl: row.media_url,
    thumbnailUrl: row.thumbnail_url,
    generated: true,
    persisted: true,
    favorite: Boolean(row.is_favorite),
    model: row.model,
    resolution: row.resolution,
    seed: row.seed,
    kind: row.kind,
    mode: row.mode,
    width: row.width,
    height: row.height,
    createdAt: row.created_at,
  };
}

function imageDimensions(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { resolve({ width: image.naturalWidth || 0, height: image.naturalHeight || 0 }); URL.revokeObjectURL(url); };
    image.onerror = () => { resolve({ width: 0, height: 0 }); URL.revokeObjectURL(url); };
    image.src = url;
  });
}

function autoReferenceSizing(reference) {
  const width = Number(reference?.width) || 0;
  const height = Number(reference?.height) || 0;
  if (!width || !height) return { megapixels: 1, detail: 'Auto from primary reference', ratioLabel: 'Uses Image 1 as the output canvas' };
  const nativeMp = (width * height) / 1_000_000;
  const megapixels = Math.max(0.25, Math.min(4, Math.round(nativeMp * 100) / 100));
  const scale = Math.sqrt((megapixels * 1_000_000) / (width * height));
  const targetWidth = Math.max(64, Math.round((width * scale) / 16) * 16);
  const targetHeight = Math.max(64, Math.round((height * scale) / 16) * 16);
  const gcd = (a, b) => b ? gcd(b, a % b) : a;
  const divisor = gcd(width, height) || 1;
  return {
    megapixels,
    detail: `≈ ${targetWidth} × ${targetHeight} · ${megapixels.toFixed(2)} MP`,
    ratioLabel: `${Math.round(width / divisor)}:${Math.round(height / divisor)} from Image 1`,
  };
}

function NavItem({ icon: Icon, label, active, onClick }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

function App() {
  const [section, setSection] = useState(sectionFromLocation);
  const [mode, setMode] = useState('Image');
  const [prompt, setPrompt] = useState('');
  const [aspect, setAspect] = useState('1:1');
  const [imageResolution, setImageResolution] = useState(1024);
  const [outputs, setOutputs] = useState(4);
  const [advanced, setAdvanced] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobStatus, setJobStatus] = useState('');
  const [jobs, setJobs] = useState([]);
  const [jobsFilter, setJobsFilter] = useState('active');
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState('');
  const [jobActionBusy, setJobActionBusy] = useState('');
  const [seed, setSeed] = useState('42');
  const [steps, setSteps] = useState(30);
  const [cfg, setCfg] = useState(7);
  const [workflowId, setWorkflowId] = useState('default-image');
  const [modelId, setModelId] = useState('saga-image-auto');
  const [references, setReferences] = useState([]);
  const [favorites, setFavorites] = useState(new Set());
  const [favoriteItems, setFavoriteItems] = useState([]);
  const [items, setItems] = useState(samples);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyAppending, setHistoryAppending] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyKind, setHistoryKind] = useState('all');
  const [historyModel, setHistoryModel] = useState('all');
  const [historyModels, setHistoryModels] = useState([]);
  const [historyPage, setHistoryPage] = useState({ nextOffset: null, hasMore: false });
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState('');
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [collectionItems, setCollectionItems] = useState([]);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [error, setError] = useState('');

  const visibleItems = useMemo(() => items.slice(0, mode === 'Edit' ? 4 : outputs), [items, outputs, mode]);
  const isEdit = mode === 'Edit';
  const autoEditInfo = useMemo(() => autoReferenceSizing(references[0]), [references]);

  React.useEffect(() => {
    const expectedHash = `#/${SECTION_HASHES[section] || 'create'}`;
    if (window.location.hash !== expectedHash) window.history.replaceState(null, '', expectedHash);
  }, [section]);

  React.useEffect(() => {
    const syncSectionFromHash = () => setSection(sectionFromLocation());
    window.addEventListener('hashchange', syncSectionFromHash);
    return () => window.removeEventListener('hashchange', syncSectionFromHash);
  }, []);

  const loadJobs = async ({ silent = false, filter = jobsFilter } = {}) => {
    if (!silent) setJobsLoading(true);
    setJobsError('');
    try {
      const response = await fetch(`/api/jobs?status=${encodeURIComponent(filter)}&limit=50`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Jobs request failed (${response.status})`);
      const payload = await response.json();
      setJobs(Array.isArray(payload?.jobs) ? payload.jobs : []);
    } catch (err) {
      setJobsError(err instanceof Error ? err.message : 'Unable to load generation jobs.');
    } finally {
      if (!silent) setJobsLoading(false);
    }
  };

  const runJobAction = async (job, action) => {
    if (!job?.id || jobActionBusy) return;
    if (action === 'cancel' && !window.confirm('Cancel this generation? The provider job will be stopped if it is still running.')) return;
    setJobActionBusy(job.id);
    setJobsError('');
    try {
      const response = await fetch('/api/job-actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: job.id, action }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error || `${action === 'retry' ? 'Retry' : 'Cancel'} failed (${response.status})`);
      if (action === 'retry') setJobsFilter('active');
      await loadJobs({ filter: action === 'retry' ? 'active' : jobsFilter });
    } catch (err) {
      setJobsError(err instanceof Error ? err.message : `Unable to ${action} job.`);
    } finally {
      setJobActionBusy('');
    }
  };

  React.useEffect(() => {
    if (section !== 'Jobs') return undefined;
    loadJobs({ filter: jobsFilter });
    const timer = window.setInterval(() => loadJobs({ silent: true, filter: jobsFilter }), 3000);
    return () => window.clearInterval(timer);
  }, [section, jobsFilter]);

  const loadHistory = async ({ append = false, kind = historyKind, model = historyModel } = {}) => {
    if (append && historyPage.nextOffset == null) return;
    append ? setHistoryAppending(true) : setHistoryLoading(true);
    setHistoryError('');
    try {
      const params = new URLSearchParams({ limit: String(HISTORY_PAGE_SIZE), offset: String(append ? historyPage.nextOffset : 0) });
      if (kind === 'image' || kind === 'video') params.set('kind', kind);
      if (model !== 'all') params.set('model', model);
      const response = await fetch(`/api/history?${params.toString()}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`History request failed (${response.status})`);
      const payload = await response.json();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toHistoryItem);
      setHistoryItems((current) => append ? [...current, ...nextItems] : nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
      setHistoryPage({ nextOffset: payload?.page?.nextOffset ?? null, hasMore: Boolean(payload?.page?.hasMore) });
      if (Array.isArray(payload?.facets?.models)) setHistoryModels(payload.facets.models);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Unable to load generation history.');
    } finally {
      append ? setHistoryAppending(false) : setHistoryLoading(false);
    }
  };

  const loadFavorites = async () => {
    setLibraryLoading(true); setLibraryError('');
    try {
      const response = await fetch('/api/favorites');
      if (!response.ok) throw new Error(`Favorites request failed (${response.status})`);
      const payload = await response.json();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toHistoryItem);
      setFavoriteItems(nextItems);
      setFavorites(new Set(nextItems.map((item) => item.id)));
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load favorites.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollections = async () => {
    setLibraryLoading(true); setLibraryError('');
    try {
      const response = await fetch('/api/collections');
      if (!response.ok) throw new Error(`Collections request failed (${response.status})`);
      const payload = await response.json();
      setCollections(Array.isArray(payload?.collections) ? payload.collections : []);
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load collections.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollectionItems = async (collection) => {
    setSelectedCollection(collection); setLibraryLoading(true); setLibraryError('');
    try {
      const response = await fetch(`/api/collection-items?collectionId=${encodeURIComponent(collection.id)}`);
      if (!response.ok) throw new Error(`Collection request failed (${response.status})`);
      const payload = await response.json();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toHistoryItem);
      setCollectionItems(nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load collection.'); }
    finally { setLibraryLoading(false); }
  };

  React.useEffect(() => {
    if (section === 'History') loadHistory({ append: false, kind: historyKind, model: historyModel });
    if (section === 'Favorites') loadFavorites();
    if (section === 'Collections') { setSelectedCollection(null); setCollectionItems([]); loadCollections(); }
  }, [section, historyKind, historyModel]);

  const addReferences = async (files) => {
    const valid = [];
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setError('References must be PNG, JPEG, or WebP images.'); continue; }
      if (file.size > 25 * 1024 * 1024) { setError(`${file.name} is larger than 25 MB.`); continue; }
      const dimensions = await imageDimensions(file);
      valid.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, file, preview: URL.createObjectURL(file), ...dimensions });
    }
    if (valid.length) { setReferences((current) => [...current, ...valid]); setMode('Edit'); setError(''); }
  };

  const removeReference = (index) => {
    setReferences((current) => {
      const target = current[index];
      if (target?.preview) URL.revokeObjectURL(target.preview);
      return current.filter((_, itemIndex) => itemIndex !== index);
    });
  };

  const runFluxEdit = async () => {
    if (!references.length) throw new Error('Add at least one reference image before running an edit.');
    if (!prompt.trim()) throw new Error('Describe the edit you want to make.');
    const effectiveSeed = Number(seed) || 42;
    const model = 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
    setJobStatus('queued');

    const { job, result } = await runImageEdit({
      sourceFiles: references.map((reference) => reference.file),
      prompt: prompt.trim(),
      negativePrompt: '',
      resolution: autoEditInfo.detail,
      seed: effectiveSeed,
      steps,
      cfg,
      megapixels: autoEditInfo.megapixels,
    }, { onStatus: setJobStatus });

    setJobStatus('completed');
    const item = {
      id: result.generationId || job.id,
      title: prompt.trim(),
      url: result.thumbnailUrl || result.mediaUrl,
      originalUrl: result.mediaUrl,
      thumbnailUrl: result.thumbnailUrl || null,
      generated: true,
      model,
      resolution: autoEditInfo.detail,
      seed: effectiveSeed,
      kind: 'image',
      mode: 'edit',
      persisted: true,
    };
    setItems((current) => [item, ...current]);
    if (section === 'History') loadHistory({ append: false });
  };

  const generate = async () => {
    if (busy) return;
    setBusy(true); setError(''); setJobStatus('');
    try {
      if (isEdit) await runFluxEdit();
      else if (mode === 'Image') throw new Error('Original image generation is not connected to a production workflow yet. The new presets are ready for that backend.');
      else if (mode === 'Video') throw new Error('Video generation is the next workflow milestone and is not connected yet.');
      else throw new Error('Choose Image, Video, or Edit to generate media.');
    } catch (err) {
      setJobStatus('failed');
      setError(err instanceof Error ? err.message : 'Generation failed.');
    } finally { setBusy(false); }
  };

  const toggleFavorite = async (item) => {
    const id = item.id;
    const nextValue = !favorites.has(id);
    setFavorites((current) => { const next = new Set(current); nextValue ? next.add(id) : next.delete(id); return next; });
    if (!item.persisted || !isUuid(id)) return;
    try {
      const response = await fetch('/api/favorites', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, isFavorite: nextValue }) });
      if (!response.ok) throw new Error('Favorite update failed');
      if (section === 'Favorites') loadFavorites();
      setHistoryItems((current) => current.map((entry) => entry.id === id ? { ...entry, favorite: nextValue } : entry));
    } catch {
      setFavorites((current) => { const next = new Set(current); nextValue ? next.delete(id) : next.add(id); return next; });
    }
  };

  const createCollection = async () => {
    const name = window.prompt('Collection name');
    if (!name?.trim()) return;
    setLibraryError('');
    try {
      const response = await fetch('/api/collections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim() }) });
      if (!response.ok) throw new Error(`Create collection failed (${response.status})`);
      await loadCollections();
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to create collection.'); }
  };

  const renameCollection = async (collection) => {
    const name = window.prompt('Rename collection', collection.name);
    if (!name?.trim() || name.trim() === collection.name) return;
    try {
      const response = await fetch('/api/collections', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: collection.id, name: name.trim() }) });
      if (!response.ok) throw new Error('Rename failed');
      await loadCollections();
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to rename collection.'); }
  };

  const deleteCollection = async (collection) => {
    if (!window.confirm(`Delete “${collection.name}”? The media itself will stay in History.`)) return;
    try {
      const response = await fetch(`/api/collections?id=${encodeURIComponent(collection.id)}`, { method: 'DELETE' });
      if (!response.ok && response.status !== 204) throw new Error('Delete failed');
      setSelectedCollection(null); setCollectionItems([]); await loadCollections();
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to delete collection.'); }
  };

  const addToCollection = async (item) => {
    if (!item.persisted || !isUuid(item.id)) return;
    if (!collections.length) await loadCollections();
    const currentCollections = collections.length ? collections : [];
    const hint = currentCollections.length ? currentCollections.map((c, index) => `${index + 1}. ${c.name}`).join('\n') : 'No collections yet. Create one from the Collections page first.';
    const answer = window.prompt(`Add to collection:\n${hint}\n\nEnter collection number or exact name:`);
    if (!answer) return;
    const index = Number.parseInt(answer, 10) - 1;
    const collection = currentCollections[index] || currentCollections.find((c) => c.name.toLowerCase() === answer.trim().toLowerCase());
    if (!collection) return window.alert('Collection not found.');
    const response = await fetch('/api/collection-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId: collection.id, generationId: item.id }) });
    if (!response.ok && response.status !== 204) return window.alert('Could not add item to collection.');
    await loadCollections();
  };

  const removeFromCollection = async (item) => {
    if (!selectedCollection) return;
    const response = await fetch('/api/collection-items', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId: selectedCollection.id, generationId: item.id }) });
    if (response.ok || response.status === 204) { await loadCollectionItems(selectedCollection); await loadCollections(); }
  };

  const reuseSettings = (item) => {
    setPrompt(item.title || '');
    if (item.seed != null) setSeed(String(item.seed));
    if (item.kind === 'video') setMode('Video');
    else if (item.mode === 'edit') { setMode('Edit'); setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); }
    else setMode('Image');
    setSection('Create');
    setError('');
  };

  const editThis = async (item) => {
    if (item.kind === 'video') return window.alert('Video editing will be connected with the video workflow phase.');
    const mediaUrl = item.originalUrl || item.url;
    if (!mediaUrl) return;
    try {
      const response = await fetch(mediaUrl);
      if (!response.ok) throw new Error(`Media request failed (${response.status})`);
      const blob = await response.blob();
      if (!blob.type.startsWith('image/')) throw new Error('Selected media is not an image.');
      const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png';
      const file = new File([blob], `saga-edit-${item.id}.${extension}`, { type: blob.type || 'image/png' });
      const dimensions = await imageDimensions(file);
      references.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
      setReferences([{ id: `history-${item.id}-${Date.now()}`, file, preview: URL.createObjectURL(blob), ...dimensions }]);
      setPrompt('');
      if (item.seed != null) setSeed(String(item.seed));
      setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b');
      setMode('Edit');
      setSection('Create');
      setError('');
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not prepare this image for editing.');
    }
  };

  const downloadItem = (item) => {
    const mediaUrl = item.originalUrl || item.url;
    if (!mediaUrl) return;
    const separator = mediaUrl.includes('?') ? '&' : '?';
    const link = document.createElement('a');
    link.href = `${mediaUrl}${separator}download=1`;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const deleteGeneration = async (item) => {
    if (!item.persisted || !isUuid(item.id)) return window.alert('Only persisted generations can be deleted.');
    if (!window.confirm('Permanently delete this generation? This removes the original, thumbnail, favorites, collection memberships, and retained source references.')) return;
    try {
      const response = await fetch(`/api/generations?id=${encodeURIComponent(item.id)}`, { method: 'DELETE' });
      if (!response.ok) {
        let detail = '';
        try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
        throw new Error(`Delete failed (${response.status})${detail}`);
      }
      setSelectedMedia((current) => current?.id === item.id ? null : current);
      setHistoryItems((current) => current.filter((entry) => entry.id !== item.id));
      setFavoriteItems((current) => current.filter((entry) => entry.id !== item.id));
      setCollectionItems((current) => current.filter((entry) => entry.id !== item.id));
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setFavorites((current) => { const next = new Set(current); next.delete(item.id); return next; });
      await loadCollections();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not delete generation.');
    }
  };

  const openMedia = (item) => setSelectedMedia(item);
  const renderCard = (item, history = false, inCollection = false) => (
    <article className={`media-card ${history ? 'history-card' : ''}`} key={item.id}>
      <div className={`media-frame ${!item.url ? 'media-frame-empty' : ''}`} style={item.url ? { backgroundImage: `url(${item.url})` } : undefined} onClick={() => openMedia(item)} role="button" tabIndex={0}>
        {!item.url && <div className="media-placeholder"><Video size={28}/><span>Video preview</span></div>}
        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? `${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}${history ? '' : ' · Klein 9B'}` : '1024 × 1024'}</div>
        <div className="media-hover"><button aria-label="Open full media"><Maximize2 size={18}/></button></div>
      </div>
      {history && <div className="history-copy"><div className="history-prompt">{item.title}</div><div className="history-meta"><span>{item.model || 'Unknown model'}</span>{item.seed != null && <span>Seed {item.seed}</span>}</div></div>}
      <div className="card-actions" style={{ gridTemplateColumns: 'repeat(7,1fr)' }}>
        <button title="Favorite" className={favorites.has(item.id) ? 'favorite active' : 'favorite'} onClick={() => toggleFavorite(item)}><Heart size={19} fill={favorites.has(item.id) ? 'currentColor' : 'none'}/></button>
        <button title="Reuse settings" onClick={() => reuseSettings(item)}><RefreshCcw size={18}/></button>
        <button title="Edit this" onClick={() => editThis(item)}><Pencil size={18}/></button>
        <button title="Download original" onClick={() => downloadItem(item)}><Download size={18}/></button>
        <button title="Open full media" onClick={() => openMedia(item)}><ArrowUpRight size={19}/></button>
        <button title={inCollection ? 'Remove from collection' : 'Add to collection'} onClick={() => inCollection ? removeFromCollection(item) : addToCollection(item)}><Folder size={18}/></button>
        <button title="Delete permanently" onClick={() => deleteGeneration(item)}><Trash2 size={18}/></button>
      </div>
    </article>
  );

  const renderLibraryHeader = (eyebrow, title, description, action) => <div className="history-header"><div><div className="history-eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button className="mobile-close" onClick={() => setMobileNav(false)}><ChevronLeft size={19}/></button></div>
        <nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label && (label !== 'Create' || mode !== 'More')} onClick={() => { setSection(label); if (label === 'Create' && mode === 'More') setMode('Image'); setMobileNav(false); }} />)}<NavItem icon={Sparkles} label="More" active={section === 'Create' && mode === 'More'} onClick={() => { setSection('Create'); setMode('More'); setError(''); setMobileNav(false); }} /></nav>
        <div className="nav-divider" />
        <nav className="nav-group">{navSecondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => { setSection(label); setMobileNav(false); }} />)}</nav>
        <div className="nav-divider" /><NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => setSection('Settings')} />
        <div className="profile-card"><div className="avatar-orb"/><div className="profile-copy"><div className="profile-name">Saga Creator <span className="pro-badge">Studio</span></div><div className="profile-email">FLUX.2 online</div></div><ChevronDown size={16}/></div>
      </aside>

      <main className="workspace">
        <div className="mobile-topbar"><button className="icon-button" onClick={() => setMobileNav(true)}><Menu size={20}/></button><div className="mobile-brand">SAGA Studio</div><button className="icon-button" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={20}/></button></div>

        {section === 'Jobs' ? <section className="history-view">
          {renderLibraryHeader('Execution', 'Jobs & queue', 'Live generation lifecycle. This page polls while open; completed media stays in History.', <button className="secondary-button" onClick={() => loadJobs({ filter: jobsFilter })} disabled={jobsLoading}>{jobsLoading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>)}
          <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Job status filter">{[['active', 'Active'], ['queued', 'Queued'], ['running', 'Running'], ['failed', 'Failed'], ['completed', 'Completed'], ['all', 'Recent']].map(([value, label]) => <button key={value} className={jobsFilter === value ? 'selected' : ''} onClick={() => setJobsFilter(value)}>{label}</button>)}</div></div>
          {jobsError && <div className="history-state error">{jobsError}</div>}
          {jobsLoading && jobs.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading jobs…</div> : jobs.length === 0 ? <div className="history-state">No lifecycle jobs match this filter.</div> : <div style={{ display: 'grid', gap: 12 }}>{jobs.map((job) => {
            const cancelled = Boolean(job.metadata?.cancelled);
            const actionBusy = jobActionBusy === job.id;
            return <article key={job.id} style={{ border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, background: 'rgba(255,255,255,.025)', padding: '16px 18px', display: 'grid', gap: 10 }}><div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}><div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}><span style={{ textTransform: 'uppercase', fontSize: 11, fontWeight: 700, letterSpacing: '.08em', padding: '5px 8px', borderRadius: 999, border: '1px solid rgba(255,255,255,.14)', opacity: job.status === 'failed' ? 1 : .8 }}>{cancelled ? 'cancelled' : job.status}</span><strong style={{ fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.prompt || 'Untitled job'}</strong></div><span style={{ fontSize: 12, color: '#7f8999' }}>{formatJobTime(job.created_at)}</span></div><div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, color: '#8f98a8' }}><span>{job.kind || 'image'} · {job.mode || 'generation'}</span><span>{job.model || 'Unknown model'}</span><span>{job.provider || 'provider n/a'}</span>{job.seed != null && <span>Seed {job.seed}</span>}{job.resolution && <span>{job.resolution}</span>}</div><div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 11, color: '#687284' }}><span>Queued {formatJobTime(job.created_at)}</span><span>Started {formatJobTime(job.started_at)}</span><span>Finished {formatJobTime(job.completed_at)}</span></div>{job.error_message && <div style={{ padding: '10px 12px', borderRadius: 9, background: 'rgba(120,20,35,.14)', border: '1px solid rgba(255,100,120,.25)', color: '#ffb4c0', fontSize: 12 }}>{job.error_message}</div>}<div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>{['queued', 'running'].includes(job.status) && <button className="secondary-button" disabled={actionBusy} onClick={() => runJobAction(job, 'cancel')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <X size={16}/>} Cancel</button>}{job.status === 'failed' && <button className="secondary-button" disabled={actionBusy} onClick={() => runJobAction(job, 'retry')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <RotateCcw size={16}/>} Retry</button>}</div></article>;
          })}</div>}
        </section> : section === 'History' ? <section className="history-view">
          {renderLibraryHeader('Library', 'Generation history', 'Thumbnail-first previews. Originals load only when you open an item.', <button className="secondary-button" onClick={() => loadHistory({ append: false })} disabled={historyLoading}>{historyLoading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>)}
          <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Media type filter">{[['all', 'All'], ['image', 'Images'], ['video', 'Videos']].map(([value, label]) => <button key={value} className={historyKind === value ? 'selected' : ''} onClick={() => setHistoryKind(value)}>{label}</button>)}</div><label className="history-model-filter"><span>Model</span><select value={historyModel} onChange={(event) => setHistoryModel(event.target.value)}><option value="all">All models</option>{historyModels.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}</select></label></div>
          {historyError && <div className="history-state error">{historyError}</div>}
          {historyLoading && historyItems.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading history…</div> : historyItems.length === 0 ? <div className="history-state">No generations match these filters.</div> : <><section className="gallery-grid history-grid">{historyItems.map((item) => renderCard(item, true))}</section>{historyPage.hasMore && <div className="history-load-more"><button className="secondary-button" onClick={() => loadHistory({ append: true })} disabled={historyAppending}>{historyAppending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {historyAppending ? 'Loading…' : 'Load more'}</button></div>}</>}
        </section> : section === 'Favorites' ? <section className="history-view">
          {renderLibraryHeader('Library', 'Favorites', 'Saved generations persist across refreshes and devices using the Studio database.', <button className="secondary-button" onClick={loadFavorites} disabled={libraryLoading}>{libraryLoading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>)}
          {libraryError && <div className="history-state error">{libraryError}</div>}
          {libraryLoading && favoriteItems.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading favorites…</div> : favoriteItems.length === 0 ? <div className="history-state">No favorites yet. Tap the heart on any persisted generation.</div> : <section className="gallery-grid history-grid">{favoriteItems.map((item) => renderCard(item, true))}</section>}
        </section> : section === 'Collections' ? <section className="history-view">
          {renderLibraryHeader('Library', selectedCollection ? selectedCollection.name : 'Collections', selectedCollection ? `${collectionItems.length} saved item${collectionItems.length === 1 ? '' : 's'}` : 'Organize persisted generations into reusable groups.', selectedCollection ? <button className="secondary-button" onClick={() => { setSelectedCollection(null); setCollectionItems([]); }}><ChevronLeft size={18}/> All collections</button> : <button className="secondary-button" onClick={createCollection}><Plus size={18}/> New collection</button>)}
          {libraryError && <div className="history-state error">{libraryError}</div>}
          {selectedCollection ? (libraryLoading && collectionItems.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collection…</div> : collectionItems.length === 0 ? <div className="history-state">This collection is empty. Add items from History or Favorites.</div> : <section className="gallery-grid history-grid">{collectionItems.map((item) => renderCard(item, true, true))}</section>) : (libraryLoading && collections.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collections…</div> : collections.length === 0 ? <div className="history-state">No collections yet.</div> : <div className="collection-grid">{collections.map((collection) => <article className="collection-card" key={collection.id}><button className="collection-cover" style={collection.coverUrl ? { backgroundImage: `url(${collection.coverUrl})` } : undefined} onClick={() => loadCollectionItems(collection)}>{!collection.coverUrl && <Folder size={34}/>}</button><div className="collection-copy"><button className="collection-title" onClick={() => loadCollectionItems(collection)}>{collection.name}</button><span>{collection.itemCount || 0} items</span></div><div className="collection-actions"><button onClick={() => renameCollection(collection)}><Pencil size={16}/></button><button onClick={() => deleteCollection(collection)}><Trash2 size={16}/></button></div></article>)}</div>)}
        </section> : section === 'Models' ? <section className="history-view">
          {renderLibraryHeader('Studio', 'Models', 'Models exposed to the generation registry. Only live backends are selectable in production.')}
          <div className="collection-grid"><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>FLUX.2 Klein 9B · DarkBeast V2 BFS</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Image editing with automatic output sizing and multi-reference conditioning.</p></article><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">PLANNED</div><h3 style={{ margin: '8px 0' }}>SAGA Image</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Original image generation UI presets are ready; the production workflow will be connected separately.</p></article></div>
        </section> : section === 'Workflows' ? <section className="history-view">
          {renderLibraryHeader('Studio', 'Workflows', 'Registered generation paths and their current capabilities.')}
          <div className="collection-grid"><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>Klein Multi-Reference Edit</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Direct R2 inputs → Studio orchestration → Modal / ComfyUI → persisted R2 result and thumbnail.</p></article></div>
        </section> : section === 'Settings' ? <section className="history-view">
          {renderLibraryHeader('Studio', 'Settings', 'Generation settings live beside the composer so they stay contextual to the selected workflow.', <button className="secondary-button" onClick={() => { setSection('Create'); setSettingsOpen(true); }}><SlidersHorizontal size={18}/> Open generation settings</button>)}
          <div className="history-state">Use the settings panel to control model, aspect ratio, resolution, seed, steps, CFG, and workflow.</div>
        </section> : <CreateWorkspace
          mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else if (nextMode === 'Video') { setWorkflowId('video-planned'); setModelId('saga-video-auto'); } else if (nextMode === 'Image') { setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}
          prompt={prompt} setPrompt={setPrompt} references={references} onAddReferences={addReferences} onRemoveReference={removeReference}
          error={error} jobStatus={jobStatus} busy={busy} onGenerate={generate} items={visibleItems} renderCard={renderCard}
          aspect={aspect} setAspect={setAspect} imageResolution={imageResolution} setImageResolution={setImageResolution}
          outputs={outputs} setOutputs={setOutputs} advanced={advanced} setAdvanced={setAdvanced}
          seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg}
          workflowId={workflowId} setWorkflowId={setWorkflowId} modelId={modelId} setModelId={setModelId}
          settingsOpen={settingsOpen} setSettingsOpen={setSettingsOpen} autoEditInfo={autoEditInfo}
        />}
      </main>

      {selectedMedia && <div className="media-modal" onClick={() => setSelectedMedia(null)}><div className="media-modal-card" onClick={(event) => event.stopPropagation()}><button className="media-modal-close" onClick={() => setSelectedMedia(null)}><X size={20}/></button>{selectedMedia.kind === 'video' ? <video src={selectedMedia.originalUrl} poster={selectedMedia.thumbnailUrl || undefined} controls playsInline /> : <img src={selectedMedia.originalUrl || selectedMedia.url} alt={selectedMedia.title || 'Generated image'} />}<div className="media-modal-copy"><strong>{selectedMedia.title || 'Generated media'}</strong><span>{selectedMedia.model || ''}{selectedMedia.seed != null ? ` · Seed ${selectedMedia.seed}` : ''}</span></div></div></div>}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
