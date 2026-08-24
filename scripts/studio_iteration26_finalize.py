from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text()
old = '- [~] **26. Consolidate CSS into a small design-token system.** Implementation in validation: `design-tokens.css` is the canonical role-based layer for surfaces/text/borders/accent/danger/success, spacing, radii, control heights, type scale, focus rings, and transitions; high-churn Studio CSS now consumes those tokens without changing rendered values, legacy root aliases point to the shared roles, and one obsolete `!important` specificity patch was removed. The visual harness asserts the token contract is loaded before rendering.'
new = '- [x] **26. Consolidate CSS into a small design-token system.** `design-tokens.css` is now the canonical role-based layer for surfaces/text/borders/accent/danger/success, spacing, radii, control heights, type scale, focus rings, and transitions. High-churn Studio CSS consumes those tokens without changing rendered values; legacy root aliases point to the shared roles; one obsolete `!important` specificity patch was removed; and the Generate contract was updated to validate the shared focus-ring token rather than a duplicated literal. The visual harness asserts the token contract is loaded before rendering. Final artifact `9533868281` from Studio Visual Preview `32764269574` was manually inspected across desktop Create, Video resolution picker, desktop Gallery, and 390px mobile Gallery with no layout or interaction regression. Validated by Studio CI `32764269513`, Studio Visual Preview `32764269574`, Backend Architecture CI `32764269509`, Modal Worker Inventory `32764269487`, Worker Fleet Live Smoke `32764269612`, and Required Check Compatibility `32764269512`. **Iteration 26 complete.**'
if old not in text:
    raise SystemExit('Item 26 in-progress marker missing')
text = text.replace(old, new, 1)
text = text.replace('P2 polish is active; next planned scope begins at **Item 26**.', 'P2 polish is active; next planned scope begins at **Item 27**.')
path.write_text(text)
print('Completed Iteration 26 checklist bookkeeping.')
