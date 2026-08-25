from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'apps/studio/scripts/capture-video-output-preview.mjs'
text = path.read_text(encoding='utf-8')
old = """  const fps = advanced.locator('.saga-fancy-select').filter({ has: advanced.getByRole('button', { name: 'Video frame rate', exact: true }) });
  const fpsTrigger = fps.locator(':scope > button');
"""
new = """  const fpsTrigger = advanced.getByRole('button', { name: 'Video frame rate', exact: true });
"""
if text.count(old) != 1:
    raise RuntimeError(f'expected one FPS locator block, got {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
