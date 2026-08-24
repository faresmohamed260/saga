import React, { useMemo, useState } from 'react';
import CreateWorkspace from '../features/create/CreateWorkspace.jsx';
import Sidebar from '../components/Sidebar.jsx';
import MobileTopbar from '../components/MobileTopbar.jsx';
import MediaCard from '../components/MediaCard.jsx';
import MediaModal from '../components/MediaModal.jsx';
import JobsView from '../features/jobs/JobsView.jsx';
import GalleryView from '../features/library/GalleryView.jsx';
import FavoritesView from '../features/library/FavoritesView.jsx';
import CollectionsView from '../features/library/CollectionsView.jsx';
import ModelsView from '../features/catalog/ModelsView.jsx';
import WorkflowsView from '../features/catalog/WorkflowsView.jsx';
import SettingsView from '../features/settings/SettingsView.jsx';
import useLibraryController from '../hooks/useLibraryController.js';
import useGenerationController from '../hooks/useGenerationController.js';

const SECTION_HASHES = { Create: 'create', Jobs: 'jobs', Gallery: 'gallery', Favorites: 'favorites', Collections: 'collections', Models: 'models', Workflows: 'workflows', Settings: 'settings' };
const HASH_SECTIONS = { ...Object.fromEntries(Object.entries(SECTION_HASHES).map(([section, hash]) => [hash, section])), history: 'Gallery' };

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

function isUuid(value) { return /^[0-9a-f-]{36}$/i.test(String(value || '')); }
function toGalleryItem(row) {
  const previewUrl = row.thumbnail_url || row.media_url || '';
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
    aspectRatio: row.metadata?.execution?.aspectRatio || null,
    frameRate: row.metadata?.execution?.frameRate || null,
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

function promptAfterReferenceRemoval(value, removedIndex) {
  const next = String(value || '').replace(/@Image\s+(\d+)/gi, (match, rawNumber) => {
    const mentionNumber = Number(rawNumber);
    const mentionIndex = mentionNumber - 1;
    if (!Number.isFinite(mentionIndex)) return match;
    if (mentionIndex === removedIndex) return '';
    if (mentionIndex > removedIndex) return `@Image ${mentionNumber - 1}`;
    return `@Image ${mentionNumber}`;
  });
  return next
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/ *\n */g, '\n')
    .trim();
}

