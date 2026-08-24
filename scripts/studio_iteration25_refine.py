from pathlib import Path

controls = Path('apps/studio/src/create-controls.jsx')
text = controls.read_text()
text = text.replace("mode === 'More' ? 'More creation tools' : 'Imagine worlds'", "mode === 'More' ? 'Creation tools' : 'Imagine worlds'")
text = text.replace('<section className="saga-more-panel"><Sparkles size={24} /><div><strong>More tools</strong><p>Choose Create in the sidebar to return to the Image composer.</p></div></section>', '<section className="saga-more-panel"><Sparkles size={24} /><div><strong>Additional tools</strong><p>Choose Create in the sidebar to return to the Image composer.</p></div></section>')
controls.write_text(text)

capture = Path('apps/studio/scripts/capture-ui-preview.mjs')
body = capture.read_text()
needle = "  await desktop.locator('.saga-more-panel').waitFor({ state: 'visible' });\n  await shot(desktop, '07-tools-sidebar.png');"
replacement = "  await desktop.locator('.saga-more-panel').waitFor({ state: 'visible' });\n  await desktop.getByRole('heading', { name: 'Creation tools', exact: true }).waitFor({ state: 'visible' });\n  await desktop.locator('.saga-more-panel').getByText('Additional tools', { exact: true }).waitFor({ state: 'visible' });\n  if ((await desktop.locator('.saga-create-stage').innerText()).includes('More tools')) throw new Error('Ambiguous More terminology remains on the Tools destination');\n  await shot(desktop, '07-tools-sidebar.png');"
if needle not in body:
    raise SystemExit('Tools validation insertion point missing')
capture.write_text(body.replace(needle, replacement, 1))

checklist = Path('docs/studio-ui-polish-checklist.md')
body = checklist.read_text()
old = '- [~] **25. Simplify persistent sidebar/product status information.** Implementation in validation: the ambiguous `More` sidebar destination is now `Tools` with an explanatory title, and the persistent footer no longer claims `FLUX.2 online`; it directs users to Jobs & Models for operational status instead of mixing provider state into account/navigation chrome.'
new = '- [~] **25. Simplify persistent sidebar/product status information.** Implementation in validation: the ambiguous `More` destination is now consistently user-facing as `Tools` / `Creation tools` / `Additional tools`, and the persistent footer no longer claims `FLUX.2 online`; it directs users to Jobs & Models for operational status instead of mixing provider state into account/navigation chrome.'
if old not in body:
    raise SystemExit('Item 25 in-progress marker missing')
checklist.write_text(body.replace(old, new, 1))
print('Refined Iteration 25 Tools terminology and validation.')
