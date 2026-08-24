from pathlib import Path

path = Path('apps/studio/scripts/capture-video-output-preview.mjs')
text = path.read_text(encoding='utf-8')
old = "const browser = await chromium.launch({ headless: true });\ntry {\n  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });"
new = "const browser = await chromium.launch({ headless: true });\nconst context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });\ntry {\n  let page = await context.newPage();"
if old not in text:
    raise SystemExit('expected browser/page setup not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