export default function App() {
  const [section, setSection] = useState(sectionFromLocation);
  const [mode, setMode] = useState('Image');
  const [prompt, setPrompt] = useState('');
  const [aspect, setAspect] = useState('1:1');
  const [imageResolution, setImageResolution] = useState(1080);
  const [outputs, setOutputs] = useState(4);
  const [advanced, setAdvanced] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
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
  const [items, setItems] = useState(samples);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [error, setError] = useState('');

  const visibleItems = useMemo(() => items.slice(0, mode === 'Edit' ? 4 : outputs), [items, outputs, mode]);
  const isEdit = mode === 'Edit';
  const autoEditInfo = useMemo(() => autoReferenceSizing(references[0]), [references]);

  const library = useLibraryController({ section, toGalleryItem });
  const { favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems, galleryLoading, galleryAppending, galleryError, galleryKind, setGalleryKind, galleryModel, setGalleryModel, galleryModels, galleryPage, libraryLoading, libraryError, setLibraryError, collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems, loadGallery, loadFavorites, loadCollections, loadCollectionItems } = library;
  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });

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


  const addReferences = async (files) => {
    const valid = [];
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setError('References must be PNG, JPEG, or WebP images.'); continue; }
      if (file.size > 25 * 1024 * 1024) { setError(`${file.name} is larger than 25 MB.`); continue; }
      const dimensions = await imageDimensions(file);
      valid.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, file, preview: URL.createObjectURL(file), ...dimensions });
    }
    if (valid.length) {
      if (mode === 'Video') {
        const next = valid[0];
        setReferences((current) => {
          current.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
          return next ? [next] : [];
        });
        if (valid.length > 1) valid.slice(1).forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
      } else {
        setReferences((current) => [...current, ...valid]);
        setMode('Edit');
      }
      setError('');
    }
  };

  const removeReference = (index) => {
    const target = references[index];
    if (!target) return;
    if (target.preview) URL.revokeObjectURL(target.preview);
    const nextReferences = references.filter((_, itemIndex) => itemIndex !== index);
    setReferences(nextReferences);
    setPrompt((current) => promptAfterReferenceRemoval(current, index));
    if (mode === 'Edit' && nextReferences.length === 0) {
      setMode('Image');
      setWorkflowId('default-image');
      setModelId('saga-image-auto');
      setError('');
    }
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
      setGalleryItems((current) => current.map((entry) => entry.id === id ? { ...entry, favorite: nextValue } : entry));
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
    if (!window.confirm(`Delete “${collection.name}”? The media itself will stay in Gallery.`)) return;
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
      setGalleryItems((current) => current.filter((entry) => entry.id !== item.id));
      setFavoriteItems((current) => current.filter((entry) => entry.id !== item.id));
      setCollectionItems((current) => current.filter((entry) => entry.id !== item.id));
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setFavorites((current) => { const next = new Set(current); next.delete(item.id); return next; });
      await loadCollections();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not delete generation.');
    }
  };

  const bulkFavorite = async (selectedItems) => {
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
      setGalleryItems((current) => current.map((entry) => candidates.some((item) => item.id === entry.id) ? { ...entry, favorite: true } : entry));
      return true;
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not favorite selected media.');
      await loadGallery({ append: false });
      return false;
    }
  };

  const bulkAddToCollection = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item?.persisted && isUuid(item.id));
    if (!candidates.length) {
      window.alert('Only persisted generations can be added to a collection.');
      return false;
    }

    let availableCollections = collections;
    if (!availableCollections.length) {
      try {
        const response = await fetch('/api/collections');
        if (!response.ok) throw new Error(`Collections request failed (${response.status})`);
        const payload = await response.json();
        availableCollections = Array.isArray(payload?.collections) ? payload.collections : [];
        setCollections(availableCollections);
      } catch (err) {
        window.alert(err instanceof Error ? err.message : 'Unable to load collections.');
        return false;
      }
    }

    if (!availableCollections.length) {
      window.alert('No collections yet. Create one from the Collections page first.');
      return false;
    }

    const hint = availableCollections.map((collection, index) => `${index + 1}. ${collection.name}`).join('\n');
    const answer = window.prompt(`Add ${candidates.length} selected item${candidates.length === 1 ? '' : 's'} to collection:\n${hint}\n\nEnter collection number or exact name:`);
    if (!answer) return false;

    const index = Number.parseInt(answer, 10) - 1;
    const collection = availableCollections[index] || availableCollections.find((entry) => entry.name.toLowerCase() === answer.trim().toLowerCase());
    if (!collection) {
      window.alert('Collection not found.');
      return false;
    }

    try {
      await Promise.all(candidates.map(async (item) => {
        const response = await fetch('/api/collection-items', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ collectionId: collection.id, generationId: item.id }),
        });
        if (!response.ok && response.status !== 204) throw new Error(`Collection update failed (${response.status})`);
      }));
      await loadCollections();
      return true;
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not add selected media to collection.');
      return false;
    }
  };

  const bulkDownload = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item?.persisted && isUuid(item.id));
    if (!candidates.length) {
      window.alert('Only persisted generations can be downloaded as a batch.');
      return false;
    }
    try {
      const response = await fetch('/api/download-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: candidates.map((item) => item.id) }),
      });
      if (!response.ok) {
        let detail = '';
        try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
        throw new Error(`Batch download failed (${response.status})${detail}`);
      }
      const blob = await response.blob();
      const disposition = response.headers.get('content-disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `saga-gallery-${new Date().toISOString().slice(0, 10)}.zip`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return true;
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not download selected media.');
      return false;
    }
  };

  const bulkDelete = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item.persisted && isUuid(item.id));
    if (!candidates.length) return false;
    if (!window.confirm(`Permanently delete ${candidates.length} selected generation${candidates.length === 1 ? '' : 's'}? This removes originals, favorites, collection memberships, and retained source references.`)) return false;

    const outcomes = await Promise.all(candidates.map(async (item) => {
      try {
        const response = await fetch(`/api/generations?id=${encodeURIComponent(item.id)}`, { method: 'DELETE' });
        if (!response.ok) {
          let detail = '';
          try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
          throw new Error(`Delete failed (${response.status})${detail}`);
        }
        return { id: item.id, ok: true };
      } catch (error) {
        return { id: item.id, ok: false, error: error instanceof Error ? error.message : 'Delete failed' };
      }
    }));

    const succeededIds = new Set(outcomes.filter((outcome) => outcome.ok).map((outcome) => outcome.id));
    const failed = outcomes.filter((outcome) => !outcome.ok);
    const failedIds = failed.map((outcome) => outcome.id);

    if (succeededIds.size) {
      setSelectedMedia((current) => current && succeededIds.has(current.id) ? null : current);
      setGalleryItems((current) => current.filter((entry) => !succeededIds.has(entry.id)));
      setFavoriteItems((current) => current.filter((entry) => !succeededIds.has(entry.id)));
      setCollectionItems((current) => current.filter((entry) => !succeededIds.has(entry.id)));
      setItems((current) => current.filter((entry) => !succeededIds.has(entry.id)));
      setFavorites((current) => {
        const next = new Set(current);
        succeededIds.forEach((id) => next.delete(id));
        return next;
      });
      await loadCollections();
    }

    if (failed.length) {
      const firstError = failed[0]?.error ? ` First error: ${failed[0].error}` : '';
      window.alert(`Deleted ${succeededIds.size} of ${candidates.length} selected items. ${failed.length} failed and remain selected for retry.${firstError}`);
      return { failedIds, succeededIds: [...succeededIds] };
    }

    return { failedIds: [], succeededIds: [...succeededIds] };
  };

  const openMedia = (item) => setSelectedMedia(item);
  const renderCard = (item, history = false, inCollection = false) => (
    <MediaCard
      key={item.id}
      item={item}
      history={history}
      inCollection={inCollection}
      favorites={favorites}
      onToggleFavorite={toggleFavorite}
      onReuseSettings={reuseSettings}
      onEdit={editThis}
      onDownload={downloadItem}
      onOpen={openMedia}
      onAddToCollection={addToCollection}
      onRemoveFromCollection={removeFromCollection}
      onDelete={deleteGeneration}
    />
  );

  return (
    <div className="app-shell">
      <Sidebar
        section={section}
        mode={mode}
        mobileOpen={mobileNav}
        onCloseMobile={() => setMobileNav(false)}
        onSectionChange={setSection}
        onModeChange={setMode}
        onClearError={() => setError('')}
      />

      <main className="workspace">
        <MobileTopbar onOpenNavigation={() => setMobileNav(true)} onOpenSettings={() => setSettingsOpen(true)} />

        {section === 'Jobs' ? <JobsView jobs={jobs} filter={jobsFilter} loading={jobsLoading} error={jobsError} actionBusyId={jobActionBusy} onFilterChange={setJobsFilter} onRefresh={() => loadJobs({ filter: jobsFilter })} onJobAction={runJobAction} />
          : section === 'Gallery' ? <GalleryView items={galleryItems} kind={galleryKind} model={galleryModel} models={galleryModels} page={galleryPage} loading={galleryLoading} appending={galleryAppending} error={galleryError} onKindChange={setGalleryKind} onModelChange={setGalleryModel} onRefresh={() => loadGallery({ append: false })} onLoadMore={() => loadGallery({ append: true })} renderCard={renderCard} onBulkFavorite={bulkFavorite} onBulkAddToCollection={bulkAddToCollection} onBulkDownload={bulkDownload} onBulkDelete={bulkDelete} />
          : section === 'Favorites' ? <FavoritesView items={favoriteItems} loading={libraryLoading} error={libraryError} onRefresh={loadFavorites} renderCard={renderCard} />
          : section === 'Collections' ? <CollectionsView collections={collections} selectedCollection={selectedCollection} items={collectionItems} loading={libraryLoading} error={libraryError} onCreate={createCollection} onBack={() => { setSelectedCollection(null); setCollectionItems([]); }} onOpen={loadCollectionItems} onRename={renameCollection} onDelete={deleteCollection} renderCard={renderCard} />
          : section === 'Models' ? <ModelsView />
          : section === 'Workflows' ? <WorkflowsView />
          : section === 'Settings' ? <SettingsView onOpenGenerationSettings={() => { setSection('Create'); setSettingsOpen(true); }} />
          : <CreateWorkspace
              mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else if (nextMode === 'Video') { setWorkflowId('video-planned'); setModelId('saga-video-auto'); } else if (nextMode === 'Image') { setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}
              prompt={prompt} setPrompt={setPrompt} references={references} onAddReferences={addReferences} onRemoveReference={removeReference}
              error={error} jobStatus={jobStatus} workerStatus={workerStatus} activeJob={activeJob} cancelBusy={cancelBusy} busy={busy} onGenerate={generate} onViewJob={viewActiveJob} onCancelJob={cancelActiveJob} items={visibleItems} renderCard={renderCard}
              aspect={aspect} setAspect={setAspect} imageResolution={imageResolution} setImageResolution={setImageResolution}
              outputs={outputs} setOutputs={setOutputs} advanced={advanced} setAdvanced={setAdvanced}
              seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg}
              workflowId={workflowId} setWorkflowId={setWorkflowId} modelId={modelId} setModelId={setModelId}
              settingsOpen={settingsOpen} setSettingsOpen={setSettingsOpen} autoEditInfo={autoEditInfo}
            />}
      </main>

      <MediaModal item={selectedMedia} onClose={() => setSelectedMedia(null)} />
    </div>
  );
}
