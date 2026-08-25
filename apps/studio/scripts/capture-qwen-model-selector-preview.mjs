import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { createUrl, generatedAt: new Date().toISOString(), qwenSelected: false, fluxRestored: false };
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  const selector = page.getByRole('group', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  const flux = selector.getByRole('button', { name: 'FLUX', exact: true });
  const qwen = selector.getByRole('button', { name: 'Qwen', exact: true });
  if (await flux.getAttribute('aria-pressed') !== 'true') throw new Error('FLUX must be the initial image model');
  await qwen.click();
  if (await qwen.getAttribute('aria-pressed') !== 'true') throw new Error('Qwen model selection did not activate');
  await page.getByText('Qwen Image Edit 2511 · Official BF16', { exact: true }).waitFor({ state: 'visible' });
  diagnostics.qwenSelected = true;
  await page.screenshot({ path: path.join(outputDir, 'qwen-model-selector.png'), fullPage: true, animations: 'disabled' });
  await flux.click();
  if (await flux.getAttribute('aria-pressed') !== 'true') throw new Error('FLUX model selection did not restore');
  diagnostics.fluxRestored = true;
} finally {
  await writeFile(path.join(outputDir, 'qwen-model-selector-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
