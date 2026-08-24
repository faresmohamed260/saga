from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'apps/studio/src'
APP = SRC / 'app/App.jsx'
HOOKS = SRC / 'hooks'
API = SRC / 'api'
HOOKS.mkdir(exist_ok=True)
API.mkdir(exist_ok=True)

app = APP.read_text()

# Shared API layer: browser/network details live here instead of App/hooks.
(API / 'studioApi.js').write_text(r'''async function jsonResponse(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error || fallback || `Request failed (${response.status})`);
  return payload;
}

export async function fetchGallery({ limit, offset, kind, model }) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (kind === 'image' || kind === 'video') params.set('kind', kind);
  if (model && model !== 'all') params.set('model', model);
  const response = await fetch(`/api/history?${params.toString()}`, { headers: { Accept: 'application/json' } });
  return jsonResponse(response, `Gallery request failed (${response.status})`);
}

export async function fetchFavorites() {
  const response = await fetch('/api/favorites');
  return jsonResponse(response, `Favorites request failed (${response.status})`);
}

export async function updateFavorite(id, isFavorite) {
  const response = await fetch('/api/favorites', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, isFavorite }) });
  if (!response.ok) throw new Error(`Favorite update failed (${response.status})`);
}

export async function fetchCollections() {
  const response = await fetch('/api/collections');
  return jsonResponse(response, `Collections request failed (${response.status})`);
}

export async function createCollection(name) {
  const response = await fetch('/api/collections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  return jsonResponse(response, `Create collection failed (${response.status})`);
}

export async function renameCollection(id, name) {
  const response = await fetch('/api/collections', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, name }) });
  return jsonResponse(response, `Rename collection failed (${response.status})`);
}

export async function deleteCollection(id) {
  const response = await fetch(`/api/collections?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 204) throw new Error(`Delete collection failed (${response.status})`);
}

export async function fetchCollectionItems(collectionId) {
  const response = await fetch(`/api/collection-items?collectionId=${encodeURIComponent(collectionId)}`);
  return jsonResponse(response, `Collection request failed (${response.status})`);
}

export async function addCollectionItem(collectionId, generationId) {
  const response = await fetch('/api/collection-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId, generationId }) });
  if (!response.ok && response.status !== 204) throw new Error(`Collection update failed (${response.status})`);
}

export async function removeCollectionItem(collectionId, generationId) {
  const response = await fetch('/api/collection-items', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId, generationId }) });
  if (!response.ok && response.status !== 204) throw new Error(`Collection update failed (${response.status})`);
}

export async function deleteGeneration(id) {
  const response = await fetch(`/api/generations?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
    throw new Error(`Delete failed (${response.status})${detail}`);
  }
}

export async function downloadBatch(ids) {
  const response = await fetch('/api/download-batch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }) });
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
    throw new Error(`Batch download failed (${response.status})${detail}`);
  }
  return response;
}

export async function runJobAction(id, action) {
  const response = await fetch('/api/job-actions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action }) });
  return jsonResponse(response, `${action === 'retry' ? 'Retry' : 'Cancel'} failed (${response.status})`);
}
''')

(HOOKS / 'useGallerySelection.js').write_text(r'''import { useEffect, useMemo, useState } from 'react';

export default function useGallerySelection(items) {
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
    if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
    return next;
  });
  const finishManaging = () => { setManaging(false); setSelected(new Set()); };
  const runBulk = async (name, callback) => {
    if (!selectedItems.length || actionBusy) return;
    setActionBusy(name);
    try {
      const result = await callback?.(selectedItems);
      if (result && Array.isArray(result.failedIds)) setSelected(new Set(result.failedIds));
      else if ((name === 'delete' || name === 'collection') && result !== false) setSelected(new Set());
    } finally { setActionBusy(''); }
  };
  return { managing, setManaging, selected, setSelected, actionBusy, selectedItems, toggle, finishManaging, runBulk };
}
''')

