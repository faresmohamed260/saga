from pathlib import Path

app = Path('apps/studio/src/app/App.jsx')
text = app.read_text(encoding='utf-8')
anchor = "const HASH_SECTIONS = { ...Object.fromEntries(Object.entries(SECTION_HASHES).map(([section, hash]) => [hash, section])), history: 'Gallery' };\n"
addition = """const CREATE_SETTINGS_STORAGE_KEY = 'saga-studio:create-settings:v6';

function initialCreateMode() {
  if (typeof window === 'undefined') return 'Image';
  try {
    const saved = JSON.parse(window.localStorage.getItem(CREATE_SETTINGS_STORAGE_KEY) || '{}');
    return ['Image', 'Video'].includes(saved.mode) ? saved.mode : 'Image';
  } catch {
    return 'Image';
  }
}
"""
if addition not in text:
    if anchor not in text:
        raise SystemExit('App mode-storage anchor missing')
    text = text.replace(anchor, anchor + addition, 1)
old = "  const [mode, setMode] = useState('Image');"
new = "  const [mode, setMode] = useState(initialCreateMode);"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('App mode state anchor missing')
app.write_text(text, encoding='utf-8')

controls = Path('apps/studio/src/create-controls.jsx')
text = controls.read_text(encoding='utf-8')
old = "      const savedMode = ['Image', 'Video'].includes(saved.mode) ? saved.mode : 'Image';\n      setMode(savedMode);\n"
if old in text:
    text = text.replace(old, '', 1)
elif "setMode(savedMode);" in text:
    raise SystemExit('Unexpected saved-mode restoration shape')
controls.write_text(text, encoding='utf-8')

nav = Path('apps/studio/scripts/capture-navigation-preview.mjs')
text = nav.read_text(encoding='utf-8')
old = """  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expectDestination(page, 'Models', 'Production models');
  await page.getByRole('button', { name: 'Start image edit', exact: true }).click();
  await page.getByRole('heading', { name: /Create from a reference|Transform your references/ }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Model launch action did not enter Create');
  diagnostics.continuation.push({ action: 'model-to-image-edit', url: page.url() });

  await page.getByRole('button', { name: 'Workflows', exact: true }).click();
  await expectDestination(page, 'Workflows', 'Production workflows');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await page.getByRole('heading', { name: 'Create motion', exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Workflow launch action did not enter Video Create');
  if (!await page.locator('.saga-composer.is-video').count()) throw new Error('Workflow launch action did not activate Video mode');
  diagnostics.continuation.push({ action: 'workflow-to-video', url: page.url() });
"""
new = """  // User journey: a stored Video preference must not override an explicit Image-model launch.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Video' }));
  });
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expectDestination(page, 'Models', 'Production models');
  await page.getByRole('button', { name: 'Start image edit', exact: true }).click();
  await page.getByRole('heading', { name: /Create from a reference|Transform your references/ }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Model launch action did not enter Create');
  if (await page.locator('.saga-composer.is-video').count()) throw new Error('Stored Video preference overrode explicit Image-model launch');
  if (await page.getByRole('button', { name: 'Image', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Image launch did not activate the Image toggle');
  diagnostics.continuation.push({ action: 'model-to-image-edit', url: page.url(), conflictingStoredMode: 'Video', visibleMode: 'Image' });

  // User journey: a stored Image preference must not override an explicit Video-workflow launch.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Image' }));
  });
  await page.getByRole('button', { name: 'Workflows', exact: true }).click();
  await expectDestination(page, 'Workflows', 'Production workflows');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await page.getByRole('heading', { name: 'Create motion', exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Workflow launch action did not enter Video Create');
  if (!await page.locator('.saga-composer.is-video').count()) throw new Error('Workflow launch action did not activate Video mode');
  if (await page.getByRole('button', { name: 'Video', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Video launch did not activate the Video toggle');
  diagnostics.continuation.push({ action: 'workflow-to-video', url: page.url(), conflictingStoredMode: 'Image', visibleMode: 'Video' });
"""
if old in text:
    text = text.replace(old, new, 1)
elif 'conflictingStoredMode' not in text:
    raise SystemExit('Desktop continuation block missing')

old_mobile = """  await page.screenshot({ path: path.join(outputDir, 'navigation-settings-mobile.png'), fullPage: true, animations: 'disabled' });

  await context.close();
"""
new_mobile = """  await page.screenshot({ path: path.join(outputDir, 'navigation-settings-mobile.png'), fullPage: true, animations: 'disabled' });
  await page.keyboard.press('Escape');

  // Mobile user journey: launch Video through navigation and verify the actual composer state.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Image' }));
  });
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  const mobileWorkflowNav = page.locator('.sidebar.open');
  await mobileWorkflowNav.getByRole('button', { name: 'Workflows', exact: true }).click();
  await expectDestination(page, 'Workflows', 'Production workflows');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await page.getByRole('heading', { name: 'Create motion', exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  if (!await page.locator('.saga-composer.is-video').count()) throw new Error('Mobile workflow launch did not activate Video composer state');
  if (await page.getByRole('button', { name: 'Video', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Mobile Video launch did not activate the Video toggle');
  diagnostics.continuation.push({ action: 'mobile-workflow-to-video', url: page.url(), conflictingStoredMode: 'Image', visibleMode: 'Video' });
  await page.screenshot({ path: path.join(outputDir, 'navigation-workflow-video-mobile.png'), fullPage: true, animations: 'disabled' });

  await context.close();
"""
if old_mobile in text:
    text = text.replace(old_mobile, new_mobile, 1)
elif 'mobile-workflow-to-video' not in text:
    raise SystemExit('Mobile continuation anchor missing')
nav.write_text(text, encoding='utf-8')
