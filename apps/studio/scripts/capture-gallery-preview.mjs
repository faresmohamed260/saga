import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const galleryUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/gallery') : `${baseUrl.replace(/\/$/, '')}/#/gallery`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { galleryUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [] };

function poster(label, width = 800, height = 800) {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#28243d"/><stop offset="1" stop-color="#111722"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><circle cx="${Math.round(width * .72)}" cy="${Math.round(height * .28)}" r="${Math.round(Math.min(width, height) * .14)}" fill="#795cff" opacity=".62"/><text x="50%" y="52%" fill="#f4f1ff" font-family="Arial, sans-serif" font-size="${Math.round(Math.min(width, height) * .065)}" font-weight="700" text-anchor="middle">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(markup)}`;
}

const rows = [
  {
    id: '11111111-1111-4111-8111-111111111111', kind: 'video', mode: 'image-to-video',
    prompt: 'Cinematic shoreline at golden hour with gentle camera drift', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '1080p', seed: 42, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 16:9', 960, 544),
    metadata: { execution: { aspectRatio: '16:9', frameRate: 24 } }, created_at: new Date().toISOString(),
  },
  {
    id: '22222222-2222-4222-8222-222222222222', kind: 'image', mode: 'edit',
    prompt: 'Editorial portrait with soft directional studio light', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '1080p', seed: 2026, media_url: poster('IMAGE · 4:5', 800, 1000), thumbnail_url: null,
    metadata: { execution: {} }, created_at: new Date().toISOString(), is_favorite: true,
  },
  {
    id: '33333333-3333-4333-8333-333333333333', kind: 'video', mode: 'video',
    prompt: 'Neon city rain, slow dolly forward, reflections across wet asphalt', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '720p', seed: 808, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 9:16', 544, 960),
    metadata: { execution: { aspectRatio: '9:16', frameRate: 30 } }, created_at: new Date().toISOString(),
  },
  {
    id: '44444444-4444-4444-8444-444444444444', kind: 'image', mode: 'edit',
    prompt: 'Retro-futurist vehicle concept on a clean exhibition floor', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '2K', seed: 73, media_url: poster('IMAGE · 1:1'), thumbnail_url: null,
    metadata: { execution: {} }, created_at: new Date().toISOString(),
  },
  {
    id: '55555555-5555-4555-8555-555555555555', kind: 'video', mode: 'image-to-video',
    prompt: 'Forest path with wind moving through the canopy and subtle handheld motion', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '1080p', seed: 314, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 4:3', 800, 600),
    metadata: { execution: { aspectRatio: '4:3', frameRate: 25 } }, created_at: new Date().toISOString(),
  },
  {
    id: '66666666-6666-4666-8666-666666666666', kind: 'image', mode: 'edit',
    prompt: 'Minimal architecture study with deep shadows and warm evening light', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '1080p', seed: 19, media_url: poster('IMAGE · 3:2', 960, 640), thumbnail_url: null,
    metadata: { execution: {} }, created_at: new Date().toISOString(),
  },
];

async function mockHistory(page) {
  await page.route('**/api/history?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: rows,
        page: { offset: 0, limit: 24, nextOffset: null, hasMore: false },
        facets: { models: ['REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', 'FLUX.2 Klein 9B · DarkBeast V2 BFS'] },
      }),
    });
  });
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'desktop', text: error?.stack || error?.message || String(error) }));
  await mockHistory(page);

  await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const cards = page.locator('.gallery-grid .history-card');
  await cards.nth(5).waitFor({ state: 'visible', timeout: 10_000 });

  if (await page.getByRole('button', { name: 'History', exact: true }).count()) throw new Error('Legacy History navigation is still visible');
  if (await cards.count() !== rows.length) throw new Error(`Gallery rendered ${await cards.count()} cards instead of ${rows.length}`);
  if (await page.locator('.history-card video').count() !== 3) throw new Error('Video cards did not render inline video previews');

  const firstBox = await cards.first().boundingBox();
  if (!firstBox || firstBox.width > 230 || firstBox.width < 175) throw new Error(`Gallery card density is outside the intended range: ${JSON.stringify(firstBox)}`);

  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');

  const overlay = cards.first().locator('.media-actions-overlay');
  const beforeOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));
  if (beforeOpacity > 0.05) throw new Error(`Gallery actions should be hidden before hover, opacity=${beforeOpacity}`);
  await cards.first().locator('.media-frame').hover();
  await page.waitForTimeout(180);
  const afterOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));
  if (afterOpacity < 0.9) throw new Error(`Gallery actions did not appear over media on hover, opacity=${afterOpacity}`);
  await page.screenshot({ path: path.join(outputDir, '11-gallery-hover-actions.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('11-gallery-hover-actions.png');

  await page.getByRole('button', { name: 'Manage', exact: true }).click();
  const manager = page.locator('.gallery-manager');
  await manager.waitFor({ state: 'visible' });
  if (await cards.first().locator('.media-actions-overlay').count()) throw new Error('Per-card hover actions remain mounted during Manage mode');
  await cards.nth(0).locator('.media-select-toggle').click();
  await cards.nth(2).locator('.media-select-toggle').click();
  if (!(await manager.locator('strong').innerText()).includes('2 selected')) throw new Error('Gallery manager did not track two selected items');
  for (const label of ['Favorite', 'Download', 'Delete']) {
    const button = manager.getByRole('button', { name: label, exact: true });
    if (await button.isDisabled()) throw new Error(`${label} bulk action stayed disabled after selection`);
  }
  await page.screenshot({ path: path.join(outputDir, '12-gallery-manager.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('12-gallery-manager.png');

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  mobile.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'mobile', text: error?.stack || error?.message || String(error) }));
  await mockHistory(mobile);
  await mobile.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const mobileCards = mobile.locator('.gallery-grid .history-card');
  await mobileCards.nth(1).waitFor({ state: 'visible', timeout: 10_000 });
  const mobileFirst = await mobileCards.nth(0).boundingBox();
  const mobileSecond = await mobileCards.nth(1).boundingBox();
  if (!mobileFirst || !mobileSecond || Math.abs(mobileFirst.width - mobileSecond.width) > 3 || Math.abs(mobileFirst.x - mobileSecond.x) < mobileFirst.width * .7) {
    throw new Error(`Mobile Gallery is not a stable two-column grid: ${JSON.stringify({ mobileFirst, mobileSecond })}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '13-gallery-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13-gallery-mobile.png');

  await mobile.getByRole('button', { name: 'Manage', exact: true }).click();
  const mobileManager = mobile.locator('.gallery-manager');
  await mobileManager.waitFor({ state: 'visible' });
  await mobileCards.first().locator('.media-select-toggle').click();
  if (!(await mobileManager.locator('strong').innerText()).includes('1 selected')) throw new Error('Mobile Gallery manager did not track selection');
  const managerBox = await mobileManager.boundingBox();
  if (!managerBox || managerBox.x < 0 || managerBox.x + managerBox.width > 390) throw new Error(`Mobile Gallery manager overflows viewport: ${JSON.stringify(managerBox)}`);
  await mobile.screenshot({ path: path.join(outputDir, '14-gallery-mobile-manager.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('14-gallery-mobile-manager.png');

  if (diagnostics.pageErrors.length) throw new Error(`Gallery page errors: ${diagnostics.pageErrors.map((entry) => `${entry.label}: ${entry.text}`).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'gallery-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
