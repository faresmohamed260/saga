from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text()
old = '- [~] **27. Dedicated typography/contrast accessibility pass.** Implementation in validation: dense 9/10/11px token tiers were raised to a 10/11/12px minimum scale, muted/subtle text roles were brightened, a shared focus halo now supplements the 2px focus ring, Gallery filter/Manage state semantics expose `aria-pressed`, and selected states add weight/shape cues so they do not depend on color alone. A deterministic accessibility-polish contract runs in the normal Studio build.'
new = '- [x] **27. Dedicated typography/contrast accessibility pass.** Dense 9/10/11px token tiers were raised to a 10/11/12px minimum scale, muted/subtle text roles were brightened, a shared focus halo supplements the 2px focus ring, Gallery filter/Manage states expose `aria-pressed`, and selected states add weight/shape cues so they do not depend on color alone. A deterministic accessibility-polish contract now runs in the normal Studio build. Final artifact `9534555187` from Studio Visual Preview `32766234976` was manually inspected across desktop Create, picker keyboard focus, desktop Gallery, and 390px mobile Manage; the readability gains do not introduce crowding or clipping and focus/state cues remain clear. Validated by Studio CI `32766235138`, Studio Visual Preview `32766234976`, Backend Architecture CI `32766235176`, Modal Worker Inventory `32766235289`, Worker Fleet Live Smoke `32766235212`, and Required Check Compatibility `32766235093`. **Iteration 27 complete.**'
if old not in text:
    raise SystemExit('Item 27 in-progress marker missing')
text = text.replace(old, new, 1)
text = text.replace('P2 polish is active; next planned scope begins at **Item 27**.', 'P2 polish is active; next planned scope begins at **Item 28**.')
path.write_text(text)
print('Completed Iteration 27 checklist bookkeeping.')
