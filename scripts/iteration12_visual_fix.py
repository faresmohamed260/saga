from pathlib import Path

path = Path('apps/studio/scripts/capture-video-output-preview.mjs')
text = path.read_text(encoding='utf-8')

old_setup = "const browser = await chromium.launch({ headless: true });\ntry {\n  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });"
new_setup = "const browser = await chromium.launch({ headless: true });\nconst context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });\ntry {\n  let page = await context.newPage();"
if old_setup in text:
    text = text.replace(old_setup, new_setup, 1)

for route in ['**/api/generate', '**/api/job-actions', '**/api/jobs?**', '**/api/generate/result?**']:
    text = text.replace(f"await page.route('{route}'", f"await context.route('{route}'", 1)

if "const context = await browser.newContext" not in text:
    raise SystemExit('browser context setup is missing')
if "await page.route('**/api/generate'" in text:
    raise SystemExit('generation route is still page-scoped')

path.write_text(text, encoding='utf-8')
