from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n--- OLD ---\n{old[:500]}")
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Video-specific compact pickers: native trigger + roving menu focus.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/features/create/VideoGenerationControls.jsx",
    """function useOutsideDismiss(open, rootRef, close) {
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
  const close = useCallback(() => setOpen(false), []);
  useOutsideDismiss(open, rootRef, close);
  return (
    <div className=\"saga-video-inline-picker\" ref={rootRef}>
      <button
        type=\"button\"
        className={`saga-control-pill ${open ? 'active' : ''}`}
        aria-label={label}
        aria-haspopup=\"menu\"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {leading}<span>{value}</span><ChevronDown size={13} />
      </button>
      {open && (
        <div className=\"saga-video-option-menu\" role=\"menu\" aria-label={label}>
          {options.map((option) => (
            <button
              type=\"button\"
              role=\"menuitemradio\"
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
""",
    """function useOutsideDismiss(open, rootRef, close, returnFocusRef = null) {
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
      requestAnimationFrame(() => returnFocusRef?.current?.focus());
    };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', pointer);
      document.removeEventListener('keydown', key);
    };
  }, [open, rootRef, close, returnFocusRef]);
}

function CompactPicker({ label, value, options, onChoose, leading }) {
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
    requestAnimationFrame(() => triggerRef.current?.focus());
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
      className=\"saga-video-inline-picker\"
      ref={rootRef}
      onBlurCapture={(event) => {
        if (!open || rootRef.current?.contains(event.relatedTarget)) return;
        setOpen(false);
      }}
    >
      <button
        ref={triggerRef}
        type=\"button\"
        className={`saga-control-pill ${open ? 'active' : ''}`}
        aria-label={label}
        aria-haspopup=\"menu\"
        aria-expanded={open}
        onKeyDown={openFromTrigger}
        onClick={() => setOpen((current) => !current)}
      >
        {leading}<span>{value}</span><ChevronDown size={13} />
      </button>
      {open && (
        <div className=\"saga-video-option-menu\" role=\"menu\" aria-label={label} aria-orientation=\"vertical\">
          {options.map((option, index) => (
            <button
              ref={(node) => { optionRefs.current[index] = node; }}
              type=\"button\"
              role=\"menuitemradio\"
              aria-checked={option.value === value}
              tabIndex={index === focusIndex ? 0 : -1}
              className={option.value === value ? 'selected' : ''}
              key={option.value}
              onFocus={() => setFocusIndex(index)}
              onKeyDown={(event) => optionKeyDown(event, index)}
              onClick={() => choose(option)}
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
""",
)

# ---------------------------------------------------------------------------
# Legacy/shared Create pickers: restore focus, close on focus exit, and make
# Advanced custom listboxes fully keyboard navigable.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/create-controls.jsx",
    """function useOutsideDismiss(open, refs, close) {
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
""",
    """function useOutsideDismiss(open, refs, close, returnFocusRef = null) {
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (refs.some((item) => item.current?.contains(event.target))) return;
      close();
    };
    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      close();
      requestAnimationFrame(() => returnFocusRef?.current?.focus());
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, refs, close, returnFocusRef]);
}
""",
)

replace_once(
    "apps/studio/src/create-controls.jsx",
    """  useOutsideDismiss(open, [anchorRef, popoverRef], onClose);
  if (!open) return null;
  return (
    <div ref={popoverRef} className={`saga-picker ${className}`} style={position || { visibility: 'hidden' }}>
      {children}
    </div>
  );
}""",
    """  useOutsideDismiss(open, [anchorRef, popoverRef], onClose, anchorRef);
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
}""",
)

for old, new in [
    (
        """          setEditAuto(false);
          setAspect(option.value);
          setOpen(false);
""",
        """          setEditAuto(false);
          setAspect(option.value);
          setOpen(false);
          requestAnimationFrame(() => anchorRef.current?.focus());
""",
    ),
    (
        """          setEditAuto(false);
          setImageResolution(option.value);
          setOpen(false);
""",
        """          setEditAuto(false);
          setImageResolution(option.value);
          setOpen(false);
          requestAnimationFrame(() => anchorRef.current?.focus());
""",
    ),
    (
        """          setValue(option.value);
          setOpen(false);
""",
        """          setValue(option.value);
          setOpen(false);
          requestAnimationFrame(() => anchorRef.current?.focus());
""",
    ),
]:
    replace_once("apps/studio/src/create-controls.jsx", old, new)

