import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import {
  ArrowUp, Check, ChevronDown, Clock3, Dice5, Image as ImageIcon, Plus,
  RotateCcw, SlidersHorizontal, Sparkles, Video, Volume2, VolumeX, X,
} from 'lucide-react';
import { setEditSizingPreference } from './generation-client.js';
import './create-workspace-v2.css';

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

const VIDEO_RESOLUTIONS = [
  { value: '480p', label: '480p', detail: 'SD' },
  { value: '720p', label: '720p', detail: 'HD' },
  { value: '1080p', label: '1080p', detail: 'Full HD' },
  { value: '2K', label: '2K', detail: '2048 px' },
  { value: '4K', label: '4K', detail: '3840 px' },
];

const STORAGE_KEY = 'saga-studio:create-settings:v4';

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

const ReferencePrompt = forwardRef(function ReferencePrompt(
  { prompt, setPrompt, references, disabled },
  ref,
) {
  const editorRef = useRef(null);
  const lastRangeRef = useRef(null);

  const rememberSelection = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection?.rangeCount || !selection.isCollapsed || !editor.contains(selection.anchorNode)) return;
    lastRangeRef.current = selection.getRangeAt(0).cloneRange();
  };

  const sync = () => {
    setPrompt(editorText(editorRef.current).slice(0, 2000));
    rememberSelection();
  };

  const insertReference = (referenceIndex) => {
    const editor = editorRef.current;
    const reference = references[referenceIndex];
    if (!editor || !reference) return;
    editor.focus();

    const selection = window.getSelection();
    let range = lastRangeRef.current?.cloneRange();
    if (!range || !editor.contains(range.startContainer)) {
      range = document.createRange();
      range.selectNodeContents(editor);
      range.collapse(false);
    }

    range.deleteContents();
    const mention = createMentionNode(reference, referenceIndex);
    const spacer = document.createTextNode('\u00a0');
    const fragment = document.createDocumentFragment();
    fragment.append(mention, spacer);
    range.insertNode(fragment);

    const next = document.createRange();
    next.setStart(spacer, spacer.textContent.length);
    next.collapse(true);
    selection?.removeAllRanges();
    selection?.addRange(next);
    lastRangeRef.current = next.cloneRange();
    setPrompt(editorText(editor).slice(0, 2000));
  };

  useImperativeHandle(ref, () => ({ insertReference }));

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || document.activeElement === editor) return;
    if (editorText(editor) !== prompt) renderPromptInto(editor, prompt, references);
  }, [prompt, references]);

  return (
    <div className="saga-prompt-shell saga-rich-prompt-shell">
      <div
        ref={editorRef}
        className="saga-rich-prompt"
        contentEditable={!disabled}
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        data-placeholder={references.length ? 'Describe the edit…' : 'Add one or more reference images, then describe the edit…'}
        onInput={sync}
        onKeyUp={rememberSelection}
        onMouseUp={rememberSelection}
        onFocus={rememberSelection}
        onPaste={(event) => {
          event.preventDefault();
          const room = Math.max(0, 2000 - editorText(editorRef.current).length);
          document.execCommand('insertText', false, event.clipboardData.getData('text/plain').slice(0, room));
          requestAnimationFrame(sync);
        }}
      />
    </div>
  );
});

