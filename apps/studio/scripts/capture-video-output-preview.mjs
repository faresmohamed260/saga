import { chromium } from 'playwright';
import sharp from 'sharp';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });
const diagnostics = { createUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [] };

const referencePng = await sharp({
  create: { width: 800, height: 600, channels: 4, background: { r: 35, g: 38, b: 56, alpha: 1 } },
}).png().toBuffer();

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));

  await page.route('**/api/generate', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        job: { id: '77777777-7777-4777-8777-777777777777' },
        status: 'running',
        workflow: 'ltx25-redgraft-video',
      }),
    });
  });
  await page.route('**/api/generate/result?**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'running' }) });
  });

  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await page.locator('.saga-composer.is-video').waitFor({ state: 'visible' });
  const extras = page.locator('.saga-video-extra-controls');
  await extras.waitFor({ state: 'visible', timeout: 3000 });

  if (await extras.locator('.saga-auto-toggle').count()) throw new Error('Video still exposes a separate Auto aspect button');
  const pickers = extras.locator('.saga-control-pill');
  if (await pickers.count() !== 2) throw new Error(`Video output controls should expose Aspect + FPS only, found ${await pickers.count()}`);
  const aspect = pickers.nth(0);
  const fps = pickers.nth(1);
  if (!/Aspect\s*·\s*Auto\s+16:9/.test(await aspect.innerText())) throw new Error(`Unified Aspect control does not show default Auto 16:9: ${await aspect.innerText()}`);
  if (!/Follows an attached reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Default Aspect tooltip does not explain Auto behavior: ${await aspect.getAttribute('title')}`);
  if (!(await fps.innerText()).includes('24 fps')) throw new Error(`Default video frame rate is not 24 fps: ${await fps.innerText()}`);

  await page.screenshot({ path: path.join(outputDir, '05b-video-output-controls.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05b-video-output-controls.png');

  await aspect.focus();
  await page.keyboard.press('ArrowDown');
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });
  await aspectMenu.waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  const aspectOptions = aspectMenu.getByRole('menuitemradio');
  const autoOption = aspectMenu.getByRole('menuitemradio').first();
  if (await autoOption.getAttribute('aria-checked') !== 'true') throw new Error('Unified Aspect menu does not mark Auto as selected by default');
  await page.keyboard.press('Home');
  for (let step = 0; step < 5; step += 1) await page.keyboard.press('ArrowDown');
  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');
  await page.keyboard.press('Enter');
  if (/Auto/.test(await aspect.innerText())) throw new Error(`Choosing a manual aspect did not leave Auto mode: ${await aspect.innerText()}`);
  if (!/Aspect\s*·\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual video aspect did not update to 9:16: ${await aspect.innerText()}`);

  await fps.focus();
  await page.keyboard.press('Space');
  const fpsMenu = page.getByRole('menu', { name: 'Video frame rate' });
  await fpsMenu.waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  await page.keyboard.press('End');
  const focusedFps = fpsMenu.getByRole('menuitemradio', { name: '30 fps', exact: true });
  if (!(await focusedFps.evaluate((element) => element === document.activeElement && element.matches(':focus-visible')))) throw new Error('Video FPS End navigation/focus-visible failed');
  const fpsOutline = await focusedFps.evaluate((element) => Number.parseFloat(getComputedStyle(element).outlineWidth));
  if (fpsOutline < 2) throw new Error(`Video FPS focus indicator is too weak: ${fpsOutline}`);
  await page.screenshot({ path: path.join(outputDir, '05f-video-picker-keyboard-focus.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05f-video-picker-keyboard-focus.png');
  await page.keyboard.press('Enter');
  if (!(await fps.innerText()).includes('30 fps')) throw new Error('Video frame-rate picker did not update to 30 fps');
  if (!(await fps.evaluate((element) => document.activeElement === element))) throw new Error('Video FPS trigger did not regain focus after selection');

  await aspect.focus();
  await page.keyboard.press('Enter');
  await aspectMenu.waitFor({ state: 'visible' });
  const desktopMenuSize = await aspectMenu.evaluate((element) => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight }));
  if (desktopMenuSize.scrollHeight > desktopMenuSize.clientHeight + 1) throw new Error(`Desktop Video Aspect menu should expose all options without scrolling: ${JSON.stringify(desktopMenuSize)}`);
  await page.screenshot({ path: path.join(outputDir, '05c-video-aspect-picker.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05c-video-aspect-picker.png');
  await page.keyboard.press('Escape');
  if (!(await aspect.evaluate((element) => document.activeElement === element))) throw new Error('Video aspect trigger did not regain focus after Escape');

  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload reference images', exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference-4x3.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 5000 });
  await aspect.focus();
  await page.keyboard.press('Enter');
  await aspectMenu.waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });
  await page.keyboard.press('Home');
  if (!/^Auto/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the Auto aspect option');
  await page.keyboard.press('Enter');
  if (!/Aspect\s*·\s*Auto\s+4:3\s*·\s*From reference/.test(await aspect.innerText())) throw new Error(`Auto aspect did not visibly expose reference provenance: ${await aspect.innerText()}`);
  if (!/From reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Reference provenance is not exposed by the unified Aspect control: ${await aspect.getAttribute('title')}`);
  await page.screenshot({ path: path.join(outputDir, '05d-video-auto-reference-aspect.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05d-video-auto-reference-aspect.png');

  await page.locator('.saga-reference-chip .saga-reference-remove').click();
  await page.locator('.saga-reference-chip').waitFor({ state: 'detached', timeout: 3000 });
  if (!/Aspect\s*·\s*Auto\s+16:9/.test(await aspect.innerText())) throw new Error(`Auto aspect did not fall back to 16:9 after removing the reference: ${await aspect.innerText()}`);

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark', hasTouch: true, isMobile: true });
  mobile.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));
  await mobile.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await mobile.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  const mobileExtras = mobile.locator('.saga-video-extra-controls');
  await mobileExtras.waitFor({ state: 'visible', timeout: 3000 });
  if (await mobileExtras.locator('.saga-auto-toggle').count()) throw new Error('Mobile Video still exposes a separate Auto aspect button');
  const mobileAspect = mobileExtras.locator('.saga-control-pill').first();
  if (!/Aspect\s*·\s*Auto\s+16:9/.test(await mobileAspect.innerText())) throw new Error(`Mobile unified Aspect state is unclear: ${await mobileAspect.innerText()}`);
  const mobileAspectBox = await mobileAspect.boundingBox();
  if (!mobileAspectBox || mobileAspectBox.x < 0 || mobileAspectBox.x + mobileAspectBox.width > 390) throw new Error(`Mobile Aspect control is clipped: ${JSON.stringify(mobileAspectBox)}`);
  await mobileAspect.click();
  const mobileAspectMenu = mobile.getByRole('menu', { name: 'Video aspect' });
  await mobileAspectMenu.waitFor({ state: 'visible' });
  const mobileMenuBox = await mobileAspectMenu.boundingBox();
  if (!mobileMenuBox || mobileMenuBox.y < 0 || mobileMenuBox.y + mobileMenuBox.height > 844) throw new Error(`Mobile Aspect menu leaves the viewport: ${JSON.stringify(mobileMenuBox)}`);
  await mobile.keyboard.press('Escape');
  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05g-video-output-controls-mobile.png');
  await mobile.close();

  const prompt = page.locator('.saga-prompt-shell textarea');
  await prompt.fill('A slow cinematic camera move through a sunlit coastal landscape');
  await page.getByRole('button', { name: /Generate/i }).click();
  const progress = page.locator('.saga-generation-progress');
  await progress.waitFor({ state: 'visible', timeout: 3000 });
  const progressText = await progress.innerText();
  if (!/Submitting generation|Generating video|Queued/i.test(progressText)) throw new Error(`Generation feedback did not expose an active state: ${progressText}`);
  await page.screenshot({ path: path.join(outputDir, '05e-video-generation-progress.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05e-video-generation-progress.png');

  if (diagnostics.pageErrors.length) throw new Error(`Video output page errors: ${diagnostics.pageErrors.join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'video-output-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
