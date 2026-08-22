import React, { useEffect, useMemo, useRef, useState } from 'react';
import './create-controls-polish.css';
import './create-controls-interactions.css';
import { setEditSizingPreference } from './generation-client.js';
import {
  Image as ImageIcon, Video, Crop, Grid2X2, Plus, X, SlidersHorizontal, Sparkles,
  ChevronDown, RotateCcw, Dice5, Check, AtSign, ArrowUp
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

const AUTO_VALUE = '__auto__';

function round64(value) {
  return Math.max(64, Math.round(value / 64) * 64);
}

export function dimensionsForPreset(aspect, longEdge) {
  const preset = ASPECT_PRESETS.find((item) => item.value === aspect) || ASPECT_PRESETS[0];
  const ratio = preset.ratio;
  if (ratio >= 1) return { width: round64(longEdge), height: round64(longEdge / ratio) };
  return { width: round64(longEdge * ratio), height: round64(longEdge) };
}

function parseAutoDimensions(detail) {
  const match = String(detail || '').match(/(\d+)\s*[×x]\s*(\d+)/i);
  return match ? { width: Number(match[1]), height: Number(match[2]) } : null;
}

function editorText(root) {
  if (!root) return '';
  const walk = (node) => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    if (node.classList?.contains('mention-token')) return node.dataset.mention || node.textContent || '';
    if (node.tagName === 'BR') return '\n';
    const value = Array.from(node.childNodes).map(walk).join('');
    return node.tagName === 'DIV' ? `${value}\n` : value;
  };
  return Array.from(root.childNodes).map(walk).join('').replace(/\n+$/, '');
}

function createMentionNode(reference, index) {
  const token = document.createElement('span');
  token.className = 'mention-token';
  token.contentEditable = 'false';
  token.dataset.mention = `@Image ${index + 1}`;
  token.dataset.referenceIndex = String(index);

  const thumb = document.createElement('span');
  thumb.className = 'mention-token-thumb';
  thumb.style.backgroundImage = `url("${String(reference?.preview || '').replace(/"/g, '\\"')}")`;

  const label = document.createElement('span');
  label.className = 'mention-token-label';
  label.textContent = `Image ${index + 1}`;

  token.append(thumb, label);
  return token;
}

function renderPromptInto(root, prompt, references) {
  if (!root) return;
  root.replaceChildren();
  const regex = /@Image\s+(\d+)/gi;
  let cursor = 0;
  let match;
  while ((match = regex.exec(prompt)) !== null) {
    if (match.index > cursor) root.append(document.createTextNode(prompt.slice(cursor, match.index)));
    const index = Number(match[1]) - 1;
    if (references[index]) root.append(createMentionNode(references[index], index));
    else root.append(document.createTextNode(match[0]));
    cursor = regex.lastIndex;
  }
  if (cursor < prompt.length) root.append(document.createTextNode(prompt.slice(cursor)));
}

