from pathlib import Path

path = Path('apps/studio/src/create-controls.jsx')
text = path.read_text()
old = '''    const onPointer = (event) => {\n      if (refs.some((item) => item.current?.contains(event.target))) return;\n      if (protectNestedEscape && event.target?.closest?.('[data-advanced-trigger="true"]')) return;\n      close();\n    };'''
new = '''    const onPointer = (event) => {\n      if (refs.some((item) => item.current?.contains(event.target))) return;\n      if (protectNestedEscape && event.target?.closest?.('[data-advanced-trigger="true"], .saga-fancy-options-portal')) return;\n      close();\n    };'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one useOutsideDismiss pointer block, found {count}')
path.write_text(text.replace(old, new, 1))
print('Advanced portal dismissal fixed')
