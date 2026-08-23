import React, { useEffect, useRef, useState } from 'react';
import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, Sparkles, XCircle } from 'lucide-react';

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

function useOutsideDismiss(open, rootRef, close) {
  useEffect(() => {
    if (!open) return undefined;
    const pointer = (event) => {
      if (!rootRef.current?.contains(event.target)) close();
    };
    const key = (event) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
      document.removeEventListener('keydown', key);
    };
  }, [open, rootRef, close]);
}

function CompactPicker({ label, value, options, onChoose, leading }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useOutsideDismiss(open, rootRef, () => setOpen(false));
  return (
    <div className="saga-video-inline-picker" ref={rootRef}>
      <button
        type="button"
        className={`saga-control-pill ${open ? 'active' : ''}`}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {leading}<span>{value}</span><ChevronDown size={13} />
      </button>
      {open && (
        <div className="saga-video-option-menu" role="menu" aria-label={label}>
          {options.map((option) => (
            <button
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              className={option.value === value ? 'selected' : ''}
              key={option.value}
              onClick={() => {
                onChoose(option.value);
                setOpen(false);
              }}
            >
              <span><strong>{option.value}</strong>{option.label && <small>{option.label}</small>}</span>
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
  const aspectValue = autoAspect ? effectiveAspect : manualAspect;
  return (
    <div className="saga-video-extra-controls" aria-label="Video output controls">
      <button
        type="button"
        className={`saga-auto-toggle ${autoAspect ? 'active' : ''}`}
        aria-pressed={autoAspect}
        title={referenceInfo.fromReference ? `Use reference aspect ratio (${referenceInfo.value})` : 'Use reference aspect ratio when an image is attached; otherwise 16:9'}
        onClick={() => setAutoAspect((current) => !current)}
      >
        <Sparkles size={15} /><span>Auto</span>
      </button>
      <CompactPicker
        label="Video aspect ratio"
        value={aspectValue}
        leading={<span className="saga-aspect-icon" style={{ aspectRatio: String(referenceInfo.ratio || 16 / 9) }} />}
        options={VIDEO_ASPECT_PRESETS}
        onChoose={(value) => {
          setManualAspect(value);
          setAutoAspect(false);
        }}
      />
      <CompactPicker
        label="Video frame rate"
        value={`${frameRate} fps`}
        leading={<Gauge size={15} />}
        options={VIDEO_FRAME_RATES.map((fps) => ({ value: `${fps} fps`, raw: fps }))}
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
