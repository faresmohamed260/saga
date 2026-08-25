from pathlib import Path

path = Path('apps/studio/src/create-controls.jsx')
text = path.read_text(encoding='utf-8')

old_refs = """  const popoverRef = useRef(null);
  const optionRefs = useRef([]);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
"""
new_refs = """  const popoverRef = useRef(null);
  const optionRefs = useRef([]);
  const pendingFocusIndexRef = useRef(0);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
"""
if old_refs in text:
    text = text.replace(old_refs, new_refs, 1)
elif 'pendingFocusIndexRef' not in text:
    raise SystemExit('FancySelect refs anchor missing')

old_open = """  const openMenu = (focusIndex = selectedIndex) => {
    const width = triggerRef.current?.getBoundingClientRect().width;
    setMenuWidth(Math.max(180, Math.round(width || 220)));
    setOpen(true);
    window.setTimeout(() => optionRefs.current[focusIndex]?.focus(), 0);
  };

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);
"""
new_open = """  const openMenu = (focusIndex = selectedIndex) => {
    const width = triggerRef.current?.getBoundingClientRect().width;
    setMenuWidth(Math.max(180, Math.round(width || 220)));
    pendingFocusIndexRef.current = focusIndex;
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return undefined;
    const frame = window.requestAnimationFrame(() => {
      optionRefs.current[pendingFocusIndexRef.current]?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, options.length]);

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);
"""
if old_open in text:
    text = text.replace(old_open, new_open, 1)
elif 'requestAnimationFrame' not in text[text.find('function FancySelect'):text.find('function RangeField')]:
    raise SystemExit('FancySelect openMenu anchor missing')

path.write_text(text, encoding='utf-8')