function ReferencePrompt({ prompt, setPrompt, references, disabled }) {
  const editorRef = useRef(null);
  const wrapRef = useRef(null);
  const [picker, setPicker] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const matches = useMemo(() => {
    const query = picker?.query || '';
    return references.map((reference, index) => ({ reference, index })).filter(({ reference, index }) => {
      if (!query) return true;
      return `image${index + 1} image ${index + 1} ${reference.file?.name || ''}`.toLowerCase().includes(query);
    });
  }, [references, picker?.query]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || document.activeElement === editor) return;
    if (editorText(editor) !== prompt) renderPromptInto(editor, prompt, references);
  }, [prompt, references]);

  useEffect(() => {
    if (activeIndex >= matches.length) setActiveIndex(0);
  }, [matches.length, activeIndex]);

  const updatePickerFromSelection = () => {
    const editor = editorRef.current;
    const wrap = wrapRef.current;
    const selection = window.getSelection();
    if (!editor || !wrap || !selection?.rangeCount || !selection.isCollapsed || !editor.contains(selection.anchorNode)) {
      setPicker(null);
      return;
    }

    const rangeToCaret = document.createRange();
    rangeToCaret.selectNodeContents(editor);
    rangeToCaret.setEnd(selection.anchorNode, selection.anchorOffset);
    const before = rangeToCaret.toString();
    const match = before.match(/@([^\s@\n]*)$/);
    if (!match || !references.length) {
      setPicker(null);
      return;
    }

    const caretRange = selection.getRangeAt(0).cloneRange();
    caretRange.collapse(true);
    let rect = caretRange.getBoundingClientRect();
    if (!rect.width && !rect.height) rect = editor.getBoundingClientRect();
    const wrapRect = wrap.getBoundingClientRect();
    setActiveIndex(0);
    setPicker({
      query: match[1].toLowerCase(),
      tokenLength: match[0].length,
      left: Math.max(8, Math.min(rect.left - wrapRect.left, wrapRect.width - 300)),
      top: Math.max(8, rect.top - wrapRect.top),
    });
  };

  const syncPrompt = () => {
    const value = editorText(editorRef.current).slice(0, 2000);
    setPrompt(value);
    requestAnimationFrame(updatePickerFromSelection);
  };

  const insertReference = (referenceIndex) => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !picker || !selection?.rangeCount) return;

    const range = selection.getRangeAt(0);
    const node = range.startContainer;
    const offset = range.startOffset;
    if (node.nodeType !== Node.TEXT_NODE) return;

    const text = node.textContent || '';
    const start = Math.max(0, offset - picker.tokenLength);
    const before = text.slice(0, start);
    const after = text.slice(offset);
    const parent = node.parentNode;
    const reference = references[referenceIndex];

    const beforeNode = document.createTextNode(before);
    const mentionNode = createMentionNode(reference, referenceIndex);
    const spacer = document.createTextNode('\u00a0');
    const afterNode = document.createTextNode(after);
    parent.insertBefore(beforeNode, node);
    parent.insertBefore(mentionNode, node);
    parent.insertBefore(spacer, node);
    parent.insertBefore(afterNode, node);
    parent.removeChild(node);

    const nextRange = document.createRange();
    nextRange.setStart(spacer, spacer.textContent.length);
    nextRange.collapse(true);
    selection.removeAllRanges();
    selection.addRange(nextRange);

    setPicker(null);
    setPrompt(editorText(editor).slice(0, 2000));
    editor.focus();
  };

  const onKeyDown = (event) => {
    if (!picker || !matches.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % matches.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + matches.length) % matches.length);
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      insertReference(matches[activeIndex]?.index ?? matches[0].index);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      setPicker(null);
    }
  };

  return <div className="prompt-editor-wrap rich-prompt-wrap" ref={wrapRef}>
    <div
      ref={editorRef}
      className="rich-prompt-editor"
      contentEditable={!disabled}
      suppressContentEditableWarning
      role="textbox"
      aria-multiline="true"
      data-placeholder={references.length ? 'Describe the edit. Type @ to reference an image…' : 'Add one or more reference images, then describe the edit…'}
      onInput={syncPrompt}
      onClick={updatePickerFromSelection}
      onKeyUp={(event) => {
        if (!['ArrowDown', 'ArrowUp', 'Enter', 'Tab', 'Escape'].includes(event.key)) updatePickerFromSelection();
      }}
      onKeyDown={onKeyDown}
      onPaste={(event) => {
        event.preventDefault();
        const text = event.clipboardData.getData('text/plain').slice(0, Math.max(0, 2000 - editorText(editorRef.current).length));
        document.execCommand('insertText', false, text);
      }}
    />
    {picker && matches.length > 0 && <div className="mention-picker" style={{ left: picker.left, top: picker.top }}>
      <div className="mention-picker-title"><AtSign size={14}/> References <span>↑↓ select · Enter insert</span></div>
      {matches.map(({ reference, index }, matchIndex) => <button
        type="button"
        key={reference.id}
        className={matchIndex === activeIndex ? 'active' : ''}
        onMouseEnter={() => setActiveIndex(matchIndex)}
        onMouseDown={(event) => { event.preventDefault(); insertReference(index); }}
      >
        <span className="mention-thumb" style={{ backgroundImage: `url(${reference.preview})` }}/>
        <span><strong>Image {index + 1}</strong><small>{reference.file?.name || 'Reference image'}</small></span>
      </button>)}
    </div>}
  </div>;
}

