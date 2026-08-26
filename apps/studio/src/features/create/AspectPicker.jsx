import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

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

export function aspectRatioValue(value, fallback = 1) {
  const match = String(value || '').match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) return fallback;
  const width = Number(match[1]);
  const height = Number(match[2]);
  return width > 0 && height > 0 ? width / height : fallback;
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
      const aboveSpace = rect.top - edge - gap;
      const belowSpace = window.innerHeight - rect.bottom - edge - gap;
      const above = aboveSpace > belowSpace && aboveSpace >= Math.min(height, 180);
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

export function AspectPicker({
  value,
  onValueChange,
  autoSelected = false,
  onAutoChoose,
  effectiveValue,
  effectiveRatio,
  autoDetail,
  fromReference = false,
  ariaLabel = 'Aspect ratio',
  triggerPrefix = 'Aspect',
  triggerRef: providedTriggerRef,
  open: controlledOpen,
  onOpenChange,
  onOpen,
}) {
  const localTriggerRef = useRef(null);
  const rootRef = useRef(null);
  const optionRefs = useRef([]);
  const triggerRef = providedTriggerRef || localTriggerRef;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const autoAvailable = typeof onAutoChoose === 'function';
  const autoValue = effectiveValue || value;
  const resolvedAutoRatio = Number(effectiveRatio) > 0
    ? Number(effectiveRatio)
    : aspectRatioValue(autoValue, aspectRatioValue(value, 1));

  const options = useMemo(() => [
    ...(autoAvailable ? [{
      value: '__auto__',
      label: 'Auto',
      ratio: resolvedAutoRatio,
      detail: autoDetail || (fromReference ? `${autoValue} · From reference` : `${autoValue} default · Follows reference when attached`),
    }] : []),
    ...ASPECT_PRESETS,
  ], [autoAvailable, resolvedAutoRatio, autoDetail, fromReference, autoValue]);

  const selectedToken = autoSelected && autoAvailable ? '__auto__' : value;
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === selectedToken));
  const [focusIndex, setFocusIndex] = useState(selectedIndex);
  const [previewIndex, setPreviewIndex] = useState(null);

  const setOpen = useCallback((next) => {
    if (controlledOpen == null) setInternalOpen(next);
    onOpenChange?.(next);
    if (next) onOpen?.();
  }, [controlledOpen, onOpenChange, onOpen]);

  useEffect(() => {
    if (!open) {
      setPreviewIndex(null);
      return undefined;
    }
    setFocusIndex(selectedIndex);
    setPreviewIndex(null);
    const focusSelected = () => optionRefs.current[selectedIndex]?.focus();
    focusSelected();
    const timer = window.setTimeout(focusSelected, 60);
    return () => window.clearTimeout(timer);
  }, [open, selectedIndex, options.length]);

  useEffect(() => {
    if (!open) return undefined;
    const pointer = (event) => {
      if (rootRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    const focus = (event) => {
      if (rootRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    const key = (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('focusin', focus);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
      document.removeEventListener('focusin', focus);
      document.removeEventListener('keydown', key);
    };
  }, [open, setOpen, triggerRef]);

  const previewOption = previewIndex == null ? options[selectedIndex] : options[previewIndex];
  const previewRatio = previewOption?.value === '__auto__'
    ? resolvedAutoRatio
    : Number(previewOption?.ratio) || aspectRatioValue(previewOption?.value, 1);
  const previewSize = useMemo(() => {
    const max = 84;
    return previewRatio >= 1
      ? { width: max, height: max / previewRatio }
      : { width: max * previewRatio, height: max };
  }, [previewRatio]);

  const desiredHeight = options.length * 32 + 16;
  const position = useAnchoredPosition(open, triggerRef, 390, desiredHeight);
  const triggerValue = autoSelected
    ? `Auto${autoValue ? ` ${autoValue}` : ''}${fromReference ? ' · From reference' : ''}`
    : value;
  const triggerTitle = autoSelected
    ? fromReference
      ? `${triggerPrefix} · Auto${autoValue ? ` ${autoValue}` : ''} · From reference`
      : `${triggerPrefix} · Auto${autoValue ? ` ${autoValue}` : ''} · Follows an attached reference when available`
    : `${triggerPrefix} · Manual ${value}`;

  const choose = (option) => {
    if (option.value === '__auto__') onAutoChoose?.();
    else onValueChange(option.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const focusOption = (index) => {
    const normalized = (index + options.length) % options.length;
    setFocusIndex(normalized);
    setPreviewIndex(normalized);
    optionRefs.current[normalized]?.focus();
  };

  const optionKeyDown = (event, index) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      window.setTimeout(() => triggerRef.current?.focus(), 0);
      return;
    }
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

  return (
    <div ref={rootRef} className="saga-shared-aspect-root">
      <button
        ref={triggerRef}
        type="button"
        className={`saga-control-pill saga-shared-aspect-trigger ${open ? 'active' : ''}`}
        data-shared-aspect-picker="true"
        aria-label={ariaLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        title={triggerTitle}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
          event.preventDefault();
          setOpen(true);
        }}
        onClick={() => setOpen(!open)}
      >
        <span className="saga-aspect-icon" style={{ aspectRatio: String(autoSelected ? resolvedAutoRatio : aspectRatioValue(value, 1)) }} />
        <span className="saga-aspect-value">{triggerPrefix} · {triggerValue}</span>
        <ChevronDown size={13} />
      </button>

      {open && (
        <div
          className="saga-picker saga-aspect-picker saga-shared-aspect-picker"
          data-aspect-picker-surface="shared"
          style={position || { visibility: 'hidden' }}
        >
          <div className="saga-picker-preview">
            <div className="saga-preview-grid">
              <span className="saga-preview-shape" style={previewSize} />
            </div>
            <strong>{previewOption?.value === '__auto__' ? `Auto${autoValue ? ` ${autoValue}` : ''}` : previewOption?.value}</strong>
            <small>{previewOption?.value === '__auto__' ? previewOption.detail : previewOption?.label}</small>
          </div>
          <div className="saga-morph-list" role="menu" aria-label={ariaLabel} onMouseLeave={() => setPreviewIndex(null)}>
            <span
              className="saga-morph-indicator"
              style={{ transform: `translate3d(0, ${((previewIndex == null ? selectedIndex : previewIndex) * 32)}px, 0)`, height: 32 }}
            />
            {options.map((option, index) => (
              <button
                ref={(node) => { optionRefs.current[index] = node; }}
                type="button"
                role="menuitemradio"
                aria-checked={option.value === selectedToken}
                tabIndex={index === focusIndex ? 0 : -1}
                className={option.value === selectedToken ? 'selected' : ''}
                key={option.value}
                onMouseEnter={() => setPreviewIndex(index)}
                onFocus={() => {
                  setFocusIndex(index);
                  setPreviewIndex(index);
                }}
                onKeyDown={(event) => optionKeyDown(event, index)}
                onClick={() => choose(option)}
              >
                <span className="saga-option-key">{option.value === '__auto__' ? 'Auto' : option.value}</span>
                <span className="saga-option-label">{option.value === '__auto__' ? option.detail : option.label}</span>
                {option.value === selectedToken && <Check className="saga-option-check" size={15} />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
