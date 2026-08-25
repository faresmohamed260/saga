from pathlib import Path

path = Path('apps/studio/src/create-controls.jsx')
text = path.read_text(encoding='utf-8')

old = """  useEffect(() => {
    if (!open) return undefined;
    const frame = window.requestAnimationFrame(() => {
      optionRefs.current[pendingFocusIndexRef.current]?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, options.length]);

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);
"""
new = """  const menuPositioned = Boolean(position);
  useEffect(() => {
    if (!open || !menuPositioned) return undefined;
    const frame = window.requestAnimationFrame(() => {
      optionRefs.current[pendingFocusIndexRef.current]?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, menuPositioned, options.length]);

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);
"""
if old in text:
    text = text.replace(old, new, 1)
elif 'menuPositioned' not in text:
    raise SystemExit('Position-aware FancySelect focus anchor missing')

path.write_text(text, encoding='utf-8')
