import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { baseUrl, generatedAt: new Date().toISOString(), screenshots: [], consoleErrors: [], pageErrors: [] };
const referencePng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');

function recordDiagnostics(page, label) {
  page.on('console', (message) => { if (message.type() === 'error') diagnostics.consoleErrors.push({ label, text: message.text() }); });
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ label, text: error?.stack || error?.message || String(error) }));
}

async function waitForStudio(page) {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.waitForTimeout(300);
}

async function shot(page, filename) {
  await page.screenshot({ path: path.join(outputDir, filename), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push(filename);
}

async function expectHidden(locator, label) {
  await locator.waitFor({ state: 'hidden', timeout: 2500 }).catch(() => { throw new Error(`${label} did not close`); });
}

async function expectText(locator, expected, label) {
  const text = (await locator.innerText()).trim();
  if (!text.includes(expected)) throw new Error(`${label}: expected ${expected}, got ${text}`);
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  recordDiagnostics(desktop, 'desktop');
  await waitForStudio(desktop);

  // Core composition: no old mode navbar, centered composer, More moved to sidebar.
  if (await desktop.locator('.create-mode-tabs,.mode-tabs').count()) throw new Error('Old Create mode navbar is still rendered');
  await desktop.getByRole('button', { name: 'More', exact: true }).waitFor({ state: 'visible' });
  const composerBox = await desktop.locator('.saga-composer').boundingBox();
  const workspaceBox = await desktop.locator('main.workspace').boundingBox();
  if (!composerBox || !workspaceBox) throw new Error('Could not measure centered composer');
  const composerCenter = composerBox.x + composerBox.width / 2;
  const workspaceCenter = workspaceBox.x + workspaceBox.width / 2;
  if (Math.abs(composerCenter - workspaceCenter) > 70) throw new Error(`Composer is not centered: ${composerCenter} vs ${workspaceCenter}`);
  await shot(desktop, '01-create-image-centered.png');

  // Image picker keyboard + outside dismissal.
  const resolutionTrigger = desktop.locator('.saga-resolution-trigger');
  await resolutionTrigger.click();
  const resolutionPicker = desktop.locator('.saga-resolution-picker');
  await resolutionPicker.waitFor({ state: 'visible' });
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });
  const focusedRole = await desktop.evaluate(() => document.activeElement?.getAttribute('role'));
  if (focusedRole !== 'menuitemradio') throw new Error(`Resolution picker did not focus selected option: ${focusedRole}`);
  await desktop.keyboard.press('ArrowDown');
  await desktop.keyboard.press('Escape');
  await expectHidden(resolutionPicker, 'Resolution picker');

  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });
  await aspectTrigger.click();
  const aspectPicker = desktop.locator('.saga-aspect-picker');
  await aspectPicker.waitFor({ state: 'visible' });
  await shot(desktop, '02-image-aspect-picker.png');
  await desktop.locator('.saga-stage-heading').click();
  await expectHidden(aspectPicker, 'Aspect picker');

  // Set image resolution/aspect for persistence verification.
  await resolutionTrigger.click();
  await resolutionPicker.getByRole('menuitemradio', { name: /High.*1536 px/i }).click();
  await aspectTrigger.click();
  await aspectPicker.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).click();

  // Advanced settings: custom dropdowns, continuous sampling values, viewport-safe panel.
  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });
  await settingsButton.click();
  const advanced = desktop.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');
  const panelBox = await advanced.boundingBox();
  const viewport = desktop.viewportSize();
  if (!panelBox || !viewport || panelBox.x < 8 || panelBox.y < 8 || panelBox.x + panelBox.width > viewport.width - 8 || panelBox.y + panelBox.height > viewport.height - 8) throw new Error(`Advanced panel out of viewport: ${JSON.stringify(panelBox)}`);
  await advanced.locator('input[aria-label="Steps value"]').fill('17');
  await advanced.locator('input[aria-label="CFG value"]').fill('2.7');
  await advanced.locator('input[aria-label="Seed"]').fill('12345');
  const outputSelect = advanced.locator('.saga-advanced-top .saga-fancy-select').nth(1);
  await outputSelect.locator(':scope > button').click();
  await outputSelect.getByRole('option', { name: '2 outputs' }).click();
  await outputSelect.locator(':scope > button').click();
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await outputSelect.locator(':scope > button').click();
  await settingsButton.click();
  await expectHidden(advanced, 'Advanced settings');

  // Video mode and all requested controls.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });
  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');
  const videoResolutionTrigger = videoControls.nth(0);
  const durationTrigger = videoControls.nth(1);
  await videoResolutionTrigger.click();
  const videoResolutionPicker = desktop.locator('.saga-picker').filter({ has: desktop.getByRole('menu', { name: 'Video resolution' }) });
  await videoResolutionPicker.waitFor({ state: 'visible' });
  for (const label of ['480p', '720p', '1080p', '2K', '4K']) await videoResolutionPicker.getByRole('menuitemradio', { name: new RegExp(label, 'i') }).waitFor({ state: 'visible' });
  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K/i }).click();

  await durationTrigger.click();
  const durationPicker = desktop.locator('.saga-duration-picker');
  await durationPicker.waitFor({ state: 'visible' });
  const durationRange = durationPicker.locator('input[aria-label="Video duration"]');
  if (await durationRange.getAttribute('min') !== '5' || await durationRange.getAttribute('max') !== '30') throw new Error('Video duration is not constrained to 5–30 seconds');
  await durationRange.fill('23');
  await desktop.locator('.saga-stage-heading').click();
  await expectHidden(durationPicker, 'Duration picker');

  const audioToggle = desktop.locator('.saga-audio-toggle');
  if (!(await audioToggle.getAttribute('aria-pressed') === 'true')) throw new Error('Video audio should default on');
  await audioToggle.click();
  if (!(await audioToggle.getAttribute('aria-pressed') === 'false')) throw new Error('Video audio toggle did not turn off');
  await shot(desktop, '04-video-controls.png');

  // Reload proves settings persist remotely in the rendered application.
  await desktop.reload({ waitUntil: 'domcontentloaded' });
  await desktop.locator('.saga-composer').waitFor({ state: 'visible' });
  await desktop.waitForTimeout(250);
  const selectedMode = desktop.locator('.saga-media-toggle button[aria-pressed="true"]');
  await expectText(selectedMode, 'Video', 'Persisted media mode');
  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(0), '4K', 'Persisted video resolution');
  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(1), '23s', 'Persisted video duration');
  await expectText(desktop.locator('.saga-audio-toggle'), 'Muted', 'Persisted audio state');

  // Switch back to Image and verify image + advanced values also persisted.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' }).click();
  await expectText(desktop.locator('.saga-resolution-trigger'), 'High', 'Persisted image resolution');
  if ((await desktop.locator('.saga-resolution-badge').innerText()).trim() !== '1536') throw new Error('Persisted resolution badge is truncated');
  await expectText(desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') }), '16:9', 'Persisted aspect');
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('input[aria-label="Steps value"]').inputValue() !== '17') throw new Error('Steps did not persist');
  if (await advanced.locator('input[aria-label="CFG value"]').inputValue() !== '2.7') throw new Error('CFG did not persist');
  if (await advanced.locator('input[aria-label="Seed"]').inputValue() !== '12345') throw new Error('Seed did not persist');
  await settingsButton.click();

  // Direct + upload auto-enters Edit, reference click inserts inline at the caret, Auto is toggleable.
  const upload = desktop.getByRole('button', { name: 'Upload reference images', exact: true });
  const chooserPromise = desktop.waitForEvent('filechooser');
  await upload.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference.png', mimeType: 'image/png', buffer: referencePng });
  const refChip = desktop.locator('.saga-reference-chip').first();
  await refChip.waitFor({ state: 'visible', timeout: 5000 });
  const richPrompt = desktop.locator('.saga-rich-prompt');
  await richPrompt.click();
  await richPrompt.pressSequentially('Put ');
  await refChip.locator('.saga-reference-main').click();
  await richPrompt.pressSequentially(' behind the subject');
  const mention = richPrompt.locator('.mention-token');
  if (await mention.count() !== 1) throw new Error('Reference click did not insert an inline prompt tag');
  const promptText = (await richPrompt.innerText()).replace(/\s+/g, ' ').trim();
  if (!/Put\s+Image 1\s+behind the subject/i.test(promptText)) throw new Error(`Reference tag was not inserted at the caret: ${promptText}`);
  const autoToggle = desktop.locator('.saga-auto-toggle');
  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not start enabled');
  await autoToggle.click();
  if (await autoToggle.getAttribute('aria-pressed') !== 'false') throw new Error('Edit Auto did not toggle off');
  await autoToggle.click();
  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not toggle back on');
  await shot(desktop, '05-edit-inline-reference-and-auto.png');

  // More is a sidebar destination, and Create returns to the compact image composer.
  await desktop.getByRole('button', { name: 'More', exact: true }).click();
  await desktop.locator('.saga-more-panel').waitFor({ state: 'visible' });
  await shot(desktop, '06-more-sidebar.png');
  await desktop.getByRole('button', { name: 'Create', exact: true }).click();
  await desktop.locator('.saga-composer').waitFor({ state: 'visible' });

  // Output wall has variable card sizes and hover-only actions.
  const slots = desktop.locator('.saga-output-slot');
  if (await slots.count() < 2) throw new Error('Output wall did not render sample outputs');
  const firstBox = await slots.nth(0).boundingBox();
  const secondBox = await slots.nth(1).boundingBox();
  if (!firstBox || !secondBox || (Math.abs(firstBox.width - secondBox.width) < 4 && Math.abs(firstBox.height - secondBox.height) < 4)) throw new Error('Output wall cards are not using varied sizes');
  const firstCard = slots.nth(0).locator('.media-card');
  const cardActions = firstCard.locator('.card-actions');
  const beforeOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);
  if (Number(beforeOpacity) > 0.05) throw new Error(`Output actions should be hidden before hover, opacity=${beforeOpacity}`);
  await firstCard.hover();
  await desktop.waitForTimeout(220);
  const afterOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);
  if (Number(afterOpacity) < 0.9) throw new Error(`Output actions did not appear on hover, opacity=${afterOpacity}`);
  await shot(desktop, '07-output-wall-hover.png');

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  recordDiagnostics(mobile, 'mobile');
  await waitForStudio(mobile);
  await shot(mobile, '08-mobile-create.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