function ReferenceStrip({ references, onRemove }) {
  if (!references.length) return null;
  return <div className="reference-strip">
    {references.map((reference, index) => <div className="reference-tile" key={reference.id}>
      <div className="reference-image" style={{ backgroundImage: `url(${reference.preview})` }}><span>{index + 1}</span></div>
      <div className="reference-meta"><strong>Image {index + 1}</strong><small>{reference.width && reference.height ? `${reference.width}×${reference.height}` : reference.file?.name}</small></div>
      <button type="button" className="reference-remove" title={`Remove Image ${index + 1}`} onClick={() => onRemove(index)}><X size={14}/></button>
    </div>)}
  </div>;
}

function SelectMenu({ value, onChange, options, label, className = '' }) {
  return <label className={`compact-native-select ${className}`} aria-label={label}>
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {options.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
    </select>
    <ChevronDown size={15}/>
  </label>;
}

function SettingsPanel({
  open, onClose, mode, outputs, setOutputs, seed, setSeed, steps, setSteps, cfg, setCfg,
  workflowId, setWorkflowId, modelId, setModelId,
}) {
  if (!open) return null;
  const isEdit = mode === 'Edit';
  const modelOptions = isEdit
    ? [{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B · DarkBeast V2' }]
    : [{ value: 'saga-image-auto', label: 'SAGA Image · Auto' }];

  return <div className="composer-settings-popover advanced-settings-only">
    <div className="settings-header"><h2>Advanced settings</h2><button className="square-button" onClick={onClose}><X size={17}/></button></div>

    <label className="field-label">Model</label>
    <SelectMenu label="Model" value={modelId} onChange={setModelId} options={modelOptions}/>

    {!isEdit && <>
      <label className="field-label">Outputs</label>
      <SelectMenu label="Outputs" value={String(outputs)} onChange={(value) => setOutputs(Number(value))} options={[1, 2, 4].map((value) => ({ value: String(value), label: `${value} output${value === 1 ? '' : 's'}` }))}/>
    </>}

    <div className="settings-divider"/>
    <div className="advanced-fields advanced-fields-always">
      <div className="inline-field"><label>Seed</label><div className="input-box"><input inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))}/><button type="button" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={17}/></button></div></div>
      <div className="inline-field"><label>Steps</label><SelectMenu label="Steps" value={String(steps)} onChange={(value) => setSteps(Number(value))} options={(isEdit ? [4,6,8,12] : [20,30,40,50]).map((value) => ({ value: String(value), label: String(value) }))}/></div>
      <div className="inline-field"><label>CFG</label><SelectMenu label="CFG" value={String(cfg)} onChange={(value) => setCfg(Number(value))} options={(isEdit ? [1,1.5,2,3] : [3.5,5,7,9]).map((value) => ({ value: String(value), label: Number(value).toFixed(1) }))}/></div>
      <div className="inline-field"><label>Workflow</label><SelectMenu label="Workflow" value={workflowId} onChange={setWorkflowId} options={isEdit ? [{ value: 'flux2-klein-image-edit', label: 'Klein Multi-Reference Edit' }] : [{ value: 'default-image', label: 'Default Image' }]}/></div>
    </div>

    <button className="reset-button" onClick={() => {
      setOutputs(isEdit ? 1 : 4);
      setSeed('42');
      setSteps(isEdit ? 4 : 30);
      setCfg(isEdit ? 1 : 7);
      setWorkflowId(isEdit ? 'flux2-klein-image-edit' : 'default-image');
      setModelId(isEdit ? 'flux2-klein-9b' : 'saga-image-auto');
    }}><RotateCcw size={18}/> Reset advanced settings</button>
  </div>;
}

