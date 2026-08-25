import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowUp, Check, ChevronDown, Clock3, Dice5, Image as ImageIcon, Plus,
  RotateCcw, SlidersHorizontal, Sparkles, Video, Volume2, VolumeX, X,
} from 'lucide-react';
import { setEditSizingPreference } from './generation-client.js';
import { AspectPicker, ASPECT_PRESETS } from './features/create/AspectPicker.jsx';
import {
  IMAGE_RESOLUTIONS, VIDEO_RESOLUTIONS, dimensionsForPreset, formatDimensions, videoDeliveryDimensions,
} from './features/create/ResolutionPresets.js';
import { advancedPresetForMode } from './features/create/model-presets.js';
import './create-workspace-v2.css';

export { IMAGE_RESOLUTIONS, dimensionsForPreset };

const STORAGE_KEY = 'saga-studio:create-settings:v6';

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
            title={onInsert ? `Insert Image ${index + 1} at cursor` : `Image ${index + 1} video reference`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onInsert?.(index)}
            disabled={!onInsert}
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

function useOutsideDismiss(open, refs, close, returnFocusRef = null, protectNestedEscape = false) {
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (refs.some((item) => item.current?.contains(event.target))) return;
      close();
    };
    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      if (protectNestedEscape && refs.some((item) => item.current?.querySelector?.('[aria-expanded=\"true\"]'))) return;
      event.preventDefault();
      event.stopPropagation();
      close();
      returnFocusRef?.current?.focus();
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, refs, close, returnFocusRef, protectNestedEscape]);
}

function MorphList({ options, value, onChoose, render, ariaLabel, focusWhen = false, onPreview }) {
  const refs = useRef([]);
  const [hoverIndex, setHoverIndex] = useState(null);
  const activeIndex = Math.max(0, options.findIndex((item) => item.value === value));
  const targetIndex = hoverIndex == null ? activeIndex : hoverIndex;
  const rowHeight = 32;

  useEffect(() => {
    if (!focusWhen) return undefined;
    const timer = window.setTimeout(() => refs.current[activeIndex]?.focus(), 40);
    return () => window.clearTimeout(timer);
  }, [focusWhen, activeIndex, options.length]);

  const previewAt = (index) => {
    setHoverIndex(index);
    onPreview?.(options[index]);
  };

  const resetPreview = () => {
    setHoverIndex(null);
    onPreview?.(null);
  };

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
    <div className="saga-morph-list" role="menu" aria-label={ariaLabel} onMouseLeave={resetPreview}>
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
          onMouseEnter={() => previewAt(index)}
          onFocus={() => previewAt(index)}
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
  useOutsideDismiss(open, [anchorRef, popoverRef], onClose, anchorRef);
  if (!open) return null;
  return (
    <div
      ref={popoverRef}
      className={`saga-picker ${className}`}
      style={position || { visibility: 'hidden' }}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (!next || popoverRef.current?.contains(next) || anchorRef.current?.contains(next)) return;
        onClose();
      }}
    >
      {children}
    </div>
  );
}