(HOOKS / 'useLibraryController.js').write_text(r'''import React from 'react';
import { fetchCollectionItems, fetchCollections, fetchFavorites, fetchGallery } from '../api/studioApi.js';

const GALLERY_PAGE_SIZE = 24;

export default function useLibraryController({ section, toGalleryItem }) {
  const [favorites, setFavorites] = React.useState(new Set());
  const [favoriteItems, setFavoriteItems] = React.useState([]);
  const [galleryItems, setGalleryItems] = React.useState([]);
  const [galleryLoading, setGalleryLoading] = React.useState(false);
  const [galleryAppending, setGalleryAppending] = React.useState(false);
  const [galleryError, setGalleryError] = React.useState('');
  const [galleryKind, setGalleryKind] = React.useState('all');
  const [galleryModel, setGalleryModel] = React.useState('all');
  const [galleryModels, setGalleryModels] = React.useState([]);
  const [galleryPage, setGalleryPage] = React.useState({ nextOffset: null, hasMore: false });
  const [libraryLoading, setLibraryLoading] = React.useState(false);
  const [libraryError, setLibraryError] = React.useState('');
  const [collections, setCollections] = React.useState([]);
  const [selectedCollection, setSelectedCollection] = React.useState(null);
  const [collectionItems, setCollectionItems] = React.useState([]);

  const loadGallery = async ({ append = false, kind = galleryKind, model = galleryModel } = {}) => {
    if (append && galleryPage.nextOffset == null) return;
    append ? setGalleryAppending(true) : setGalleryLoading(true);
    setGalleryError('');
    try {
      const payload = await fetchGallery({ limit: GALLERY_PAGE_SIZE, offset: append ? galleryPage.nextOffset : 0, kind, model });
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setGalleryItems((current) => append ? [...current, ...nextItems] : nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
      setGalleryPage({ nextOffset: payload?.page?.nextOffset ?? null, hasMore: Boolean(payload?.page?.hasMore) });
      if (Array.isArray(payload?.facets?.models)) setGalleryModels(payload.facets.models);
    } catch (err) { setGalleryError(err instanceof Error ? err.message : 'Unable to load Gallery.'); }
    finally { append ? setGalleryAppending(false) : setGalleryLoading(false); }
  };

  const loadFavorites = async () => {
    setLibraryLoading(true); setLibraryError('');
    try {
      const payload = await fetchFavorites();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setFavoriteItems(nextItems);
      setFavorites(new Set(nextItems.map((item) => item.id)));
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load favorites.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollections = async () => {
    setLibraryLoading(true); setLibraryError('');
    try { const payload = await fetchCollections(); setCollections(Array.isArray(payload?.collections) ? payload.collections : []); }
    catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load collections.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollectionItems = async (collection) => {
    setSelectedCollection(collection); setLibraryLoading(true); setLibraryError('');
    try {
      const payload = await fetchCollectionItems(collection.id);
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
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
    if (section === 'Gallery') loadGallery({ append: false, kind: galleryKind, model: galleryModel });
    if (section === 'Favorites') loadFavorites();
    if (section === 'Collections') { setSelectedCollection(null); setCollectionItems([]); loadCollections(); }
  }, [section, galleryKind, galleryModel]);

  return { favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems, galleryLoading, galleryAppending, galleryError, galleryKind, setGalleryKind, galleryModel, setGalleryModel, galleryModels, galleryPage, libraryLoading, libraryError, setLibraryError, collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems, loadGallery, loadFavorites, loadCollections, loadCollectionItems };
}
''')

(HOOKS / 'useGenerationController.js').write_text(r'''import React from 'react';
import { runImageEdit, runVideoGeneration } from '../generation-client.js';
import { runJobAction } from '../api/studioApi.js';

export default function useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {
  const [busy, setBusy] = React.useState(false);
  const [jobStatus, setJobStatus] = React.useState('');
  const [workerStatus, setWorkerStatus] = React.useState(null);
  const [activeJob, setActiveJob] = React.useState(null);
  const [cancelBusy, setCancelBusy] = React.useState(false);
  const generationAbortRef = React.useRef(null);

  const runFluxEdit = async () => {
    if (!references.length) throw new Error('Add at least one reference image before running an edit.');
    if (!prompt.trim()) throw new Error('Describe the edit you want to make.');
    const effectiveSeed = Number(seed) || 42;
    setJobStatus('queued');
    const { job, result } = await runImageEdit({ sourceFiles: references.map((reference) => reference.file), prompt: prompt.trim(), negativePrompt: '', resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
    setJobStatus('completed');
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS', resolution: autoEditInfo.detail, seed: effectiveSeed, kind: 'image', mode: 'edit', persisted: true }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

  const runLtxVideo = async (videoOptions = {}) => {
    if (!prompt.trim()) throw new Error('Describe the video you want to generate.');
    const effectiveSeed = Number(seed) || 42;
    const videoResolution = String(videoOptions.videoResolution || '480p');
    const videoDuration = Math.max(5, Math.min(30, Math.round(Number(videoOptions.videoDuration) || 5)));
    const videoAudio = videoOptions.videoAudio !== false;
    const videoAspect = String(videoOptions.videoAspect || '16:9');
    const requestedFrameRate = Number(videoOptions.videoFrameRate);
    const videoFrameRate = [24, 25, 30].includes(requestedFrameRate) ? requestedFrameRate : 24;
    const sourceFile = references[0]?.file || null;
    setJobStatus(sourceFile ? 'uploading' : 'queued');
    const { job, result } = await runVideoGeneration({ sourceFile, prompt: prompt.trim(), resolution: videoResolution, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
    setJobStatus('completed');
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', resolution: videoResolution, seed: effectiveSeed, kind: 'video', mode: sourceFile ? 'image-to-video' : 'video', persisted: true, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

  const generate = async (generationOptions = {}) => {
    if (busy) return;
    const controller = new AbortController(); generationAbortRef.current = controller;
    setBusy(true); setError(''); setJobStatus(''); setWorkerStatus(null); setActiveJob(null); setCancelBusy(false);
    try {
      if (isEdit) await runFluxEdit();
      else if (mode === 'Image') throw new Error('Original image generation is not connected to a production workflow yet. The new presets are ready for that backend.');
      else if (mode === 'Video') await runLtxVideo(generationOptions);
      else throw new Error('Choose Image, Video, or Edit to generate media.');
    } catch (err) {
      if (err?.name === 'AbortError') { setJobStatus('cancelled'); setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' })); setError(''); }
      else { setJobStatus('failed'); const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || '')) ? String(err.workerState) : 'failed'; setWorkerStatus((current) => ({ ...(current || {}), ...(err?.worker || {}), state: terminalWorkerState, errorCode: err?.errorCode || null })); setError(err instanceof Error ? err.message : 'Generation failed.'); }
    } finally { if (generationAbortRef.current === controller) generationAbortRef.current = null; setBusy(false); setCancelBusy(false); }
  };

  const viewActiveJob = () => { setJobsFilter('all'); setSection('Jobs'); };
  const cancelActiveJob = async () => {
    if (!busy || !activeJob?.id || cancelBusy) return;
    if (!window.confirm('Cancel this generation? The provider job will be stopped if it is still running.')) return;
    setCancelBusy(true); setError('');
    try { const payload = await runJobAction(activeJob.id, 'cancel'); setActiveJob(payload?.job || activeJob); setJobStatus('cancelled'); setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' })); generationAbortRef.current?.abort(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to cancel generation.'); setCancelBusy(false); }
  };
  return { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob };
}
''')

