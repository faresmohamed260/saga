from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1))


image = "apps/studio/scripts/capture-image-generation-preview.mjs"
replace_once(
    image,
    "  const editSubmit = page.getByRole('button', { name: 'Edit image', exact: true });",
    "  const editSubmit = page.getByRole('button', { name: 'Generate image', exact: true });",
)
replace_once(image, "after clicking Edit", "after clicking Generate")
replace_once(image, "after clicking Edit", "after clicking Generate")
replace_once(image, "Image Edit action remains enabled", "Image Generate action remains enabled")
replace_once(image, "Image Edit action stayed disabled", "Image Generate action stayed disabled")

qwen = "apps/studio/scripts/capture-qwen-generation-preview.mjs"
old_selector = """  const selector = page.getByRole('group', { name: 'Image model', exact: true });
  await selector.getByRole('button', { name: 'Qwen', exact: true }).click();
  diagnostics.qwenSelected = true;
  const upload = page.getByRole('button', { name: 'Upload reference images', exact: true });"""
new_selector = """  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const advanced = page.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible', timeout: 5000 });
  const modelSelector = advanced.getByRole('button', { name: 'Image model', exact: true });
  await modelSelector.click();
  await page.getByRole('option', { name: 'Qwen Image Edit 2511', exact: true }).click();
  if (!(await modelSelector.innerText()).includes('Qwen Image Edit 2511')) throw new Error('Qwen model selection did not activate from Advanced');
  await page.getByRole('button', { name: 'Close advanced settings', exact: true }).click();
  await advanced.waitFor({ state: 'hidden', timeout: 3000 });
  diagnostics.qwenSelected = true;
  const upload = page.getByRole('button', { name: 'Upload reference images', exact: true });"""
replace_once(qwen, old_selector, new_selector)
replace_once(
    qwen,
    "  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();\n  const advanced = page.locator('.saga-advanced-panel');",
    "  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();",
)
replace_once(qwen, "  await page.getByRole('button', { name: 'Edit image', exact: true }).click();", "  await page.getByRole('button', { name: 'Generate image', exact: true }).click();")

print('Generation preview contracts fixed')
