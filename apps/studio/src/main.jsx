import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  WandSparkles, History, Heart, Folder, Box, Workflow, Settings, Image as ImageIcon,
  Video, Crop, Grid2X2, Plus, X, SlidersHorizontal, Sparkles, RefreshCcw, Pencil,
  ArrowUpRight, MoreHorizontal, ChevronDown, RotateCcw, Dice5, Palette, ImagePlus,
  Menu, ChevronLeft, Play, Layers3, Upload, Download, Maximize2
} from 'lucide-react';
import './styles.css';

const samples = [
  {
    id: 1,
    title: 'Forest refuge',
    url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=85',
  },
  {
    id: 2,
    title: 'Orbital horizon',
    url: 'https://images.unsplash.com/photo-1446776877081-d282a0f896e2?auto=format&fit=crop&w=1200&q=85',
  },
  {
    id: 3,
    title: 'Neon portrait',
    url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1200&q=85',
  },
  {
    id: 4,
    title: 'Future city',
    url: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1200&q=85',
  },
];

const navPrimary = [
  [WandSparkles, 'Create'],
  [History, 'History'],
  [Heart, 'Favorites'],
  [Folder, 'Collections'],
];

const navSecondary = [
  [Box, 'Models'],
  [Workflow, 'Workflows'],
];

