import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const galleryUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/gallery') : `${baseUrl.replace(/\/$/, '')}/#/gallery`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const requiredWidths = [320, 390, 768, 1024, 1440, 1920];
const transitionWidths = [768, 900, 1024, 1100];
const widths = [...new Set([...requiredWidths, 900, 1100])].sort((a, b) => a - b);
const diagnostics = {
  createUrl,
  galleryUrl,
  generatedAt: new Date().toISOString(),
  requiredWidths,
  transitionWidths,
  screenshots: [],
  measurements: [],
  consoleErrors: [],
  pageErrors: [],
};

function poster(label, width = 800, height = 800) {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#28243d"/><stop offset="1" stop-color="#111722"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><circle cx="${Math.round(width * .72)}" cy="${Math.round(height * .28)}" r="${Math.round(Math.min(width, height) * .14)}" fill="#795cff" opacity=".62"/><text x="50%" y="52%" fill="#f4f1ff" font-family="Arial, sans-serif" font-size="${Math.round(Math.min(width, height) * .065)}" font-weight="700" text-anchor="middle">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(markup)}`;
}

const galleryRows = [
  {
    id: '11111111-1111-4111-8111-111111111111', kind: 'video', mode: 'image-to-video',
    prompt: 'Cinematic shoreline at golden hour with gentle camera drift', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '1080p', seed: 42, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 16:9', 960, 544),
    metadata: { execution: { aspectRatio: '16:9', frameRate: 24 } }, created_at: '2026-08-24T18:00:00.000Z',
  },
  {
    id: '22222222-2222-4222-8222-222222222222', kind: 'image', mode: 'edit',
    prompt: 'Editorial portrait with soft directional studio light', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '1080p', seed: 2026, media_url: poster('IMAGE · 4:5', 800, 1000), thumbnail_url: null,
    metadata: { execution: {} }, created_at: '2026-08-24T17:00:00.000Z', is_favorite: true,
  },
  {
    id: '33333333-3333-4333-8333-333333333333', kind: 'video', mode: 'video',
    prompt: 'Neon city rain, slow dolly forward, reflections across wet asphalt', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '720p', seed: 808, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 9:16', 544, 960),
    metadata: { execution: { aspectRatio: '9:16', frameRate: 30 } }, created_at: '2026-08-24T16:00:00.000Z',
  },
  {
    id: '44444444-4444-4444-8444-444444444444', kind: 'image', mode: 'edit',
    prompt: 'Retro-futurist vehicle concept on a clean exhibition floor', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '2K', seed: 73, media_url: poster('IMAGE · 1:1'), thumbnail_url: null,
    metadata: { execution: {} }, created_at: '2026-08-24T15:00:00.000Z',
  },
  {
    id: '55555555-5555-4555-8555-555555555555', kind: 'video', mode: 'image-to-video',
    prompt: 'Forest path with wind moving through the canopy and subtle handheld motion', model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    resolution: '1080p', seed: 314, media_url: 'data:video/mp4;base64,', thumbnail_url: poster('VIDEO · 4:3', 800, 600),
    metadata: { execution: { aspectRatio: '4:3', frameRate: 25 } }, created_at: '2026-08-24T14:00:00.000Z',
  },
  {
    id: '66666666-6666-4666-8666-666666666666', kind: 'image', mode: 'edit',
    prompt: 'Minimal architecture study with deep shadows and warm evening light', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '1080p', seed: 19, media_url: poster('IMAGE · 3:2', 960, 640), thumbnail_url: null,
    metadata: { execution: {} }, created_at: '2026-08-24T13:00:00.000Z',
  },
];

async function mockGallery(page) {
  await page.route('**/api/history?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: galleryRows,
        page: { offset: 0, limit: 24, nextOffset: null, hasMore: false },
        facets: { models: ['REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', 'FLUX.2 Klein 9B · DarkBeast V2 BFS'] },
      }),
    });
  });
}

function viewportHeight(width) {
  if (width <= 390) return 844;
  if (width <= 768) return 1024;
  if (width >= 1920) return 1080;
  return 1000;
}

function slug(width) {
  return String(width).padStart(4, '0');
}

async function assertNoHorizontalOverflow(page, label, width) {
  const measurement = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    htmlClientWidth: document.documentElement.clientWidth,
    htmlScrollWidth: document.documentElement.scrollWidth,
    bodyClientWidth: document.body.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  diagnostics.measurements.push({ label, width, type: 'document', ...measurement });
  const overflow = Math.max(measurement.htmlScrollWidth - measurement.htmlClientWidth, measurement.bodyScrollWidth - measurement.bodyClientWidth);
  if (overflow > 1) throw new Error(`${label} at ${width}px has ${overflow}px horizontal overflow: ${JSON.stringify(measurement)}`);
}

async function assertContained(locator, label, width, allowance = 1) {
  if (!(await locator.isVisible().catch(() => false))) return;
  const box = await locator.boundingBox();
  if (!box) throw new Error(`${label} at ${width}px could not be measured`);
  diagnostics.measurements.push({ label, width, type: 'element', box });
  if (box.x < -allowance || box.x + box.width > width + allowance) {
    throw new Error(`${label} at ${width}px escapes viewport: ${JSON.stringify(box)}`);
  }
}

async function assertMinimumWidth(locator, label, width, minimum) {
  const box = await locator.boundingBox();
  if (!box) throw new Error(`${label} at ${width}px could not be measured`);
  diagnostics.measurements.push({ label, width, type: 'minimum-width', minimum, box });
  if (box.width < minimum) throw new Error(`${label} at ${width}px is too narrow (${box.width}px < ${minimum}px): ${JSON.stringify(box)}`);
}

