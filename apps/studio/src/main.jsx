import React, { useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  WandSparkles, History, Heart, Folder, Box, Workflow, Settings, Image as ImageIcon,
  Video, Crop, Grid2X2, Plus, X, SlidersHorizontal, Sparkles, RefreshCcw, Pencil,
  ArrowUpRight, MoreHorizontal, ChevronDown, RotateCcw, Dice5, Palette, ImagePlus,
  Menu, ChevronLeft, Maximize2
} from 'lucide-react';
import './styles.css';

const FLUX2_API_URL = (import.meta.env.VITE_FLUX2_KLEIN_API_URL || 'https://faresmohamed260--saga-flux2-klein-gateway-web.modal.run').replace(/\/$/, '');

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

async function persistGeneratedImage(blob, { model, resolution }) {
  try {
    const response = await fetch('/api/media', {
      method: 'POST',
      headers: {
        'Content-Type': blob.type || 'image/png',
        'X-Saga-Model': model,
        'X-Saga-Resolution': resolution,
      },
      body: blob,
    });
    if (!response.ok) return null;
    const payload = await response.json();
    return payload?.url || null;
  } catch {
    return null;
  }
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
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const visibleItems = useMemo(() => items.slice(0, outputs), [items, outputs]);
  const isEdit = mode === 'Edit';
  const activeEditQuality = editQualityOptions.find((option) => option.value === editMegapixels) || editQualityOptions[2];

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

    const form = new FormData();
    form.append('image_file', sourceFile, sourceFile.name);
    form.append('prompt', prompt.trim());
    form.append('negative_prompt', '');
    form.append('seed', String(Number(seed) || 42));
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
    const persistedUrl = await persistGeneratedImage(blob, { model, resolution: activeEditQuality.detail });
    const url = persistedUrl || URL.createObjectURL(blob);
    const item = {
      id: `flux-${Date.now()}`,
      title: prompt.trim(),
      url,
      generated: true,
      model,
      resolution: activeEditQuality.detail,
      persisted: Boolean(persistedUrl),
    };
    setItems((current) => [item, ...current]);
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

        <section className="gallery-grid">
          {visibleItems.map((item) => <article className="media-card" key={item.id}>
            <div className="media-frame" style={{backgroundImage:`url(${item.url})`}}><div className="size-badge"><Sparkles size={12}/>{item.generated?`${item.resolution || 'FLUX.2'} · Klein 9B`:'1024 × 1024'}</div><div className="media-hover"><button><Maximize2 size={18}/></button></div></div>
            <div className="card-actions"><button className={favorites.has(item.id)?'favorite active':'favorite'} onClick={()=>toggleFavorite(item.id)}><Heart size={20} fill={favorites.has(item.id)?'currentColor':'none'}/></button><button onClick={generate}><RefreshCcw size={19}/></button><button onClick={()=>{setMode('Edit'); setPrompt('');}}><Pencil size={19}/></button><button><ArrowUpRight size={20}/></button><button><MoreHorizontal size={20}/></button></div>
          </article>)}
        </section>
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
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
