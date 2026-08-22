import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Image as ImageIcon, Video, Crop, Grid2X2, Plus, X, SlidersHorizontal, Sparkles,
  Palette, ImagePlus, ChevronDown, RotateCcw, Dice5, Check, AtSign
} from 'lucide-react';

export const ASPECT_PRESETS = [
  { value: '1:1', label: 'Square', ratio: 1 },
  { value: '4:5', label: 'Portrait', ratio: 4 / 5 },
  { value: '3:4', label: 'Portrait', ratio: 3 / 4 },
  { value: '2:3', label: 'Tall', ratio: 2 / 3 },
  { value: '9:16', label: 'Vertical', ratio: 9 / 16 },
  { value: '5:4', label: 'Classic', ratio: 5 / 4 },
  { value: '4:3', label: 'Classic', ratio: 4 / 3 },
  { value: '3:2', label: 'Photo', ratio: 3 / 2 },
  { value: '16:10', label: 'Wide', ratio: 16 / 10 },
  { value: '16:9', label: 'Widescreen', ratio: 16 / 9 },
  { value: '21:9', label: 'Cinematic', ratio: 21 / 9 },
];

export const IMAGE_RESOLUTIONS = [
  { value: 512, label: 'Draft', detail: '512 px' },
  { value: 768, label: 'Standard', detail: '768 px' },
  { value: 1024, label: 'HD', detail: '1024 px' },
  { value: 1536, label: 'High', detail: '1536 px' },
  { value: 2048, label: 'Max', detail: '2048 px' },
];

const STYLE_PRESETS = [
  ['Photoreal', 'photorealistic, natural lighting, realistic materials and skin texture'],
  ['Cinematic', 'cinematic lighting, filmic contrast, deliberate composition'],
  ['Editorial', 'editorial photography, refined styling, clean commercial composition'],
  ['Illustration', 'polished digital illustration, expressive detail, cohesive color design'],
  ['Anime', 'high quality anime illustration, clean linework, expressive lighting'],
];

function round64(value) {
  return Math.max(64, Math.round(value / 64) * 64);
}

export function dimensionsForPreset(aspect, longEdge) {
  const preset = ASPECT_PRESETS.find((item) => item.value === aspect) || ASPECT_PRESETS[0];
  const ratio = preset.ratio;
  if (ratio >= 1) return { width: round64(longEdge), height: round64(longEdge / ratio) };
  return { width: round64(longEdge * ratio), height: round64(longEdge) };
}

function MorphGrid({ options, value, onChange, className = '', renderOption }) {
  const refs = useRef([]);
  const [hovered, setHovered] = useState(null);
  const activeIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const targetIndex = hovered == null ? activeIndex : hovered;
  const target = refs.current[targetIndex];
  const style = target ? {
    width: target.offsetWidth,
    height: target.offsetHeight,
    transform: `translate3d(${target.offsetLeft}px, ${target.offsetTop}px, 0)`,
    opacity: 1,
  } : { opacity: 0 };

  return <div className={`morph-grid ${className}`} onMouseLeave={() => setHovered(null)}>
    <span className="morph-indicator" style={style}/>
    {options.map((option, index) => <button
      ref={(node) => { refs.current[index] = node; }}
      type="button"
      key={option.value}
      className={option.value === value ? 'selected' : ''}
      onMouseEnter={() => setHovered(index)}
      onFocus={() => setHovered(index)}
      onClick={() => onChange(option.value)}
    >{renderOption ? renderOption(option) : option.label}</button>)}
  </div>;
}

