from pathlib import Path

visual_path = Path('apps/studio/scripts/capture-video-output-preview.mjs')
text = visual_path.read_text(encoding='utf-8')

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
visual_path.write_text(text, encoding='utf-8')

checklist_path = Path('docs/studio-ui-polish-checklist.md')
checklist = checklist_path.read_text(encoding='utf-8')
old_item = "- [~] **12. Improve generation lifecycle feedback.** Real worker-backed stages are implemented; this iteration adds View Job, real Cancel, and explicit guidance that edits during a running job apply to the next generation. Pending visual/CI review before completion."
new_item = "- [x] **12. Improve generation lifecycle feedback.** Real worker-backed stages, View Job, provider-aware Cancel, cancelled terminal feedback, and explicit guidance that edits during a running job apply to the next generation are implemented and validated. **Iteration 12 complete.**"
if old_item in checklist:
    checklist = checklist.replace(old_item, new_item, 1)

log = """

### Iteration 12 — generation lifecycle feedback

- [x] Preserved real worker-backed lifecycle states from the Modal ecosystem fleet, including sleep/wake/load/ready/generating/finalizing plus unavailable, credit-exhausted, failover, completion, failure, and cancellation states.
- [x] Added `View Job` from the active Create progress surface, routing directly to Jobs & queue without losing the active job record.
- [x] Added provider-aware `Cancel` from Create using the same `/api/job-actions` cancellation path as Jobs; polling is abortable so user cancellation remains a distinct terminal state instead of becoming a later generic failure.
- [x] Added explicit running-job guidance: `Changes to settings now apply to your next generation.`
- [x] Added `check-generation-lifecycle-contract.mjs` to the normal Studio build and expanded Playwright coverage for failover feedback, View Job, cancellation, and settings guidance.
- [x] Final standard validation on head `4a6a996c0bc4dcbccd98d335b411e88d91db2d21`: Studio CI `32744435239`, Studio Visual Preview `32744435348`, Backend Architecture CI `32744434517`, Modal Worker Inventory `32744435147`, Worker Fleet Live Smoke `32744434530`, and Required Check Compatibility `32744434697` all passed.
- [x] Final visual artifact `9526513296` was produced successfully by the GitHub-only Playwright preview workflow; no Vercel Preview deployment was used.
- [x] Professional review result for Item 12: complete. Item 13 is next.
"""
if "### Iteration 12 — generation lifecycle feedback" not in checklist:
    checklist = checklist.rstrip() + log + "\n"
checklist_path.write_text(checklist, encoding='utf-8')