# GalleryView now delegates selection state to a dedicated hook.
view_path = SRC / 'features/library/GalleryView.jsx'
view = view_path.read_text()
view = view.replace("import React, { useEffect, useMemo, useState } from 'react';", "import React from 'react';\nimport useGallerySelection from '../../hooks/useGallerySelection.js';")
start = view.index("  const [managing, setManaging]")
end = view.index("\n\n  return (", start)
view = view[:start] + "  const { managing, setManaging, selected, setSelected, actionBusy, toggle, finishManaging, runBulk } = useGallerySelection(items);" + view[end:]
view_path.write_text(view)

# App imports/hooks and remove extracted state/loading/generation blocks.
app = app.replace("import { runImageEdit, runVideoGeneration } from '../generation-client.js';\n", "")
app = app.replace("import SettingsView from '../features/settings/SettingsView.jsx';\n", "import SettingsView from '../features/settings/SettingsView.jsx';\nimport useLibraryController from '../hooks/useLibraryController.js';\nimport useGenerationController from '../hooks/useGenerationController.js';\n")
app = app.replace("const GALLERY_PAGE_SIZE = 24;\n", "")
for line in [
"  const [busy, setBusy] = useState(false);\n", "  const [jobStatus, setJobStatus] = useState('');\n", "  const [workerStatus, setWorkerStatus] = useState(null);\n", "  const [activeJob, setActiveJob] = useState(null);\n", "  const [cancelBusy, setCancelBusy] = useState(false);\n", "  const generationAbortRef = React.useRef(null);\n",
"  const [favorites, setFavorites] = useState(new Set());\n", "  const [favoriteItems, setFavoriteItems] = useState([]);\n", "  const [galleryItems, setGalleryItems] = useState([]);\n", "  const [galleryLoading, setGalleryLoading] = useState(false);\n", "  const [galleryAppending, setGalleryAppending] = useState(false);\n", "  const [galleryError, setGalleryError] = useState('');\n", "  const [galleryKind, setGalleryKind] = useState('all');\n", "  const [galleryModel, setGalleryModel] = useState('all');\n", "  const [galleryModels, setGalleryModels] = useState([]);\n", "  const [galleryPage, setGalleryPage] = useState({ nextOffset: null, hasMore: false });\n", "  const [libraryLoading, setLibraryLoading] = useState(false);\n", "  const [libraryError, setLibraryError] = useState('');\n", "  const [collections, setCollections] = useState([]);\n", "  const [selectedCollection, setSelectedCollection] = useState(null);\n", "  const [collectionItems, setCollectionItems] = useState([]);\n"]:
    app = app.replace(line, '')

# Remove library loading block from loadGallery through its section effect.
start = app.index("  const loadGallery = async")
end_marker = "  }, [section, galleryKind, galleryModel]);\n"
end = app.index(end_marker, start) + len(end_marker)
app = app[:start] + app[end:]

# Remove generation functions runFluxEdit through cancelActiveJob.
start = app.index("  const runFluxEdit = async")
end = app.index("\n\n  const toggleFavorite", start)
app = app[:start] + app[end:]

# Insert hooks after autoEditInfo.
anchor = "  const autoEditInfo = useMemo(() => autoReferenceSizing(references[0]), [references]);\n"
hook_code = r'''
  const library = useLibraryController({ section, toGalleryItem });
  const { favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems, galleryLoading, galleryAppending, galleryError, galleryKind, setGalleryKind, galleryModel, setGalleryModel, galleryModels, galleryPage, libraryLoading, libraryError, setLibraryError, collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems, loadGallery, loadFavorites, loadCollections, loadCollectionItems } = library;
  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });
'''
app = app.replace(anchor, anchor + hook_code)
APP.write_text(app)

print('Iteration 20 controller/API split applied.')
