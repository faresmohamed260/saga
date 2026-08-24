from pathlib import Path
import iteration8_shared_aspect_patch as base

ROOT = Path(__file__).resolve().parents[3]


def refine_component() -> None:
    base.apply_product()
    path = ROOT / "apps/studio/src/features/create/AspectPicker.jsx"
    text = path.read_text()

    old_focus = '''  useEffect(() => {\n    if (!open) {\n      setPreviewIndex(null);\n      return undefined;\n    }\n    setFocusIndex(selectedIndex);\n    setPreviewIndex(null);\n    const frame = requestAnimationFrame(() => optionRefs.current[selectedIndex]?.focus());\n    return () => cancelAnimationFrame(frame);\n  }, [open, selectedIndex, options.length]);\n'''
    new_focus = '''  useEffect(() => {\n    if (!open) {\n      setPreviewIndex(null);\n      return undefined;\n    }\n    setFocusIndex(selectedIndex);\n    setPreviewIndex(null);\n    const focusSelected = () => optionRefs.current[selectedIndex]?.focus();\n    focusSelected();\n    const timer = window.setTimeout(focusSelected, 60);\n    return () => window.clearTimeout(timer);\n  }, [open, selectedIndex, options.length]);\n'''
    if text.count(old_focus) != 1:
        raise RuntimeError("Could not locate shared AspectPicker option-focus effect")
    text = text.replace(old_focus, new_focus, 1)

    old_effect = '''    const pointer = (event) => {\n      if (rootRef.current?.contains(event.target)) return;\n      setOpen(false);\n    };\n    const key = (event) => {\n      if (event.key !== 'Escape') return;\n      event.preventDefault();\n      event.stopPropagation();\n      setOpen(false);\n      triggerRef.current?.focus();\n    };\n    document.addEventListener('pointerdown', pointer);\n    document.addEventListener('keydown', key);\n    return () => {\n      document.removeEventListener('pointerdown', pointer);\n      document.removeEventListener('keydown', key);\n    };\n'''
    new_effect = '''    const pointer = (event) => {\n      if (rootRef.current?.contains(event.target)) return;\n      setOpen(false);\n    };\n    const focus = (event) => {\n      if (rootRef.current?.contains(event.target)) return;\n      setOpen(false);\n    };\n    const key = (event) => {\n      if (event.key !== 'Escape') return;\n      event.preventDefault();\n      event.stopPropagation();\n      setOpen(false);\n      triggerRef.current?.focus();\n    };\n    document.addEventListener('pointerdown', pointer);\n    document.addEventListener('focusin', focus);\n    document.addEventListener('keydown', key);\n    return () => {\n      document.removeEventListener('pointerdown', pointer);\n      document.removeEventListener('focusin', focus);\n      document.removeEventListener('keydown', key);\n    };\n'''
    if text.count(old_effect) != 1:
        raise RuntimeError("Could not locate shared AspectPicker dismissal effect")
    text = text.replace(old_effect, new_effect, 1)

    old_root = '''    <div\n      ref={rootRef}\n      className="saga-shared-aspect-root"\n      onBlurCapture={(event) => {\n        if (!open || rootRef.current?.contains(event.relatedTarget)) return;\n        setOpen(false);\n      }}\n    >\n'''
    new_root = '''    <div ref={rootRef} className="saga-shared-aspect-root">\n'''
    if text.count(old_root) != 1:
        raise RuntimeError("Could not locate shared AspectPicker root blur handler")
    text = text.replace(old_root, new_root, 1)

    path.write_text(text)
    base.validate_source()
    print("Iteration 8 deterministic focus-management refinement applied")


if __name__ == '__main__':
    refine_component()
