from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


preview = "apps/studio/scripts/capture-ui-preview.mjs"
replace_once(
    preview,
    "  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Edit image') throw new Error('Edit primary action lost its accessible name');",
    "  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Generate image') throw new Error('Edit primary action lost its consistent Generate accessible name');",
)
replace_once(
    preview,
    "  if (await mobile.locator('.saga-submit').count()) throw new Error('Mobile Image setup still exposes a separate Add image submit action');",
    "  const mobileGenerate = mobile.locator('.saga-submit');\n  await mobileGenerate.waitFor({ state: 'visible' });\n  if ((await mobileGenerate.getAttribute('aria-label')) !== 'Generate image' || !(await mobileGenerate.isDisabled())) throw new Error('Mobile Image setup must keep a separate disabled Generate action until a reference is attached');",
)

navigation = "apps/studio/scripts/capture-navigation-preview.mjs"
replace_once(
    navigation,
    "  await page.locator('.mobile-topbar').getByRole('button', { name: 'Open generation settings', exact: true }).click();",
    "  await page.locator('.mobile-topbar').getByRole('button', { name: 'Advanced settings', exact: true }).click();",
)

print('Browser contracts aligned')
