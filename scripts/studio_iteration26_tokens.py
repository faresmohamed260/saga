from pathlib import Path
import re

ROOT = Path('apps/studio/src')
FILES = [
    ROOT / 'styles.css',
    ROOT / 'create-controls.css',
    ROOT / 'create-workspace-v2.css',
    ROOT / 'gallery-controls.css',
    ROOT / 'studio-polish.css',
]

# Preserve the existing public aliases while making the shared token file canonical.
styles = (ROOT / 'styles.css').read_text()
aliases = {
    '--bg: #080a0f;': '--bg: var(--saga-color-bg);',
    '--panel: #0d1017;': '--panel: var(--saga-color-surface-1);',
    '--panel-2: #11151d;': '--panel-2: var(--saga-color-surface-2);',
    '--line: rgba(255,255,255,.11);': '--line: var(--saga-border);',
    '--line-strong: rgba(255,255,255,.18);': '--line-strong: var(--saga-border-strong);',
    '--muted: #9da4b3;': '--muted: var(--saga-color-text-muted);',
    '--muted-2: #737b8a;': '--muted-2: var(--saga-color-text-subtle);',
    '--accent: #7a5cff;': '--accent: var(--saga-color-accent);',
    '--accent-2: #4b9cff;': '--accent-2: var(--saga-color-accent-secondary);',
}
for old, new in aliases.items():
    if old not in styles:
        raise SystemExit(f'Missing root alias: {old}')
    styles = styles.replace(old, new, 1)
(ROOT / 'styles.css').write_text(styles)

property_tokens = {
    'border-radius': {
        '7px': 'var(--saga-radius-xs)',
        '9px': 'var(--saga-radius-sm)',
        '10px': 'var(--saga-radius-md)',
        '12px': 'var(--saga-radius-lg)',
        '14px': 'var(--saga-radius-xl)',
        '17px': 'var(--saga-radius-2xl)',
        '22px': 'var(--saga-radius-3xl)',
        '999px': 'var(--saga-radius-pill)',
    },
    'font-size': {
        '9px': 'var(--saga-text-2xs)',
        '10px': 'var(--saga-text-xs)',
        '11px': 'var(--saga-text-sm)',
        '12px': 'var(--saga-text-md)',
        '13px': 'var(--saga-text-lg)',
        '14px': 'var(--saga-text-base)',
    },
}

literal_tokens = {
    '#080a0f': 'var(--saga-color-bg)',
    '#0d1017': 'var(--saga-color-surface-1)',
    '#11151d': 'var(--saga-color-surface-2)',
    '#11151c': 'var(--saga-color-surface-2-alt)',
    '#151920': 'var(--saga-color-surface-control)',
    '#1d222b': 'var(--saga-color-surface-control-hover)',
    '#9da4b3': 'var(--saga-color-text-muted)',
    '#737b8a': 'var(--saga-color-text-subtle)',
    '#7a5cff': 'var(--saga-color-accent)',
    '#9f8cff': 'var(--saga-color-accent-soft)',
    '#4b9cff': 'var(--saga-color-accent-secondary)',
    'rgba(255,255,255,.11)': 'var(--saga-border)',
    'rgba(255,255,255,.18)': 'var(--saga-border-strong)',
    'rgba(255,255,255,.08)': 'var(--saga-border-subtle)',
}

for path in FILES:
    text = path.read_text()
    for prop, values in property_tokens.items():
        for value, token in values.items():
            text = re.sub(rf'({re.escape(prop)}\s*:\s*){re.escape(value)}(?=\s*[;}}])', rf'\1{token}', text)
    for literal, token in literal_tokens.items():
        text = text.replace(literal, token)
    text = text.replace('outline:2px solid var(--saga-color-accent-soft)', 'outline:var(--saga-focus-ring)')
    text = text.replace('outline: 2px solid var(--saga-color-accent-soft)', 'outline: var(--saga-focus-ring)')
    text = text.replace('transition:.18s ease', 'transition:var(--saga-transition-base)')
    text = text.replace('transition: .18s ease', 'transition: var(--saga-transition-base)')
    text = text.replace('transition:.16s ease', 'transition:var(--saga-transition-fast)')
    text = text.replace('transition: .16s ease', 'transition: var(--saga-transition-fast)')
    path.write_text(text)

# One obsolete specificity patch can safely go because create-controls.css loads after styles.css.
controls = (ROOT / 'create-controls.css').read_text()
controls = controls.replace('.mode-tabs{display:none!important}', '.mode-tabs{display:none}')
(ROOT / 'create-controls.css').write_text(controls)

# Add a lightweight rendered token contract to the existing visual harness.
capture = Path('apps/studio/scripts/capture-ui-preview.mjs')
body = capture.read_text()
needle = "  await waitForStudio(desktop);\n\n  // Core composition:"
insert = """  await waitForStudio(desktop);\n\n  const tokenContract = await desktop.evaluate(() => {\n    const root = getComputedStyle(document.documentElement);\n    return {\n      bg: root.getPropertyValue('--saga-color-bg').trim(),\n      radius: root.getPropertyValue('--saga-radius-lg').trim(),\n      control: root.getPropertyValue('--saga-control-md').trim(),\n      text: root.getPropertyValue('--saga-text-md').trim(),\n      focus: root.getPropertyValue('--saga-focus-ring').trim(),\n    };\n  });\n  if (tokenContract.bg !== '#080a0f' || tokenContract.radius !== '12px' || tokenContract.control !== '36px' || tokenContract.text !== '12px' || !tokenContract.focus.includes('2px')) {\n    throw new Error(`Studio design token contract is incomplete: ${JSON.stringify(tokenContract)}`);\n  }\n\n  // Core composition:"""
if needle not in body:
    raise SystemExit('Visual token-contract insertion point missing')
capture.write_text(body.replace(needle, insert, 1))

checklist = Path('docs/studio-ui-polish-checklist.md')
body = checklist.read_text()
old = '- [ ] **26. Consolidate CSS into a small design-token system.** Standardize spacing, radii, control heights, typography, surfaces, accent/danger/success, and reduce specificity/`!important` patches.'
new = '- [~] **26. Consolidate CSS into a small design-token system.** Implementation in validation: `design-tokens.css` is the canonical role-based layer for surfaces/text/borders/accent/danger/success, spacing, radii, control heights, type scale, focus rings, and transitions; high-churn Studio CSS now consumes those tokens without changing rendered values, legacy root aliases point to the shared roles, and one obsolete `!important` specificity patch was removed. The visual harness asserts the token contract is loaded before rendering.'
if old not in body:
    raise SystemExit('Item 26 marker missing')
checklist.write_text(body.replace(old, new, 1))

print('Iteration 26 token migration applied.')