function ReferenceStrip({ references, onRemove, onInsert }) {
  if (!references.length) return null;
  return (
    <div className="saga-reference-strip" aria-label="Reference images">
      {references.map((reference, index) => (
        <div className="saga-reference-chip" key={reference.id}>
          <button
            type="button"
            className="saga-reference-main"
            title={`Insert Image ${index + 1} at cursor`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onInsert(index)}
          >
            <span className="saga-reference-thumb" style={{ backgroundImage: `url(${reference.preview})` }}>
              <b>{index + 1}</b>
            </span>
            <span className="saga-reference-copy">
              <strong>Image {index + 1}</strong>
              <small>{reference.width && reference.height ? `${reference.width}×${reference.height}` : reference.file?.name}</small>
            </span>
          </button>
          <button
            type="button"
            className="saga-reference-remove"
            title={`Remove Image ${index + 1}`}
            onClick={(event) => {
              event.stopPropagation();
              onRemove(index);
            }}
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

function useAnchoredPosition(open, anchorRef, desiredWidth, desiredHeight) {
  const [position, setPosition] = useState(null);

  useEffect(() => {
    if (!open) {
      setPosition(null);
      return undefined;
    }

    const update = () => {
      const anchor = anchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const edge = 12;
      const gap = 8;
      const width = Math.min(desiredWidth, window.innerWidth - edge * 2);
      const height = Math.min(desiredHeight, window.innerHeight - edge * 2);
      const spaceAbove = rect.top - edge - gap;
      const spaceBelow = window.innerHeight - rect.bottom - edge - gap;
      const above = spaceAbove > spaceBelow && spaceAbove >= Math.min(height, 180);
      let top = above ? rect.top - gap - height : rect.bottom + gap;
      top = Math.max(edge, Math.min(top, window.innerHeight - height - edge));
      let left = rect.left;
      left = Math.max(edge, Math.min(left, window.innerWidth - width - edge));
      setPosition({ position: 'fixed', top, left, width, height });
    };

    const frame = requestAnimationFrame(update);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open, anchorRef, desiredWidth, desiredHeight]);

  return position;
}

function useOutsideDismiss(open, refs, close) {
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (refs.some((item) => item.current?.contains(event.target))) return;
      close();
    };
    const onKey = (event) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, refs, close]);
}

function MorphList({ options, value, onChoose, render, ariaLabel, focusWhen = false }) {
  const refs = useRef([]);
  const [hoverIndex, setHoverIndex] = useState(null);
  const activeIndex = Math.max(0, options.findIndex((item) => item.value === value));
  const targetIndex = hoverIndex == null ? activeIndex : hoverIndex;
  const rowHeight = 42;

  useEffect(() => {
    if (!focusWhen) return undefined;
    const timer = window.setTimeout(() => refs.current[activeIndex]?.focus(), 40);
    return () => window.clearTimeout(timer);
  }, [focusWhen, activeIndex, options.length]);

  const keyDown = (event, index) => {
    let next = null;
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % options.length;
    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index - 1 + options.length) % options.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = options.length - 1;
    if (next != null) {
      event.preventDefault();
      refs.current[next]?.focus();
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onChoose(options[index]);
    }
  };

  return (
    <div className="saga-morph-list" role="menu" aria-label={ariaLabel} onMouseLeave={() => setHoverIndex(null)}>
      <span
        className="saga-morph-indicator"
        style={{ transform: `translate3d(0, ${targetIndex * rowHeight}px, 0)`, height: rowHeight }}
      />
      {options.map((option, index) => (
        <button
          ref={(node) => { refs.current[index] = node; }}
          type="button"
          role="menuitemradio"
          aria-checked={option.value === value}
          tabIndex={index === activeIndex ? 0 : -1}
          className={option.value === value ? 'selected' : ''}
          key={option.value}
          onMouseEnter={() => setHoverIndex(index)}
          onFocus={() => setHoverIndex(index)}
          onKeyDown={(event) => keyDown(event, index)}
          onClick={() => onChoose(option)}
        >
          {render(option)}
          {option.value === value && <Check className="saga-option-check" size={15} />}
        </button>
      ))}
    </div>
  );
}

function PickerShell({ open, anchorRef, width, height, className = '', children, onClose }) {
  const popoverRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, width, height);
  useOutsideDismiss(open, [anchorRef, popoverRef], onClose);
  if (!open) return null;
  return (
    <div ref={popoverRef} className={`saga-picker ${className}`} style={position || { visibility: 'hidden' }}>
      {children}
    </div>
  );
}

