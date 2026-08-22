import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  WandSparkles, History, Heart, Folder, Box, Workflow, Settings, Image as ImageIcon,
  Video, Crop, Grid2X2, Plus, X, SlidersHorizontal, Sparkles, RefreshCcw, Pencil,
  ArrowUpRight, MoreHorizontal, ChevronDown, RotateCcw, Dice5, Palette, ImagePlus,
  Menu, ChevronLeft, Maximize2, LoaderCircle
} from 'lucide-react';
import './styles.css';

const FLUX2_API_URL = (import.meta.env.VITE_FLUX2_KLEIN_API_URL || 'https://faresmohamed260--saga-flux2-klein-gateway-web.modal.run').replace(/\/$/, '');
const HISTORY_PAGE_SIZE = 24;

const samples = [
  { id: 1, title: 'Forest refuge', url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=85' },
  { id: 2, title: 'Orbital horizon', url: 'https://images.unsplash.com/photo-1446776877081-d282a0f896e2?auto=format&fit=crop&w=1200&q=85' },
  { id: 3, title: 'Neon portrait', url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1200&q=85' },
  { id: 4, title: 'Future city', url: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1200&q=85' },
];

const navPrimary = [[WandSparkles, 'Create'], [History, 'History'], [Heart, 'Favorites'], [Folder, 'Collections']];
const navSecondary = [[Box, 'Models'], [Workflow, 'Workflows']];
const editQualityOptions = [
  { value: '0.25', label: 'Draft', detail: '0.25 MP' },
  { value: '0.5', label: 'Balanced', detail: '0.5 MP' },
  { value: '1.0', label: 'Quality', detail: '1.0 MP' },
];

function encodeHeader(value) {
  return encodeURIComponent(String(value ?? ''));
}

async function persistGeneratedImage(blob, { model, resolution, prompt, negativePrompt = '', seed }) {
  try {
    const response = await fetch('/api/media', {
      method: 'POST',
      headers: {
        'Content-Type': blob.type || 'image/png',
        'X-Saga-Model': encodeHeader(model),
        'X-Saga-Resolution': encodeHeader(resolution),
        'X-Saga-Prompt': encodeHeader(prompt),
        'X-Saga-Negative-Prompt': encodeHeader(negativePrompt),
        'X-Saga-Seed': String(seed ?? ''),
      },
      body: blob,
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
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

function NavItem({ icon: Icon, label, active, onClick }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

function App() {
  const [section, setSection] = useState('Create');
  const [mode, setMode] = useState('Image');
  const [prompt, setPrompt] = useState('');
  const [aspect, setAspect] = useState('1:1');
  const [outputs, setOutputs] = useState(4);
  const [advanced, setAdvanced] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [seed, setSeed] = useState('42');
  const [editMegapixels, setEditMegapixels] = useState('1.0');
  const [favorites, setFavorites] = useState(new Set());
  const [items, setItems] = useState(samples);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyAppending, setHistoryAppending] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyKind, setHistoryKind] = useState('all');
  const [historyModel, setHistoryModel] = useState('all');
  const [historyModels, setHistoryModels] = useState([]);
  const [historyPage, setHistoryPage] = useState({ nextOffset: null, hasMore: false });
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const visibleItems = useMemo(() => items.slice(0, outputs), [items, outputs]);
  const isEdit = mode === 'Edit';
  const activeEditQuality = editQualityOptions.find((option) => option.value === editMegapixels) || editQualityOptions[2];

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
      setHistoryPage({
        nextOffset: payload?.page?.nextOffset ?? null,
        hasMore: Boolean(payload?.page?.hasMore),
      });
      if (Array.isArray(payload?.facets?.models)) setHistoryModels(payload.facets.models);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Unable to load generation history.');
    } finally {
      append ? setHistoryAppending(false) : setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (section === 'History') loadHistory({ append: false, kind: historyKind, model: historyModel });
  }, [section, historyKind, historyModel]);

  const chooseSource = () => fileInputRef.current?.click();

  const onSourceChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.');
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError('Reference image must be 25 MB or smaller.');
      return;
    }
    if (sourcePreview) URL.revokeObjectURL(sourcePreview);
    setSourceFile(file);
    setSourcePreview(URL.createObjectURL(file));
    setError('');
    setMode('Edit');
  };

  const clearSource = () => {
    if (sourcePreview) URL.revokeObjectURL(sourcePreview);
    setSourcePreview('');
    setSourceFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const runFluxEdit = async () => {
    if (!sourceFile) throw new Error('Add a source image before running an edit.');
    if (!prompt.trim()) throw new Error('Describe the edit you want to make.');

    const effectiveSeed = Number(seed) || 42;
    const form = new FormData();
    form.append('image_file', sourceFile, sourceFile.name);
    form.append('prompt', prompt.trim());
    form.append('negative_prompt', '');
    form.append('seed', String(effectiveSeed));
    form.append('steps', '4');
    form.append('cfg', '1.0');
    form.append('megapixels', editMegapixels);

    const response = await fetch(`${FLUX2_API_URL}/edit`, { method: 'POST', body: form });
    if (!response.ok) {
      let detail = '';
      try {
        const body = await response.json();
        detail = body?.detail ? `: ${body.detail}` : '';
      } catch {
        detail = '';
      }
      throw new Error(`FLUX.2 Klein request failed (${response.status})${detail}`);
    }

    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) throw new Error('The generation backend returned an unexpected response.');
    const model = 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
    const persisted = await persistGeneratedImage(blob, {
      model,
      resolution: activeEditQuality.detail,
      prompt: prompt.trim(),
      negativePrompt: '',
      seed: effectiveSeed,
    });
    const url = persisted?.url || URL.createObjectURL(blob);
    const item = {
      id: persisted?.generationId || `flux-${Date.now()}`,
      title: prompt.trim(),
      url: persisted?.thumbnailUrl || url,
      originalUrl: url,
      generated: true,
      model,
      resolution: activeEditQuality.detail,
      seed: effectiveSeed,
      persisted: Boolean(persisted?.historyPersisted),
    };
    setItems((current) => [item, ...current]);
    if (persisted?.historyPersisted && section === 'History') loadHistory({ append: false });
  };

  const generate = async () => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (isEdit) {
        await runFluxEdit();
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 700));
        setItems((prev) => [prev[1], prev[3], prev[0], prev[2]]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed.');
    } finally {
      setBusy(false);
    }
  };

  const toggleFavorite = (id) => {
    setFavorites((current) => {
      const next = new Set(current);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const openMedia = (item) => setSelectedMedia(item);

  const renderCard = (item, history = false) => (
    <article className={`media-card ${history ? 'history-card' : ''}`} key={item.id}>
      <div
        className={`media-frame ${!item.url ? 'media-frame-empty' : ''}`}
        style={item.url ? { backgroundImage: `url(${item.url})` } : undefined}
        onClick={() => openMedia(item)}
        role="button"
        tabIndex={0}
      >
        {!item.url && <div className="media-placeholder"><Video size={28}/><span>Video preview</span></div>}
        <div className="size-badge">{item.kind === 'video' ? <Video size={12}/> : <Sparkles size={12}/>} {item.generated ? `${item.resolution || (item.kind === 'video' ? 'Video' : 'Image')}${history ? '' : ' · Klein 9B'}` : '1024 × 1024'}</div>
        <div className="media-hover"><button aria-label="Open full media"><Maximize2 size={18}/></button></div>
      </div>
      {history && <div className="history-copy">
        <div className="history-prompt">{item.title}</div>
        <div className="history-meta"><span>{item.model || 'Unknown model'}</span>{item.seed != null && <span>Seed {item.seed}</span>}</div>
      </div>}
      <div className="card-actions">
        <button className={favorites.has(item.id) ? 'favorite active' : 'favorite'} onClick={() => toggleFavorite(item.id)}><Heart size={20} fill={favorites.has(item.id) ? 'currentColor' : 'none'}/></button>
        <button onClick={() => { setPrompt(item.title || ''); setMode('Edit'); setSection('Create'); }}><RefreshCcw size={19}/></button>
        <button onClick={() => { setPrompt(item.title || ''); setMode('Edit'); setSection('Create'); }}><Pencil size={19}/></button>
        <button onClick={() => openMedia(item)}><ArrowUpRight size={20}/></button>
        <button><MoreHorizontal size={20}/></button>
      </div>
    </article>
  );

  return (
    <div className="app-shell">
      <input ref={fileInputRef} type="file" accept="image/*" onChange={onSourceChange} style={{display:'none'}} />

      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div>
          <button className="mobile-close" onClick={() => setMobileNav(false)}><ChevronLeft size={19}/></button>
        </div>
        <nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => {setSection(label); setMobileNav(false);}} />)}</nav>
        <div className="nav-divider" />
        <nav className="nav-group">{navSecondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => {setSection(label); setMobileNav(false);}} />)}</nav>
        <div className="nav-divider" />
        <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => setSection('Settings')} />
        <div className="profile-card"><div className="avatar-orb"/><div className="profile-copy"><div className="profile-name">Saga Creator <span className="pro-badge">Studio</span></div><div className="profile-email">FLUX.2 online</div></div><ChevronDown size={16}/></div>
      </aside>

      <main className="workspace">
        <div className="mobile-topbar"><button className="icon-button" onClick={() => setMobileNav(true)}><Menu size={20}/></button><div className="mobile-brand">SAGA Studio</div><button className="icon-button" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={20}/></button></div>

        {section === 'History' ? (
          <section className="history-view">
            <div className="history-header">
              <div><div className="history-eyebrow">Library</div><h1>Generation history</h1><p>Thumbnail-first previews. Originals load only when you open an item.</p></div>
              <button className="secondary-button" onClick={() => loadHistory({ append: false })} disabled={historyLoading}>{historyLoading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>
            </div>

            <div className="history-toolbar">
              <div className="history-kind-tabs" role="group" aria-label="Media type filter">
                {[['all','All'],['image','Images'],['video','Videos']].map(([value,label]) => <button key={value} className={historyKind === value ? 'selected' : ''} onClick={() => setHistoryKind(value)}>{label}</button>)}
              </div>
              <label className="history-model-filter">
                <span>Model</span>
                <select value={historyModel} onChange={(event) => setHistoryModel(event.target.value)}>
                  <option value="all">All models</option>
                  {historyModels.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}
                </select>
              </label>
            </div>

            {historyError && <div className="history-state error">{historyError}</div>}
            {historyLoading && historyItems.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading history…</div>
              : historyItems.length === 0 ? <div className="history-state">No generations match these filters.</div>
              : <>
                <section className="gallery-grid history-grid">{historyItems.map((item) => renderCard(item, true))}</section>
                {historyPage.hasMore && <div className="history-load-more"><button className="secondary-button" onClick={() => loadHistory({ append: true })} disabled={historyAppending}>{historyAppending ? <LoaderCircle className="spin" size={18}/> : <Plus size={18}/>} {historyAppending ? 'Loading…' : 'Load more'}</button></div>}
              </>}
          </section>
        ) : (
          <>
            <div className="mode-tabs">
              {[[ImageIcon,'Image'],[Video,'Video'],[Crop,'Edit'],[Grid2X2,'More']].map(([Icon,label]) => <button className={`mode-tab ${mode===label?'selected':''}`} key={label} onClick={() => {setMode(label); setError('');}}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>)}
            </div>

            <section className="composer-panel">
              <div className="chip-row">
                {isEdit ? (
                  sourcePreview ? <div className="ref-chip"><div className="chip-thumb" style={{backgroundImage:`url(${sourcePreview})`}}/><div><strong>Source image</strong><span>{sourceFile?.name}</span></div><button onClick={clearSource} style={{background:'transparent',border:0,color:'inherit',cursor:'pointer'}}><X size={16}/></button></div>
                  : <button className="add-chip" onClick={chooseSource} title="Add source image"><Plus size={22}/></button>
                ) : <>
                  <div className="ref-chip"><div className="chip-thumb forest"/><div><strong>Reference</strong><span>forest_mood.png</span></div><X size={16}/></div>
                  <div className="ref-chip"><div className="chip-thumb style"/><div><strong>Style</strong><span>Cinematic Teal & Orange</span></div><X size={16}/></div>
                  <button className="add-chip"><Plus size={22}/></button>
                </>}
              </div>
              <textarea value={prompt} onChange={(e)=>setPrompt(e.target.value)} placeholder={mode==='Video'?'Describe the motion, scene, and camera movement...':isEdit?'Describe what you want FLUX.2 Klein to change...':'Describe what you want to create...'} maxLength={2000}/>
              <div className="composer-footer"><span>{prompt.length} / 2000</span><Sparkles size={18}/></div>
            </section>

            {error && <div style={{marginTop:12,padding:'12px 14px',border:'1px solid rgba(255,100,120,.35)',borderRadius:10,background:'rgba(120,20,35,.14)',color:'#ffb4c0',fontSize:13}}>{error}</div>}
            {isEdit && <div style={{marginTop:12,color:'#8f98a8',fontSize:12}}>Live backend · FLUX.2 Klein 9B · modal-01 · A10 · 4 steps · {activeEditQuality.detail}</div>}

            <div className="action-row">
              <div className="attach-actions"><button className="secondary-button" onClick={chooseSource}><ImagePlus size={18}/>{isEdit ? (sourceFile?'Replace source':'Source image') : 'Reference'}</button><button className="secondary-button"><Palette size={18}/> Style</button></div>
              <div className="generate-actions"><button className="square-button" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={19}/></button><button className={`generate-button ${busy?'busy':''}`} onClick={generate} disabled={busy}><Sparkles size={18}/>{busy ? (isEdit?'Editing…':'Generating…') : (isEdit?'Edit image':'Generate')}</button></div>
            </div>

            <section className="gallery-grid">{visibleItems.map((item) => renderCard(item, false))}</section>
          </>
        )}
      </main>

      <aside className={`settings-panel ${settingsOpen?'open':''}`}>
        <div className="settings-header"><h2>Settings</h2><button className="square-button" onClick={() => setSettingsOpen(false)}><SlidersHorizontal size={18}/></button></div>
        <label className="field-label">Model</label>
        <button className="select-box"><span><Sparkles size={16}/>{isEdit?'FLUX.2 Klein 9B':'SAGA Image'}</span><span className="auto-pill">{isEdit?'LIVE':'AUTO'}</span><ChevronDown size={16}/></button>
        <label className="field-label">Aspect Ratio</label>
        <div className="aspect-grid">{['1:1','16:9','9:16','4:3'].map((ratio)=><button key={ratio} onClick={()=>setAspect(ratio)} className={aspect===ratio?'selected':''}><span className={`ratio-icon ratio-${ratio.replace(':','-')}`}/>{ratio}</button>)}</div>
        <label className="field-label">Resolution</label>
        {isEdit ? <div className="output-grid">{editQualityOptions.map((option)=><button key={option.value} onClick={()=>setEditMegapixels(option.value)} className={editMegapixels===option.value?'selected':''} title={option.detail}>{option.label}</button>)}</div> : <button className="select-box"><span>{`1024 × 1024 (${aspect})`}</span><ChevronDown size={16}/></button>}
        {isEdit && <div style={{marginTop:8,color:'#7f8999',fontSize:11}}>Draft 0.25 MP · Balanced 0.5 MP · Quality 1.0 MP</div>}
        <label className="field-label">Outputs</label>
        <div className="output-grid">{[1,2,4].map((count)=><button key={count} onClick={()=>setOutputs(count)} className={outputs===count?'selected':''}>{count}</button>)}</div>
        <div className="settings-divider"/>
        <button className="advanced-toggle" onClick={()=>setAdvanced(!advanced)}><span>Advanced</span><ChevronDown className={advanced?'rotated':''} size={17}/></button>
        {advanced && <div className="advanced-fields">
          <div className="inline-field"><label>Seed</label><div className="input-box"><input value={seed} onChange={(e)=>setSeed(e.target.value)}/><button onClick={()=>setSeed(String(Math.floor(Math.random()*999999999)))}><Dice5 size={17}/></button></div></div>
          <div className="inline-field"><label>Steps</label><button className="compact-select">{isEdit?'4':'30'} <ChevronDown size={15}/></button></div>
          <div className="inline-field"><label>CFG</label><button className="compact-select">{isEdit?'1.0':'7.0'} <ChevronDown size={15}/></button></div>
          <div className="inline-field"><label>Workflow</label><button className="compact-select">{isEdit?'Klein Edit':'Default'} <ChevronDown size={15}/></button></div>
        </div>}
        <button className="reset-button" onClick={()=>{setAspect('1:1');setOutputs(4);setSeed('42');setEditMegapixels('1.0');}}><RotateCcw size={18}/> Reset to Defaults</button>
      </aside>
      {settingsOpen && <div className="panel-scrim" onClick={()=>setSettingsOpen(false)}/>} 

      {selectedMedia && <div className="media-modal" onClick={() => setSelectedMedia(null)}>
        <div className="media-modal-card" onClick={(event) => event.stopPropagation()}>
          <button className="media-modal-close" onClick={() => setSelectedMedia(null)}><X size={20}/></button>
          {selectedMedia.kind === 'video'
            ? <video src={selectedMedia.originalUrl} poster={selectedMedia.thumbnailUrl || undefined} controls playsInline />
            : <img src={selectedMedia.originalUrl || selectedMedia.url} alt={selectedMedia.title || 'Generated image'} />}
          <div className="media-modal-copy"><strong>{selectedMedia.title || 'Generated media'}</strong><span>{selectedMedia.model || ''}{selectedMedia.seed != null ? ` · Seed ${selectedMedia.seed}` : ''}</span></div>
        </div>
      </div>}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
