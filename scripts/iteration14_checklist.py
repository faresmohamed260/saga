from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text(encoding='utf-8')
old = "- [ ] **14. Make bulk selection wording precise.** Use `Select visible` unless selection truly spans all matching paginated results."
new = "- [x] **14. Make bulk selection wording precise.** Gallery Manage mode now says `Select visible`, matching its actual behavior of selecting only the currently loaded media rather than implying all matching paginated results. Validated by Studio CI 32746565855, Studio Visual Preview 32746565875, Backend Architecture CI 32746565882, Modal Worker Inventory 32746565838, Worker Fleet Live Smoke 32746565893, and Required Check Compatibility 32746565840. **Iteration 14 complete.**"
if old not in text:
    raise SystemExit('Iteration 14 checklist line not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
