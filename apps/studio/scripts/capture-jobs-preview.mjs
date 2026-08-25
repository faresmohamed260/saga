import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const jobsUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/jobs') : `${baseUrl.replace(/\/$/, '')}/#/jobs`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { jobsUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [] };
const now = Date.now();
const jobs = [
  {
    id: '77777777-7777-4777-8777-777777777777',
    status: 'running', kind: 'video', mode: 'video',
    model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', provider: 'modal-ltx25-redgraft',
    prompt: 'Cinematic ocean portrait with slow camera movement', resolution: '1080p', seed: 42,
    created_at: new Date(now - 94_000).toISOString(), started_at: new Date(now - 91_000).toISOString(), completed_at: null,
    metadata: {
      lifecycle: 'job-v1', assignedWorkerId: 'modal-02',
      workerRuntime: { state: 'loading', workerId: 'modal-02', displayName: 'Worker 02', updatedAt: new Date(now - 3_000).toISOString() },
    },
  },
  {
    id: '88888888-8888-4888-8888-888888888888',
    status: 'running', kind: 'image', mode: 'edit',
    model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS', provider: 'modal-flux2-klein',
    prompt: 'Editorial portrait with soft directional studio light', resolution: '≈ 1088 × 1440 · 1.57 MP', seed: 2026,
    created_at: new Date(now - 46_000).toISOString(), started_at: new Date(now - 43_000).toISOString(), completed_at: null,
    metadata: {
      lifecycle: 'job-v1', assignedWorkerId: 'modal-03',
      workerRuntime: { state: 'generating', workerId: 'modal-03', displayName: 'Worker 03', updatedAt: new Date(now - 2_000).toISOString() },
    },
  },
];

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));
  await page.route('**/api/jobs?**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ jobs, filter: 'active', limit: 50 }) });
  });
  await page.goto(jobsUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('heading', { name: 'Jobs & queue', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });

  const tabs = page.getByRole('group', { name: 'Job status filter' });
  const tabButtons = tabs.getByRole('button');
  if (await tabButtons.count() !== 6) throw new Error(`Expected 6 Jobs filters, found ${await tabButtons.count()}`);
  const active = tabButtons.filter({ hasText: 'Active' });
  if (await active.getAttribute('aria-pressed') !== 'true') throw new Error('Active Jobs filter is not selected');
  const tabStyle = await active.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundImage || style.backgroundColor, color: style.color, border: style.borderColor, radius: style.borderRadius };
  });
  if (!tabStyle.background || tabStyle.background === 'none' || tabStyle.background === 'rgba(0, 0, 0, 0)') throw new Error(`Jobs filters lost Studio styling: ${JSON.stringify(tabStyle)}`);
  if (tabStyle.radius === '0px') throw new Error(`Jobs filter radius is native/un-styled: ${JSON.stringify(tabStyle)}`);

  const states = page.locator('.saga-generation-progress');
  if (await states.count() !== 2) throw new Error(`Expected runtime state surface in both job cards, found ${await states.count()}`);
  const text = await states.allTextContents();
  if (!text.some((value) => value.includes('Loading model') && value.includes('Worker 02'))) throw new Error(`Loading worker state is missing: ${JSON.stringify(text)}`);
  if (!text.some((value) => value.includes('Generating image') && value.includes('Worker 03'))) throw new Error(`Generating worker state is missing: ${JSON.stringify(text)}`);
  const tracks = states.locator('.saga-generation-progress-track.indeterminate');
  if (await tracks.count() !== 2) throw new Error('Active Jobs do not expose the same progress treatment as Create');

  const file = '15-jobs-live-state.png';
  await page.screenshot({ path: path.join(outputDir, file), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push(file);
  await writeFile(path.join(outputDir, 'jobs-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
} finally {
  await browser.close();
}
