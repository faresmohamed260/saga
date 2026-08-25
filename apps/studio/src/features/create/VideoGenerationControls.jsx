import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, CheckCircle2, ChevronDown, ExternalLink, Gauge, LoaderCircle, X, XCircle } from 'lucide-react';
import { AspectPicker } from './AspectPicker.jsx';

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

function CompactPicker({ label, value, displayValue = value, title, options, onChoose, leading, menuClassName = '' }) {
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
        <div className={`saga-video-option-menu ${menuClassName}`.trim()} role="menu" aria-label={label} aria-orientation="vertical">
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
  return (
    <div className="saga-video-extra-controls" aria-label="Video output controls">
      <AspectPicker
        ariaLabel="Video aspect"
        value={manualAspect}
        onValueChange={(value) => {
          setManualAspect(value);
          setAutoAspect(false);
        }}
        autoSelected={autoAspect}
        onAutoChoose={() => setAutoAspect(true)}
        effectiveValue={effectiveAspect}
        effectiveRatio={referenceInfo.ratio || undefined}
        autoDetail={referenceInfo.fromReference
          ? `${referenceInfo.value} · From reference`
          : '16:9 · Follows reference'}
        fromReference={autoAspect && referenceInfo.fromReference}
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
  submitting: ['Submitting generation', 'Sending the request to the assigned model ecosystem.'],
  queued: ['Waiting for worker', 'The request is queued for an available ecosystem worker.'],
  sleeping: ['Worker sleeping', 'Compute is scaled to zero and will start on demand.'],
  waking: ['Starting worker', 'The assigned worker is waking from zero compute.'],
  loading: ['Loading model', 'Cached model assets are loading into GPU memory.'],
  ready: ['Worker ready', 'The model ecosystem is ready to begin generation.'],
  generating: ['Generating', 'The assigned model ecosystem is producing the requested media.'],
  running: ['Generating', 'The assigned model ecosystem is producing the requested media.'],
  finalizing: ['Finalizing result', 'Generation is complete and the result is being prepared for Gallery.'],
  credit_exhausted: ['Switching worker', 'The assigned worker reached its credit limit. A standby worker will be used when available.'],
  unavailable: ['Worker unavailable', 'The assigned worker is unavailable. A standby worker will be used when available.'],
  completed: ['Generation ready', 'The completed result has been saved to Gallery.'],
  cancelled: ['Generation cancelled', 'The running provider job was stopped by request.'],
  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],
};

export function VideoGenerationProgress({ busy, status, workerStatus, activeJob, cancelBusy = false, onViewJob, onCancelJob, kind = 'video' }) {
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
    if (status !== 'completed' && status !== 'failed' && status !== 'cancelled') {
      setShowTerminal(false);
      return undefined;
    }
    setShowTerminal(true);
    const timer = window.setTimeout(() => setShowTerminal(false), 5000);
    return () => window.clearTimeout(timer);
  }, [busy, status]);

  if (!busy && !showTerminal) return null;
  const terminalStatus = !busy && ['completed', 'failed', 'cancelled'].includes(status) ? status : '';
  const normalized = terminalStatus || workerStatus?.state || status || (busy ? 'submitting' : 'completed');
  const [baseTitle, baseDetail] = STATUS_COPY[normalized] || STATUS_COPY.running;
  const workerName = workerStatus?.displayName || '';
  const failedWorkers = Array.isArray(workerStatus?.failedWorkers) ? workerStatus.failedWorkers : [];
  const failoverReason = workerStatus?.failoverReason
    || failedWorkers.find((failure) => failure?.kind === 'credit_exhausted')?.kind
    || failedWorkers.find((failure) => failure?.kind === 'unavailable')?.kind
    || '';
  const allCreditsExhausted = workerStatus?.errorCode === 'ALL_WORKERS_CREDIT_EXHAUSTED';
  const terminalError = !busy && status === 'failed';
  let title = normalized === 'generating' || normalized === 'running' ? `Generating ${kind}` : baseTitle;
  let detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;
  if (allCreditsExhausted) {
    title = 'Workers out of credits';
    detail = 'No worker in this model ecosystem currently has available credits. Try again later or choose another model.';
  } else if (busy && failoverReason === 'credit_exhausted') {
    title = 'Switching worker';
    detail = `The previous worker reached its credit limit. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  } else if (busy && failoverReason === 'unavailable') {
    title = 'Switching worker';
    detail = `The previous worker became unavailable. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  }
  const terminal = normalized === 'completed' || normalized === 'failed' || normalized === 'cancelled' || terminalError;
  return (
    <div className={`saga-generation-progress is-${normalized}`} role="status" aria-live="polite">
      <div className="saga-generation-progress-icon">
        {normalized === 'completed' ? <CheckCircle2 size={17} /> : terminalError || normalized === 'failed' ? <XCircle size={17} /> : <LoaderCircle className="spin" size={17} />}
      </div>
      <div className="saga-generation-progress-copy">
        <div><strong>{title}</strong>{busy && <span>{elapsed}s elapsed</span>}</div>
        <small>{detail}</small>
        <div className={`saga-generation-progress-track ${terminal ? 'terminal' : 'indeterminate'}`} aria-hidden="true">
          <span />
        </div>
        {busy && <small className="saga-generation-next-note">Changes to settings now apply to your next generation.</small>}
        {activeJob?.id && (
          <div className="saga-generation-progress-actions" aria-label="Generation actions">
            <button type="button" onClick={onViewJob}><ExternalLink size={14} /> View Job</button>
            {busy && <button type="button" className="danger" disabled={cancelBusy} onClick={onCancelJob}>{cancelBusy ? <LoaderCircle className="spin" size={14} /> : <X size={14} />} {cancelBusy ? 'Cancelling…' : 'Cancel'}</button>}
          </div>
        )}
      </div>
    </div>
  );
}