function ReferencePrompt({ prompt, setPrompt, references, disabled }) {
  const textareaRef = useRef(null);
  const [picker, setPicker] = useState(null);

  const updatePicker = (value, caret) => {
    const before = value.slice(0, caret);
    const match = before.match(/@([^@\n]*)$/);
    if (!match || !references.length) return setPicker(null);
    setPicker({ start: caret - match[0].length, end: caret, query: match[1].trim().toLowerCase() });
  };

  const onChange = (event) => {
    setPrompt(event.target.value);
    updatePicker(event.target.value, event.target.selectionStart || 0);
  };

  const insertReference = (index) => {
    if (!picker) return;
    const mention = `@Image ${index + 1}`;
    const next = `${prompt.slice(0, picker.start)}${mention}${prompt.slice(picker.end)}`;
    setPrompt(next);
    setPicker(null);
    requestAnimationFrame(() => {
      const position = picker.start + mention.length;
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(position, position);
    });
  };

  const matches = useMemo(() => references.map((reference, index) => ({ reference, index })).filter(({ reference, index }) => {
    if (!picker?.query) return true;
    return `image ${index + 1} ${reference.file?.name || ''}`.toLowerCase().includes(picker.query);
  }), [references, picker]);

  return <div className="prompt-editor-wrap">
    <textarea
      ref={textareaRef}
      value={prompt}
      onChange={onChange}
      onClick={(event) => updatePicker(event.currentTarget.value, event.currentTarget.selectionStart || 0)}
      onKeyUp={(event) => updatePicker(event.currentTarget.value, event.currentTarget.selectionStart || 0)}
      placeholder={references.length ? 'Describe the edit. Type @ to reference an image…' : 'Add one or more reference images, then describe the edit…'}
      maxLength={2000}
      disabled={disabled}
    />
    {picker && matches.length > 0 && <div className="mention-picker">
      <div className="mention-picker-title"><AtSign size={14}/> References</div>
      {matches.map(({ reference, index }) => <button type="button" key={reference.id} onMouseDown={(event) => { event.preventDefault(); insertReference(index); }}>
        <span className="mention-thumb" style={{ backgroundImage: `url(${reference.preview})` }}/>
        <span><strong>Image {index + 1}</strong><small>{reference.file?.name || 'Reference image'}</small></span>
      </button>)}
    </div>}
  </div>;
}

function ReferenceStrip({ references, onAdd, onRemove }) {
  const inputRef = useRef(null);
  return <>
    <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(event) => {
      const files = Array.from(event.target.files || []);
      if (files.length) onAdd(files);
      event.target.value = '';
    }}/>
    <div className="reference-strip">
      {references.map((reference, index) => <div className="reference-tile" key={reference.id}>
        <div className="reference-image" style={{ backgroundImage: `url(${reference.preview})` }}><span>{index + 1}</span></div>
        <div className="reference-meta"><strong>Image {index + 1}</strong><small>{reference.width && reference.height ? `${reference.width}×${reference.height}` : reference.file?.name}</small></div>
        <button type="button" className="reference-remove" title={`Remove Image ${index + 1}`} onClick={() => onRemove(index)}><X size={14}/></button>
      </div>)}
      <button type="button" className="add-reference-tile" onClick={() => inputRef.current?.click()}><Plus size={20}/><span>{references.length ? 'Add image' : 'Add references'}</span></button>
    </div>
    <button type="button" className="secondary-button add-reference-button" onClick={() => inputRef.current?.click()}><ImagePlus size={18}/> {references.length ? 'Add references' : 'Reference images'}</button>
  </>;
}