replace_once(
    "apps/studio/src/create-controls.jsx",
    """  useOutsideDismiss(open, [anchorRef, popoverRef], () => setOpen(false));
""",
    """  useOutsideDismiss(open, [anchorRef, popoverRef], () => setOpen(false), anchorRef);
""",
)

replace_once(
    "apps/studio/src/create-controls.jsx",
    """function FancySelect({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useOutsideDismiss(open, [rootRef], () => setOpen(false));
  const selected = options.find((item) => String(item.value) === String(value)) || options[0];

  return (
    <div className={`saga-fancy-select ${open ? 'open' : ''}`} ref={rootRef}>
      <button type=\"button\" aria-haspopup=\"listbox\" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <span>{selected?.label}</span><ChevronDown size={15} />
      </button>
      {open && (
        <div className=\"saga-fancy-options\" role=\"listbox\" aria-label={label}>
          {options.map((option) => (
            <button
              type=\"button\"
              role=\"option\"
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
""",
    """function FancySelect({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const optionRefs = useRef([]);
  const selectedIndex = Math.max(0, options.findIndex((item) => String(item.value) === String(value)));
  const [focusIndex, setFocusIndex] = useState(selectedIndex);
  const selected = options[selectedIndex] || options[0];
  useOutsideDismiss(open, [rootRef], () => setOpen(false), triggerRef);

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
    onChange(option.value);
    setOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
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
      className={`saga-fancy-select ${open ? 'open' : ''}`}
      ref={rootRef}
      onBlurCapture={(event) => {
        if (!open || rootRef.current?.contains(event.relatedTarget)) return;
        setOpen(false);
      }}
    >
      <button
        ref={triggerRef}
        type=\"button\"
        aria-haspopup=\"listbox\"
        aria-expanded={open}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
          event.preventDefault();
          setOpen(true);
        }}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.label}</span><ChevronDown size={15} />
      </button>
      {open && (
        <div className=\"saga-fancy-options\" role=\"listbox\" aria-label={label} aria-orientation=\"vertical\">
          {options.map((option, index) => (
            <button
              ref={(node) => { optionRefs.current[index] = node; }}
              type=\"button\"
              role=\"option\"
              aria-selected={String(option.value) === String(value)}
              tabIndex={index === focusIndex ? 0 : -1}
              key={option.value}
              onFocus={() => setFocusIndex(index)}
              onKeyDown={(event) => optionKeyDown(event, index)}
              onClick={() => choose(option)}
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
""",
)

replace_once(
    "apps/studio/src/create-controls.jsx",
    """  useOutsideDismiss(open, [anchorRef, panelRef], onClose);
""",
    """  useOutsideDismiss(open, [anchorRef, panelRef], onClose, anchorRef);
""",
)

# Arrow keys on closed trigger buttons open their menu and let the existing
# roving list focus the selected item.
trigger_replacements = [
    (
        """                    aria-haspopup=\"menu\"
                    aria-expanded={resolutionOpen}
                    onClick={() => {
""",
        """                    aria-haspopup=\"menu\"
                    aria-expanded={resolutionOpen}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
                      event.preventDefault();
                      setResolutionOpen(true);
                      setAspectOpen(false);
                      setSettingsOpen(false);
                    }}
                    onClick={() => {
""",
    ),
    (
        """                    aria-haspopup=\"menu\"
                    aria-expanded={aspectOpen}
                    onClick={() => {
""",
        """                    aria-haspopup=\"menu\"
                    aria-expanded={aspectOpen}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
                      event.preventDefault();
                      setAspectOpen(true);
                      setResolutionOpen(false);
                      setSettingsOpen(false);
                    }}
                    onClick={() => {
""",
    ),
    (
        """                    aria-haspopup=\"menu\"
                    aria-expanded={videoResolutionOpen}
                    onClick={() => {
""",
        """                    aria-haspopup=\"menu\"
                    aria-expanded={videoResolutionOpen}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
                      event.preventDefault();
                      setVideoResolutionOpen(true);
                      setDurationOpen(false);
                      setSettingsOpen(false);
                    }}
                    onClick={() => {
""",
    ),
]
for old, new in trigger_replacements:
    replace_once("apps/studio/src/create-controls.jsx", old, new)