function AspectPicker({ open, setOpen, anchorRef, aspect, setAspect, editAuto, setEditAuto, autoRatio, autoInfo }) {
  const displayRatio = editAuto ? autoRatio : (ASPECT_PRESETS.find((item) => item.value === aspect)?.ratio || 1);
  const [preview, setPreview] = useState(displayRatio);
  useEffect(() => setPreview(displayRatio), [displayRatio, open]);

  const previewSize = useMemo(() => {
    const max = 84;
    return preview >= 1 ? { width: max, height: max / preview } : { width: max * preview, height: max };
  }, [preview]);

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={420} height={354} className="saga-aspect-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview">
        <div className="saga-preview-grid">
          <span className="saga-preview-shape" style={previewSize} />
        </div>
        <strong>{editAuto ? 'Auto' : aspect}</strong>
        <small>{editAuto ? (autoInfo?.ratioLabel || 'Primary reference canvas') : ASPECT_PRESETS.find((item) => item.value === aspect)?.label}</small>
      </div>
      <MorphList
        focusWhen={open}
        ariaLabel="Aspect ratio"
        options={ASPECT_PRESETS}
        value={editAuto ? '__none__' : aspect}
        onChoose={(option) => {
          setEditAuto(false);
          setAspect(option.value);
          setOpen(false);
        }}
        render={(option) => (
          <>
            <span className="saga-option-key">{option.value}</span>
            <span className="saga-option-label">{option.label}</span>
          </>
        )}
      />
    </PickerShell>
  );
}

function ResolutionPicker({
  open, setOpen, anchorRef, imageResolution, setImageResolution, aspect,
  editAuto, setEditAuto, autoInfo,
}) {
  const autoDimensions = parseAutoDimensions(autoInfo?.detail);
  const [previewValue, setPreviewValue] = useState(Number(imageResolution));
  useEffect(() => setPreviewValue(Number(imageResolution)), [imageResolution, open]);
  const dimensions = editAuto ? autoDimensions : dimensionsForPreset(aspect, previewValue);

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={410} height={282} className="saga-resolution-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview saga-resolution-preview">
        <div className="saga-resolution-cube">{editAuto ? <Sparkles size={20} /> : previewValue}</div>
        <strong>{editAuto ? 'Auto' : IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution))?.label}</strong>
        <small>{editAuto ? autoInfo?.detail : dimensions ? `${dimensions.width}×${dimensions.height}` : ''}</small>
      </div>
      <MorphList
        focusWhen={open}
        ariaLabel="Resolution"
        options={IMAGE_RESOLUTIONS}
        value={editAuto ? '__none__' : Number(imageResolution)}
        onChoose={(option) => {
          setEditAuto(false);
          setImageResolution(option.value);
          setOpen(false);
        }}
        render={(option) => (
          <>
            <span className="saga-option-label">{option.label}</span>
            <span className="saga-option-detail">{option.detail}</span>
          </>
        )}
      />
    </PickerShell>
  );
}

function VideoResolutionPicker({ open, setOpen, anchorRef, value, setValue }) {
  return (
    <PickerShell open={open} anchorRef={anchorRef} width={310} height={238} onClose={() => setOpen(false)}>
      <MorphList
        focusWhen={open}
        ariaLabel="Video resolution"
        options={VIDEO_RESOLUTIONS}
        value={value}
        onChoose={(option) => {
          setValue(option.value);
          setOpen(false);
        }}
        render={(option) => (
          <>
            <span className="saga-option-label">{option.label}</span>
            <span className="saga-option-detail">{option.detail}</span>
          </>
        )}
      />
    </PickerShell>
  );
}

function DurationPicker({ open, setOpen, anchorRef, value, setValue }) {
  const popoverRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, 330, 196);
  useOutsideDismiss(open, [anchorRef, popoverRef], () => setOpen(false));
  if (!open) return null;
  const commit = (next) => setValue(Math.max(5, Math.min(30, Math.round(Number(next) || 5))));
  return (
    <div ref={popoverRef} className="saga-picker saga-duration-picker" style={position || { visibility: 'hidden' }}>
      <div className="saga-duration-head">
        <div><strong>Duration</strong><small>5–30 seconds</small></div>
        <label><input type="number" min="5" max="30" value={value} onChange={(event) => commit(event.target.value)} /><span>s</span></label>
      </div>
      <input
        className="saga-duration-range"
        aria-label="Video duration"
        type="range"
        min="5"
        max="30"
        step="1"
        value={value}
        onChange={(event) => commit(event.target.value)}
      />
      <div className="saga-duration-presets">
        {[5, 10, 15, 20, 25, 30].map((seconds) => (
          <button type="button" className={seconds === value ? 'selected' : ''} onClick={() => commit(seconds)} key={seconds}>{seconds}s</button>
        ))}
      </div>
    </div>
  );
}