function SelectMenu({ value, onChange, options, label }) {
  return <label className="compact-native-select" aria-label={label}>
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {options.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
    </select>
    <ChevronDown size={15}/>
  </label>;
}

function SettingsPanel({
  open, onClose, mode, aspect, setAspect, imageResolution, setImageResolution, outputs, setOutputs,
  advanced, setAdvanced, seed, setSeed, steps, setSteps, cfg, setCfg, workflowId, setWorkflowId,
  modelId, setModelId, autoEditInfo,
}) {
  const isEdit = mode === 'Edit';
  const modelOptions = isEdit
    ? [{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B · DarkBeast V2' }]
    : [{ value: 'saga-image-auto', label: 'SAGA Image · Auto' }];
  const aspectOptions = ASPECT_PRESETS;
  const resolutionOptions = IMAGE_RESOLUTIONS;

  return <aside className={`settings-panel ${open ? 'open' : ''}`}>
    <div className="settings-header"><h2>Settings</h2><button className="square-button" onClick={onClose}><SlidersHorizontal size={18}/></button></div>

    <label className="field-label">Model</label>
    <SelectMenu label="Model" value={modelId} onChange={setModelId} options={modelOptions}/>

    <label className="field-label">Aspect Ratio</label>
    {isEdit ? <div className="auto-setting-card"><span className="auto-setting-icon">A</span><div><strong>Automatic</strong><small>{autoEditInfo?.ratioLabel || 'Uses the primary reference image'}</small></div><Check size={17}/></div> : <MorphGrid className="aspect-morph-grid" options={aspectOptions} value={aspect} onChange={setAspect} renderOption={(option) => <><span className="ratio-preview" style={{ aspectRatio: String(option.ratio) }}/><strong>{option.value}</strong><small>{option.label}</small></>}/>} 

    <label className="field-label">Resolution</label>
    {isEdit ? <div className="auto-setting-card"><span className="auto-setting-icon">↗</span><div><strong>Automatic output size</strong><small>{autoEditInfo?.detail || 'Add a primary reference to calculate output size'}</small></div><Check size={17}/></div> : <MorphGrid className="resolution-morph-grid" options={resolutionOptions} value={imageResolution} onChange={setImageResolution} renderOption={(option) => <><strong>{option.label}</strong><small>{option.detail}</small></>}/>} 

    <label className="field-label">Outputs</label>
    {isEdit ? <div className="auto-setting-card compact"><span className="auto-setting-icon">1</span><div><strong>Single output</strong><small>Klein Edit currently returns one persisted result per job</small></div></div> : <MorphGrid className="output-morph-grid" options={[1,2,4].map((value) => ({ value, label: String(value) }))} value={outputs} onChange={setOutputs}/>} 

    <div className="settings-divider"/>
    <button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}><span>Advanced</span><ChevronDown className={advanced ? 'rotated' : ''} size={17}/></button>
    {advanced && <div className="advanced-fields">
      <div className="inline-field"><label>Seed</label><div className="input-box"><input inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))}/><button type="button" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={17}/></button></div></div>
      <div className="inline-field"><label>Steps</label><SelectMenu label="Steps" value={String(steps)} onChange={(value) => setSteps(Number(value))} options={(isEdit ? [4,6,8,12] : [20,30,40,50]).map((value) => ({ value: String(value), label: String(value) }))}/></div>
      <div className="inline-field"><label>CFG</label><SelectMenu label="CFG" value={String(cfg)} onChange={(value) => setCfg(Number(value))} options={(isEdit ? [1,1.5,2,3] : [3.5,5,7,9]).map((value) => ({ value: String(value), label: Number(value).toFixed(1) }))}/></div>
      <div className="inline-field"><label>Workflow</label><SelectMenu label="Workflow" value={workflowId} onChange={setWorkflowId} options={isEdit ? [{ value: 'flux2-klein-image-edit', label: 'Klein Multi-Reference Edit' }] : [{ value: 'default-image', label: 'Default Image' }]}/></div>
    </div>}
    <button className="reset-button" onClick={() => {
      setAspect('1:1'); setImageResolution(1024); setOutputs(4); setSeed('42'); setSteps(isEdit ? 4 : 30); setCfg(isEdit ? 1 : 7); setWorkflowId(isEdit ? 'flux2-klein-image-edit' : 'default-image'); setModelId(isEdit ? 'flux2-klein-9b' : 'saga-image-auto');
    }}><RotateCcw size={18}/> Reset to Defaults</button>
  </aside>;
}