# ---------------------------------------------------------------------------
# Focus-visible styling: 2px indicator across custom picker triggers/options.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/create-workspace-v2.css",
    ".workspace .saga-morph-list button:focus-visible{outline:1px solid #7665ce;outline-offset:-2px}\n",
    ".workspace .saga-morph-list button:focus-visible{outline:2px solid #9f8cff;outline-offset:-2px}\n",
)
replace_once(
    "apps/studio/src/create-workspace-v2.css",
    ".workspace .saga-control-pill:hover,.workspace .saga-control-pill.active{background:#1d222b;border-color:#3b4350;color:#fff}\n",
    ".workspace .saga-control-pill:hover,.workspace .saga-control-pill.active{background:#1d222b;border-color:#3b4350;color:#fff}\n.workspace .saga-control-pill:focus-visible,.workspace .saga-fancy-select>button:focus-visible{outline:2px solid #9f8cff;outline-offset:2px}\n",
)
replace_once(
    "apps/studio/src/create-workspace-v2.css",
    ".workspace .saga-fancy-options button:hover,.workspace .saga-fancy-options button[aria-selected=true]{background:#252a34;color:#fff}\n",
    ".workspace .saga-fancy-options button:hover,.workspace .saga-fancy-options button[aria-selected=true]{background:#252a34;color:#fff}\n.workspace .saga-fancy-options button:focus-visible{outline:2px solid #9f8cff;outline-offset:-2px;background:#252a34;color:#fff}\n",
)
replace_once(
    "apps/studio/src/create-workspace-v2.css",
    ".workspace .saga-video-option-menu button:hover,.workspace .saga-video-option-menu button.selected{background:#252a33;color:#fff}\n",
    ".workspace .saga-video-option-menu button:hover,.workspace .saga-video-option-menu button.selected{background:#252a33;color:#fff}\n.workspace .saga-video-option-menu button:focus-visible{outline:2px solid #9f8cff;outline-offset:-2px;background:#252a33;color:#fff}\n",
)

# ---------------------------------------------------------------------------
# Visual-preview regression checks for legacy/shared pickers.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """async function expectText(locator, expected, label) {
  const text = (await locator.innerText()).trim();
  if (!text.includes(expected)) throw new Error(`${label}: expected ${expected}, got ${text}`);
}
""",
    """async function expectText(locator, expected, label) {
  const text = (await locator.innerText()).trim();
  if (!text.includes(expected)) throw new Error(`${label}: expected ${expected}, got ${text}`);
}

async function expectFocused(locator, label) {
  if (!(await locator.evaluate((element) => document.activeElement === element))) throw new Error(`${label} did not receive focus`);
}

async function expectStrongFocus(locator, label) {
  const result = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return { visible: element.matches(':focus-visible'), outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  if (!result.visible || result.outlineStyle === 'none' || Number.parseFloat(result.outlineWidth) < 2) {
    throw new Error(`${label} focus indicator is not strong enough: ${JSON.stringify(result)}`);
  }
}
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  const resolutionTrigger = desktop.locator('.saga-resolution-trigger');
  await resolutionTrigger.click();
  const resolutionPicker = desktop.locator('.saga-resolution-picker');
""",
    """  const resolutionTrigger = desktop.locator('.saga-resolution-trigger');
  await resolutionTrigger.focus();
  await desktop.keyboard.press('Enter');
  const resolutionPicker = desktop.locator('.saga-resolution-picker');
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  await shot(desktop, '02-image-resolution-picker.png');
  await desktop.keyboard.press('Escape');
  await expectHidden(resolutionPicker, 'Resolution picker');

  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });
  await aspectTrigger.click();