function ResolutionPicker({
  open, setOpen, anchorRef, imageResolution, setImageResolution, aspect,
  editAuto, setEditAuto, autoInfo,
}) {
  const autoDimensions = parseAutoDimensions(autoInfo?.detail);
  const selectedOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];
  const [previewValue, setPreviewValue] = useState(Number(selectedOption.value));
  useEffect(() => setPreviewValue(Number(selectedOption.value)), [selectedOption.value, open]);
  const previewOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(previewValue)) || selectedOption;
  const dimensions = editAuto ? autoDimensions : dimensionsForPreset(aspect, previewValue);

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className="saga-resolution-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview saga-resolution-preview">
        <div className="saga-resolution-cube">{editAuto ? <Sparkles size={20} /> : previewValue}</div>
        <strong>{editAuto ? 'Auto' : previewOption.label}</strong>
        <small>{editAuto ? autoInfo?.detail : dimensions ? `${formatDimensions(dimensions)} at ${aspect}` : ''}</small>
      </div>
      <MorphList
        focusWhen={open}
        onPreview={(option) => setPreviewValue(option ? Number(option.value) : Number(selectedOption.value))}
        ariaLabel="Resolution"
        options={IMAGE_RESOLUTIONS}
        value={editAuto ? '__none__' : Number(imageResolution)}
        onChoose={(option) => {
          setEditAuto(false);
          setImageResolution(option.value);
          setOpen(false);
          anchorRef.current?.focus();
        }}
        render={(option) => {
          const optionDimensions = dimensionsForPreset(aspect, Number(option.value));
          return (
            <>
              <span className="saga-option-label">{option.label}</span>
              <span className="saga-option-detail">{formatDimensions(optionDimensions)}</span>
            </>
          );
        }}
      />
    </PickerShell>
  );
}

function VideoResolutionPicker({ open, setOpen, anchorRef, value, setValue, aspect }) {
  const selectedOption = VIDEO_RESOLUTIONS.find((item) => item.value === value) || VIDEO_RESOLUTIONS[2];
  const [previewValue, setPreviewValue] = useState(selectedOption.value);
  useEffect(() => setPreviewValue(selectedOption.value), [selectedOption.value, open]);
  const previewOption = VIDEO_RESOLUTIONS.find((item) => item.value === previewValue) || selectedOption;
  const previewDimensions = videoDeliveryDimensions(previewOption.value, aspect);

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className="saga-video-resolution-picker saga-resolution-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview saga-resolution-preview">
        <div className="saga-resolution-cube">{previewOption.label}</div>
        <strong>{previewOption.label}</strong>
        <small>{formatDimensions(previewDimensions)} at {aspect}</small>
      </div>
      <MorphList
        focusWhen={open}
        onPreview={(option) => setPreviewValue(option?.value ?? selectedOption.value)}
        ariaLabel="Video resolution"
        options={VIDEO_RESOLUTIONS}
        value={value}
        onChoose={(option) => {
          setValue(option.value);
          setOpen(false);
          anchorRef.current?.focus();
        }}
        render={(option) => {
          const optionDimensions = videoDeliveryDimensions(option.value, aspect);
          return (
            <>
              <span className="saga-option-label">{option.label}</span>
              <span className="saga-option-detail">{formatDimensions(optionDimensions)}</span>
            </>
          );
        }}
      />
    </PickerShell>
  );
}

