from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')
old = '''    controls = sub_once(
        controls,
        r'(              <div className="saga-seed-row">.*?
              </div>)',
        lambda match: match.group(1) + negative_block,
        "render backend negative prompt control",
    )'''
new = '''    controls = replace_once(
        controls,
        "              </div>\\n              {preset.stepsEditable ? (",
        "              </div>" + negative_block + "\\n              {preset.stepsEditable ? (",
        "render backend negative prompt control",
    )'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one broken seed-insertion block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
