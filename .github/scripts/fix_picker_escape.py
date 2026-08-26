from pathlib import Path

path = Path('apps/studio/src/create-controls.jsx')
text = path.read_text()
old = '''      style={position || { visibility: 'hidden' }}\n      onBlurCapture={(event) => {\n        const next = event.relatedTarget;\n        if (!next || popoverRef.current?.contains(next) || anchorRef.current?.contains(next)) return;\n        onClose();\n      }}\n    >'''
new = '''      style={position || { visibility: 'hidden' }}\n      onKeyDownCapture={(event) => {\n        if (event.key !== 'Escape') return;\n        event.preventDefault();\n        event.stopPropagation();\n        onClose();\n        window.setTimeout(() => anchorRef.current?.focus(), 0);\n      }}\n      onBlurCapture={(event) => {\n        const next = event.relatedTarget;\n        if (!next || popoverRef.current?.contains(next) || anchorRef.current?.contains(next)) return;\n        onClose();\n      }}\n    >'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one PickerShell match, found {count}')
path.write_text(text.replace(old, new, 1))
print('Picker Escape handling fixed')
