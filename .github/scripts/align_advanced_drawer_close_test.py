from pathlib import Path

path = Path('apps/studio/scripts/capture-ui-preview.mjs')
text = path.read_text()
replacements = [
    (
        "  await shot(desktop, '03-advanced-custom-dropdown.png');\n  await settingsButton.click();\n  await expectHidden(advanced, 'Advanced settings');",
        "  await shot(desktop, '03-advanced-custom-dropdown.png');\n  await advanced.getByRole('button', { name: 'Close advanced settings', exact: true }).click();\n  await expectHidden(advanced, 'Advanced settings');",
    ),
    (
        "  if (await advanced.getByText('No production image workflow connected', { exact: true }).count()) throw new Error('Legacy disconnected Image Advanced message returned after reload');\n  await settingsButton.click();",
        "  if (await advanced.getByText('No production image workflow connected', { exact: true }).count()) throw new Error('Legacy disconnected Image Advanced message returned after reload');\n  await advanced.getByRole('button', { name: 'Close advanced settings', exact: true }).click();",
    ),
    (
        "  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error('FLUX Reset did not restore 4 / 1.0');\n  await settingsButton.click();\n  await shot(desktop, '06-edit-inline-reference-and-auto.png');",
        "  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error('FLUX Reset did not restore 4 / 1.0');\n  await advanced.getByRole('button', { name: 'Close advanced settings', exact: true }).click();\n  await shot(desktop, '06-edit-inline-reference-and-auto.png');",
    ),
]
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected one match, found {count}: {old[:100]!r}')
    text = text.replace(old, new, 1)
path.write_text(text)
print('Advanced drawer close browser checks aligned')
