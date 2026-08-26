import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { createUrl, generatedAt: new Date().toISOString(), qwenSelected: false, qwenLabels: false, fluxRestored: false };
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('button', { name: 'Open generation settings', exact: true }).click();
  const selector = page.getByRole('combobox', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX must be the initial image model');
  await selector.selectOption('qwen-image-edit-2511');
  if (await selector.inputValue() !== 'qwen-image-edit-2511') throw new Error('Qwen model selection did not activate');
  await page.getByText('Qwen Image Edit 2511 · Abliterated BF16 + Lightning', { exact: true }).waitFor({ state: 'visible' });
  await page.getByText('Add an image, describe the change, and generate with the live Qwen edit model.', { exact: true }).waitFor({ state: 'visible' });
  await page.getByText('Reset to Qwen defaults', { exact: true }).waitFor({ state: 'visible' });
  diagnostics.qwenSelected = true;
  diagnostics.qwenLabels = true;
  await page.screenshot({ path: path.join(outputDir, 'qwen-model-selector.png'), fullPage: true, animations: 'disabled' });
  await selector.selectOption('flux2-klein-9b');
  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX model selection did not restore');
  await page.getByText('Add an image, describe the change, and generate with the live FLUX edit model.', { exact: true }).waitFor({ state: 'visible' });
  diagnostics.fluxRestored = true;
} finally {
  await writeFile(path.join(outputDir, 'qwen-model-selector-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
