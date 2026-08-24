from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def write(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:900]}")
    path.write_text(text.replace(old, new, 1))


def remove_between(relative_path: str, start: str, end: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    if text.count(start) != 1 or text.count(end) < 1:
        raise RuntimeError(f"{relative_path}: could not uniquely locate removal block {start!r} -> {end!r}")
    left = text.index(start)
    right = text.index(end, left)
    path.write_text(text[:left] + text[right:])


def mark_progress() -> None:
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '''**Iteration 7 — unified Video Aspect control**\n\n- Status: `[x]` complete\n- Completed item: **07**\n- Next item: **08 — unify Image and Video aspect selection into one reusable `AspectPicker`**\n- Rule: do not start Item 08 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.\n''',
        '''**Iteration 8 — shared Image/Video AspectPicker**\n\n- Status: `[~]` in progress\n- Working item: **08**\n- Rule: extract one reusable AspectPicker for Image and Video with shared ratio preview, option labels, keyboard behavior, responsive anchored positioning, and optional Auto/reference provenance; validate GitHub CI/visual previews and professional review before completion.\n''',
    )
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '- [ ] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Shared ratio preview, labels, selection behavior, keyboard support, responsive positioning, optional reference-source indicator.\n',
        '- [~] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Shared ratio preview, labels, selection behavior, keyboard support, responsive positioning, optional reference-source indicator. **Iteration 8 in progress.**\n',
    )
    print("Iteration 8 marked in progress")


SHARED_COMPONENT = r'''import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
    const frame = requestAnimationFrame(() => optionRefs.current[selectedIndex]?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, selectedIndex, options.length]);

  useEffect(() => {
    if (!open) return undefined;
    const pointer = (event) => {
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
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
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

  const desiredHeight = options.length * 32 + 14;
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
    <div
      ref={rootRef}
      className="saga-shared-aspect-root"
      onBlurCapture={(event) => {
        if (!open || rootRef.current?.contains(event.relatedTarget)) return;
        setOpen(false);
      }}
    >
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
'''


