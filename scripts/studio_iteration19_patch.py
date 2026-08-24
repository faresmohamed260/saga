from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'apps/studio/src'
APP = SRC / 'app/App.jsx'
OLD_VIEW = SRC / 'features/library/HistoryView.jsx'
NEW_VIEW = SRC / 'features/library/GalleryView.jsx'
OLD_CSS = SRC / 'history-controls.css'
NEW_CSS = SRC / 'gallery-controls.css'
INDEX = ROOT / 'apps/studio/index.html'


def replace(path, pairs):
    text = path.read_text()
    for old, new in pairs:
        text = text.replace(old, new)
    path.write_text(text)

# App-level internal terminology. Keep /api/history and the #/history route alias for compatibility.
replace(APP, [
    ("import HistoryView from '../features/library/HistoryView.jsx';", "import GalleryView from '../features/library/GalleryView.jsx';"),
    ('HISTORY_PAGE_SIZE', 'GALLERY_PAGE_SIZE'),
    ('toHistoryItem', 'toGalleryItem'),
    ('historyItems', 'galleryItems'),
    ('setHistoryItems', 'setGalleryItems'),
    ('historyLoading', 'galleryLoading'),
    ('setHistoryLoading', 'setGalleryLoading'),
    ('historyAppending', 'galleryAppending'),
    ('setHistoryAppending', 'setGalleryAppending'),
    ('historyError', 'galleryError'),
    ('setHistoryError', 'setGalleryError'),
    ('historyKind', 'galleryKind'),
    ('setHistoryKind', 'setGalleryKind'),
    ('historyModel', 'galleryModel'),
    ('setHistoryModel', 'setGalleryModel'),
    ('historyModels', 'galleryModels'),
    ('setHistoryModels', 'setGalleryModels'),
    ('historyPage', 'galleryPage'),
    ('setHistoryPage', 'setGalleryPage'),
    ('loadHistory', 'loadGallery'),
    ('<HistoryView', '<GalleryView'),
    ('History request failed', 'Gallery request failed'),
])

# Rename the Gallery component and remove legacy history-prefixed CSS hooks.
view = OLD_VIEW.read_text()
view = view.replace('function HistoryView', 'function GalleryView')
view = view.replace('className="history-view gallery-view"', 'className="gallery-view"')
view = view.replace('history-', 'gallery-')
NEW_VIEW.write_text(view)
OLD_VIEW.unlink()

# Rename stylesheet and its selectors.
css = OLD_CSS.read_text().replace('history-', 'gallery-')
NEW_CSS.write_text(css)
OLD_CSS.unlink()
replace(INDEX, [('/src/history-controls.css', '/src/gallery-controls.css')])

# Media cards and visual tests should use Gallery terminology too.
for path in list(SRC.rglob('*.jsx')) + list(SRC.rglob('*.js')) + list(SRC.rglob('*.css')) + list((ROOT / 'apps/studio/scripts').glob('*.mjs')):
    if path == APP or path == NEW_VIEW or path == NEW_CSS:
        continue
    text = path.read_text()
    updated = text.replace('history-card', 'gallery-card')
    if updated != text:
        path.write_text(updated)

print('Iteration 19 Gallery internal rename applied.')
