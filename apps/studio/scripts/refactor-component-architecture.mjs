import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const srcDir = path.join(root, 'apps/studio/src');
const mainPath = path.join(srcDir, 'main.jsx');
const source = fs.readFileSync(mainPath, 'utf8');

const write = (relativePath, content) => {
  const target = path.join(srcDir, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${content.trim()}\n`, 'utf8');
};

write('components/LibraryHeader.jsx', `
import React from 'react';

export default function LibraryHeader({ eyebrow, title, description, action = null }) {
  return (
    <div className="history-header">
      <div>
        <div className="history-eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
`);

write('components/MediaCard.jsx', `
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
    <article className={\`media-card \${history ? 'history-card' : ''}\`}>
      <div
        className={\`media-frame \${!item.url ? 'media-frame-empty' : ''}\`}
        style={item.url && item.kind !== 'video' ? { backgroundImage: \`url(\${item.url})\` } : undefined}
        onClick={() => onOpen(item)}
        role="button"
        tabIndex={0}
      >
        {item.kind === 'video' && item.url ? <video className="media-video-preview" src={item.originalUrl || item.url} muted playsInline preload="metadata" /> : null}
        {!item.url && <div className="media-placeholder"><Video size={28}/><span>Video preview</span></div>}
        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? \`\${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}\${history ? '' : ' · Klein 9B'}\` : '1024 × 1024'}</div>
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
`);

write('components/MediaModal.jsx', `
import React from 'react';
import { X } from 'lucide-react';

export default function MediaModal({ item, onClose }) {
  if (!item) return null;
  return (
    <div className="media-modal" onClick={onClose}>
      <div className="media-modal-card" onClick={(event) => event.stopPropagation()}>
        <button className="media-modal-close" onClick={onClose}><X size={20}/></button>
        {item.kind === 'video' ? <video src={item.originalUrl} poster={item.thumbnailUrl || undefined} controls playsInline /> : <img src={item.originalUrl || item.url} alt={item.title || 'Generated image'} />}
        <div className="media-modal-copy"><strong>{item.title || 'Generated media'}</strong><span>{item.model || ''}{item.seed != null ? \` · Seed \${item.seed}\` : ''}</span></div>
      </div>
    </div>
  );
}
`);

write('components/MobileTopbar.jsx', `
import React from 'react';
import { Menu, SlidersHorizontal } from 'lucide-react';

export default function MobileTopbar({ onOpenNavigation, onOpenSettings }) {
  return (
    <div className="mobile-topbar">
      <button className="icon-button" onClick={onOpenNavigation}><Menu size={20}/></button>
      <div className="mobile-brand">SAGA Studio</div>
      <button className="icon-button" onClick={onOpenSettings}><SlidersHorizontal size={20}/></button>
    </div>
  );
}
`);

write('components/Sidebar.jsx', `
import React from 'react';
import { Box, ChevronDown, ChevronLeft, Folder, Heart, History, LoaderCircle, Settings, Sparkles, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [History, 'History'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick }) {
  return <button className={\`nav-item \${active ? 'active' : ''}\`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, mode, mobileOpen, onCloseMobile, onSectionChange, onModeChange, onClearError }) {
  const chooseSection = (label) => {
    onSectionChange(label);
    if (label === 'Create' && mode === 'More') onModeChange('Image');
    onCloseMobile();
  };

  return (
    <aside className={\`sidebar \${mobileOpen ? 'open' : ''}\`}>
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
`);

write('features/jobs/JobsView.jsx', `
import React from 'react';
import { LoaderCircle, RefreshCcw, RotateCcw, X } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

function formatJobTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export default function JobsView({ jobs, filter, loading, error, actionBusyId, onFilterChange, onRefresh, onJobAction }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Execution" title="Jobs & queue" description="Live generation lifecycle. This page polls while open; completed media stays in History." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Job status filter">{[['active', 'Active'], ['queued', 'Queued'], ['running', 'Running'], ['failed', 'Failed'], ['completed', 'Completed'], ['all', 'Recent']].map(([value, label]) => <button key={value} className={filter === value ? 'selected' : ''} onClick={() => onFilterChange(value)}>{label}</button>)}</div></div>
      {error && <div className="history-state error">{error}</div>}
      {loading && jobs.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading jobs…</div> : jobs.length === 0 ? <div className="history-state">No lifecycle jobs match this filter.</div> : <div style={{ display: 'grid', gap: 12 }}>{jobs.map((job) => {
        const cancelled = Boolean(job.metadata?.cancelled);
        const actionBusy = actionBusyId === job.id;
        return <article key={job.id} style={{ border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, background: 'rgba(255,255,255,.025)', padding: '16px 18px', display: 'grid', gap: 10 }}><div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}><div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}><span style={{ textTransform: 'uppercase', fontSize: 11, fontWeight: 700, letterSpacing: '.08em', padding: '5px 8px', borderRadius: 999, border: '1px solid rgba(255,255,255,.14)', opacity: job.status === 'failed' ? 1 : .8 }}>{cancelled ? 'cancelled' : job.status}</span><strong style={{ fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.prompt || 'Untitled job'}</strong></div><span style={{ fontSize: 12, color: '#7f8999' }}>{formatJobTime(job.created_at)}</span></div><div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, color: '#8f98a8' }}><span>{job.kind || 'image'} · {job.mode || 'generation'}</span><span>{job.model || 'Unknown model'}</span><span>{job.provider || 'provider n/a'}</span>{job.seed != null && <span>Seed {job.seed}</span>}{job.resolution && <span>{job.resolution}</span>}</div><div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 11, color: '#687284' }}><span>Queued {formatJobTime(job.created_at)}</span><span>Started {formatJobTime(job.started_at)}</span><span>Finished {formatJobTime(job.completed_at)}</span></div>{job.error_message && <div style={{ padding: '10px 12px', borderRadius: 9, background: 'rgba(120,20,35,.14)', border: '1px solid rgba(255,100,120,.25)', color: '#ffb4c0', fontSize: 12 }}>{job.error_message}</div>}<div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>{['queued', 'running'].includes(job.status) && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'cancel')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <X size={16}/>} Cancel</button>}{job.status === 'failed' && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'retry')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <RotateCcw size={16}/>} Retry</button>}</div></article>;
      })}</div>}
    </section>
  );
}
`);

write('features/library/HistoryView.jsx', `
import React from 'react';
import { LoaderCircle, Plus, RefreshCcw } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function HistoryView({ items, kind, model, models, page, loading, appending, error, onKindChange, onModelChange, onRefresh, onLoadMore, renderCard }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title="Generation history" description="Thumbnail-first previews. Originals load only when you open an item." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Media type filter">{[['all', 'All'], ['image', 'Images'], ['video', 'Videos']].map(([value, label]) => <button key={value} className={kind === value ? 'selected' : ''} onClick={() => onKindChange(value)}>{label}</button>)}</div><label className="history-model-filter"><span>Model</span><select value={model} onChange={(event) => onModelChange(event.target.value)}><option value="all">All models</option>{models.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}</select></label></div>
      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading history…</div> : items.length === 0 ? <div className="history-state">No generations match these filters.</div> : <><section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true))}</section>{page.hasMore && <div className="history-load-more"><button className="secondary-button" onClick={onLoadMore} disabled={appending}>{appending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {appending ? 'Loading…' : 'Load more'}</button></div>}</>}
    </section>
  );
}
`);

write('features/library/FavoritesView.jsx', `
import React from 'react';
import { LoaderCircle, RefreshCcw } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function FavoritesView({ items, loading, error, onRefresh, renderCard }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title="Favorites" description="Saved generations persist across refreshes and devices using the Studio database." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      {error && <div className="history-state error">{error}</div>}
      {loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading favorites…</div> : items.length === 0 ? <div className="history-state">No favorites yet. Tap the heart on any persisted generation.</div> : <section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true))}</section>}
    </section>
  );
}
`);

write('features/library/CollectionsView.jsx', `
import React from 'react';
import { ChevronLeft, Folder, LoaderCircle, Pencil, Plus, Trash2 } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function CollectionsView({ collections, selectedCollection, items, loading, error, onCreate, onBack, onOpen, onRename, onDelete, renderCard }) {
  const action = selectedCollection
    ? <button className="secondary-button" onClick={onBack}><ChevronLeft size={18}/> All collections</button>
    : <button className="secondary-button" onClick={onCreate}><Plus size={18}/> New collection</button>;
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Library" title={selectedCollection ? selectedCollection.name : 'Collections'} description={selectedCollection ? \`\${items.length} saved item\${items.length === 1 ? '' : 's'}\` : 'Organize persisted generations into reusable groups.'} action={action} />
      {error && <div className="history-state error">{error}</div>}
      {selectedCollection ? (loading && items.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collection…</div> : items.length === 0 ? <div className="history-state">This collection is empty. Add items from History or Favorites.</div> : <section className="gallery-grid history-grid">{items.map((item) => renderCard(item, true, true))}</section>) : (loading && collections.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading collections…</div> : collections.length === 0 ? <div className="history-state">No collections yet.</div> : <div className="collection-grid">{collections.map((collection) => <article className="collection-card" key={collection.id}><button className="collection-cover" style={collection.coverUrl ? { backgroundImage: \`url(\${collection.coverUrl})\` } : undefined} onClick={() => onOpen(collection)}>{!collection.coverUrl && <Folder size={34}/>}</button><div className="collection-copy"><button className="collection-title" onClick={() => onOpen(collection)}>{collection.name}</button><span>{collection.itemCount || 0} items</span></div><div className="collection-actions"><button onClick={() => onRename(collection)}><Pencil size={16}/></button><button onClick={() => onDelete(collection)}><Trash2 size={16}/></button></div></article>)}</div>)}
    </section>
  );
}
`);

write('features/catalog/ModelsView.jsx', `
import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function ModelsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Models" description="Models exposed to the generation registry. Only live backends are selectable in production." />
      <div className="collection-grid"><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>FLUX.2 Klein 9B · DarkBeast V2 BFS</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Image editing with automatic output sizing and multi-reference conditioning.</p></article><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">PLANNED</div><h3 style={{ margin: '8px 0' }}>SAGA Image</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Original image generation UI presets are ready; the production workflow will be connected separately.</p></article></div>
    </section>
  );
}
`);

write('features/catalog/WorkflowsView.jsx', `
import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function WorkflowsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Workflows" description="Registered generation paths and their current capabilities." />
      <div className="collection-grid"><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>Klein Multi-Reference Edit</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Direct R2 inputs → Studio orchestration → Modal / ComfyUI → persisted R2 result and thumbnail.</p></article></div>
    </section>
  );
}
`);

write('features/settings/SettingsView.jsx', `
import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Settings" description="Generation settings live beside the composer so they stay contextual to the selected workflow." action={<button className="secondary-button" onClick={onOpenGenerationSettings}><SlidersHorizontal size={18}/> Open generation settings</button>} />
      <div className="history-state">Use the settings panel to control model, aspect ratio, resolution, seed, steps, CFG, and workflow.</div>
    </section>
  );
}
`);

write('features/create/CreateWorkspace.jsx', `
export { default } from '../../create-controls.jsx';
`);

const importStart = source.indexOf("import React, { useMemo, useState } from 'react';");
const constantsStart = source.indexOf('const HISTORY_PAGE_SIZE');
if (importStart !== 0 || constantsStart < 0) throw new Error('Unexpected Studio main import layout');

const appImports = `import React, { useMemo, useState } from 'react';
import { runImageEdit, runVideoGeneration } from '../generation-client.js';
import CreateWorkspace from '../features/create/CreateWorkspace.jsx';
import Sidebar from '../components/Sidebar.jsx';
import MobileTopbar from '../components/MobileTopbar.jsx';
import MediaCard from '../components/MediaCard.jsx';
import MediaModal from '../components/MediaModal.jsx';
import JobsView from '../features/jobs/JobsView.jsx';
import HistoryView from '../features/library/HistoryView.jsx';
import FavoritesView from '../features/library/FavoritesView.jsx';
import CollectionsView from '../features/library/CollectionsView.jsx';
import ModelsView from '../features/catalog/ModelsView.jsx';
import WorkflowsView from '../features/catalog/WorkflowsView.jsx';
import SettingsView from '../features/settings/SettingsView.jsx';

`;

let appSource = appImports + source.slice(constantsStart);
appSource = appSource.replace('function App() {', 'export default function App() {');

const renderCardStart = appSource.indexOf('  const renderCard =');
const renderHeaderStart = appSource.indexOf('  const renderLibraryHeader =');
if (renderCardStart < 0 || renderHeaderStart < 0) throw new Error('Could not locate media render helpers');
const returnStart = appSource.indexOf('  return (\n    <div className="app-shell">', renderHeaderStart);
if (returnStart < 0) throw new Error('Could not locate Studio App return block');

const renderAdapter = `  const renderCard = (item, history = false, inCollection = false) => (
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

`;
appSource = appSource.slice(0, renderCardStart) + renderAdapter + appSource.slice(returnStart);

const newReturn = `  return (
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
          : section === 'History' ? <HistoryView items={historyItems} kind={historyKind} model={historyModel} models={historyModels} page={historyPage} loading={historyLoading} appending={historyAppending} error={historyError} onKindChange={setHistoryKind} onModelChange={setHistoryModel} onRefresh={() => loadHistory({ append: false })} onLoadMore={() => loadHistory({ append: true })} renderCard={renderCard} />
          : section === 'Favorites' ? <FavoritesView items={favoriteItems} loading={libraryLoading} error={libraryError} onRefresh={loadFavorites} renderCard={renderCard} />
          : section === 'Collections' ? <CollectionsView collections={collections} selectedCollection={selectedCollection} items={collectionItems} loading={libraryLoading} error={libraryError} onCreate={createCollection} onBack={() => { setSelectedCollection(null); setCollectionItems([]); }} onOpen={loadCollectionItems} onRename={renameCollection} onDelete={deleteCollection} renderCard={renderCard} />
          : section === 'Models' ? <ModelsView />
          : section === 'Workflows' ? <WorkflowsView />
          : section === 'Settings' ? <SettingsView onOpenGenerationSettings={() => { setSection('Create'); setSettingsOpen(true); }} />
          : <CreateWorkspace
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

      <MediaModal item={selectedMedia} onClose={() => setSelectedMedia(null)} />
    </div>
  );
}
`;

appSource = appSource.slice(0, appSource.indexOf('  return (\n    <div className="app-shell">')) + newReturn;
write('app/App.jsx', appSource);

write('main.jsx', `
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App.jsx';
import './styles.css';
import './create-controls.css';

createRoot(document.getElementById('root')).render(<App />);
`);

console.log('Studio component architecture generated.');