def apply_product() -> None:
    component_path = ROOT / "apps/studio/src/features/create/AspectPicker.jsx"
    if component_path.exists():
        raise RuntimeError("Shared AspectPicker already exists; refusing to overwrite unexpectedly")
    component_path.write_text(SHARED_COMPONENT)

    replace_once(
        "apps/studio/src/create-controls.jsx",
        "import { setEditSizingPreference } from './generation-client.js';\nimport './create-workspace-v2.css';\n\nexport const ASPECT_PRESETS = [\n  { value: '1:1', label: 'Square', ratio: 1 },\n  { value: '4:5', label: 'Portrait', ratio: 4 / 5 },\n  { value: '3:4', label: 'Portrait', ratio: 3 / 4 },\n  { value: '2:3', label: 'Tall', ratio: 2 / 3 },\n  { value: '9:16', label: 'Vertical', ratio: 9 / 16 },\n  { value: '5:4', label: 'Classic', ratio: 5 / 4 },\n  { value: '4:3', label: 'Classic', ratio: 4 / 3 },\n  { value: '3:2', label: 'Photo', ratio: 3 / 2 },\n  { value: '16:10', label: 'Wide', ratio: 16 / 10 },\n  { value: '16:9', label: 'Widescreen', ratio: 16 / 9 },\n  { value: '21:9', label: 'Cinematic', ratio: 21 / 9 },\n];\n",
        "import { setEditSizingPreference } from './generation-client.js';\nimport { AspectPicker, ASPECT_PRESETS } from './features/create/AspectPicker.jsx';\nimport './create-workspace-v2.css';\n",
    )
    remove_between(
        "apps/studio/src/create-controls.jsx",
        "function AspectPicker({ open, setOpen, anchorRef, aspect, setAspect, editAuto, setEditAuto, autoRatio, autoInfo }) {",
        "function ResolutionPicker(",
    )
    replace_once(
        "apps/studio/src/create-controls.jsx",
        '''                  <button\n                    ref={aspectButtonRef}\n                    type="button"\n                    className={`saga-control-pill ${aspectOpen ? 'active' : ''}`}\n                    aria-haspopup="menu"\n                    aria-expanded={aspectOpen}\n                    onKeyDown={(event) => {\n                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;\n                      event.preventDefault();\n                      setAspectOpen(true);\n                      setResolutionOpen(false);\n                      setSettingsOpen(false);\n                    }}\n                    onClick={() => {\n                      setAspectOpen((current) => !current);\n                      setResolutionOpen(false);\n                      setSettingsOpen(false);\n                    }}\n                  >\n                    <span className="saga-aspect-icon" style={{ aspectRatio: String(isEdit && editAuto ? primaryRatio : (ASPECT_PRESETS.find((item) => item.value === aspect)?.ratio || 1)) }} />\n                    <span>{isEdit && editAuto ? 'Auto' : aspect}</span>\n                  </button>\n''',
        '''                  <AspectPicker\n                    triggerRef={aspectButtonRef}\n                    open={aspectOpen}\n                    onOpenChange={(next) => {\n                      setAspectOpen(next);\n                      if (next) {\n                        setResolutionOpen(false);\n                        setSettingsOpen(false);\n                      }\n                    }}\n                    ariaLabel="Aspect ratio"\n                    value={aspect}\n                    onValueChange={(value) => {\n                      if (isEdit) setEditAuto(false);\n                      setAspect(value);\n                    }}\n                    autoSelected={isEdit && editAuto}\n                    effectiveRatio={primaryRatio}\n                    autoDetail={autoEditInfo?.ratioLabel || 'Primary reference canvas'}\n                    fromReference={isEdit && editAuto && references.length > 0}\n                  />\n''',
    )
    replace_once(
        "apps/studio/src/create-controls.jsx",
        '''        <AspectPicker\n          open={aspectOpen}\n          setOpen={setAspectOpen}\n          anchorRef={aspectButtonRef}\n          aspect={aspect}\n          setAspect={setAspect}\n          editAuto={isEdit && editAuto}\n          setEditAuto={isEdit ? setEditAuto : () => {}}\n          autoRatio={primaryRatio}\n          autoInfo={autoEditInfo}\n        />\n''',
        "",
    )

    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "import React, { useCallback, useEffect, useRef, useState } from 'react';\nimport { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, XCircle } from 'lucide-react';\n\nexport const VIDEO_ASPECT_PRESETS = [\n  { value: '1:1', label: 'Square' },\n  { value: '4:5', label: 'Portrait' },\n  { value: '3:4', label: 'Portrait' },\n  { value: '2:3', label: 'Tall' },\n  { value: '9:16', label: 'Vertical' },\n  { value: '5:4', label: 'Classic' },\n  { value: '4:3', label: 'Classic' },\n  { value: '3:2', label: 'Photo' },\n  { value: '16:10', label: 'Wide' },\n  { value: '16:9', label: 'Widescreen' },\n  { value: '21:9', label: 'Cinematic' },\n];\n\nexport const VIDEO_FRAME_RATES = [24, 25, 30];\n",
        "import React, { useCallback, useEffect, useRef, useState } from 'react';\nimport { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, XCircle } from 'lucide-react';\nimport { AspectPicker } from './AspectPicker.jsx';\n\nexport const VIDEO_FRAME_RATES = [24, 25, 30];\n",
    )
    remove_between(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "function aspectRatioValue(value, fallback = 16 / 9) {",
        "export function referenceAspect(",
    )
    remove_between(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "export function VideoOutputControls({",
        "const STATUS_COPY =",
    )
    video_controls = r'''export function VideoOutputControls({
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
          : '16:9 default · Follows reference when attached'}
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

'''
    path = ROOT / "apps/studio/src/features/create/VideoGenerationControls.jsx"
    text = path.read_text()
    marker = "const STATUS_COPY ="
    text = text.replace(marker, video_controls + marker, 1)
    path.write_text(text)

    replace_once(
        "apps/studio/scripts/capture-ui-preview.mjs",
        "  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });\n  await aspectTrigger.focus();\n",
        "  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });\n  if (await aspectTrigger.getAttribute('data-shared-aspect-picker') !== 'true') throw new Error('Image mode is not using the shared AspectPicker trigger');\n  await aspectTrigger.focus();\n",
    )
    replace_once(
        "apps/studio/scripts/capture-ui-preview.mjs",
        "  const aspectPicker = desktop.locator('.saga-aspect-picker');\n  await aspectPicker.waitFor({ state: 'visible' });\n",
        "  const aspectPicker = desktop.locator('.saga-aspect-picker');\n  await aspectPicker.waitFor({ state: 'visible' });\n  if (await aspectPicker.getAttribute('data-aspect-picker-surface') !== 'shared') throw new Error('Image aspect menu is not the shared AspectPicker surface');\n",
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        "  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);\n",
        "  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);\n  if (await aspect.getAttribute('data-shared-aspect-picker') !== 'true') throw new Error('Video mode is not using the shared AspectPicker trigger');\n",
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        "  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });\n  await aspectMenu.waitFor({ state: 'visible' });\n",
        "  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });\n  await aspectMenu.waitFor({ state: 'visible' });\n  const sharedAspectSurface = page.locator('.saga-shared-aspect-picker');\n  if (await sharedAspectSurface.getAttribute('data-aspect-picker-surface') !== 'shared') throw new Error('Video aspect menu is not the shared AspectPicker surface');\n  if (await sharedAspectSurface.locator('.saga-picker-preview').count() !== 1) throw new Error('Video shared AspectPicker is missing the ratio preview panel');\n",
    )

    replace_once(
        "apps/studio/src/studio-polish.css",
        '''.workspace .saga-video-option-menu {\n  top: calc(100% + 8px);\n  bottom: auto;\n  max-height: min(420px, calc(100vh - 24px));\n  overflow-y: auto;\n  overscroll-behavior: contain;\n  scrollbar-width: thin;\n}\n''',
        '''.workspace .saga-video-option-menu {\n  top: calc(100% + 8px);\n  bottom: auto;\n  max-height: min(420px, calc(100vh - 24px));\n  overflow-y: auto;\n  overscroll-behavior: contain;\n  scrollbar-width: thin;\n}\n\n.workspace .saga-shared-aspect-root {\n  display: inline-flex;\n  min-width: 0;\n}\n\n.workspace .saga-shared-aspect-trigger {\n  justify-content: flex-start;\n  max-width: 100%;\n}\n\n.workspace .saga-shared-aspect-trigger .saga-aspect-value {\n  min-width: 0;\n}\n\n.workspace .saga-shared-aspect-picker .saga-morph-list {\n  overflow-y: auto;\n  overscroll-behavior: contain;\n  scrollbar-width: thin;\n}\n''',
    )
    print("Iteration 8 shared AspectPicker product patch applied")


