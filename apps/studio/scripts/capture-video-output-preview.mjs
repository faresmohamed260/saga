import { chromium } from 'playwright';
import sharp from 'sharp';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });
const diagnostics = { createUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [], submitted: null, sourceUpload: null };
const referencePng = await sharp({ create: { width: 800, height: 600, channels: 4, background: { r: 35, g: 38, b: 56, alpha: 1 } } }).png().toBuffer();

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));
  await context.route('**/api/favorites', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }));
  await context.route('**/api/uploads', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    diagnostics.sourceUpload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        uploadUrl: '/__visual-test-upload/reference-4x3.png',
        key: 'visual-tests/reference-4x3.png',
        contentType: 'image/png',
      }),
    });
  });
  await context.route('**/__visual-test-upload/**', async (route) => route.fulfill({ status: 200, body: '' }));
  await context.route('**/api/generate', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    diagnostics.submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        job: { id: '77777777-7777-4777-8777-777777777777' },
        status: 'running', workflow: 'ltx25-redgraft-video',
        worker: { workerId: 'ltx-standby-01', ecosystem: 'ltx25-redgraft', displayName: 'REDGraft LTX 2.5 · Standby', state: 'waking', failedWorkers: [] },
      }),
    });
  });
  await context.route('**/api/generate/result?**', async (route) => route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'running' }) }));

  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await page.locator('.saga-composer.is-video').waitFor({ state: 'visible' });

  if (await page.locator('.saga-video-extra-controls').count()) throw new Error('Video Aspect/FPS still render in the prompt toolbar');
  if (await page.locator('.saga-toolbar-left [data-shared-aspect-picker="true"]').count()) throw new Error('Inline Video Aspect trigger still exists');
  if (await page.locator('.saga-toolbar-left .saga-fancy-select').count()) throw new Error('Inline Video FPS picker still exists');

  const settings = page.getByRole('button', { name: 'Advanced settings', exact: true });
  await settings.click();
  const advanced = page.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  const closeAdvanced = advanced.getByRole('button', { name: 'Close advanced settings', exact: true });
  await advanced.getByText('REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', { exact: true }).waitFor({ state: 'visible' });
  const fixedSteps = advanced.locator('[data-ltx-fixed-steps="11"]');
  if (!/11\s+8 \+ 3/.test((await fixedSteps.innerText()).replace(/\s+/g, ' '))) throw new Error(`LTX fixed recipe is unclear: ${await fixedSteps.innerText()}`);
  const cfg = advanced.locator('input[aria-label="CFG value"]');
  if (await cfg.inputValue() !== '1') throw new Error(`LTX CFG default is not 1.0: ${await cfg.inputValue()}`);
  if (await advanced.locator('input[aria-label="Steps value"]').count()) throw new Error('LTX exposes an editable Steps control despite its fixed custom-sigma recipe');

  const aspect = advanced.getByRole('button', { name: 'Video aspect', exact: true });
  const fpsTrigger = advanced.getByRole('button', { name: 'Video frame rate', exact: true });
  if (!/Aspect\s*·\s*Auto\s+16:9/.test(await aspect.innerText())) throw new Error(`LTX Auto aspect default is wrong: ${await aspect.innerText()}`);
  if (!(await fpsTrigger.innerText()).includes('24 fps')) throw new Error(`LTX FPS default is not 24: ${await fpsTrigger.innerText()}`);
  await page.screenshot({ path: path.join(outputDir, '05b-video-output-controls.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05b-video-output-controls.png');

  await aspect.focus();
  await page.keyboard.press('ArrowDown');
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });
  await aspectMenu.waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  await page.keyboard.press('Home');
  for (let index = 0; index < 5; index += 1) await page.keyboard.press('ArrowDown');
  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');
  await page.keyboard.press('Enter');
  if (!/Aspect\s*·\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual Video aspect did not update: ${await aspect.innerText()}`);
  const resolution = page.locator('.saga-video-resolution-trigger');
  if (!/1080×1920 at 9:16/.test(await resolution.getAttribute('title') || '')) throw new Error(`Video resolution did not follow moved Aspect control: ${await resolution.getAttribute('title')}`);

  await fpsTrigger.focus();
  await page.keyboard.press('Space');
  const fpsListbox = page.getByRole('listbox', { name: 'Video frame rate' });
  await fpsListbox.waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'option', null, { timeout: 1500 });
  await page.keyboard.press('End');
  const fps30 = fpsListbox.getByRole('option', { name: '30 fps', exact: true });
  if (!(await fps30.evaluate((element) => element === document.activeElement))) throw new Error('Frame-rate keyboard navigation did not reach 30 fps');
  await page.screenshot({ path: path.join(outputDir, '05f-video-picker-keyboard-focus.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05f-video-picker-keyboard-focus.png');
  await page.keyboard.press('Enter');
  if (!(await fpsTrigger.innerText()).includes('30 fps')) throw new Error('Frame-rate selection did not update to 30 fps');

  // Auto aspect remains reference-aware even though the control moved into Advanced.
  await closeAdvanced.click();
  await advanced.waitFor({ state: 'hidden' });
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload reference images', exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference-4x3.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 5000 });
  await settings.click();
  await advanced.waitFor({ state: 'visible' });
  const aspectWithReference = advanced.getByRole('button', { name: 'Video aspect', exact: true });
  await aspectWithReference.click();
  const autoOption = page.getByRole('menu', { name: 'Video aspect' }).getByRole('menuitemradio').first();
  await autoOption.click();
  if (!/Auto\s+4:3\s*·\s*From reference/.test(await aspectWithReference.innerText())) throw new Error(`Auto aspect did not follow 4:3 reference: ${await aspectWithReference.innerText()}`);

  // CFG is editable and reaches the actual image-to-video request; fixed steps remain 11.
  await cfg.fill('1.4');
  await closeAdvanced.click();
  await advanced.waitFor({ state: 'hidden' });
  const prompt = page.locator('.saga-prompt-shell textarea');
  await prompt.fill('A slow cinematic camera move through a sunlit coastal landscape');
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  for (let attempt = 0; attempt < 40 && !diagnostics.submitted; attempt += 1) await page.waitForTimeout(50);
  if (!diagnostics.sourceUpload) throw new Error('Image-to-video source upload ticket was not requested');
  if (!diagnostics.submitted) throw new Error('Video generation request was not submitted');
  if (Number(diagnostics.submitted.steps) !== 11) throw new Error(`Video request did not send fixed 11 steps: ${JSON.stringify(diagnostics.submitted)}`);
  if (Number(diagnostics.submitted.cfg) !== 1.4) throw new Error(`Video request did not send edited CFG: ${JSON.stringify(diagnostics.submitted)}`);
  if (Number(diagnostics.submitted.frameRate) !== 30) throw new Error(`Video request did not send selected 30 fps: ${JSON.stringify(diagnostics.submitted)}`);
  if (diagnostics.submitted.aspectRatio !== '4:3') throw new Error(`Video request did not send Auto reference aspect: ${JSON.stringify(diagnostics.submitted)}`);
  if (diagnostics.submitted.workflowId !== 'ltx25-redgraft-video') throw new Error(`Video request did not use the production LTX workflow: ${JSON.stringify(diagnostics.submitted)}`);
  if (diagnostics.submitted.sourceKeys?.[0] !== 'visual-tests/reference-4x3.png') throw new Error(`Video request did not send uploaded reference key: ${JSON.stringify(diagnostics.submitted)}`);

  // Mobile: Aspect/FPS stay out of the composer and remain accessible in Advanced.
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await mobile.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  if (await mobile.locator('.saga-toolbar-left [data-shared-aspect-picker="true"]').count()) throw new Error('Mobile Video still shows inline Aspect');
  await mobile.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const mobileAdvanced = mobile.locator('.saga-advanced-panel');
  await mobileAdvanced.waitFor({ state: 'visible' });
  const mobileBox = await mobileAdvanced.boundingBox();
  if (!mobileBox || mobileBox.x < 0 || mobileBox.y < 0 || mobileBox.x + mobileBox.width > 390 || mobileBox.y + mobileBox.height > 844) throw new Error(`Mobile Advanced leaves viewport: ${JSON.stringify(mobileBox)}`);
  await mobileAdvanced.getByRole('button', { name: 'Video aspect', exact: true }).waitFor({ state: 'visible' });
  await mobileAdvanced.getByRole('button', { name: 'Video frame rate', exact: true }).waitFor({ state: 'visible' });
  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05g-video-output-controls-mobile.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'video-output-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
