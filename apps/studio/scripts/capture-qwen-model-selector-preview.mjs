import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { createUrl, generatedAt: new Date().toISOString(), qwenSelected: false, qwenStepsEditable: false, fluxRestored: false };
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const selector = page.getByRole('button', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  if (!(await selector.innerText()).includes('FLUX.2 Klein 9B')) throw new Error('FLUX must be the initial image model');

  await selector.click();
  await page.getByRole('option', { name: 'Qwen Image Edit 2511', exact: true }).click();
  if (!(await selector.innerText()).includes('Qwen Image Edit 2511')) throw new Error('Qwen model selection did not activate');

  const steps = page.locator('input[aria-label="Steps value"]');
  await steps.waitFor({ state: 'visible', timeout: 10_000 });
  if (Number(await steps.inputValue()) !== 4) throw new Error('Qwen must retain four steps as the tuned default');
  await steps.fill('7');
  await steps.press('Enter');
  if (Number(await steps.inputValue()) !== 7) throw new Error('Qwen Steps input did not accept a user-selected value');
  await page.getByRole('button', { name: 'Reset to Qwen defaults', exact: true }).waitFor({ state: 'visible', timeout: 10_000 });
  diagnostics.qwenSelected = true;
  diagnostics.qwenStepsEditable = true;
  await page.screenshot({ path: path.join(outputDir, 'qwen-model-selector.png'), fullPage: true, animations: 'disabled' });

  await selector.click();
  await page.getByRole('option', { name: 'FLUX.2 Klein 9B', exact: true }).click();
  if (!(await selector.innerText()).includes('FLUX.2 Klein 9B')) throw new Error('FLUX model selection did not restore');
  await page.getByRole('button', { name: 'Reset to FLUX defaults', exact: true }).waitFor({ state: 'visible', timeout: 10_000 });
  diagnostics.fluxRestored = true;
} finally {
  await writeFile(path.join(outputDir, 'qwen-model-selector-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
