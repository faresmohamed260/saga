from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'apps/studio/src/create-controls.jsx'
text = path.read_text(encoding='utf-8')
old = '''      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
'''
new = '''      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="listbox"
'''
if text.count(old) != 1:
    raise RuntimeError(f'expected one FancySelect trigger, got {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

contract = root / 'apps/studio/scripts/check-create-advanced-contract.mjs'
text = contract.read_text(encoding='utf-8')
needle = "expect(controls.includes('label=\"Video frame rate\"'), 'Video frame rate must live in Advanced');\n"
addition = needle + "expect(controls.includes('aria-label={label}'), 'Advanced custom-select triggers must expose their accessible labels');\n"
if text.count(needle) != 1:
    raise RuntimeError('contract marker missing')
contract.write_text(text.replace(needle, addition, 1), encoding='utf-8')
