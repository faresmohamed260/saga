import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, XCircle } from 'lucide-react';

export const VIDEO_ASPECT_PRESETS = [
  { value: '1:1', label: 'Square' },
  { value: '4:5', label: 'Portrait' },
  { value: '3:4', label: 'Portrait' },
  { value: '2:3', label: 'Tall' },
  { value: '9:16', label: 'Vertical' },
  { value: '5:4', label: 'Classic' },
  { value: '4:3', label: 'Classic' },
  { value: '3:2', label: 'Photo' },
  { value: '16:10', label: 'Wide' },
  { value: '16:9', label: 'Widescreen' },
  { value: '21:9', label: 'Cinematic' },
];

export const VIDEO_FRAME_RATES = [24, 25, 30];

function gcd(a, b) {
  let left = Math.abs(Math.round(Number(a) || 0));
  let right = Math.abs(Math.round(Number(b) || 0));
  while (right) [left, right] = [right, left % right];
  return left || 1;
}

function aspectRatioValue(value, fallback = 16 / 9) {
  const match = String(value || '').match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) return fallback;
  const width = Number(match[1]);
  const height = Number(match[2]);
  return width > 0 && height > 0 ? width / height : fallback;
}

export function referenceAspect(reference) {
  const width = Number(reference?.width) || 0;
  const height = Number(reference?.height) || 0;
  if (!width || !height) return { value: '16:9', ratio: 16 / 9, fromReference: false };
  const divisor = gcd(width, height);
  return {
    value: `${Math.round(width / divisor)}:${Math.round(height / divisor)}`,
    ratio: width / height,
    fromReference: true,
  };
}

function useOutsideDismiss(open, rootRef, close, returnFocusRef = null) {
  useEffect(() => {
    if (!open) return undefined;
    const pointer = (event) => {
      if (!rootRef.current?.contains(event.target)) close();
    };
    const key = (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      close();
      returnFocusRef?.current?.focus();
    };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
      document.removeEventListener('keydown', key);
    };
  }, [open, rootRef, close, returnFocusRef]);
}