def validate_source() -> None:
    create = read("apps/studio/src/create-controls.jsx")
    video = read("apps/studio/src/features/create/VideoGenerationControls.jsx")
    shared = read("apps/studio/src/features/create/AspectPicker.jsx")
    image_test = read("apps/studio/scripts/capture-ui-preview.mjs")
    video_test = read("apps/studio/scripts/capture-video-output-preview.mjs")
    checks = {
        "shared component exports AspectPicker": "export function AspectPicker" in shared,
        "shared component owns canonical presets": "export const ASPECT_PRESETS" in shared,
        "image imports shared picker": "import { AspectPicker, ASPECT_PRESETS } from './features/create/AspectPicker.jsx';" in create,
        "video imports shared picker": "import { AspectPicker } from './AspectPicker.jsx';" in video,
        "legacy image AspectPicker removed": "function AspectPicker({ open, setOpen" not in create,
        "duplicate video presets removed": "VIDEO_ASPECT_PRESETS" not in video,
        "image visual test asserts shared picker": "Image mode is not using the shared AspectPicker trigger" in image_test,
        "video visual test asserts shared picker": "Video mode is not using the shared AspectPicker trigger" in video_test,
    }
    failed = [label for label, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("Source validation failed: " + "; ".join(failed))
    print("Iteration 8 source validation passed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['mark', 'apply', 'validate'])
    args = parser.parse_args()
    if args.action == 'mark':
        mark_progress()
    elif args.action == 'apply':
        apply_product()
    else:
        validate_source()
