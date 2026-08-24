from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text()
old = '- [ ] **27. Dedicated typography/contrast accessibility pass.** Raise overly small 9–11px text where appropriate, improve muted contrast, audit focus visibility and non-color state communication.'
new = '- [~] **27. Dedicated typography/contrast accessibility pass.** Implementation in validation: dense 9/10/11px token tiers were raised to a 10/11/12px minimum scale, muted/subtle text roles were brightened, a shared focus halo now supplements the 2px focus ring, Gallery filter/Manage state semantics expose `aria-pressed`, and selected states add weight/shape cues so they do not depend on color alone. A deterministic accessibility-polish contract runs in the normal Studio build.'
if old not in text:
    raise SystemExit('Item 27 pending marker missing')
path.write_text(text.replace(old, new, 1))
print('Marked Iteration 27 in validation.')
