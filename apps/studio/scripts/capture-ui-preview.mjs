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
  await desktop.route('**/api/favorites', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const dataUrl = `data:image/png;base64,${referencePng.toString('base64')}`;
    const shapes = [[1080, 1440], [1440, 1080], [1080, 1080], [2048, 1152]];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: shapes.map(([width, height], index) => ({
          id: `00000000-0000-4000-8000-00000000000${index + 1}`,
          status: 'completed',
          kind: 'image',
          mode: 'edit',
          model: 'FLUX.2 Klein 9B',
          prompt: `Favorite generation ${index + 1}`,
          media_url: dataUrl,
          thumbnail_url: dataUrl,
          mime_type: 'image/png',
          resolution: '1080 px',
          width,
          height,
          seed: 42 + index,
          workflow_id: 'flux2-klein-image-edit',
          metadata: { execution: { steps: 4, cfg: 1.0 } },
          is_favorite: true,
          created_at: new Date(Date.UTC(2026, 7, 25, 3, index)).toISOString(),
        })),
      }),
    });
  });
  await waitForStudio(desktop);
  await desktop.locator('.saga-output-slot').first().waitFor({ state: 'visible', timeout: 3000 });

  const tokenContract = await desktop.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return {
      bg: root.getPropertyValue('--saga-color-bg').trim(),
      radius: root.getPropertyValue('--saga-radius-lg').trim(),
      control: root.getPropertyValue('--saga-control-md').trim(),
      text: root.getPropertyValue('--saga-text-md').trim(),
      focus: root.getPropertyValue('--saga-focus-ring').trim(),
    };
  });
  if (tokenContract.bg !== '#080a0f' || tokenContract.radius !== '12px' || tokenContract.control !== '36px' || tokenContract.text !== '12px' || !tokenContract.focus.includes('2px')) {
    throw new Error(`Studio design token contract is incomplete: ${JSON.stringify(tokenContract)}`);
  }

  // Core composition: no old mode navbar or placeholder Tools surface; Image is a real FLUX setup state.
  if (await desktop.locator('.create-mode-tabs,.mode-tabs').count()) throw new Error('Old Create mode navbar is still rendered');
  if (await desktop.getByRole('button', { name: 'Tools', exact: true }).count()) throw new Error('Placeholder Tools navigation is still rendered');
  const sidebar = desktop.locator('.sidebar');
  if ((await sidebar.innerText()).includes('FLUX.2 online')) throw new Error('Provider status leaked into persistent sidebar account chrome');
  await sidebar.getByText('Status in Jobs & Models', { exact: true }).waitFor({ state: 'visible' });
  const composerBox = await desktop.locator('.saga-composer').boundingBox();
  const workspaceBox = await desktop.locator('main.workspace').boundingBox();
  if (!composerBox || !workspaceBox) throw new Error('Could not measure centered composer');
  const composerCenter = composerBox.x + composerBox.width / 2;
  const workspaceCenter = workspaceBox.x + workspaceBox.width / 2;
  if (Math.abs(composerCenter - workspaceCenter) > 70) throw new Error(`Composer is not centered: ${composerCenter} vs ${workspaceCenter}`);
  const upload = desktop.getByRole('button', { name: 'Upload reference images', exact: true });
  await upload.waitFor({ state: 'visible' });
  if (await desktop.locator('.saga-submit').count()) throw new Error('Image setup still exposes a wide submit-style Add image action');
  const uploadBox = await upload.boundingBox();
  if (!uploadBox || Math.abs(uploadBox.width - uploadBox.height) > 1 || uploadBox.width < 36) throw new Error(`Image setup circular upload action is missing: ${JSON.stringify(uploadBox)}`);
  await shot(desktop, '01-create-image-centered.png');
  await shot(desktop, '01b-generate-primary.png');
  await upload.focus();
  await expectStrongFocus(upload, 'Image setup circular upload action');

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

  // Image setup Advanced must expose the real FLUX controls that will be used after a reference is attached.
  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });
  await settingsButton.click();
  const advanced = desktop.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');
  const panelBox = await advanced.boundingBox();
  const viewport = desktop.viewportSize();
  if (!panelBox || !viewport || panelBox.x < 8 || panelBox.y < 8 || panelBox.x + panelBox.width > viewport.width - 8 || panelBox.y + panelBox.height > viewport.height - 8) throw new Error(`Advanced panel out of viewport: ${JSON.stringify(panelBox)}`);
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="Steps value"]').waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="CFG value"]').waitFor({ state: 'visible' });
  await advanced.locator('textarea[aria-label="Negative prompt"]').waitFor({ state: 'visible' });
  await shot(desktop, '03-advanced-custom-dropdown.png');
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
  const durationTrigger = desktop.getByRole('button', { name: 'Video duration 10 seconds', exact: true });
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
  if ((await desktop.evaluate(() => document.activeElement?.getAttribute('aria-label') || '')) !== 'Video duration 23 seconds') throw new Error('Duration trigger did not regain focus after Escape');

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
  await expectText(desktop.getByRole('button', { name: 'Video duration 23 seconds', exact: true }), '23s', 'Persisted video duration');
  if (await desktop.locator('.saga-audio-toggle').getAttribute('aria-pressed') !== 'false') throw new Error('Persisted audio state did not remain muted');

  // Switch back to Image and verify canvas preferences persist while the live FLUX setup controls remain available.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' }).click();
  await expectText(desktop.locator('.saga-resolution-trigger'), '2048 px', 'Persisted image resolution');
  const imageResolutionTitle = await desktop.locator('.saga-resolution-trigger').getAttribute('title') || '';
  if (!/2048×1152 at 16:9/.test(imageResolutionTitle)) throw new Error(`Image resolution trigger lacks exact canvas context: ${imageResolutionTitle}`);
  await expectText(desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') }), '16:9', 'Persisted aspect');
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="Steps value"]').waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="CFG value"]').waitFor({ state: 'visible' });
  await advanced.locator('textarea[aria-label="Negative prompt"]').waitFor({ state: 'visible' });
  if (await advanced.getByText('No production image workflow connected', { exact: true }).count()) throw new Error('Legacy disconnected Image Advanced message returned after reload');
  await settingsButton.click();

  // Drag/drop attaches the first reference; the same circular + remains available for additional references.
  const composer = desktop.locator('.saga-composer');
  await composer.evaluate((element, encoded) => {
    const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
    const file = new File([bytes], 'reference.png', { type: 'image/png' });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    window.__sagaReferenceDropTransfer = transfer;
    element.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  }, referencePng.toString('base64'));
  await desktop.locator('.saga-drop-overlay').waitFor({ state: 'visible' });
  await expectText(desktop.locator('.saga-drop-overlay'), 'Drop images to upload', 'Drag-over upload affordance');
  await composer.evaluate((element) => {
    element.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: window.__sagaReferenceDropTransfer }));
    delete window.__sagaReferenceDropTransfer;
  });
  await desktop.locator('.saga-composer.is-edit').waitFor({ state: 'visible' });
  await upload.waitFor({ state: 'visible' });
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
  if (await desktop.locator('.saga-auto-toggle').count()) throw new Error('Edit exposes a duplicate standalone Auto control');
  const editAspectTrigger = desktop.locator('.saga-shared-aspect-trigger');
  await expectText(editAspectTrigger, 'Canvas · Auto', 'Edit automatic canvas trigger');
  if (await desktop.locator('.saga-resolution-trigger').count()) throw new Error('Edit Auto should not expose a second resolution Auto control');
  await editAspectTrigger.click();
  const editAspectMenu = desktop.locator('.saga-aspect-picker');
  await editAspectMenu.waitFor({ state: 'visible' });
  await editAspectMenu.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).click();
  await desktop.locator('.saga-resolution-trigger').waitFor({ state: 'visible' });
  await editAspectTrigger.click();
  await editAspectMenu.getByRole('menuitemradio', { name: /Auto/i }).click();
  if (await desktop.locator('.saga-resolution-trigger').count()) throw new Error('Returning to Edit Auto did not collapse manual resolution control');

  // FLUX Advanced defaults are real production values and Reset restores them.
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  const fluxSteps = advanced.locator('input[aria-label="Steps value"]');
  const fluxCfg = advanced.locator('input[aria-label="CFG value"]');
  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error(`FLUX preset is not 4 steps / CFG 1.0: ${await fluxSteps.inputValue()} / ${await fluxCfg.inputValue()}`);
  await fluxSteps.fill('7');
  await fluxCfg.fill('1.8');
  await advanced.getByRole('button', { name: 'Reset to FLUX defaults', exact: true }).click();
  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error('FLUX Reset did not restore 4 / 1.0');
  await settingsButton.click();
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

  // Placeholder Tools navigation was removed; continue directly with the real Create output wall.
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
  const animateAction = cardActions.getByRole('button', { name: 'Animate this', exact: true });
  await animateAction.waitFor({ state: 'visible' });
  await animateAction.click();
  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible', timeout: 3000 });
  await desktop.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 3000 });
  await shot(desktop, '08b-output-animate.png');

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  recordDiagnostics(mobile, 'mobile');
  await waitForStudio(mobile);
  const mobileUpload = mobile.getByRole('button', { name: 'Upload reference images', exact: true });
  await mobileUpload.waitFor({ state: 'visible' });
  if (await mobile.locator('.saga-submit').count()) throw new Error('Mobile Image setup still exposes a separate Add image submit action');
  const mobileUploadBox = await mobileUpload.boundingBox();
  if (!mobileUploadBox || mobileUploadBox.width < 44 || mobileUploadBox.height < 44 || mobileUploadBox.width > 48 || mobileUploadBox.height > 48 || Math.abs(mobileUploadBox.width - mobileUploadBox.height) > 1) throw new Error(`Mobile circular upload action does not provide a 44px touch target: ${JSON.stringify(mobileUploadBox)}`);
  await shot(mobile, '09-mobile-create.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