export default function CreateWorkspace({
  mode, setMode, prompt, setPrompt, references, onAddReferences, onRemoveReference,
  error, jobStatus, busy, onGenerate, items, renderCard,
  aspect, setAspect, imageResolution, setImageResolution, outputs, setOutputs,
  advanced, setAdvanced, seed, setSeed, steps, setSteps, cfg, setCfg,
  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,
}) {
  const isEdit = mode === 'Edit';
  const [styleOpen, setStyleOpen] = useState(false);
  const imageDimensions = dimensionsForPreset(aspect, imageResolution);
  const unsupported = mode !== 'Edit';

  useEffect(() => {
    if (mode === 'Edit') {
      if (workflowId !== 'flux2-klein-image-edit') setWorkflowId('flux2-klein-image-edit');
      if (modelId !== 'flux2-klein-9b') setModelId('flux2-klein-9b');
      if (outputs !== 1) setOutputs(1);
    } else {
      if (modelId === 'flux2-klein-9b') setModelId('saga-image-auto');
      if (outputs === 1) setOutputs(4);
    }
  }, [mode]);

  const applyStyle = (name, text) => {
    const suffix = `Style: ${text}.`;
    setPrompt((current) => current.trim() ? `${current.trim()}\n${suffix}` : suffix);
    setStyleOpen(false);
  };

  return <>
    <div className="mode-tabs">{[[ImageIcon, 'Image'], [Video, 'Video'], [Crop, 'Edit'], [Grid2X2, 'More']].map(([Icon, label]) => <button className={`mode-tab ${mode === label ? 'selected' : ''}`} key={label} onClick={() => setMode(label)}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>)}</div>

    <section className={`composer-panel composer-panel-v2 ${references.length ? 'has-references' : ''}`}>
      {isEdit && <ReferenceStrip references={references} onAdd={onAddReferences} onRemove={onRemoveReference}/>} 
      {!isEdit && <div className="composer-mode-hint">{mode === 'Image' ? `Original image · ${imageDimensions.width}×${imageDimensions.height} · ${aspect}` : mode === 'Video' ? 'Video generation is the next workflow milestone.' : 'Additional tools will appear here as workflows are added.'}</div>}
      {isEdit ? <ReferencePrompt prompt={prompt} setPrompt={setPrompt} references={references} disabled={busy}/> : <div className="prompt-editor-wrap"><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={mode === 'Video' ? 'Describe the motion, scene, and camera movement…' : 'Describe what you want to create…'} maxLength={2000} disabled={busy}/></div>}
      <div className="composer-footer"><span>{isEdit && references.length ? `${references.length} reference${references.length === 1 ? '' : 's'} · type @ to mention · ` : ''}{prompt.length} / 2000</span><Sparkles size={18}/></div>
    </section>

    {error && <div className="composer-error">{error}</div>}
    {isEdit && <div className="backend-status">{jobStatus ? `Job ${jobStatus} · ` : ''}Live backend · FLUX.2 Klein 9B · automatic output size · {references.length || 0} reference{references.length === 1 ? '' : 's'}</div>}

    <div className="action-row">
      <div className="attach-actions">
        {isEdit && <button className="secondary-button" onClick={() => document.querySelector('.reference-strip + .add-reference-button')?.click()}><ImagePlus size={18}/> Add references</button>}
        <div className="style-menu-wrap"><button className="secondary-button" onClick={() => setStyleOpen((value) => !value)}><Palette size={18}/> Style</button>{styleOpen && <div className="style-popover">{STYLE_PRESETS.map(([name, text]) => <button type="button" key={name} onClick={() => applyStyle(name, text)}><strong>{name}</strong><small>{text}</small></button>)}</div>}</div>
      </div>
      <div className="generate-actions"><button className="square-button" onClick={() => setSettingsOpen(true)} title="Generation settings"><SlidersHorizontal size={19}/></button><button className={`generate-button ${busy ? 'busy' : ''}`} onClick={onGenerate} disabled={busy || (isEdit && references.length === 0)}><Sparkles size={18}/>{busy ? (isEdit ? (jobStatus === 'uploading' ? 'Uploading…' : jobStatus === 'queued' ? 'Queued…' : 'Editing…') : 'Working…') : isEdit ? 'Edit image' : unsupported ? 'Generate' : 'Generate'}</button></div>
    </div>

    <section className="gallery-grid">{items.map((item) => renderCard(item, false))}</section>

    <SettingsPanel
      open={settingsOpen} onClose={() => setSettingsOpen(false)} mode={mode}
      aspect={aspect} setAspect={setAspect} imageResolution={imageResolution} setImageResolution={setImageResolution}
      outputs={outputs} setOutputs={setOutputs} advanced={advanced} setAdvanced={setAdvanced}
      seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg}
      workflowId={workflowId} setWorkflowId={setWorkflowId} modelId={modelId} setModelId={setModelId}
      autoEditInfo={autoEditInfo}
    />
    {settingsOpen && <div className="panel-scrim" onClick={() => setSettingsOpen(false)}/>} 
  </>;
}