""",
    """  await desktop.keyboard.press('End');
  if (!/4K/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last resolution option');
  await expectStrongFocus(resolutionPicker.getByRole('menuitemradio').last(), 'Resolution End option');
  await shot(desktop, '02-image-resolution-picker.png');
  await desktop.keyboard.press('Home');
  if (!/SD/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first resolution option');
  await desktop.keyboard.press('Escape');
  await expectHidden(resolutionPicker, 'Resolution picker');
  await expectFocused(resolutionTrigger, 'Resolution trigger after Escape');
  await expectStrongFocus(resolutionTrigger, 'Resolution trigger');

  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });
  await aspectTrigger.focus();
  await desktop.keyboard.press('Space');
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  const aspectPreviewBefore = await aspectPicker.locator('.saga-preview-shape').boundingBox();
  await aspectPicker.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).hover();
""",
    """  await desktop.keyboard.press('End');
  if (!/21:9/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last aspect option');
  await expectStrongFocus(aspectPicker.getByRole('menuitemradio').last(), 'Aspect End option');
  await shot(desktop, '02b-image-picker-keyboard-focus.png');
  await desktop.keyboard.press('Home');
  if (!/1:1/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first aspect option');
  const aspectPreviewBefore = await aspectPicker.locator('.saga-preview-shape').boundingBox();
  await aspectPicker.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).hover();
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  await shot(desktop, '02-image-aspect-picker.png');
  await desktop.locator('.saga-stage-heading').click();
  await expectHidden(aspectPicker, 'Aspect picker');
""",
    """  await shot(desktop, '02-image-aspect-picker.png');
  await desktop.keyboard.press('Escape');
  await expectHidden(aspectPicker, 'Aspect picker');
  await expectFocused(aspectTrigger, 'Aspect trigger after Escape');
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  const outputSelect = advanced.locator('.saga-advanced-top .saga-fancy-select').nth(1);
  await outputSelect.locator(':scope > button').click();
  await outputSelect.getByRole('option', { name: '2 outputs' }).click();
  await outputSelect.locator(':scope > button').click();
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await outputSelect.locator(':scope > button').click();
""",
    """  const outputSelect = advanced.locator('.saga-advanced-top .saga-fancy-select').nth(1);
  const outputTrigger = outputSelect.locator(':scope > button');
  await outputTrigger.focus();
  await desktop.keyboard.press('Enter');
  const outputOptions = outputSelect.getByRole('option');
  await outputOptions.first().waitFor({ state: 'visible' });
  await desktop.keyboard.press('End');
  if (!/4 outputs/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last advanced select option');
  await desktop.keyboard.press('Home');
  if (!/1 output/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first advanced select option');
  await desktop.keyboard.press('ArrowDown');
  if (!/2 outputs/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('ArrowDown did not move advanced select focus');
  await expectStrongFocus(outputOptions.nth(1), 'Advanced output option');
  await shot(desktop, '03b-advanced-picker-keyboard-focus.png');
  await desktop.keyboard.press('Enter');
  await expectText(outputTrigger, '2 outputs', 'Advanced keyboard selection');
  await expectFocused(outputTrigger, 'Advanced select trigger after selection');
  await desktop.keyboard.press('Space');
  await outputOptions.first().waitFor({ state: 'visible' });
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await desktop.keyboard.press('Escape');
  await expectFocused(outputTrigger, 'Advanced select trigger after Escape');
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  await videoResolutionTrigger.click();
  const videoResolutionPicker = desktop.locator('.saga-picker').filter({ has: desktop.getByRole('menu', { name: 'Video resolution' }) });
""",
    """  await videoResolutionTrigger.focus();
  await desktop.keyboard.press('ArrowDown');
  const videoResolutionPicker = desktop.locator('.saga-picker').filter({ has: desktop.getByRole('menu', { name: 'Video resolution' }) });
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  await shot(desktop, '04-video-resolution-picker.png');
  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K.*3840 px/i }).click();

  await durationTrigger.click();
""",
    """  await shot(desktop, '04-video-resolution-picker.png');
  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K.*3840 px/i }).click();
  await expectFocused(videoResolutionTrigger, 'Video resolution trigger after selection');

  await durationTrigger.focus();
  await desktop.keyboard.press('Enter');