function useAnchoredPickerPosition(open, anchorRef, desiredWidth, desiredHeight) {
  const [position, setPosition] = useState(null);

  useEffect(() => {
    if (!open) {
      setPosition(null);
      return undefined;
    }

    const updatePosition = () => {
      const anchor = anchorRef?.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const gap = 9;
      const edge = 12;
      const width = Math.min(desiredWidth, viewportWidth - edge * 2);
      const height = Math.min(desiredHeight, viewportHeight - edge * 2);
      const spaceAbove = rect.top - edge - gap;
      const spaceBelow = viewportHeight - rect.bottom - edge - gap;
      const openAbove = spaceAbove >= Math.min(height, 220) || spaceAbove > spaceBelow;
      let top = openAbove ? rect.top - gap - height : rect.bottom + gap;
      top = Math.max(edge, Math.min(top, viewportHeight - height - edge));
      let left = rect.right - width;
      left = Math.max(edge, Math.min(left, viewportWidth - width - edge));
      setPosition({ top, left, width, height });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, anchorRef, desiredWidth, desiredHeight]);

  return position;
}

function pickerKeyDown(event, index, options, refs, choose, close, anchorRef) {
  const last = options.length - 1;
  let nextIndex = null;
  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') nextIndex = index >= last ? 0 : index + 1;
  if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') nextIndex = index <= 0 ? last : index - 1;
  if (event.key === 'Home') nextIndex = 0;
  if (event.key === 'End') nextIndex = last;
  if (nextIndex != null) {
    event.preventDefault();
    refs.current[nextIndex]?.focus();
    return;
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    choose(options[index]);
    return;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    close();
    requestAnimationFrame(() => anchorRef?.current?.focus());
    return;
  }
  if (event.key === 'Tab') close();
}

function AspectPicker({ aspect, setAspect, open, setOpen, anchorRef, autoEnabled = false, onAutoChange, autoRatio = 1, autoInfo }) {
  const itemRefs = useRef([]);
  const [hovered, setHovered] = useState(null);
  const position = useAnchoredPickerPosition(open, anchorRef, 510, 390);
  const options = useMemo(() => onAutoChange ? [{ value: AUTO_VALUE, label: 'Auto', ratio: autoRatio || 1, auto: true }, ...ASPECT_PRESETS] : ASPECT_PRESETS, [onAutoChange, autoRatio]);
  const selectedValue = autoEnabled ? AUTO_VALUE : aspect;
  const activeIndex = Math.max(0, options.findIndex((item) => item.value === selectedValue));
  const hoverIndex = hovered == null ? activeIndex : hovered;
  const display = options[hoverIndex] || options[activeIndex] || options[0];
  const target = itemRefs.current[hoverIndex];
  const indicatorStyle = target ? {
    width: target.offsetWidth,
    height: target.offsetHeight,
    transform: `translate3d(${target.offsetLeft}px, ${target.offsetTop}px, 0)`,
    opacity: 1,
  } : { opacity: 0 };

  const previewSize = useMemo(() => {
    const max = 94;
    const ratio = Number(display?.ratio) || 1;
    if (ratio >= 1) return { width: max, height: max / ratio };
    return { width: max * ratio, height: max };
  }, [display]);

  const choose = (option) => {
    if (option.auto) onAutoChange?.(true);
    else {
      onAutoChange?.(false);
      setAspect(option.value);
    }
    setOpen(false);
    requestAnimationFrame(() => anchorRef?.current?.focus());
  };

  useEffect(() => {
    if (!open) {
      setHovered(null);
      return undefined;
    }
    const frame = requestAnimationFrame(() => itemRefs.current[activeIndex]?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, activeIndex]);

  if (!open) return null;
  return <div className="grok-aspect-popover" style={position || { visibility: 'hidden' }} role="menu" aria-label="Aspect ratio">
    <div className="grok-aspect-preview">
      <div className="grok-preview-grid">
        <span className="grok-preview-shape" style={{ width: previewSize.width, height: previewSize.height }}/>
      </div>
      <strong>{display.auto ? 'Auto' : display.value}</strong>
      <small>{display.auto ? (autoInfo?.ratioLabel || 'Primary reference canvas') : display.label}</small>
    </div>
    <div className="grok-aspect-list" onMouseLeave={() => setHovered(null)}>
      <span className="grok-aspect-morph-indicator" style={indicatorStyle}/>
      {options.map((option, index) => <button
        ref={(node) => { itemRefs.current[index] = node; }}
        type="button"
        role="menuitemradio"
        aria-checked={option.value === selectedValue}
        tabIndex={index === activeIndex ? 0 : -1}
        key={option.value}
        className={option.value === selectedValue ? 'active' : ''}
        onMouseEnter={() => setHovered(index)}
        onFocus={() => setHovered(index)}
        onKeyDown={(event) => pickerKeyDown(event, index, options, itemRefs, choose, () => setOpen(false), anchorRef)}
        onClick={() => choose(option)}
      >
        <span className="ratio-code">{option.auto ? <Sparkles size={14}/> : option.value}</span>
        <span>{option.auto ? 'Automatic' : option.label}</span>
        {option.value === selectedValue ? <Check size={15}/> : null}
      </button>)}
    </div>
  </div>;
}

function ResolutionPicker({ imageResolution, setImageResolution, aspect, open, setOpen, anchorRef, autoEnabled = false, onAutoChange, autoInfo, autoDimensions }) {
  const itemRefs = useRef([]);
  const [hovered, setHovered] = useState(null);
  const position = useAnchoredPickerPosition(open, anchorRef, 430, onAutoChange ? 310 : 272);
  const options = useMemo(() => onAutoChange ? [{ value: AUTO_VALUE, label: 'Auto', detail: autoInfo?.detail || 'Automatic output size', auto: true }, ...IMAGE_RESOLUTIONS] : IMAGE_RESOLUTIONS, [onAutoChange, autoInfo?.detail]);
  const selectedValue = autoEnabled ? AUTO_VALUE : Number(imageResolution);
  const activeIndex = Math.max(0, options.findIndex((item) => item.value === selectedValue));
  const hoverIndex = hovered == null ? activeIndex : hovered;
  const display = options[hoverIndex] || options[activeIndex] || options[0];
  const target = itemRefs.current[hoverIndex];
  const indicatorStyle = target ? {
    width: target.offsetWidth,
    height: target.offsetHeight,
    transform: `translate3d(${target.offsetLeft}px, ${target.offsetTop}px, 0)`,
    opacity: 1,
  } : { opacity: 0 };
  const dimensions = display.auto ? autoDimensions : dimensionsForPreset(aspect, display.value);
  const previewSize = display.auto ? 68 : 56 + Math.max(0, hoverIndex - (onAutoChange ? 1 : 0)) * 8;

  const choose = (option) => {
    if (option.auto) onAutoChange?.(true);
    else {
      onAutoChange?.(false);
      setImageResolution(option.value);
    }
    setOpen(false);
    requestAnimationFrame(() => anchorRef?.current?.focus());
  };

  useEffect(() => {
    if (!open) {
      setHovered(null);
      return undefined;
    }
    const frame = requestAnimationFrame(() => itemRefs.current[activeIndex]?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, activeIndex]);

  if (!open) return null;
  return <div className="grok-resolution-popover" style={position || { visibility: 'hidden' }} role="menu" aria-label="Resolution">
    <div className="grok-resolution-preview">
      <div className="grok-resolution-stage">
        <span className={`grok-resolution-shape ${display.auto ? 'auto' : ''}`} style={{ width: previewSize, height: previewSize }}>{display.auto ? <Sparkles size={17}/> : display.value}</span>
      </div>
      <strong>{display.label}</strong>
      <small>{dimensions?.width && dimensions?.height ? `${dimensions.width}×${dimensions.height} · ` : ''}{display.detail}</small>
    </div>
    <div className="grok-resolution-list" onMouseLeave={() => setHovered(null)}>
      <span className="grok-resolution-morph-indicator" style={indicatorStyle}/>
      {options.map((option, index) => <button
        ref={(node) => { itemRefs.current[index] = node; }}
        type="button"
        role="menuitemradio"
        aria-checked={option.value === selectedValue}
        tabIndex={index === activeIndex ? 0 : -1}
        key={option.value}
        className={option.value === selectedValue ? 'active' : ''}
        onMouseEnter={() => setHovered(index)}
        onFocus={() => setHovered(index)}
        onKeyDown={(event) => pickerKeyDown(event, index, options, itemRefs, choose, () => setOpen(false), anchorRef)}
        onClick={() => choose(option)}
      >
        <span>{option.auto ? <><Sparkles size={13}/> Auto</> : option.label}</span>
        <span>{option.detail}</span>
        {option.value === selectedValue ? <Check size={15}/> : null}
      </button>)}
    </div>
  </div>;
}

export default function CreateWorkspace({
  mode, setMode, prompt, setPrompt, references, onAddReferences, onRemoveReference,
  error, jobStatus, busy, onGenerate, items, renderCard,
  aspect, setAspect, imageResolution, setImageResolution, outputs, setOutputs,
  seed, setSeed, steps, setSteps, cfg, setCfg,
  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,
}) {
  const isEdit = mode === 'Edit';
  const referenceInputRef = useRef(null);
  const aspectWrapRef = useRef(null);
  const resolutionWrapRef = useRef(null);
  const aspectButtonRef = useRef(null);
  const resolutionButtonRef = useRef(null);
  const autoInfoBaselineRef = useRef(null);
  const [aspectOpen, setAspectOpen] = useState(false);
  const [resolutionOpen, setResolutionOpen] = useState(false);
  const [editAuto, setEditAuto] = useState(true);

  const imageDimensions = dimensionsForPreset(aspect, imageResolution);
  const imageResolutionOption = IMAGE_RESOLUTIONS.find((option) => option.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];
  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;
  const autoInfoForPicker = editAuto ? autoEditInfo : (autoInfoBaselineRef.current || autoEditInfo);
  const autoDimensions = parseAutoDimensions(autoInfoForPicker?.detail);

  useEffect(() => {
    if (autoEditInfo) autoInfoBaselineRef.current = { ...autoEditInfo };
  }, [autoEditInfo]);

  useEffect(() => {
    const baseline = autoInfoBaselineRef.current;
    if (autoEditInfo && baseline) {
      if (!isEdit || editAuto) {
        Object.assign(autoEditInfo, baseline);
      } else {
        const manual = dimensionsForPreset(aspect, imageResolution);
        Object.assign(autoEditInfo, {
          megapixels: Math.max(0.25, Math.min(4, (manual.width * manual.height) / 1_000_000)),
          detail: `${manual.width} × ${manual.height} · Manual`,
          ratioLabel: `${aspect} manual canvas`,
        });
      }
    }
    if (isEdit) setEditSizingPreference({ mode: editAuto ? 'auto' : 'manual', aspect, resolution: Number(imageResolution) });
  }, [isEdit, editAuto, aspect, imageResolution, autoEditInfo]);

  useEffect(() => {
    if (mode === 'Edit') {
      if (workflowId !== 'flux2-klein-image-edit') setWorkflowId('flux2-klein-image-edit');
      if (modelId !== 'flux2-klein-9b') setModelId('flux2-klein-9b');
      if (outputs !== 1) setOutputs(1);
      setEditAuto(true);
    } else {
      if (modelId === 'flux2-klein-9b') setModelId('saga-image-auto');
      if (outputs === 1) setOutputs(4);
    }
  }, [mode]);

  useEffect(() => {
    setAspectOpen(false);
    setResolutionOpen(false);
    setSettingsOpen(false);
  }, [mode, setSettingsOpen]);

  useEffect(() => {
    if (!aspectOpen && !resolutionOpen) return undefined;
    const onPointerDown = (event) => {
      if (aspectOpen && !aspectWrapRef.current?.contains(event.target)) setAspectOpen(false);
      if (resolutionOpen && !resolutionWrapRef.current?.contains(event.target)) setResolutionOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [aspectOpen, resolutionOpen]);

  const addReferenceFiles = (files) => {
    if (!files.length) return;
    setAspectOpen(false);
    setResolutionOpen(false);
    setSettingsOpen(false);
    if (mode !== 'Edit') setMode('Edit');
    onAddReferences(files);
  };

  const selectMode = (nextMode) => {
    setMode(nextMode);
    setAspectOpen(false);
    setResolutionOpen(false);
    setSettingsOpen(false);
  };

  const modeLabel = mode === 'Video' ? 'Video' : isEdit ? 'Edit' : mode === 'More' ? 'More' : 'Image';
  const sizingControlsVisible = mode === 'Image' || isEdit;

  return <>
    <input
      ref={referenceInputRef}
      type="file"
      accept="image/png,image/jpeg,image/webp"
      multiple
      hidden
      onChange={(event) => {
        addReferenceFiles(Array.from(event.target.files || []));
        event.target.value = '';
      }}
    />

    <div className="mode-tabs create-mode-tabs">
      {[[ImageIcon, 'Image'], [Video, 'Video'], [Crop, 'Edit'], [Grid2X2, 'More']].map(([Icon, label]) => <button
        type="button"
        className={`mode-tab ${mode === label ? 'selected' : ''}`}
        key={label}
        onClick={() => selectMode(label)}
      ><Icon size={18} strokeWidth={1.8}/><span>{label}</span></button>)}
    </div>

    <section className={`composer-panel composer-panel-v4 ${references.length ? 'has-references' : ''}`}>
      {isEdit && <ReferenceStrip references={references} onRemove={onRemoveReference}/>} 

      {!isEdit && <div className="grok-context-line">
        {mode === 'Image'
          ? `Original image · ${imageDimensions.width}×${imageDimensions.height} · ${imageResolutionOption.label}`
          : mode === 'Video'
            ? 'Video generation workflow'
            : 'More creation tools'}
      </div>}

      {isEdit
        ? <ReferencePrompt prompt={prompt} setPrompt={setPrompt} references={references} disabled={busy}/>
        : <div className="prompt-editor-wrap"><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={mode === 'Video' ? 'Describe the motion, scene, and camera movement…' : mode === 'More' ? 'Describe what you want to create…' : 'Type to imagine'} maxLength={2000} disabled={busy}/></div>}

      <div className="grok-toolbar">
        <div className="grok-toolbar-left">
          <button
            type="button"
            className="grok-circle-button"
            title="Upload reference images"
            aria-label="Upload reference images"
            onClick={() => referenceInputRef.current?.click()}
          ><Plus size={23}/></button>

          {sizingControlsVisible && <>
            {isEdit && <button type="button" className={`grok-text-choice grok-auto-choice ${editAuto ? 'selected' : ''}`} onClick={() => setEditAuto(true)}><Sparkles size={14}/> Auto</button>}

            <div className="grok-resolution-wrap" ref={resolutionWrapRef}>
              <button
                ref={resolutionButtonRef}
                type="button"
                className={`grok-resolution-button ${resolutionOpen ? 'active' : ''}`}
                aria-haspopup="menu"
                aria-expanded={resolutionOpen}
                onKeyDown={(event) => {
                  if (!resolutionOpen && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
                    event.preventDefault();
                    setResolutionOpen(true);
                    setAspectOpen(false);
                    setSettingsOpen(false);
                  }
                }}
                onClick={() => { setResolutionOpen((value) => !value); setAspectOpen(false); setSettingsOpen(false); }}
              >
                <span className={`grok-resolution-icon ${isEdit && editAuto ? 'auto' : ''}`}>{isEdit && editAuto ? 'A' : String(imageResolution).slice(0, 2)}</span>
                <span>{isEdit && editAuto ? 'Auto' : imageResolutionOption.label}</span>
                <ChevronDown size={14}/>
              </button>
              <ResolutionPicker
                imageResolution={imageResolution}
                setImageResolution={setImageResolution}
                aspect={aspect}
                open={resolutionOpen}
                setOpen={setResolutionOpen}
                anchorRef={resolutionButtonRef}
                autoEnabled={isEdit && editAuto}
                onAutoChange={isEdit ? setEditAuto : undefined}
                autoInfo={autoInfoForPicker}
                autoDimensions={autoDimensions}
              />
            </div>

            <div className="grok-aspect-wrap" ref={aspectWrapRef}>
              <button
                ref={aspectButtonRef}
                type="button"
                className={`grok-aspect-button ${aspectOpen ? 'active' : ''}`}
                aria-haspopup="menu"
                aria-expanded={aspectOpen}
                onKeyDown={(event) => {
                  if (!aspectOpen && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
                    event.preventDefault();
                    setAspectOpen(true);
                    setResolutionOpen(false);
                    setSettingsOpen(false);
                  }
                }}
                onClick={() => { setAspectOpen((value) => !value); setResolutionOpen(false); setSettingsOpen(false); }}
              >
                <span className="grok-ratio-icon" style={{ aspectRatio: String(isEdit && editAuto ? primaryRatio : (ASPECT_PRESETS.find((item) => item.value === aspect) || ASPECT_PRESETS[0]).ratio) }}/>
                <span>{isEdit && editAuto ? 'Auto' : aspect}</span>
              </button>
              <AspectPicker
                aspect={aspect}
                setAspect={setAspect}
                open={aspectOpen}
                setOpen={setAspectOpen}
                anchorRef={aspectButtonRef}
                autoEnabled={isEdit && editAuto}
                onAutoChange={isEdit ? setEditAuto : undefined}
                autoRatio={primaryRatio}
                autoInfo={autoInfoForPicker}
              />
            </div>
          </>}

          {isEdit && references.length > 0 && <span className="grok-edit-note">{references.length} reference{references.length === 1 ? '' : 's'} · {editAuto ? 'Auto canvas' : `${aspect} manual`}</span>}
          {mode === 'Video' && <span className="grok-edit-note">Video workflow</span>}
          {mode === 'More' && <span className="grok-edit-note">Additional tools</span>}
        </div>

        <div className="grok-toolbar-right">
          <span className="grok-prompt-count">{prompt.length} / 2000</span>
          <button type="button" className={`grok-icon-button grok-settings-button ${settingsOpen ? 'selected' : ''}`} title="Advanced settings" aria-label="Advanced settings" onClick={() => { setSettingsOpen((value) => !value); setAspectOpen(false); setResolutionOpen(false); }}><SlidersHorizontal size={19}/></button>
          <button
            type="button"
            className={`grok-submit ${busy ? 'busy' : ''}`}
            title={isEdit ? 'Edit image' : modeLabel === 'Video' ? 'Generate video' : 'Generate'}
            aria-label={isEdit ? 'Edit image' : modeLabel === 'Video' ? 'Generate video' : 'Generate'}
            onClick={onGenerate}
            disabled={busy || (isEdit && references.length === 0)}
          ><ArrowUp size={23}/></button>
        </div>
      </div>

      <SettingsPanel
        open={settingsOpen} onClose={() => setSettingsOpen(false)} mode={mode}
        outputs={outputs} setOutputs={setOutputs}
        seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg}
        workflowId={workflowId} setWorkflowId={setWorkflowId} modelId={modelId} setModelId={setModelId}
      />
    </section>

    {error && <div className="composer-error">{error}</div>}
    {isEdit && <div className="backend-status">{jobStatus ? `Job ${jobStatus} · ` : ''}Live backend · FLUX.2 Klein 9B · {editAuto ? `automatic canvas from Image 1 · ${references.length || 0} reference${references.length === 1 ? '' : 's'}` : `${aspect} · ${imageDimensions.width}×${imageDimensions.height} manual canvas · ${references.length || 0} reference${references.length === 1 ? '' : 's'}`}</div>}

    <section className="gallery-grid composer-gallery">{items.map((item) => renderCard(item, false))}</section>
  </>;
}
