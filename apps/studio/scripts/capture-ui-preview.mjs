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

async function expectFocused(locator, label) {
  await locator.waitFor({ state: 'attached' });
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (await locator.evaluate((element) => document.activeElement === element)) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`${label} did not receive focus`);
}

async function expectStrongFocus(locator, label) {
  const result = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return { visible: element.matches(':focus-visible'), outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  if (!result.visible || result.outlineStyle === 'none' || Number.parseFloat(result.outlineWidth) < 2) {
    throw new Error(`${label} focus indicator is not strong enough: ${JSON.stringify(result)}`);
  }
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
  const primarySubmit = desktop.locator('.saga-submit');
  await primarySubmit.waitFor({ state: 'visible' });
  if ((await primarySubmit.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Desktop primary action does not expose the Generate verb');
  if (await primarySubmit.getAttribute('aria-label') !== 'Generate image') throw new Error('Desktop primary action lost its mode-specific accessible name');
  const primarySubmitBox = await primarySubmit.boundingBox();
  if (!primarySubmitBox || primarySubmitBox.width < 100 || primarySubmitBox.width < primarySubmitBox.height * 2.4) throw new Error(`Desktop Generate action is not visually promoted as a primary verb: ${JSON.stringify(primarySubmitBox)}`);
  const primarySubmitStyle = await primarySubmit.evaluate((element) => {
    const style = getComputedStyle(element);
    return { display: style.display, fontWeight: Number(style.fontWeight), borderRadius: style.borderRadius };
  });
  if (!primarySubmitStyle.display.includes('flex') || primarySubmitStyle.fontWeight < 700) throw new Error(`Desktop Generate action styling is not sufficiently primary: ${JSON.stringify(primarySubmitStyle)}`);
  await shot(desktop, '01-create-image-centered.png');
  await shot(desktop, '01b-generate-primary.png');
  await primarySubmit.focus();
  await expectStrongFocus(primarySubmit, 'Generate primary action');

  // Image picker keyboard, morphing and outside dismissal.
  const resolutionTrigger = desktop.locator('.saga-resolution-trigger');
  await resolutionTrigger.focus();
  await desktop.keyboard.press('Enter');
  const resolutionPicker = desktop.locator('.saga-resolution-picker');
  await resolutionPicker.waitFor({ state: 'visible' });
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });
  const focusedRole = await desktop.evaluate(() => document.activeElement?.getAttribute('role'));
  if (focusedRole !== 'menuitemradio') throw new Error(`Resolution picker did not focus selected option: ${focusedRole}`);
  const expectedImageRows = [['480 px', '512×512'], ['720 px', '704×704'], ['1080 px', '1088×1088'], ['2048 px', '2048×2048'], ['3840 px', '3840×3840']];
  const imageRows = resolutionPicker.getByRole('menuitemradio');
  if (await imageRows.count() !== expectedImageRows.length) throw new Error('Image resolution picker row count is wrong');
  for (let index = 0; index < expectedImageRows.length; index += 1) {
    const [label, detail] = expectedImageRows[index];
    const row = imageRows.nth(index);
    if ((await row.locator('.saga-option-label').innerText()).trim() !== label) throw new Error(`Image label mismatch at ${index}`);
    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Image delivery detail mismatch at ${index}`);
  }
  const resolutionPreviewBefore = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();
  const resolutionLabelBefore = (await resolutionPicker.locator('.saga-picker-preview strong').innerText()).trim();
  await desktop.keyboard.press('ArrowDown');
  await desktop.waitForTimeout(180);
  const resolutionPreviewAfter = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();
  const resolutionLabelAfter = (await resolutionPicker.locator('.saga-picker-preview strong').innerText()).trim();
  if (resolutionPreviewBefore === resolutionPreviewAfter) throw new Error('Resolution preview did not morph with keyboard focus');
  if (resolutionLabelBefore === resolutionLabelAfter || resolutionLabelAfter !== '2048 px') throw new Error(`Resolution label did not morph with preview: ${resolutionLabelBefore} -> ${resolutionLabelAfter}`);
  await desktop.keyboard.press('End');
  if (!/3840 px/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last resolution option');
  await expectStrongFocus(resolutionPicker.getByRole('menuitemradio').last(), 'Resolution End option');
  await shot(desktop, '02-image-resolution-picker.png');
  await desktop.keyboard.press('Home');
  if (!/480 px/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first resolution option');
  await desktop.keyboard.press('Escape');
  await expectHidden(resolutionPicker, 'Resolution picker');
  await expectFocused(resolutionTrigger, 'Resolution trigger after Escape');
  await expectStrongFocus(resolutionTrigger, 'Resolution trigger');

  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });
  if (await aspectTrigger.getAttribute('data-shared-aspect-picker') !== 'true') throw new Error('Image mode is not using the shared AspectPicker trigger');
  await aspectTrigger.focus();
  await desktop.keyboard.press('Space');
  const aspectPicker = desktop.locator('.saga-aspect-picker');
  await aspectPicker.waitFor({ state: 'visible' });
  if (await aspectPicker.getAttribute('data-aspect-picker-surface') !== 'shared') throw new Error('Image aspect menu is not the shared AspectPicker surface');
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  const aspectList = aspectPicker.locator('.saga-morph-list');
  const aspectScroll = await aspectList.evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));
  if (aspectScroll.scrollHeight > aspectScroll.clientHeight + 1) throw new Error(`Aspect picker still scrolls: ${JSON.stringify(aspectScroll)}`);
  await desktop.keyboard.press('End');
  if (!/21:9/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last aspect option');
  await expectStrongFocus(aspectPicker.getByRole('menuitemradio').last(), 'Aspect End option');
  await shot(desktop, '02b-image-picker-keyboard-focus.png');
  await desktop.keyboard.press('Home');
  if (!/1:1/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first aspect option');
  const aspectPreviewBefore = await aspectPicker.locator('.saga-preview-shape').boundingBox();
  await aspectPicker.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).hover();
  await desktop.waitForTimeout(200);
  const aspectPreviewAfter = await aspectPicker.locator('.saga-preview-shape').boundingBox();
  if (!aspectPreviewBefore || !aspectPreviewAfter || (Math.abs(aspectPreviewBefore.width - aspectPreviewAfter.width) < 3 && Math.abs(aspectPreviewBefore.height - aspectPreviewAfter.height) < 3)) throw new Error('Aspect preview did not morph on hover');
  await shot(desktop, '02-image-aspect-picker.png');
  await desktop.keyboard.press('Escape');
  await expectHidden(aspectPicker, 'Aspect picker');
  await expectFocused(aspectTrigger, 'Aspect trigger after Escape');

  // Set image resolution/aspect for persistence verification.
  await resolutionTrigger.click();
  await resolutionPicker.getByRole('menuitemradio', { name: /2048 px.*2048×2048/i }).click();
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
  const outputTrigger = outputSelect.locator(':scope > button');
  await outputTrigger.focus();
  await desktop.keyboard.press('Enter');
  const outputOptions = outputSelect.getByRole('option');
  await outputOptions.first().waitFor({ state: 'visible' });
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'option', null, { timeout: 1500 });
  await desktop.keyboard.press('End');
  if (!/4 outputs/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last advanced select option');
  await desktop.keyboard.press('Home');
  if (!/1 output/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first advanced select option');
  await desktop.keyboard.press('ArrowDown');
  if (!/2 outputs/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('ArrowDown did not move advanced select focus');
  await expectStrongFocus(outputOptions.nth(1), 'Advanced output option');
  await shot(desktop, '03b-advanced-picker-keyboard-focus.png');
  await desktop.keyboard.press('Enter');
  await expectText(outputTrigger, '2 outputs', 'Advanced keyboard selection');
  await expectFocused(outputTrigger, 'Advanced select trigger after selection');
  await desktop.keyboard.press('Space');
  await outputOptions.first().waitFor({ state: 'visible' });
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await desktop.keyboard.press('Escape');
  await advanced.waitFor({ state: 'visible' });
  await expectFocused(outputTrigger, 'Advanced select trigger after Escape');
  await settingsButton.click();
  await expectHidden(advanced, 'Advanced settings');

  // Video mode and all requested controls.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });
  if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Video mode primary action does not retain the Generate verb');
  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Generate video') throw new Error('Video Generate action lost its mode-specific accessible name');
  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');
  const videoResolutionTrigger = desktop.locator('.saga-video-resolution-trigger');
  await expectText(videoResolutionTrigger, '1080p', 'Video resolution trigger label');
  if ((await videoResolutionTrigger.innerText()).includes('Full HD')) throw new Error('Video resolution trigger still uses Full HD terminology');
  const videoResolutionTitle = await videoResolutionTrigger.getAttribute('title') || '';
  if (!/1920×1080 at 16:9/.test(videoResolutionTitle)) throw new Error(`Video resolution trigger does not expose exact delivery context: ${videoResolutionTitle}`);
  const durationTrigger = desktop.getByRole('button', { name: /10s/, exact: false });
  await videoResolutionTrigger.focus();
  await desktop.keyboard.press('ArrowDown');
  const videoResolutionPicker = desktop.locator('.saga-picker').filter({ has: desktop.getByRole('menu', { name: 'Video resolution' }) });
  await videoResolutionPicker.waitFor({ state: 'visible' });
  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  const expectedVideoRows = [['480p', '854×480'], ['720p', '1280×720'], ['1080p', '1920×1080'], ['2K', '2048×1152']];
  const videoRows = videoResolutionPicker.getByRole('menuitemradio');
  if (await videoRows.count() !== expectedVideoRows.length) throw new Error('Video resolution picker row count is wrong');
  for (let index = 0; index < expectedVideoRows.length; index += 1) {
    const [label, detail] = expectedVideoRows[index];
    const row = videoRows.nth(index);
    if ((await row.locator('.saga-option-label').innerText()).trim() !== label) throw new Error(`Video label mismatch at ${index}`);
    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Video delivery detail mismatch at ${index}`);
  }
  const videoList = videoResolutionPicker.locator('.saga-morph-list');
  const videoScroll = await videoList.evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));
  if (videoScroll.scrollHeight > videoScroll.clientHeight + 1) throw new Error(`Video resolution picker scrolls: ${JSON.stringify(videoScroll)}`);
  const videoPreview = videoResolutionPicker.locator('.saga-picker-preview');
  if (await videoPreview.count() !== 1) throw new Error('Video resolution picker is missing the shared preview panel');
  const videoPreviewLabelBefore = (await videoPreview.locator('strong').innerText()).trim();
  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048×1152/i }).hover();
  await desktop.waitForTimeout(180);
  const videoPreviewLabelAfter = (await videoPreview.locator('strong').innerText()).trim();
  if (videoPreviewLabelBefore === videoPreviewLabelAfter || videoPreviewLabelAfter !== '2K') throw new Error(`Video resolution preview did not morph: ${videoPreviewLabelBefore} -> ${videoPreviewLabelAfter}`);
  if ((await videoPreview.locator('small').innerText()).trim() !== '2048×1152 at 16:9') throw new Error(`Video preview does not expose delivery dimensions + aspect: ${await videoPreview.locator('small').innerText()}`);
  if (await videoResolutionPicker.getByRole('menuitemradio', { name: /4K/i }).count()) throw new Error('Video picker advertises unsupported 4K output');
  await shot(desktop, '04-video-resolution-picker.png');
  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048×1152/i }).click();
  await expectFocused(videoResolutionTrigger, 'Video resolution trigger after selection');

  await durationTrigger.focus();
  await desktop.keyboard.press('Enter');
  const durationPicker = desktop.locator('.saga-duration-picker');
  await durationPicker.waitFor({ state: 'visible' });
  const durationRange = durationPicker.locator('input[aria-label="Video duration"]');
  if (await durationRange.getAttribute('min') !== '5' || await durationRange.getAttribute('max') !== '30') throw new Error('Video duration is not constrained to 5–30 seconds');
  await durationRange.fill('23');
  await desktop.keyboard.press('Escape');
  await expectHidden(durationPicker, 'Duration picker');
  await expectFocused(durationTrigger, 'Duration trigger after Escape');

  const audioToggle = desktop.locator('.saga-audio-toggle');
  if (!(await audioToggle.getAttribute('aria-pressed') === 'true')) throw new Error('Video audio should default on');
  const audioBox = await audioToggle.boundingBox();
  if (!audioBox || Math.abs(audioBox.width - audioBox.height) > 1 || audioBox.width > 38) throw new Error(`Audio toggle is not circular: ${JSON.stringify(audioBox)}`);
  if ((await audioToggle.innerText()).trim()) throw new Error('Audio toggle should be icon-only');
  await audioToggle.click();
  if (!(await audioToggle.getAttribute('aria-pressed') === 'false')) throw new Error('Video audio toggle did not turn off');
  await shot(desktop, '05-video-controls.png');

  // Reload proves settings persist remotely in the rendered application.
  await desktop.reload({ waitUntil: 'domcontentloaded' });
  await desktop.locator('.saga-composer').waitFor({ state: 'visible' });
  await desktop.waitForTimeout(250);
  const selectedMode = desktop.locator('.saga-media-toggle button[aria-pressed="true"]');
  await expectText(selectedMode, 'Video', 'Persisted media mode');
  await expectText(desktop.locator('.saga-video-resolution-trigger'), '2K', 'Persisted video resolution');
  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(1), '23s', 'Persisted video duration');
  if (await desktop.locator('.saga-audio-toggle').getAttribute('aria-pressed') !== 'false') throw new Error('Persisted audio state did not remain muted');

  // Switch back to Image and verify image + advanced values also persisted.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' }).click();
  await expectText(desktop.locator('.saga-resolution-trigger'), '2048 px', 'Persisted image resolution');
  const imageResolutionTitle = await desktop.locator('.saga-resolution-trigger').getAttribute('title') || '';
  if (!/2048×1152 at 16:9/.test(imageResolutionTitle)) throw new Error(`Image resolution trigger lacks exact canvas context: ${imageResolutionTitle}`);
  await expectText(desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') }), '16:9', 'Persisted aspect');
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('input[aria-label="Steps value"]').inputValue() !== '17') throw new Error('Steps did not persist');
  if (await advanced.locator('input[aria-label="CFG value"]').inputValue() !== '2.7') throw new Error('CFG did not persist');
  if (await advanced.locator('input[aria-label="Seed"]').inputValue() !== '12345') throw new Error('Seed did not persist');
  const persistedOutputSelect = advanced.locator('.saga-advanced-top .saga-fancy-select').nth(1);
  await persistedOutputSelect.locator(':scope > button').click();
  await persistedOutputSelect.getByRole('option', { name: '4 outputs' }).click();
  await settingsButton.click();

  // Direct + upload auto-enters Edit, reference click inserts inline at the caret, Auto is toggleable.
  const upload = desktop.getByRole('button', { name: 'Upload reference images', exact: true });
  const chooserPromise = desktop.waitForEvent('filechooser');
  await upload.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference.png', mimeType: 'image/png', buffer: referencePng });
  const secondChooserPromise = desktop.waitForEvent('filechooser');
  await upload.click();
  const secondChooser = await secondChooserPromise;
  await secondChooser.setFiles({ name: 'reference-2.png', mimeType: 'image/png', buffer: referencePng });
  const refChips = desktop.locator('.saga-reference-chip');
  await refChips.nth(1).waitFor({ state: 'visible', timeout: 5000 });
  if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Edit') throw new Error('Edit mode primary action does not expose its principal Edit verb');
  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Edit image') throw new Error('Edit primary action lost its accessible name');
  const richPrompt = desktop.locator('.saga-rich-prompt');
  await richPrompt.click();
  await richPrompt.pressSequentially('Put ');
  await refChips.nth(0).locator('.saga-reference-main').click();
  await richPrompt.pressSequentially(' beside ');
  await refChips.nth(1).locator('.saga-reference-main').click();
  await richPrompt.pressSequentially(' behind the subject');
  const mentions = richPrompt.locator('.mention-token');
  if (await mentions.count() !== 2) throw new Error('Reference clicks did not insert both inline prompt tags');
  const promptText = (await richPrompt.innerText()).replace(/\s+/g, ' ').trim();
  if (!/Put\s+Image 1\s+beside\s+Image 2\s+behind the subject/i.test(promptText)) throw new Error(`Reference tags were not inserted at the caret: ${promptText}`);
  const autoToggle = desktop.locator('.saga-auto-toggle');
  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not start enabled');
  await autoToggle.click();
  if (await autoToggle.getAttribute('aria-pressed') !== 'false') throw new Error('Edit Auto did not toggle off');
  await autoToggle.click();
  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not toggle back on');
  await shot(desktop, '06-edit-inline-reference-and-auto.png');

  // Removing references cleans prompt tags, renumbers survivors, and exits Edit when the last reference is gone.
  await refChips.nth(0).locator('.saga-reference-remove').click();
  await desktop.waitForTimeout(120);
  if (await desktop.locator('.saga-reference-chip').count() !== 1) throw new Error('Removing one reference did not update the reference strip');
  const remainingMentions = richPrompt.locator('.mention-token');
  if (await remainingMentions.count() !== 1) throw new Error('Removed reference tag was not cleaned from the prompt');
  if (await remainingMentions.first().getAttribute('data-mention') !== '@Image 1') throw new Error('Remaining reference tag was not renumbered to Image 1');
  await desktop.locator('.saga-reference-chip .saga-reference-remove').click();
  await desktop.locator('.saga-composer:not(.is-edit)').waitFor({ state: 'visible', timeout: 2500 });
  const imageModeButton = desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' });
  if (await imageModeButton.getAttribute('aria-pressed') !== 'true') throw new Error('Removing the final reference did not return Studio to Image mode');
  if (await desktop.locator('.saga-reference-chip').count() !== 0) throw new Error('Final reference was not removed');
  const cleanedPrompt = await desktop.locator('.saga-prompt-shell textarea').inputValue();
  if (/@Image\s+\d+/i.test(cleanedPrompt)) throw new Error(`Stale reference tag remains after removing all references: ${cleanedPrompt}`);
  await shot(desktop, '06b-reference-removal-cleanup.png');

  // More is a sidebar destination, and Create returns to the compact image composer.
  await desktop.getByRole('button', { name: 'More', exact: true }).click();
  await desktop.locator('.saga-more-panel').waitFor({ state: 'visible' });
  await shot(desktop, '07-more-sidebar.png');
  await desktop.getByRole('button', { name: 'Create', exact: true }).click();
  await desktop.locator('.saga-composer').waitFor({ state: 'visible' });

  // Output wall uses equal-width masonry cards, full-bleed frames and one-row aligned hover actions.
  const slots = desktop.locator('.saga-output-slot');
  if (await slots.count() < 4) throw new Error(`Output wall should render four review outputs, got ${await slots.count()}`);
  const firstBox = await slots.nth(0).boundingBox();
  const secondBox = await slots.nth(1).boundingBox();
  const thirdBox = await slots.nth(2).boundingBox();
  if (!firstBox || !secondBox || !thirdBox) throw new Error('Could not measure output cards');
  if (Math.abs(firstBox.width - secondBox.width) > 3 || Math.abs(firstBox.width - thirdBox.width) > 3) throw new Error(`Output cards are not aligned to equal masonry columns: ${firstBox.width}, ${secondBox.width}, ${thirdBox.width}`);
  if (Math.abs(firstBox.height - secondBox.height) < 4) throw new Error('Output wall cards are not using varied heights');
  if (Math.abs(firstBox.x - secondBox.x) < firstBox.width * 0.5 || Math.abs(secondBox.x - thirdBox.x) < secondBox.width * 0.5) throw new Error('First three output cards are not distributed across three columns');
  const firstCard = slots.nth(0).locator('.media-card');
  const firstFrame = firstCard.locator('.media-frame');
  const firstCardBox = await firstCard.boundingBox();
  const firstFrameBox = await firstFrame.boundingBox();
  if (!firstCardBox || !firstFrameBox || Math.abs(firstCardBox.width - firstFrameBox.width) > 2 || Math.abs(firstCardBox.height - firstFrameBox.height) > 2) throw new Error(`Output frame is misaligned inside card: card=${JSON.stringify(firstCardBox)} frame=${JSON.stringify(firstFrameBox)}`);
  const cardActions = firstCard.locator('.card-actions');
  const beforeOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);
  if (Number(beforeOpacity) > 0.05) throw new Error(`Output actions should be hidden before hover, opacity=${beforeOpacity}`);
  await firstCard.hover();
  await desktop.waitForTimeout(220);
  const afterOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);
  if (Number(afterOpacity) < 0.9) throw new Error(`Output actions did not appear on hover, opacity=${afterOpacity}`);
  const actionBox = await cardActions.boundingBox();
  if (!actionBox || actionBox.x < firstCardBox.x + 6 || actionBox.x + actionBox.width > firstCardBox.x + firstCardBox.width - 6) throw new Error(`Output action bar is not aligned to its card: ${JSON.stringify(actionBox)}`);
  if (actionBox.height > 44) throw new Error(`Output action bar wrapped vertically: height=${actionBox.height}`);
  const actionButtons = cardActions.locator('button');
  const buttonYs = [];
  for (let index = 0; index < await actionButtons.count(); index += 1) {
    const box = await actionButtons.nth(index).boundingBox();
    if (box) buttonYs.push(Math.round(box.y));
  }
  if (new Set(buttonYs).size > 1) throw new Error(`Output action buttons wrap to multiple rows: ${buttonYs.join(',')}`);
  await shot(desktop, '08-output-wall-hover.png');

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  recordDiagnostics(mobile, 'mobile');
  await waitForStudio(mobile);
  const mobileSubmit = mobile.locator('.saga-submit');
  await mobileSubmit.waitFor({ state: 'visible' });
  if (await mobileSubmit.locator('.saga-submit-label').isVisible()) throw new Error('Mobile Generate action should collapse its text label');
  if (await mobileSubmit.getAttribute('aria-label') !== 'Generate image') throw new Error('Compact mobile Generate action lost its accessible name');
  const mobileSubmitBox = await mobileSubmit.boundingBox();
  if (!mobileSubmitBox || mobileSubmitBox.width > 40 || mobileSubmitBox.height > 40 || Math.abs(mobileSubmitBox.width - mobileSubmitBox.height) > 1) throw new Error(`Mobile Generate action is not compact/circular: ${JSON.stringify(mobileSubmitBox)}`);
  await shot(mobile, '09-mobile-create.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