function NavItem({ icon: Icon, label, active, onClick }) {
  return (
    <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}>
      <Icon size={19} strokeWidth={1.8} />
      <span>{label}</span>
    </button>
  );
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
  const [seed, setSeed] = useState('123456789');
  const [favorites, setFavorites] = useState(new Set());
  const [items, setItems] = useState(samples);

  const visibleItems = useMemo(() => items.slice(0, outputs), [items, outputs]);

  const generate = () => {
    setBusy(true);
    window.setTimeout(() => {
      setItems((prev) => [prev[1], prev[3], prev[0], prev[2]]);
      setBusy(false);
    }, 900);
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
      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark">S</div>
          <div className="brand-text">SAGA <span>Studio</span></div>
          <button className="mobile-close" onClick={() => setMobileNav(false)}><ChevronLeft size={19}/></button>
        </div>

        <nav className="nav-group primary-nav">
          {navPrimary.map(([Icon, label]) => (
            <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => {setSection(label); setMobileNav(false);}} />
          ))}
        </nav>

        <div className="nav-divider" />
        <nav className="nav-group">
          {navSecondary.map(([Icon, label]) => (
            <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => {setSection(label); setMobileNav(false);}} />
          ))}
        </nav>
        <div className="nav-divider" />
        <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => setSection('Settings')} />

        <div className="profile-card">
          <div className="avatar-orb" />
          <div className="profile-copy">
            <div className="profile-name">Saga Creator <span className="pro-badge">Pro</span></div>
            <div className="profile-email">creator@saga.studio</div>
          </div>
          <ChevronDown size={16} />
        </div>
      </aside>

      <main className="workspace">
        <div className="mobile-topbar">
          <button className="icon-button" onClick={() => setMobileNav(true)}><Menu size={20}/></button>
          <div className="mobile-brand">SAGA Studio</div>
          <button className="icon-button" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={20}/></button>
        </div>

        <div className="mode-tabs">
          {[
            [ImageIcon, 'Image'], [Video, 'Video'], [Crop, 'Edit'], [Grid2X2, 'More']
          ].map(([Icon, label]) => (
            <button className={`mode-tab ${mode === label ? 'selected' : ''}`} key={label} onClick={() => setMode(label)}>
              <Icon size={19} strokeWidth={1.8}/><span>{label}</span>
            </button>
          ))}
        </div>

        <section className="composer-panel">
          <div className="chip-row">
            <div className="ref-chip">
              <div className="chip-thumb forest" />
              <div><strong>Reference</strong><span>forest_mood.png</span></div>
              <X size={16}/>
            </div>
            <div className="ref-chip">
              <div className="chip-thumb style" />
              <div><strong>Style</strong><span>Cinematic Teal & Orange</span></div>
              <X size={16}/>
            </div>
            <button className="add-chip"><Plus size={22}/></button>
          </div>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={mode === 'Video' ? 'Describe the motion, scene, and camera movement...' : mode === 'Edit' ? 'Describe what you want to change...' : 'Describe what you want to create...'}
            maxLength={2000}
          />
          <div className="composer-footer"><span>{prompt.length} / 2000</span><Sparkles size={18}/></div>
        </section>

        <div className="action-row">
          <div className="attach-actions">
            <button className="secondary-button"><ImagePlus size={18}/> Reference</button>
            <button className="secondary-button"><Palette size={18}/> Style</button>
          </div>
          <div className="generate-actions">
            <button className="square-button" onClick={() => setSettingsOpen(true)}><SlidersHorizontal size={19}/></button>
            <button className={`generate-button ${busy ? 'busy' : ''}`} onClick={generate} disabled={busy}>
              <Sparkles size={18}/>{busy ? 'Generating…' : 'Generate'}
            </button>
          </div>
        </div>

        <section className="gallery-grid">
          {visibleItems.map((item) => (
            <article className="media-card" key={item.id}>
              <div className="media-frame" style={{backgroundImage:`url(${item.url})`}}>
                <div className="size-badge"><Sparkles size={12}/> 1024 × 1024</div>
                <div className="media-hover"><button><Maximize2 size={18}/></button></div>
              </div>
              <div className="card-actions">
                <button className={favorites.has(item.id) ? 'favorite active' : 'favorite'} onClick={() => toggleFavorite(item.id)}><Heart size={20} fill={favorites.has(item.id) ? 'currentColor' : 'none'}/></button>
                <button onClick={generate}><RefreshCcw size={19}/></button>
                <button onClick={() => setMode('Edit')}><Pencil size={19}/></button>
                <button><ArrowUpRight size={20}/></button>
                <button><MoreHorizontal size={20}/></button>
              </div>
            </article>
          ))}
        </section>
      </main>

      <aside className={`settings-panel ${settingsOpen ? 'open' : ''}`}>
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="square-button" onClick={() => setSettingsOpen(false)}><SlidersHorizontal size={18}/></button>
        </div>

        <label className="field-label">Model</label>
        <button className="select-box"><span><Sparkles size={16}/> SAGA Image</span><span className="auto-pill">AUTO</span><ChevronDown size={16}/></button>

        <label className="field-label">Aspect Ratio</label>
        <div className="aspect-grid">
          {['1:1','16:9','9:16','4:3'].map((ratio) => (
            <button key={ratio} onClick={() => setAspect(ratio)} className={aspect===ratio?'selected':''}>
              <span className={`ratio-icon ratio-${ratio.replace(':','-')}`} />
              {ratio}
            </button>
          ))}
        </div>

        <label className="field-label">Resolution</label>
        <button className="select-box"><span>1024 × 1024 ({aspect})</span><ChevronDown size={16}/></button>

        <label className="field-label">Outputs</label>
        <div className="output-grid">
          {[1,2,4].map((count) => <button key={count} onClick={()=>setOutputs(count)} className={outputs===count?'selected':''}>{count}</button>)}
        </div>

        <div className="settings-divider"/>
        <button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}><span>Advanced</span><ChevronDown className={advanced?'rotated':''} size={17}/></button>

        {advanced && <div className="advanced-fields">
          <div className="inline-field"><label>Seed</label><div className="input-box"><input value={seed} onChange={(e)=>setSeed(e.target.value)}/><button onClick={()=>setSeed(String(Math.floor(Math.random()*999999999)))}><Dice5 size={17}/></button></div></div>
          <div className="inline-field"><label>Steps</label><button className="compact-select">30 <ChevronDown size={15}/></button></div>
          <div className="inline-field"><label>CFG</label><button className="compact-select">7.0 <ChevronDown size={15}/></button></div>
          <div className="inline-field"><label>Workflow</label><button className="compact-select">Default <ChevronDown size={15}/></button></div>
        </div>}

        <button className="reset-button" onClick={()=>{setAspect('1:1'); setOutputs(4); setSeed('123456789');}}><RotateCcw size={18}/> Reset to Defaults</button>
      </aside>
      {settingsOpen && <div className="panel-scrim" onClick={()=>setSettingsOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
