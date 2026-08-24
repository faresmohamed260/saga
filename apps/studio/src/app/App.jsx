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
import useMediaActions from '../hooks/useMediaActions.js';

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
  const mediaActions = useMediaActions({
    section, setSection, setMode, setPrompt, setSeed, setSteps, setCfg, setWorkflowId, setModelId,
    references, setReferences, setError, setItems, selectedMedia, setSelectedMedia,
    favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems,
    collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems,
    setLibraryError, loadGallery, loadFavorites, loadCollections, loadCollectionItems,
  });
  const { toggleFavorite, createCollection, renameCollection, deleteCollection, addToCollection, removeFromCollection, reuseSettings, editThis, downloadItem, deleteGeneration, bulkFavorite, bulkAddToCollection, bulkDownload, bulkDelete } = mediaActions;

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
