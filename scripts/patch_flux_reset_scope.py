from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'apps/studio/src/create-controls.jsx'
text = path.read_text(encoding='utf-8')
old = "                if (isEdit) setOutputs(1);\n"
if text.count(old) != 1:
    raise RuntimeError(f'expected one hidden output reset, got {text.count(old)}')
path.write_text(text.replace(old, '', 1), encoding='utf-8')

contract = root / 'apps/studio/scripts/check-create-advanced-contract.mjs'
text = contract.read_text(encoding='utf-8')
needle = "expect(controls.includes('data-ltx-fixed-steps=\"11\"'), 'LTX fixed 8+3 step recipe must be explicit in Advanced');\n"
addition = needle + "expect(!controls.includes('if (isEdit) setOutputs(1)'), 'FLUX preset reset must not silently change output count');\n"
if text.count(needle) != 1:
    raise RuntimeError('contract marker missing')
contract.write_text(text.replace(needle, addition, 1), encoding='utf-8')