function CompactPicker({ label, value, displayValue = value, title, options, onChoose, leading }) {
  const [open, setOpen] = useState(false);
  const [focusIndex, setFocusIndex] = useState(0);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const optionRefs = useRef([]);
  const matchedIndex = options.findIndex((option) => option.value === value);
  const selectedIndex = matchedIndex >= 0 ? matchedIndex : 0;
  const close = useCallback(() => setOpen(false), []);
  useOutsideDismiss(open, rootRef, close, triggerRef);

  useEffect(() => {
    if (!open) return undefined;
    setFocusIndex(selectedIndex);
    const frame = requestAnimationFrame(() => optionRefs.current[selectedIndex]?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, selectedIndex, options.length]);

  const focusOption = (index) => {
    const normalized = (index + options.length) % options.length;
    setFocusIndex(normalized);
    optionRefs.current[normalized]?.focus();
  };

  const choose = (option) => {
    onChoose(option.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const optionKeyDown = (event, index) => {
    let next = null;
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = index + 1;
    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = index - 1;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = options.length - 1;
    if (next != null) {
      event.preventDefault();
      focusOption(next);
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(options[index]);
    }
  };

  const openFromTrigger = (event) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    setFocusIndex(selectedIndex);
    setOpen(true);
  };

  return (
    <div
      className="saga-video-inline-picker"
      ref={rootRef}
      onBlurCapture={(event) => {
        if (!open || rootRef.current?.contains(event.relatedTarget)) return;
        setOpen(false);
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        className={`saga-control-pill ${open ? 'active' : ''}`}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        title={title}
        onKeyDown={openFromTrigger}
        onClick={() => setOpen((current) => !current)}
      >
        {leading}<span>{displayValue}</span><ChevronDown size={13} />
      </button>
      {open && (
        <div className="saga-video-option-menu" role="menu" aria-label={label} aria-orientation="vertical">
          {options.map((option, index) => (
            <button
              ref={(node) => { optionRefs.current[index] = node; }}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              tabIndex={index === focusIndex ? 0 : -1}
              className={option.value === value ? 'selected' : ''}
              key={option.value}
              onFocus={() => setFocusIndex(index)}
              onKeyDown={(event) => optionKeyDown(event, index)}
              onClick={() => choose(option)}
            >
              <span><strong>{option.displayValue || option.value}</strong>{option.label && <small>{option.label}</small>}</span>
              {option.value === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function VideoOutputControls({
  autoAspect,
  setAutoAspect,
  manualAspect,
  setManualAspect,
  effectiveAspect,
  referenceInfo,
  frameRate,
  setFrameRate,
}) {
  const aspectSelection = autoAspect ? '__auto__' : manualAspect;
  const aspectValue = autoAspect ? effectiveAspect : manualAspect;
  const aspectIconRatio = aspectRatioValue(aspectValue, referenceInfo.ratio || 16 / 9);
  const aspectDisplay = autoAspect
    ? `Aspect · Auto ${aspectValue}${referenceInfo.fromReference ? ' · Ref' : ''}`
    : `Aspect · ${manualAspect}`;
  const aspectTitle = autoAspect
    ? referenceInfo.fromReference
      ? `Aspect · Auto ${aspectValue} · From reference`
      : `Aspect · Auto ${aspectValue} · Follows an attached reference when available`
    : `Aspect · Manual ${manualAspect}`;
  const aspectOptions = [
    {
      value: '__auto__',
      displayValue: 'Auto',
      label: referenceInfo.fromReference
        ? `${referenceInfo.value} · From reference`
        : '16:9 default · Follows reference when attached',
    },
    ...VIDEO_ASPECT_PRESETS,
  ];

  return (
    <div className="saga-video-extra-controls" aria-label="Video output controls">
      <CompactPicker
        label="Video aspect"
        value={aspectSelection}
        displayValue={aspectDisplay}
        title={aspectTitle}
        leading={<span className="saga-aspect-icon" style={{ aspectRatio: String(aspectIconRatio) }} />}
        options={aspectOptions}
        onChoose={(value) => {
          if (value === '__auto__') {
            setAutoAspect(true);
            return;
          }
          setManualAspect(value);
          setAutoAspect(false);
        }}
      />
      <CompactPicker
        label="Video frame rate"
        value={`${frameRate} fps`}
        leading={<Gauge size={15} />}
        options={VIDEO_FRAME_RATES.map((fps) => ({ value: `${fps} fps` }))}
        onChoose={(value) => setFrameRate(Number.parseInt(value, 10) || 24)}
      />
    </div>
  );
}

const STATUS_COPY = {
  uploading: ['Uploading reference', 'Preparing the source image for generation.'],
  submitting: ['Submitting generation', 'Sending the video request to the generation service.'],
  queued: ['Queued', 'The request is waiting for an available generation worker.'],
  running: ['Generating video', 'REDGraft LTX 2.5 is rendering the requested frames.'],
  completed: ['Video ready', 'The completed video has been saved to Gallery.'],
  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],
};

export function VideoGenerationProgress({ busy, status }) {
  const [elapsed, setElapsed] = useState(0);
  const [showTerminal, setShowTerminal] = useState(false);

  useEffect(() => {
    if (!busy) return undefined;
    const started = Date.now();
    setElapsed(0);
    setShowTerminal(true);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    if (busy) return undefined;
    if (status !== 'completed' && status !== 'failed') {
      setShowTerminal(false);
      return undefined;
    }
    setShowTerminal(true);
    const timer = window.setTimeout(() => setShowTerminal(false), 5000);
    return () => window.clearTimeout(timer);
  }, [busy, status]);

  if (!busy && !showTerminal) return null;
  const normalized = status || (busy ? 'submitting' : 'completed');
  const [title, detail] = STATUS_COPY[normalized] || STATUS_COPY.running;
  const terminal = normalized === 'completed' || normalized === 'failed';
  return (
    <div className={`saga-generation-progress is-${normalized}`} role="status" aria-live="polite">
      <div className="saga-generation-progress-icon">
        {normalized === 'completed' ? <CheckCircle2 size={17} /> : normalized === 'failed' ? <XCircle size={17} /> : <LoaderCircle className="spin" size={17} />}
      </div>
      <div className="saga-generation-progress-copy">
        <div><strong>{title}</strong>{busy && <span>{elapsed}s elapsed</span>}</div>
        <small>{detail}</small>
        <div className={`saga-generation-progress-track ${terminal ? 'terminal' : 'indeterminate'}`} aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
