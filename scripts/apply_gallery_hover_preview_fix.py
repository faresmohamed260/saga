from pathlib import Path

path = Path('apps/studio/src/components/MediaCard.jsx')
text = path.read_text(encoding='utf-8')
old = "  const hoverPreviewActive = previewVisible && previewHoverCapable && previewHoverIntent;"
new = "  const hoverPreviewActive = previewHoverCapable && previewHoverIntent;"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('Gallery hover preview gate anchor missing')
path.write_text(text, encoding='utf-8')