""",
)

replace_once(
    "apps/studio/scripts/capture-ui-preview.mjs",
    """  await durationRange.fill('23');
  await desktop.locator('.saga-stage-heading').click();
  await expectHidden(durationPicker, 'Duration picker');
""",
    """  await durationRange.fill('23');
  await desktop.keyboard.press('Escape');
  await expectHidden(durationPicker, 'Duration picker');
  await expectFocused(durationTrigger, 'Duration trigger after Escape');
""",
)

# ---------------------------------------------------------------------------
# Dedicated Video-output compact-picker keyboard checks + screenshot.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/scripts/capture-video-output-preview.mjs",
    """  await aspect.click();
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect ratio' });
  await aspectMenu.waitFor({ state: 'visible' });
  await aspectMenu.getByRole('menuitemradio', { name: /9:16/ }).click();
""",
    """  await aspect.focus();
  await page.keyboard.press('ArrowDown');
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect ratio' });
  await aspectMenu.waitFor({ state: 'visible' });
  const aspectOptions = aspectMenu.getByRole('menuitemradio');
  await page.keyboard.press('Home');
  for (let step = 0; step < 4; step += 1) await page.keyboard.press('ArrowDown');
  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');
  await page.keyboard.press('Enter');
""",
)

replace_once(
    "apps/studio/scripts/capture-video-output-preview.mjs",
    """  await fps.click();
  const fpsMenu = page.getByRole('menu', { name: 'Video frame rate' });
  await fpsMenu.waitFor({ state: 'visible' });
  await fpsMenu.getByRole('menuitemradio', { name: '30 fps', exact: true }).click();
  if (!(await fps.innerText()).includes('30 fps')) throw new Error('Video frame-rate picker did not update to 30 fps');

  await aspect.click();
""",
    """  await fps.focus();
  await page.keyboard.press('Space');
  const fpsMenu = page.getByRole('menu', { name: 'Video frame rate' });
  await fpsMenu.waitFor({ state: 'visible' });
  await page.keyboard.press('End');
  const focusedFps = fpsMenu.getByRole('menuitemradio', { name: '30 fps', exact: true });
  if (!(await focusedFps.evaluate((element) => element === document.activeElement && element.matches(':focus-visible')))) throw new Error('Video FPS End navigation/focus-visible failed');
  const fpsOutline = await focusedFps.evaluate((element) => Number.parseFloat(getComputedStyle(element).outlineWidth));
  if (fpsOutline < 2) throw new Error(`Video FPS focus indicator is too weak: ${fpsOutline}`);
  await page.screenshot({ path: path.join(outputDir, '05f-video-picker-keyboard-focus.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05f-video-picker-keyboard-focus.png');
  await page.keyboard.press('Enter');
  if (!(await fps.innerText()).includes('30 fps')) throw new Error('Video frame-rate picker did not update to 30 fps');
  if (!(await fps.evaluate((element) => document.activeElement === element))) throw new Error('Video FPS trigger did not regain focus after selection');

  await aspect.focus();
  await page.keyboard.press('Enter');
""",
)

replace_once(
    "apps/studio/scripts/capture-video-output-preview.mjs",
    """  diagnostics.screenshots.push('05c-video-aspect-picker.png');
  await page.keyboard.press('Escape');
""",
    """  diagnostics.screenshots.push('05c-video-aspect-picker.png');
  await page.keyboard.press('Escape');
  if (!(await aspect.evaluate((element) => document.activeElement === element))) throw new Error('Video aspect trigger did not regain focus after Escape');
""",
)

print("Iteration 4 keyboard patch applied successfully")
