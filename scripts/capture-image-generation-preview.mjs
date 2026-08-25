import { chromium } from 'playwright';
import sharp from 'sharp';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = {
  createUrl,
  generatedAt: new Date().toISOString(),
  screenshots: [],
  pageErrors: [],
  submitted: null,
  sourceUpload: null,
  resultPolls: 0,
};
const referencePng = await sharp({
  create: { width: 800, height: 600, channels: 4, background: { r: 48, g: 52, b: 70, alpha: 1 } },
}).png().toBuffer();
const resultPng = await sharp({
  create: { width: 800, height: 608, channels: 4, background: { r: 95, g: 72, b: 150, alpha: 1 } },
}).png().toBuffer();
const resultDataUrl = `data:image/png;base64,${resultPng.toString('base64')}`;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));

  await context.route('**/api/favorites', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) });
  });
  await context.route('**/api/uploads', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    diagnostics.sourceUpload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        uploadUrl: '/__visual-test-upload/flux-reference.png',
        key: 'visual-tests/flux-reference.png',
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
        job: { id: '88888888-8888-4888-8888-888888888888' },
        status: 'running',
        workflow: 'flux2-klein-image-edit',
        worker: {
          workerId: 'flux-primary-01',
          ecosystem: 'flux2-klein-9b',
          displayName: 'FLUX.2 Klein 9B · Primary',
          state: 'generating',
          failedWorkers: [],
        },
      }),
    });
  });
  await context.route('**/api/generate/result?**', async (route) => {
    diagnostics.resultPolls += 1;
    if (diagnostics.resultPolls === 1) {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'running',
          worker: {
            workerId: 'flux-primary-01',
            ecosystem: 'flux2-klein-9b',
            displayName: 'FLUX.2 Klein 9B · Primary',
            state: 'generating',
            failedWorkers: [],
          },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'completed',
        persisted: true,
        generationId: '99999999-9999-4999-8999-999999999999',
        mediaUrl: resultDataUrl,
        thumbnailUrl: resultDataUrl,
      }),
    });
  });

  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.getByRole('heading', { name: 'Create from a reference', exact: true }).waitFor({ state: 'visible' });

  // Start exactly as a user does: the single Image primary CTA opens the file chooser.
  const addImage = page.getByRole('button', { name: 'Add reference image', exact: true });
  const chooserPromise = page.waitForEvent('filechooser');
  await addImage.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'flux-reference.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 5000 });
  await page.locator('.saga-composer.is-edit').waitFor({ state: 'visible', timeout: 5000 });
  await page.getByRole('heading', { name: 'Transform your references', exact: true }).waitFor({ state: 'visible' });
  const editSubmit = page.getByRole('button', { name: 'Edit image', exact: true });
  await editSubmit.waitFor({ state: 'visible' });

  // Enter the visible prompt and change real FLUX worker controls through Advanced.
  const prompt = page.locator('.saga-rich-prompt');
  await prompt.fill('Turn the reference into a cinematic twilight portrait with soft rim light');
  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const advanced = page.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="Seed"]').fill('12345');
  await advanced.locator('textarea[aria-label="Negative prompt"]').fill('blur, text artifacts');
  await advanced.locator('input[aria-label="Steps value"]').fill('6');
  await advanced.locator('input[aria-label="CFG value"]').fill('1.5');
  await page.getByRole('button', { name: 'Close advanced settings', exact: true }).click();
  await advanced.waitFor({ state: 'hidden' });

  // Submit through the visible primary action and verify the user receives an immediate running state.
  await editSubmit.click();
  for (let attempt = 0; attempt < 40 && !diagnostics.submitted; attempt += 1) await page.waitForTimeout(50);
  if (!diagnostics.sourceUpload) throw new Error('FLUX source upload ticket was not requested after clicking Edit');
  if (!diagnostics.submitted) throw new Error('FLUX image-edit request was not submitted after clicking Edit');
  const progress = page.locator('.saga-generation-progress');
  await progress.waitFor({ state: 'visible', timeout: 3000 });
  await progress.getByText('Generating image', { exact: true }).waitFor({ state: 'visible', timeout: 3000 });
  if (!(await editSubmit.isDisabled())) throw new Error('Image Edit action remains enabled while generation is running');
  await page.screenshot({ path: path.join(outputDir, '07-image-generation-running.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('07-image-generation-running.png');

  // Verify what the user action actually sent to the production workflow contract.
  const submitted = diagnostics.submitted;
  if (submitted.workflowId !== 'flux2-klein-image-edit') throw new Error(`Image edit used the wrong workflow: ${JSON.stringify(submitted)}`);
  if (submitted.sourceKeys?.[0] !== 'visual-tests/flux-reference.png') throw new Error(`Image edit lost the uploaded source key: ${JSON.stringify(submitted)}`);
  if (submitted.sourceFilenames?.[0] !== 'flux-reference.png') throw new Error(`Image edit lost the source filename: ${JSON.stringify(submitted)}`);
  if (submitted.sourceContentTypes?.[0] !== 'image/png') throw new Error(`Image edit lost the source MIME type: ${JSON.stringify(submitted)}`);
  if (submitted.prompt !== 'Turn the reference into a cinematic twilight portrait with soft rim light') throw new Error(`Image edit prompt changed before submission: ${JSON.stringify(submitted)}`);
  if (submitted.negativePrompt !== 'blur, text artifacts') throw new Error(`Image edit negative prompt was not submitted: ${JSON.stringify(submitted)}`);
  if (Number(submitted.seed) !== 12345 || Number(submitted.steps) !== 6 || Number(submitted.cfg) !== 1.5) throw new Error(`Image edit Advanced values were not submitted: ${JSON.stringify(submitted)}`);
  if (!String(submitted.resolution || '').includes('0.48 MP')) throw new Error(`Image edit Auto sizing did not follow the 800×600 reference: ${JSON.stringify(submitted)}`);
  if (Math.abs(Number(submitted.megapixels) - 0.48) > 0.001) throw new Error(`Image edit megapixels did not follow the reference: ${JSON.stringify(submitted)}`);

  // Let the mocked worker complete and verify the result appears in the same visible Create workspace.
  const resultSlot = page.locator('.saga-output-slot').first();
  await resultSlot.waitFor({ state: 'visible', timeout: 7000 });
  await progress.getByText('Generation ready', { exact: true }).waitFor({ state: 'visible', timeout: 3000 });
  if (await editSubmit.isDisabled()) throw new Error('Image Edit action stayed disabled after completion');
  const generatedCard = resultSlot.locator('.media-card');
  await generatedCard.waitFor({ state: 'visible' });
  const frameStyle = await generatedCard.locator('.media-frame').getAttribute('style') || '';
  if (!frameStyle.includes('data:image/png')) throw new Error('Completed FLUX result did not render in Recent work');
  await page.screenshot({ path: path.join(outputDir, '07b-image-generation-complete.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('07b-image-generation-complete.png');

  if (diagnostics.resultPolls < 2) throw new Error(`Image result lifecycle was not polled through running to complete: ${diagnostics.resultPolls}`);
  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'image-generation-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
