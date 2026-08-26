import { chromium } from 'playwright';
import sharp from 'sharp';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });
const referencePng = await sharp({ create: { width: 800, height: 600, channels: 4, background: { r: 42, g: 54, b: 72, alpha: 1 } } }).png().toBuffer();
const resultPng = await sharp({ create: { width: 800, height: 600, channels: 4, background: { r: 78, g: 91, b: 126, alpha: 1 } } }).png().toBuffer();
const resultDataUrl = `data:image/png;base64,${resultPng.toString('base64')}`;
const diagnostics = { submitted: null, resultPolls: 0, qwenSelected: false, qwenBackendLabel: false };

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  await context.route('**/api/favorites', async (route) => route.request().method() === 'GET' ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }) : route.continue());
  await context.route('**/api/uploads', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ uploadUrl: '/__qwen-test-upload/reference.png', key: 'visual-tests/qwen-reference.png', contentType: 'image/png' }) });
  });
  await context.route('**/__qwen-test-upload/**', async (route) => route.fulfill({ status: 200, body: '' }));
  await context.route('**/api/generate', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    diagnostics.submitted = route.request().postDataJSON();
    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ job: { id: '77777777-7777-4777-8777-777777777777' }, status: 'running', workflow: 'qwen-image-edit-2511', worker: { workerId: 'qwen-primary-01', ecosystem: 'qwen-image-edit-2511', displayName: 'Qwen Image Edit 2511 · Primary', state: 'generating', failedWorkers: [] } }) });
  });
  await context.route('**/api/generate/result?**', async (route) => {
    diagnostics.resultPolls += 1;
    if (diagnostics.resultPolls === 1) return route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'running', worker: { workerId: 'qwen-primary-01', ecosystem: 'qwen-image-edit-2511', displayName: 'Qwen Image Edit 2511 · Primary', state: 'generating' } }) });
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'completed', persisted: true, generationId: '66666666-6666-4666-8666-666666666666', mediaUrl: resultDataUrl, thumbnailUrl: resultDataUrl }) });
  });

  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const advanced = page.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible', timeout: 5000 });
  const modelSelector = advanced.getByRole('button', { name: 'Image model', exact: true });
  await modelSelector.click();
  await page.getByRole('option', { name: 'Qwen Image Edit 2511', exact: true }).click();
  if (!(await modelSelector.innerText()).includes('Qwen Image Edit 2511')) throw new Error('Qwen model selection did not activate from Advanced');
  await page.getByRole('button', { name: 'Close advanced settings', exact: true }).click();
  await advanced.waitFor({ state: 'hidden', timeout: 3000 });
  diagnostics.qwenSelected = true;
  const upload = page.getByRole('button', { name: 'Upload reference images', exact: true });
  const chooserPromise = page.waitForEvent('filechooser');
  await upload.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'qwen-reference.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-composer.is-edit').waitFor({ state: 'visible', timeout: 5000 });
  await page.locator('.saga-rich-prompt').fill('Make the reference look like a clean editorial photograph');
  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  await advanced.getByText('Qwen Image Edit 2511 · Abliterated BF16 + Lightning', { exact: true }).waitFor({ state: 'visible' });
  await advanced.getByText('Reset to Qwen defaults', { exact: true }).waitFor({ state: 'visible' });
  await advanced.getByText('4-step BF16 Lightning LoRA', { exact: true }).waitFor({ state: 'visible' });
  if (await advanced.locator('input[aria-label="Steps value"]').count()) throw new Error('Qwen fixed four-step recipe unexpectedly exposed an editable Steps input');
  const cfg = advanced.locator('input[aria-label="CFG value"]');
  if (Number(await cfg.inputValue()) !== 1) throw new Error('Qwen Advanced defaults did not switch to CFG 1');
  await page.getByRole('button', { name: 'Close advanced settings', exact: true }).click();
  await page.getByRole('button', { name: 'Generate image', exact: true }).click();
  for (let attempt = 0; attempt < 40 && !diagnostics.submitted; attempt += 1) await page.waitForTimeout(50);
  if (!diagnostics.submitted) throw new Error('Qwen image edit was not submitted');
  if (diagnostics.submitted.workflowId !== 'qwen-image-edit-2511') throw new Error(`Wrong Qwen workflow: ${JSON.stringify(diagnostics.submitted)}`);
  if (Number(diagnostics.submitted.steps) !== 4 || Number(diagnostics.submitted.cfg) !== 1) throw new Error(`Wrong Qwen defaults: ${JSON.stringify(diagnostics.submitted)}`);
  await page.locator('.saga-generation-progress').getByText('Generation ready', { exact: true }).waitFor({ state: 'visible', timeout: 7000 });
  await page.getByText(/Live backend · Qwen Image Edit 2511 ·/).waitFor({ state: 'visible', timeout: 5000 });
  diagnostics.qwenBackendLabel = true;
  await page.screenshot({ path: path.join(outputDir, 'qwen-generation-complete.png'), fullPage: true, animations: 'disabled' });
} finally {
  await writeFile(path.join(outputDir, 'qwen-generation-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