async function assertNoOverlap(first, second, label, width, allowance = 1) {
  if (!(await first.isVisible().catch(() => false)) || !(await second.isVisible().catch(() => false))) return;
  const [firstBox, secondBox] = await Promise.all([first.boundingBox(), second.boundingBox()]);
  if (!firstBox || !secondBox) throw new Error(`${label} at ${width}px could not be measured`);
  diagnostics.measurements.push({ label, width, type: 'pair', firstBox, secondBox });
  const overlapX = Math.min(firstBox.x + firstBox.width, secondBox.x + secondBox.width) - Math.max(firstBox.x, secondBox.x);
  const overlapY = Math.min(firstBox.y + firstBox.height, secondBox.y + secondBox.height) - Math.max(firstBox.y, secondBox.y);
  if (overlapX > allowance && overlapY > allowance) {
    throw new Error(`${label} overlaps at ${width}px: ${JSON.stringify({ firstBox, secondBox, overlapX, overlapY })}`);
  }
}

async function shot(page, filename) {
  await page.screenshot({ path: path.join(outputDir, filename), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push(filename);
}

const browser = await chromium.launch({ headless: true });
try {
  for (const width of widths) {
    const context = await browser.newContext({
      viewport: { width, height: viewportHeight(width) },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      reducedMotion: 'reduce',
      hasTouch: width <= 390,
      isMobile: width <= 390,
    });
    const page = await context.newPage();
    page.on('console', (message) => {
      if (message.type() === 'error') diagnostics.consoleErrors.push({ width, route: page.url(), text: message.text() });
    });
    page.on('pageerror', (error) => diagnostics.pageErrors.push({ width, route: page.url(), text: error?.stack || error?.message || String(error) }));

    await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
    await page.waitForTimeout(120);
    await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
    await page.locator('.saga-composer.is-video').waitFor({ state: 'visible', timeout: 2500 });
    await page.locator('.saga-video-resolution-trigger').waitFor({ state: 'visible' });
    await page.locator('.saga-audio-toggle').waitFor({ state: 'visible' });
    await page.getByRole('button', { name: /Video duration \d+ seconds/ }).waitFor({ state: 'visible' });
    await page.locator('.saga-submit').waitFor({ state: 'visible' });
    await assertNoHorizontalOverflow(page, 'Create / Video', width);
    await assertContained(page.locator('main.workspace'), 'Create workspace', width);
    await assertContained(page.locator('.saga-composer'), 'Video composer', width);
    await assertContained(page.locator('.saga-submit'), 'Generate video action', width);
    await shot(page, `responsive-create-video-${slug(width)}.png`);

    await mockGallery(page);
    await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
    const cards = page.locator('.gallery-grid .gallery-card');
    await cards.nth(5).waitFor({ state: 'visible', timeout: 10_000 });
    const search = width <= 760 ? page.getByRole('button', { name: 'Search Gallery', exact: true }) : page.locator('.gallery-search-desktop input');
    const modelSelect = width <= 760 ? page.locator('.gallery-mobile-filter-panel .gallery-model-filter select') : page.locator('.gallery-model-filter select').first();
    await assertNoHorizontalOverflow(page, 'Gallery compact', width);
    await assertContained(page.locator('main.workspace'), 'Gallery workspace', width);
    await assertContained(search, 'Gallery search', width);
    await assertContained(page.locator('.gallery-grid'), 'Gallery grid', width);
    await assertNoOverlap(search, page.locator('.gallery-sort'), 'Gallery search / sort', width);
    if (width <= 390) {
      await search.click();
      const mobileSearch = page.locator('.gallery-search-mobile input');
      await mobileSearch.waitFor({ state: 'visible' });
      await assertMinimumWidth(mobileSearch, 'Gallery search', width, 140);
      await page.getByRole('button', { name: /^Filter/ }).click();
      const mobileFilters = page.locator('.gallery-mobile-filter-panel');
      await mobileFilters.waitFor({ state: 'visible' });
      await assertContained(mobileFilters, 'Gallery mobile filters', width);
      await assertMinimumWidth(modelSelect, 'Gallery model filter', width, 90);
    }
    const firstCard = await cards.first().boundingBox();
    if (!firstCard || firstCard.width < 120) throw new Error(`Gallery cards collapse below 120px at ${width}px: ${JSON.stringify(firstCard)}`);
    diagnostics.measurements.push({ label: 'Gallery first card', width, type: 'element', box: firstCard });
    await shot(page, `responsive-gallery-${slug(width)}.png`);

    if (transitionWidths.includes(width)) {
      await page.getByRole('button', { name: 'Manage', exact: true }).click();
      const manager = page.locator('.gallery-manager');
      await manager.waitFor({ state: 'visible' });
      const selectButton = cards.first().locator('.media-frame-primary');
      await selectButton.click();
      if (await selectButton.getAttribute('aria-pressed') !== 'true') throw new Error(`Gallery selection did not activate at ${width}px`);
      await assertNoHorizontalOverflow(page, 'Gallery manage', width);
      await assertContained(manager, 'Gallery manager', width);
      await shot(page, `responsive-gallery-manage-${slug(width)}.png`);
    }

    await context.close();
  }

  const missingRequired = requiredWidths.filter((width) => !widths.includes(width));
  if (missingRequired.length) throw new Error(`Responsive matrix is missing required widths: ${missingRequired.join(', ')}`);
  if (diagnostics.pageErrors.length) {
    throw new Error(`Responsive preview page errors: ${diagnostics.pageErrors.map((entry) => `${entry.width}px ${entry.text}`).join(' | ')}`);
  }
} finally {
  await writeFile(path.join(outputDir, 'responsive-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
