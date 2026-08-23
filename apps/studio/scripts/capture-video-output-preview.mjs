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

  const auto = extras.locator('.saga-auto-toggle');
  const pickers = extras.locator('.saga-control-pill');
  const aspect = pickers.nth(0);
  const fps = pickers.nth(1);
  if (await auto.getAttribute('aria-pressed') !== 'true') throw new Error('Video Auto aspect should default on');
  if (!(await aspect.innerText()).includes('16:9')) throw new Error(`Default video aspect is not 16:9: ${await aspect.innerText()}`);
  if (!(await fps.innerText()).includes('24 fps')) throw new Error(`Default video frame rate is not 24 fps: ${await fps.innerText()}`);

  await page.screenshot({ path: path.join(outputDir, '05b-video-output-controls.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05b-video-output-controls.png');

  await aspect.click();
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect ratio' });
  await aspectMenu.waitFor({ state: 'visible' });
  await aspectMenu.getByRole('menuitemradio', { name: /9:16/ }).click();
  if (await auto.getAttribute('aria-pressed') !== 'false') throw new Error('Choosing a manual video aspect did not disable Auto');
  if (!(await aspect.innerText()).includes('9:16')) throw new Error('Manual video aspect did not update to 9:16');

  await fps.click();
  const fpsMenu = page.getByRole('menu', { name: 'Video frame rate' });
  await fpsMenu.waitFor({ state: 'visible' });
  await fpsMenu.getByRole('menuitemradio', { name: '30 fps', exact: true }).click();
  if (!(await fps.innerText()).includes('30 fps')) throw new Error('Video frame-rate picker did not update to 30 fps');

  await aspect.click();
  await aspectMenu.waitFor({ state: 'visible' });
  await page.screenshot({ path: path.join(outputDir, '05c-video-aspect-picker.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05c-video-aspect-picker.png');
  await page.keyboard.press('Escape');

  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload reference images', exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference-4x3.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 5000 });
  await auto.click();
  if (await auto.getAttribute('aria-pressed') !== 'true') throw new Error('Video Auto aspect did not re-enable');
  if (!(await aspect.innerText()).includes('4:3')) throw new Error(`Auto aspect did not inherit the 800x600 reference ratio: ${await aspect.innerText()}`);
  await page.screenshot({ path: path.join(outputDir, '05d-video-auto-reference-aspect.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05d-video-auto-reference-aspect.png');

  await page.locator('.saga-reference-chip .saga-reference-remove').click();
  await page.locator('.saga-reference-chip').waitFor({ state: 'detached', timeout: 3000 });
  if (!(await aspect.innerText()).includes('16:9')) throw new Error('Auto aspect did not fall back to 16:9 after removing the reference');

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
