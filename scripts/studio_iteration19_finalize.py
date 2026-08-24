from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checklist = ROOT / 'docs/studio-ui-polish-checklist.md'
text = checklist.read_text()
old = '- [ ] **19. Rename History internals to Gallery.** `HistoryView`, `historyItems`, `loadHistory`, CSS names, etc.; API path may be migrated separately if risk is not justified.'
new = '- [x] **19. Rename History internals to Gallery.** `GalleryView`, `galleryItems`, `loadGallery`, `gallery-*` CSS hooks, and `gallery-controls.css` now match the product terminology. The existing `/api/history` endpoint and legacy `#/history` route alias are intentionally retained as compatibility surfaces to avoid unnecessary migration risk. Final artifact `9529741150` from Studio Visual Preview `32752854888` was manually inspected at desktop, 390px mobile, and mobile Manage states: Gallery layout, filters, cards, and the bottom manager remain visually unchanged and contained. Validated by Studio CI `32752855009`, Studio Visual Preview `32752854888`, Backend Architecture CI `32752854626`, Modal Worker Inventory `32752854616`, Worker Fleet Live Smoke `32752854778`, and Required Check Compatibility `32752854618`. **Iteration 19 complete.**'
if old in text:
    checklist.write_text(text.replace(old, new, 1))
elif new not in text:
    raise SystemExit('Iteration 19 checklist entry not found')

for rel in [
    'scripts/studio_iteration19_patch.py',
    '.github/workflows/studio-iteration19-patch.yml',
    'scripts/studio_iteration12_patch.py',
    '.github/workflows/studio-iteration12-patch.yml',
    'scripts/studio_iteration19_finalize.py',
    '.github/workflows/studio-iteration19-finalize.yml',
]:
    path = ROOT / rel
    if path.exists():
        path.unlink()

print('Iteration 19 finalized and temporary patch machinery removed.')