function FancySelect({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useOutsideDismiss(open, [rootRef], () => setOpen(false));
  const selected = options.find((item) => String(item.value) === String(value)) || options[0];

  return (
    <div className={`saga-fancy-select ${open ? 'open' : ''}`} ref={rootRef}>
      <button type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <span>{selected?.label}</span><ChevronDown size={15} />
      </button>
      {open && (
        <div className="saga-fancy-options" role="listbox" aria-label={label}>
          {options.map((option) => (
            <button
              type="button"
              role="option"
              aria-selected={String(option.value) === String(value)}
              key={option.value}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <span>{option.label}</span>
              {String(option.value) === String(value) && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RangeField({ label, help, value, onChange, min, max, step, decimals = 0 }) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : min;
  const commit = (raw) => {
    const next = Math.max(min, Math.min(max, Number(raw)));
    if (Number.isFinite(next)) onChange(Number(next.toFixed(decimals)));
  };
  return (
    <div className="saga-advanced-range">
      <div className="saga-advanced-range-head">
        <div><strong>{label}</strong><small>{help}</small></div>
        <input aria-label={`${label} value`} type="number" min={min} max={max} step={step} value={safe} onChange={(event) => commit(event.target.value)} />
      </div>
      <input aria-label={label} type="range" min={min} max={max} step={step} value={safe} onChange={(event) => commit(event.target.value)} />
      <div className="saga-range-scale"><span>{min}</span><span>{max}</span></div>
    </div>
  );
}

function AdvancedSettings({
  open, onClose, anchorRef, mode, outputs, setOutputs, seed, setSeed, steps, setSteps,
  cfg, setCfg, workflowId, setWorkflowId, modelId, setModelId,
}) {
  const panelRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, 430, 610);
  useOutsideDismiss(open, [anchorRef, panelRef], onClose);
  if (!open) return null;
  const isEdit = mode === 'Edit';
  const isVideo = mode === 'Video';
  const modelOptions = isEdit
    ? [{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B · DarkBeast V2' }]
    : isVideo
      ? [{ value: 'saga-video-auto', label: 'SAGA Video · Auto' }]
      : [{ value: 'saga-image-auto', label: 'SAGA Image · Auto' }];
  const workflowOptions = isEdit
    ? [{ value: 'flux2-klein-image-edit', label: 'Klein Multi-Reference Edit' }]
    : isVideo
      ? [{ value: 'video-planned', label: 'Video workflow · planned' }]
      : [{ value: 'default-image', label: 'Default Image' }];

  return (
    <div ref={panelRef} className="saga-advanced-panel" style={position || { visibility: 'hidden' }} role="dialog" aria-label="Advanced settings">
      <header>
        <div>
          <span>GENERATION CONTROLS</span>
          <h2>Advanced</h2>
          <p>Fine-tune sampling and execution without duplicating canvas controls.</p>
        </div>
        <button type="button" aria-label="Close advanced settings" onClick={onClose}><X size={17} /></button>
      </header>

      <div className="saga-advanced-body">
        <div className="saga-advanced-top">
          <label><span>MODEL</span><FancySelect label="Model" value={modelId} options={modelOptions} onChange={setModelId} /></label>
          {!isEdit && !isVideo && (
            <label><span>OUTPUTS</span><FancySelect label="Outputs" value={outputs} options={[1, 2, 4].map((n) => ({ value: n, label: `${n} output${n === 1 ? '' : 's'}` }))} onChange={(v) => setOutputs(Number(v))} /></label>
          )}
        </div>

        <section className="saga-advanced-card">
          <div className="saga-card-title"><strong>Sampling</strong><small>Precise controls for reproducibility.</small></div>
          <div className="saga-seed-row">
            <div><strong>Seed</strong><small>Reuse a seed to reproduce a result.</small></div>
            <div className="saga-seed-input">
              <input aria-label="Seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} />
              <button type="button" aria-label="Random seed" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={15} /></button>
            </div>
          </div>
          <RangeField label="Steps" help="Sampling iterations" value={steps} onChange={setSteps} min={1} max={50} step={1} />
          <RangeField label="CFG" help="Prompt guidance strength" value={cfg} onChange={setCfg} min={0} max={20} step={0.1} decimals={1} />
        </section>

        <section className="saga-advanced-card">
          <div className="saga-card-title"><strong>Execution</strong><small>Backend path for this mode.</small></div>
          <FancySelect label="Workflow" value={workflowOptions.some((o) => o.value === workflowId) ? workflowId : workflowOptions[0].value} options={workflowOptions} onChange={setWorkflowId} />
          {isVideo && <p className="saga-planned-note">Video controls are ready for the upcoming production workflow; no backend capability is being simulated here.</p>}
        </section>

        <button
          type="button"
          className="saga-reset"
          onClick={() => {
            setOutputs(isEdit ? 1 : 4);
            setSeed('42');
            setSteps(isEdit ? 4 : 30);
            setCfg(isEdit ? 1 : 7);
            setWorkflowId(isEdit ? 'flux2-klein-image-edit' : isVideo ? 'video-planned' : 'default-image');
            setModelId(isEdit ? 'flux2-klein-9b' : isVideo ? 'saga-video-auto' : 'saga-image-auto');
          }}
        >
          <RotateCcw size={16} /> Reset advanced settings
        </button>
      </div>
    </div>
  );
}

function MediaModeToggle({ mode, setMode }) {
  const visualMode = mode === 'Video' ? 'Video' : 'Image';
  return (
    <div className="saga-media-toggle" role="group" aria-label="Media mode">
      <button type="button" className={visualMode === 'Image' ? 'selected' : ''} aria-pressed={visualMode === 'Image'} onClick={() => setMode('Image')}>
        <ImageIcon size={16} /><span>Image</span>
      </button>
      <button type="button" className={visualMode === 'Video' ? 'selected' : ''} aria-pressed={visualMode === 'Video'} onClick={() => setMode('Video')}>
        <Video size={16} /><span>Video</span>
      </button>
    </div>
  );
}

function OutputWall({ items, renderCard }) {
  return (
    <section className="saga-output-wall" aria-label="Generation outputs">
      {items.map((item, index) => (
        <div className={`saga-output-slot saga-output-slot-${index % 6}`} key={item.id}>
          {renderCard(item, false)}
        </div>
      ))}
    </section>
  );
}

export default function CreateWorkspace({
  mode, setMode, prompt, setPrompt, references, onAddReferences, onRemoveReference,
  error, jobStatus, busy, onGenerate, items, renderCard,
  aspect, setAspect, imageResolution, setImageResolution, outputs, setOutputs,
  seed, setSeed, steps, setSteps, cfg, setCfg,
  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,
}) {
  const isEdit = mode === 'Edit';
  const isVideo = mode === 'Video';
  const referenceInputRef = useRef(null);
  const promptRef = useRef(null);
  const resolutionButtonRef = useRef(null);
  const aspectButtonRef = useRef(null);
  const videoResolutionButtonRef = useRef(null);
  const durationButtonRef = useRef(null);
  const settingsButtonRef = useRef(null);

  const [resolutionOpen, setResolutionOpen] = useState(false);
  const [aspectOpen, setAspectOpen] = useState(false);
  const [videoResolutionOpen, setVideoResolutionOpen] = useState(false);
  const [durationOpen, setDurationOpen] = useState(false);
  const [editAuto, setEditAuto] = useState(true);
  const [videoResolution, setVideoResolution] = useState('1080p');
  const [videoDuration, setVideoDuration] = useState(10);
  const [videoAudio, setVideoAudio] = useState(true);
  const [preferencesReady, setPreferencesReady] = useState(false);
  const autoBaselineRef = useRef(null);

  const imageOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];
  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;
  const imageDimensions = dimensionsForPreset(aspect, Number(imageResolution));
  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : mode === 'More' ? 'More creation tools' : 'Imagine worlds';

  useEffect(() => {
    if (autoEditInfo) autoBaselineRef.current = { ...autoEditInfo };
  }, [autoEditInfo]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      const savedMode = ['Image', 'Video', 'More'].includes(saved.mode) ? saved.mode : 'Image';
      setMode(savedMode);
      if (ASPECT_PRESETS.some((item) => item.value === saved.aspect)) setAspect(saved.aspect);
      if (IMAGE_RESOLUTIONS.some((item) => item.value === Number(saved.imageResolution))) setImageResolution(Number(saved.imageResolution));
      if ([1, 2, 4].includes(Number(saved.outputs))) setOutputs(Number(saved.outputs));
      if (saved.seed != null) setSeed(String(saved.seed));
      if (Number.isFinite(Number(saved.steps))) setSteps(Math.max(1, Math.min(50, Number(saved.steps))));
      if (Number.isFinite(Number(saved.cfg))) setCfg(Math.max(0, Math.min(20, Number(saved.cfg))));
      if (typeof saved.workflowId === 'string') setWorkflowId(saved.workflowId);
      if (typeof saved.modelId === 'string') setModelId(saved.modelId);
      if (typeof saved.editAuto === 'boolean') setEditAuto(saved.editAuto);
      if (VIDEO_RESOLUTIONS.some((item) => item.value === saved.videoResolution)) setVideoResolution(saved.videoResolution);
      if (Number.isFinite(Number(saved.videoDuration))) setVideoDuration(Math.max(5, Math.min(30, Math.round(Number(saved.videoDuration)))));
      if (typeof saved.videoAudio === 'boolean') setVideoAudio(saved.videoAudio);
    } catch {
      // Ignore malformed local preferences.
    } finally {
      setPreferencesReady(true);
    }
  }, []);

  useEffect(() => {
    if (!preferencesReady) return;
    const persistedMode = isEdit ? 'Image' : mode;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      mode: persistedMode,
      aspect,
      imageResolution: Number(imageResolution),
      outputs: Number(outputs),
      seed,
      steps: Number(steps),
      cfg: Number(cfg),
      workflowId: isEdit ? 'default-image' : workflowId,
      modelId: isEdit ? 'saga-image-auto' : modelId,
      editAuto,
      videoResolution,
      videoDuration,
      videoAudio,
    }));
  }, [
    preferencesReady, mode, isEdit, aspect, imageResolution, outputs, seed, steps, cfg,
    workflowId, modelId, editAuto, videoResolution, videoDuration, videoAudio,
  ]);

  useEffect(() => {
    if (!isEdit) return;
    const baseline = autoBaselineRef.current;
    if (autoEditInfo && baseline) {
      if (editAuto) Object.assign(autoEditInfo, baseline);
      else {
        const manual = dimensionsForPreset(aspect, Number(imageResolution));
        Object.assign(autoEditInfo, {
          megapixels: Math.max(0.25, Math.min(4, (manual.width * manual.height) / 1_000_000)),
          detail: `${manual.width} × ${manual.height} · Manual`,
          ratioLabel: `${aspect} manual canvas`,
        });
      }
    }
    setEditSizingPreference({ mode: editAuto ? 'auto' : 'manual', aspect, resolution: Number(imageResolution) });
  }, [isEdit, editAuto, aspect, imageResolution, autoEditInfo]);

  useEffect(() => {
    setAspectOpen(false);
    setResolutionOpen(false);
    setVideoResolutionOpen(false);
    setDurationOpen(false);
    setSettingsOpen(false);
  }, [mode]);

  const addReferenceFiles = (files) => {
    if (!files.length) return;
    onAddReferences(files);
    setAspectOpen(false);
    setResolutionOpen(false);
    setVideoResolutionOpen(false);
    setDurationOpen(false);
    setSettingsOpen(false);
  };

  if (mode === 'More') {
    return (
      <div className="saga-create-stage">
        <div className="saga-stage-heading"><span>STUDIO</span><h1>{heading}</h1><p>Additional creation workflows will live here without crowding the core Image and Video composer.</p></div>
        <section className="saga-more-panel"><Sparkles size={24} /><div><strong>More tools</strong><p>Choose Create in the sidebar to return to the Image composer.</p></div></section>
      </div>
    );
  }

  return (
    <>
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

      <div className="saga-create-stage">
        <div className="saga-stage-heading">
          <span>{isEdit ? 'EDIT' : isVideo ? 'VIDEO' : 'CREATE'}</span>
          <h1>{heading}</h1>
          <p>{isEdit ? 'Click a reference to insert it exactly where your cursor is.' : isVideo ? 'Shape the shot, duration, resolution, and audio before generation.' : 'Describe an image, choose the canvas, and iterate.'}</p>
        </div>

        <section className={`saga-composer ${isEdit ? 'is-edit' : ''} ${isVideo ? 'is-video' : ''}`}>
          {isEdit && (
            <ReferenceStrip
              references={references}
              onRemove={onRemoveReference}
              onInsert={(index) => promptRef.current?.insertReference(index)}
            />
          )}

          {isEdit ? (
            <ReferencePrompt ref={promptRef} prompt={prompt} setPrompt={setPrompt} references={references} disabled={busy} />
          ) : (
            <div className="saga-prompt-shell">
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder={isVideo ? 'Describe the scene, motion, and camera movement…' : 'Type to imagine'}
                maxLength={2000}
                disabled={busy}
              />
            </div>
          )}

          <div className="saga-toolbar">
            <div className="saga-toolbar-left">
              <button type="button" className="saga-round-button" title="Upload reference images" aria-label="Upload reference images" onClick={() => referenceInputRef.current?.click()}>
                <Plus size={21} />
              </button>

              <MediaModeToggle mode={mode} setMode={setMode} />

              {isEdit && (
                <button
                  type="button"
                  className={`saga-auto-toggle ${editAuto ? 'active' : ''}`}
                  aria-pressed={editAuto}
                  onClick={() => setEditAuto((current) => !current)}
                >
                  <Sparkles size={15} /><span>Auto</span>
                </button>
              )}

              {!isVideo ? (
                <>
                  <button
                    ref={resolutionButtonRef}
                    type="button"
                    className={`saga-control-pill saga-resolution-trigger ${resolutionOpen ? 'active' : ''}`}
                    aria-haspopup="menu"
                    aria-expanded={resolutionOpen}
                    onClick={() => {
                      setResolutionOpen((current) => !current);
                      setAspectOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    <span className="saga-resolution-badge">{isEdit && editAuto ? 'A' : Number(imageResolution)}</span>
                    <span>{isEdit && editAuto ? 'Auto' : imageOption.label}</span>
                    <ChevronDown size={13} />
                  </button>

                  <button
                    ref={aspectButtonRef}
                    type="button"
                    className={`saga-control-pill ${aspectOpen ? 'active' : ''}`}
                    aria-haspopup="menu"
                    aria-expanded={aspectOpen}
                    onClick={() => {
                      setAspectOpen((current) => !current);
                      setResolutionOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    <span className="saga-aspect-icon" style={{ aspectRatio: String(isEdit && editAuto ? primaryRatio : (ASPECT_PRESETS.find((item) => item.value === aspect)?.ratio || 1)) }} />
                    <span>{isEdit && editAuto ? 'Auto' : aspect}</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    ref={videoResolutionButtonRef}
                    type="button"
                    className={`saga-control-pill ${videoResolutionOpen ? 'active' : ''}`}
                    aria-haspopup="menu"
                    aria-expanded={videoResolutionOpen}
                    onClick={() => {
                      setVideoResolutionOpen((current) => !current);
                      setDurationOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    <Video size={15} /><span>{videoResolution}</span><ChevronDown size={13} />
                  </button>

                  <button
                    ref={durationButtonRef}
                    type="button"
                    className={`saga-control-pill ${durationOpen ? 'active' : ''}`}
                    aria-haspopup="dialog"
                    aria-expanded={durationOpen}
                    onClick={() => {
                      setDurationOpen((current) => !current);
                      setVideoResolutionOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    <Clock3 size={15} /><span>{videoDuration}s</span><ChevronDown size={13} />
                  </button>

                  <button
                    type="button"
                    className={`saga-audio-toggle ${videoAudio ? 'active' : ''}`}
                    aria-pressed={videoAudio}
                    title={videoAudio ? 'Audio enabled' : 'Audio disabled'}
                    onClick={() => setVideoAudio((current) => !current)}
                  >
                    {videoAudio ? <Volume2 size={17} /> : <VolumeX size={17} />}
                    <span>{videoAudio ? 'Audio' : 'Muted'}</span>
                  </button>
                </>
              )}
            </div>

            <div className="saga-toolbar-right">
              <span className="saga-prompt-count">{prompt.length} / 2000</span>
              <button
                ref={settingsButtonRef}
                type="button"
                className={`saga-settings-button ${settingsOpen ? 'active' : ''}`}
                title="Advanced settings"
                aria-label="Advanced settings"
                onClick={() => {
                  setSettingsOpen((current) => !current);
                  setAspectOpen(false);
                  setResolutionOpen(false);
                  setVideoResolutionOpen(false);
                  setDurationOpen(false);
                }}
              >
                <SlidersHorizontal size={18} />
              </button>
              <button
                type="button"
                className="saga-submit"
                title={isEdit ? 'Edit image' : isVideo ? 'Generate video' : 'Generate image'}
                aria-label={isEdit ? 'Edit image' : isVideo ? 'Generate video' : 'Generate image'}
                onClick={onGenerate}
                disabled={busy || (isEdit && references.length === 0)}
              >
                <ArrowUp size={21} />
              </button>
            </div>
          </div>
        </section>

        {error && <div className="saga-composer-error">{error}</div>}
        {isEdit && (
          <div className="saga-backend-status">
            {jobStatus ? `Job ${jobStatus} · ` : ''}Live backend · FLUX.2 Klein 9B · {editAuto ? 'Auto canvas' : `${aspect} · ${imageDimensions.width}×${imageDimensions.height}`} · {references.length} reference{references.length === 1 ? '' : 's'}
          </div>
        )}

        <ResolutionPicker
          open={resolutionOpen}
          setOpen={setResolutionOpen}
          anchorRef={resolutionButtonRef}
          imageResolution={imageResolution}
          setImageResolution={setImageResolution}
          aspect={aspect}
          editAuto={isEdit && editAuto}
          setEditAuto={isEdit ? setEditAuto : () => {}}
          autoInfo={autoEditInfo}
        />
        <AspectPicker
          open={aspectOpen}
          setOpen={setAspectOpen}
          anchorRef={aspectButtonRef}
          aspect={aspect}
          setAspect={setAspect}
          editAuto={isEdit && editAuto}
          setEditAuto={isEdit ? setEditAuto : () => {}}
          autoRatio={primaryRatio}
          autoInfo={autoEditInfo}
        />
        <VideoResolutionPicker
          open={videoResolutionOpen}
          setOpen={setVideoResolutionOpen}
          anchorRef={videoResolutionButtonRef}
          value={videoResolution}
          setValue={setVideoResolution}
        />
        <DurationPicker
          open={durationOpen}
          setOpen={setDurationOpen}
          anchorRef={durationButtonRef}
          value={videoDuration}
          setValue={setVideoDuration}
        />
        <AdvancedSettings
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          anchorRef={settingsButtonRef}
          mode={mode}
          outputs={outputs}
          setOutputs={setOutputs}
          seed={seed}
          setSeed={setSeed}
          steps={steps}
          setSteps={setSteps}
          cfg={cfg}
          setCfg={setCfg}
          workflowId={workflowId}
          setWorkflowId={setWorkflowId}
          modelId={modelId}
          setModelId={setModelId}
        />

        <OutputWall items={items} renderCard={renderCard} />
      </div>
    </>
  );
}