function DurationPicker({ open, setOpen, anchorRef, value, setValue }) {
  const popoverRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, 330, 196);
  useOutsideDismiss(open, [anchorRef, popoverRef], () => setOpen(false), anchorRef);
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
  const [menuWidth, setMenuWidth] = useState(220);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const popoverRef = useRef(null);
  const optionRefs = useRef([]);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const selected = options[selectedIndex] || options[0];
  const menuHeight = Math.min(260, Math.max(46, options.length * 34 + 10));
  const position = useAnchoredPosition(open, triggerRef, menuWidth, menuHeight);

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  const openMenu = (focusIndex = selectedIndex) => {
    const width = triggerRef.current?.getBoundingClientRect().width;
    setMenuWidth(Math.max(180, Math.round(width || 220)));
    setOpen(true);
    window.setTimeout(() => optionRefs.current[focusIndex]?.focus(), 0);
  };

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);

  const move = (index) => {
    const normalized = (index + options.length) % options.length;
    optionRefs.current[normalized]?.focus();
  };

  const handleOptionKeyDown = (event, index) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
    else if (event.key === 'Home') { event.preventDefault(); move(0); }
    else if (event.key === 'End') { event.preventDefault(); move(options.length - 1); }
    else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); }
    else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onChange(options[index].value);
      close(true);
    } else if (event.key === 'Tab') close(false);
  };

  const menu = open && typeof document !== 'undefined' ? createPortal(
    <div
      ref={popoverRef}
      className="saga-fancy-options saga-fancy-options-portal"
      role="listbox"
      aria-label={label}
      style={{ position: 'fixed', top: position.top, left: position.left, width: position.width, height: 'auto', maxHeight: position.height }}
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          ref={(node) => { optionRefs.current[index] = node; }}
          type="button"
          role="option"
          aria-selected={option.value === value}
          onKeyDown={(event) => handleOptionKeyDown(event, index)}
          onClick={() => { onChange(option.value); close(true); }}
        >
          <span>{option.label}</span>{option.value === value && <Check size={14} />}
        </button>
      ))}
    </div>,
    document.body,
  ) : null;

  return (
    <div
      className={`saga-fancy-select ${open ? 'open' : ''}`}
      ref={rootRef}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next && (rootRef.current?.contains(next) || popoverRef.current?.contains(next))) return;
        if (open) close(false);
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            openMenu(event.key === 'ArrowUp' ? options.length - 1 : selectedIndex);
          } else if (event.key === 'Escape' && open) {
            event.preventDefault();
            event.stopPropagation();
            close(true);
          }
        }}
        onClick={() => open ? close(false) : openMenu(selectedIndex)}
      >
        <span>{selected?.label}</span><ChevronDown size={14} />
      </button>
      {menu}
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
  cfg, setCfg, negativePrompt, setNegativePrompt, workflowId, setWorkflowId, modelId, setModelId,
  videoAutoAspect, setVideoAutoAspect, videoManualAspect, setVideoManualAspect,
  videoAspect, videoReferenceInfo, videoFrameRate, setVideoFrameRate,
}) {
  const panelRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, 450, 690);
  useOutsideDismiss(open, [anchorRef, panelRef], onClose, anchorRef, true);
  if (!open) return null;
  const isEdit = mode === 'Edit';
  const isVideo = mode === 'Video';
  const preset = advancedPresetForMode(mode);

  return (
    <div ref={panelRef} className="saga-advanced-panel" style={position || { visibility: 'hidden' }} role="dialog" aria-label="Advanced settings">
      <header>
        <div>
          <span>GENERATION CONTROLS</span>
          <h2>Advanced</h2>
          <p>{preset ? 'Model-aware defaults with controls that reach the production worker.' : 'Advanced controls appear only for connected production workflows.'}</p>
        </div>
        <button type="button" aria-label="Close advanced settings" onClick={onClose}><X size={17} /></button>
      </header>

      <div className="saga-advanced-body">
        {preset ? (
          <>
            <div className="saga-advanced-runtime" aria-label="Active production model">
              <div><span>MODEL</span><strong>{preset.modelLabel}</strong></div>
              <div><span>WORKFLOW</span><strong>{preset.workflowLabel}</strong></div>
            </div>

            <section className="saga-advanced-card">
              <div className="saga-card-title"><strong>Sampling</strong><small>Defaults are tuned per production model.</small></div>
              <div className="saga-seed-row">
                <div><strong>Seed</strong><small>Reuse a seed to reproduce a result.</small></div>
                <div className="saga-seed-input">
                  <input aria-label="Seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} />
                  <button type="button" aria-label="Random seed" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={15} /></button>
                </div>
              </div>
              <label className="saga-negative-prompt">
                <span><strong>Negative prompt</strong><small>Tell the active workflow what to avoid.</small></span>
                <textarea
                  value={negativePrompt}
                  onChange={(event) => setNegativePrompt(event.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder="Optional exclusions…"
                  aria-label="Negative prompt"
                />
              </label>
              {preset.stepsEditable ? (
                <RangeField label="Steps" help="Sampling iterations" value={steps} onChange={setSteps} min={1} max={50} step={1} />
              ) : (
                <div className="saga-fixed-setting" data-ltx-fixed-steps="11">
                  <div><strong>Steps</strong><small>Fixed distilled two-stage schedule</small></div>
                  <span>11</span>
                </div>
              )}
              <RangeField label="CFG" help={isVideo ? 'Distilled default is 1.0' : 'Prompt guidance strength'} value={cfg} onChange={setCfg} min={0} max={20} step={0.1} decimals={1} />
            </section>

            {isVideo && (
              <section className="saga-advanced-card saga-video-advanced-output">
                <div className="saga-card-title"><strong>Video output</strong><small>Canvas and timing controls sent to LTX.</small></div>
                <div className="saga-advanced-control-field">
                  <span>ASPECT RATIO</span>
                  <AspectPicker
                    ariaLabel="Video aspect"
                    triggerPrefix="Aspect"
                    value={videoManualAspect}
                    onValueChange={(value) => {
                      setVideoManualAspect(value);
                      setVideoAutoAspect(false);
                    }}
                    autoSelected={videoAutoAspect}
                    onAutoChoose={() => setVideoAutoAspect(true)}
                    effectiveValue={videoAspect}
                    effectiveRatio={videoReferenceInfo?.ratio || undefined}
                    autoDetail={videoReferenceInfo?.fromReference
                      ? `${videoReferenceInfo.value} · From reference`
                      : '16:9 · Follows reference when attached'}
                    fromReference={videoAutoAspect && Boolean(videoReferenceInfo?.fromReference)}
                  />
                </div>
                <label className="saga-advanced-control-field">
                  <span>FRAME RATE</span>
                  <FancySelect
                    label="Video frame rate"
                    value={videoFrameRate}
                    options={[24, 25, 30].map((fps) => ({ value: fps, label: `${fps} fps` }))}
                    onChange={(value) => setVideoFrameRate(Number(value))}
                  />
                </label>
              </section>
            )}

            <button
              type="button"
              className="saga-reset"
              onClick={() => {
                setSeed(preset.seed);
                setSteps(preset.steps);
                setCfg(preset.cfg);
                setNegativePrompt(preset.negativePrompt || '');
                setWorkflowId(preset.workflowId);
                setModelId(preset.modelId);
                if (isVideo) {
                  setVideoAutoAspect(true);
                  setVideoManualAspect('16:9');
                  setVideoFrameRate(24);
                }
              }}
            >
              <RotateCcw size={16} /> Reset to {isVideo ? 'LTX' : 'FLUX'} defaults
            </button>
          </>
        ) : (
          <section className="saga-advanced-card saga-advanced-unavailable">
            <div className="saga-card-title"><strong>No production image workflow connected</strong></div>
            <p>Original image generation is not live yet, so Studio does not expose sampling controls that would have no backend effect. Add a reference image to use FLUX.2 Klein editing, or switch to Video for LTX.</p>
          </section>
        )}
      </div>
    </div>
  );
}

function MediaModeToggle({ mode, setMode }) {
  const visualMode = mode === 'Video' ? 'Video' : 'Image';
  return (
    <div className="saga-media-toggle" role="group" aria-label="Media mode">
      <button type="button" className={visualMode === 'Image' ? 'selected' : ''} aria-pressed={visualMode === 'Image'} onClick={() => { if (visualMode !== 'Image') setMode('Image'); }}>
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
  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,
  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,
  videoAspect = '16:9', composerStatusSlot = null,
  videoAutoAspect = true, setVideoAutoAspect = () => {}, videoManualAspect = '16:9', setVideoManualAspect = () => {},
  videoReferenceInfo = null, videoFrameRate = 24, setVideoFrameRate = () => {},
}) {
  const isEdit = mode === 'Edit';
  const isVideo = mode === 'Video';
  const isImageSetup = mode === 'Image';
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
  const videoOption = VIDEO_RESOLUTIONS.find((item) => item.value === videoResolution) || VIDEO_RESOLUTIONS[2];
  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;
  const imageDimensions = dimensionsForPreset(aspect, Number(imageResolution));
  const videoDimensions = videoDeliveryDimensions(videoResolution, videoAspect);
  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Create from a reference';

  useEffect(() => {
    if (autoEditInfo) autoBaselineRef.current = { ...autoEditInfo };
  }, [autoEditInfo]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      const savedMode = ['Image', 'Video'].includes(saved.mode) ? saved.mode : 'Image';
      setMode(savedMode);
      if (ASPECT_PRESETS.some((item) => item.value === saved.aspect)) setAspect(saved.aspect);
      if (IMAGE_RESOLUTIONS.some((item) => item.value === Number(saved.imageResolution))) setImageResolution(Number(saved.imageResolution));
      if ([1, 2, 4].includes(Number(saved.outputs))) setOutputs(Number(saved.outputs));
      if (saved.seed != null) setSeed(String(saved.seed));
      if (Number.isFinite(Number(saved.steps))) setSteps(Math.max(1, Math.min(50, Number(saved.steps))));
      if (Number.isFinite(Number(saved.cfg))) setCfg(Math.max(0, Math.min(20, Number(saved.cfg))));
      if (typeof saved.negativePrompt === 'string') setNegativePrompt(saved.negativePrompt.slice(0, 2000));
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
      negativePrompt,
      workflowId: isEdit ? 'default-image' : workflowId,
      modelId: isEdit ? 'saga-image-auto' : modelId,
      editAuto,
      videoResolution,
      videoDuration,
      videoAudio,
    }));
  }, [
    preferencesReady, mode, isEdit, aspect, imageResolution, outputs, seed, steps, cfg, negativePrompt,
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
          <p>{isEdit ? 'Describe the change and reference images directly in your prompt.' : isVideo ? 'Describe the shot, then set duration, framing, resolution, and audio.' : 'Add an image, describe the change, and generate with the live FLUX edit model.'}</p>
        </div>

        <section className={`saga-composer ${isEdit ? 'is-edit' : ''} ${isVideo ? 'is-video' : ''}`}>
          {(isEdit || (isVideo && references.length > 0)) && (
            <ReferenceStrip
              references={references}
              onRemove={onRemoveReference}
              onInsert={isEdit ? (index) => promptRef.current?.insertReference(index) : undefined}
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


              {!isVideo ? (
                <>
                  {!(isEdit && editAuto) && (
                  <button
                    ref={resolutionButtonRef}
                    type="button"
                    className={`saga-control-pill saga-resolution-trigger ${resolutionOpen ? 'active' : ''}`}
                    aria-haspopup="menu"
                    aria-expanded={resolutionOpen}
                    aria-label={isEdit && editAuto ? `Image resolution Auto, ${autoEditInfo?.detail || 'from reference'}` : `Image resolution ${imageOption.label}, ${formatDimensions(imageDimensions)} at ${aspect}`}
                    title={isEdit && editAuto ? `Image resolution · Auto · ${autoEditInfo?.detail || 'from reference'}` : `Image resolution · ${imageOption.label} · ${formatDimensions(imageDimensions)} at ${aspect}`}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
                      event.preventDefault();
                      setResolutionOpen(true);
                      setAspectOpen(false);
                      setSettingsOpen(false);
                    }}
                    onClick={() => {
                      setResolutionOpen((current) => !current);
                      setAspectOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    {isEdit && editAuto ? <Sparkles size={15} /> : <ImageIcon size={15} />}
                    <span>{isEdit && editAuto ? 'Auto' : imageOption.label}</span>
                    <ChevronDown size={13} />
                  </button>
                  )}

                  <AspectPicker
                    triggerRef={aspectButtonRef}
                    open={aspectOpen}
                    onOpenChange={(next) => {
                      setAspectOpen(next);
                      if (next) {
                        setResolutionOpen(false);
                        setSettingsOpen(false);
                      }
                    }}
                    ariaLabel="Aspect ratio"
                    triggerPrefix={isEdit ? 'Canvas' : 'Aspect'}
                    value={aspect}
                    onValueChange={(value) => {
                      if (isEdit) setEditAuto(false);
                      setAspect(value);
                    }}
                    autoSelected={isEdit && editAuto}
                    onAutoChoose={isEdit ? () => setEditAuto(true) : undefined}
                    effectiveRatio={primaryRatio}
                    autoDetail={autoEditInfo?.ratioLabel || 'Primary reference canvas'}
                    fromReference={isEdit && editAuto && references.length > 0}
                  />
                </>
              ) : (
                <>
                  <button
                    ref={videoResolutionButtonRef}
                    type="button"
                    className={`saga-control-pill saga-video-resolution-trigger ${videoResolutionOpen ? 'active' : ''}`}
                    aria-haspopup="menu"
                    aria-expanded={videoResolutionOpen}
                    aria-label={`Video resolution ${videoOption.label}, ${formatDimensions(videoDimensions)} at ${videoAspect}`}
                    title={`Video resolution · ${videoOption.label} · ${formatDimensions(videoDimensions)} at ${videoAspect}`}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
                      event.preventDefault();
                      setVideoResolutionOpen(true);
                      setDurationOpen(false);
                      setSettingsOpen(false);
                    }}
                    onClick={() => {
                      setVideoResolutionOpen((current) => !current);
                      setDurationOpen(false);
                      setSettingsOpen(false);
                    }}
                  >
                    <Video size={15} /><span>{videoOption.label}</span><ChevronDown size={13} />
                  </button>

                  <button
                    ref={durationButtonRef}
                    type="button"
                    className={`saga-control-pill ${durationOpen ? 'active' : ''}`}
                    aria-haspopup="dialog"
                    aria-expanded={durationOpen}
                    aria-label={`Video duration ${videoDuration} seconds`}
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
                    aria-label={videoAudio ? 'Disable audio' : 'Enable audio'}
                    title={videoAudio ? 'Audio enabled' : 'Audio disabled'}
                    onClick={() => setVideoAudio((current) => !current)}
                  >
                    {videoAudio ? <Volume2 size={17} /> : <VolumeX size={17} />}
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
                title={isImageSetup ? 'Add a reference image to start editing' : isEdit ? 'Edit image' : 'Generate video'}
                aria-label={isImageSetup ? 'Add reference image' : isEdit ? 'Edit image' : 'Generate video'}
                onClick={() => {
                  if (isImageSetup) {
                    referenceInputRef.current?.click();
                    return;
                  }
                  onGenerate({ videoResolution, videoDuration, videoAudio });
                }}
                disabled={busy || (isEdit && references.length === 0)}
              >
                <span className="saga-submit-label">{isImageSetup ? 'Add image' : isEdit ? 'Edit' : 'Generate'}</span>
                {isImageSetup ? <Plus size={18} aria-hidden="true" /> : <ArrowUp size={18} aria-hidden="true" />}
              </button>
            </div>
          </div>
          {composerStatusSlot}
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
        <VideoResolutionPicker
          open={videoResolutionOpen}
          setOpen={setVideoResolutionOpen}
          anchorRef={videoResolutionButtonRef}
          value={videoResolution}
          setValue={setVideoResolution}
          aspect={videoAspect}
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
          negativePrompt={negativePrompt}
          setNegativePrompt={setNegativePrompt}
          workflowId={workflowId}
          setWorkflowId={setWorkflowId}
          modelId={modelId}
          setModelId={setModelId}
          videoAutoAspect={videoAutoAspect}
          setVideoAutoAspect={setVideoAutoAspect}
          videoManualAspect={videoManualAspect}
          setVideoManualAspect={setVideoManualAspect}
          videoAspect={videoAspect}
          videoReferenceInfo={videoReferenceInfo}
          videoFrameRate={videoFrameRate}
          setVideoFrameRate={setVideoFrameRate}
        />

        <OutputWall items={items} renderCard={renderCard} />
      </div>
    </>
  );
}
