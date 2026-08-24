from pathlib import Path

capture = Path('apps/studio/scripts/capture-ui-preview.mjs')
text = capture.read_text()
text = text.replace('// Core composition: no old mode navbar, centered composer, More moved to sidebar.', '// Core composition: no old mode navbar, centered composer, additional creation Tools live in the sidebar.')
text = text.replace("await desktop.getByRole('button', { name: 'More', exact: true }).waitFor({ state: 'visible' });", "await desktop.getByRole('button', { name: 'Tools', exact: true }).waitFor({ state: 'visible' });\n  const sidebar = desktop.locator('.sidebar');\n  if ((await sidebar.innerText()).includes('FLUX.2 online')) throw new Error('Provider status leaked into persistent sidebar account chrome');\n  await sidebar.getByText('Status in Jobs & Models', { exact: true }).waitFor({ state: 'visible' });")
text = text.replace('// More is a sidebar destination, and Create returns to the compact image composer.', '// Tools is the clarified sidebar destination for additional creation utilities, and Create returns to the compact image composer.')
text = text.replace("await desktop.getByRole('button', { name: 'More', exact: true }).click();", "await desktop.getByRole('button', { name: 'Tools', exact: true }).click();")
text = text.replace("await shot(desktop, '07-more-sidebar.png');", "await shot(desktop, '07-tools-sidebar.png');")
capture.write_text(text)

checklist = Path('docs/studio-ui-polish-checklist.md')
body = checklist.read_text()
old = '- [ ] **25. Simplify persistent sidebar/product status information.** Clarify `More`; keep backend/provider status in Jobs/Models instead of persistent account navigation when possible.'
new = '- [~] **25. Simplify persistent sidebar/product status information.** Implementation in validation: the ambiguous `More` sidebar destination is now `Tools` with an explanatory title, and the persistent footer no longer claims `FLUX.2 online`; it directs users to Jobs & Models for operational status instead of mixing provider state into account/navigation chrome.'
if old not in body:
    raise SystemExit('Item 25 marker missing')
checklist.write_text(body.replace(old, new, 1))
print('Patched Iteration 25 visual contract and checklist.')
