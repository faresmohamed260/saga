import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const galleryUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/gallery') : `${baseUrl.replace(/\/$/, '')}/#/gallery`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { galleryUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [] };
const now = new Date().toISOString();
const rows = [
  {
    id: '99999999-9999-4999-8999-999999999991', kind: 'image', mode: 'edit',
    prompt: 'Portrait reference filling the square gallery card', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '≈ 1088 × 1440 · 1.57 MP', width: 1088, height: 1440, seed: 42,
    media_url: '/mock/gallery-portrait.svg', thumbnail_url: null, metadata: { execution: {} }, created_at: now,
  },
  {
    id: '99999999-9999-4999-8999-999999999992', kind: 'image', mode: 'edit',
    prompt: 'Wide reference filling the square gallery card', model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    resolution: '2048 × 1152 · Manual', width: 2048, height: 1152, seed: 73,
    media_url: '/mock/gallery-landscape.svg', thumbnail_url: null, metadata: { execution: {} }, created_at: now,
  },
];

function svg(label, width, height) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#ce8b67"/><stop offset=".5" stop-color="#775d87"/><stop offset="1" stop-color="#202942"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><rect x="4%" y="4%" width="92%" height="92%" rx="30" fill="none" stroke="#fff" stroke-width="12" opacity=".7"/><text x="50%" y="50%" fill="#fff" font-family="Arial,sans-serif" font-size="${Math.round(Math.min(width, height) * .06)}" font-weight="700" text-anchor="middle">${label}</text></svg>`;
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));
  await page.route('**/api/history?**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: rows, page: { offset: 0, limit: 24, nextOffset: null, hasMore: false }, facets: { models: [rows[0].model] } }) });
  });
  await page.route('**/mock/gallery-portrait.svg', async (route) => route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svg('PORTRAIT COVER', 1088, 1440) }));
  await page.route('**/mock/gallery-landscape.svg', async (route) => route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svg('LANDSCAPE COVER', 2048, 1152) }));

  await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const cards = page.locator('.gallery-grid .gallery-card');
  await cards.nth(1).waitFor({ state: 'visible', timeout: 10_000 });

  const portraitFrame = cards.nth(0).locator('.media-frame-image');
  const landscapeFrame = cards.nth(1).locator('.media-frame-image');
  for (const [label, frame] of [['portrait', portraitFrame], ['landscape', landscapeFrame]]) {
    const style = await frame.evaluate((element) => {
      const computed = getComputedStyle(element);
      return { backgroundSize: computed.backgroundSize, backgroundRepeat: computed.backgroundRepeat, backgroundPosition: computed.backgroundPosition, backgroundImage: computed.backgroundImage };
    });
    if (style.backgroundSize !== 'cover' || style.backgroundRepeat !== 'no-repeat') throw new Error(`${label} thumbnail does not fill its gallery card: ${JSON.stringify(style)}`);
    if (!style.backgroundImage || style.backgroundImage === 'none') throw new Error(`${label} thumbnail image did not render`);
  }

  const badges = await cards.locator('.size-badge').allTextContents();
  if ((badges[0] || '').trim() !== '1080 px') throw new Error(`1088×1440 should map to 1080 px, got ${JSON.stringify(badges[0])}`);
  if ((badges[1] || '').trim() !== '2048 px') throw new Error(`2048×1152 should map to 2048 px, got ${JSON.stringify(badges[1])}`);
  if (badges.some((text) => /1088|1440|1152|MP/i.test(text))) throw new Error(`Raw dimensions or megapixel metadata leaked into Gallery badges: ${JSON.stringify(badges)}`);

  const file = '16-gallery-thumbnail-fit.png';
  await page.screenshot({ path: path.join(outputDir, file), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push(file);
  await writeFile(path.join(outputDir, 'gallery-thumbnail-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
} finally {
  await browser.close();
}
