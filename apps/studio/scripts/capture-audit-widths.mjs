import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const galleryUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/gallery') : `${baseUrl.replace(/\/$/, '')}/#/gallery`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const widths = [360, 430, 1280];
const diagnostics = { widths, measurements: [], pageErrors: [], consoleErrors: [] };

function poster(label, width = 800, height = 800) {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#161923"/><text x="50%" y="52%" fill="#f3f4f7" font-family="Arial" font-size="42" text-anchor="middle">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(markup)}`;
}

const galleryItems = [
  { id: '11111111-1111-4111-8111-111111111111', kind: 'image', mode: 'edit', prompt: 'Reference edit', model: 'FLUX.2 Klein 9B', resolution: '1080p', seed: 42, media_url: poster('IMAGE', 800, 1000), created_at: '2026-08-25T10:00:00.000Z' },
  { id: '22222222-2222-4222-8222-222222222222', kind: 'video', mode: 'video', prompt: 'Motion study', model: 'REDGraft LTX 2.5', resolution: '1080p', seed: 24, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO', 960, 544), metadata: { execution: { aspectRatio: '16:9', frameRate: 24 } }, created_at: '2026-08-25T09:00:00.000Z' },
];

async function mockData(page) {
  await page.route('**/api/history?**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: galleryItems, page: { nextOffset: null, hasMore: false }, facets: { models: ['FLUX.2 Klein 9B', 'REDGraft LTX 2.5'] } }) }));
  await page.route('**/api/favorites', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }));
  await page.route('**/api/collections', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ collections: [] }) }));
}

async function measure(page, width, label) {
  const value = await page.evaluate(() => ({
    html: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  diagnostics.measurements.push({ width, label, ...value });
  if (Math.max(value.html, value.body) > 1) throw new Error(`${label} has horizontal overflow at ${width}px: ${JSON.stringify(value)}`);
}

const browser = await chromium.launch({ headless: true });
try {
  for (const width of widths) {
    const mobile = width <= 430;
    const context = await browser.newContext({ viewport: { width, height: mobile ? 900 : 900 }, colorScheme: 'dark', reducedMotion: 'reduce', hasTouch: mobile, isMobile: mobile });
    const page = await context.newPage();
    await mockData(page);
    page.on('pageerror', (error) => diagnostics.pageErrors.push({ width, text: error?.stack || String(error) }));
    page.on('console', (message) => { if (message.type() === 'error') diagnostics.consoleErrors.push({ width, text: message.text() }); });

    await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.locator('.saga-create-stage').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
    await page.locator('.saga-composer.is-video').waitFor({ state: 'visible', timeout: 5000 });
    await measure(page, width, 'Create Video');
    const submit = await page.locator('.saga-submit').boundingBox();
    if (!submit || (mobile && (submit.width < 44 || submit.height < 44))) throw new Error(`Primary action misses 44px touch target at ${width}px: ${JSON.stringify(submit)}`);
    await page.screenshot({ path: path.join(outputDir, `audit-create-video-${width}.png`), fullPage: true, animations: 'disabled' });

    await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.gallery-grid .gallery-card').nth(1).waitFor({ state: 'visible', timeout: 5000 });
    await measure(page, width, 'Gallery');
    await page.screenshot({ path: path.join(outputDir, `audit-gallery-${width}.png`), fullPage: true, animations: 'disabled' });

    await context.close();
  }
  if (diagnostics.pageErrors.length) throw new Error(`Audit-width page errors: ${diagnostics.pageErrors.map((entry) => `${entry.width}px ${entry.text}`).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'audit-width-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
