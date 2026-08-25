import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const galleryUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/gallery') : `${baseUrl.replace(/\/$/, '')}/#/gallery`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

function poster(label, width = 800, height = 1000, accent = '#8269ff') {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#242832"/><stop offset="1" stop-color="#0d1118"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><circle cx="${Math.round(width * .68)}" cy="${Math.round(height * .28)}" r="${Math.round(Math.min(width, height) * .16)}" fill="${accent}" opacity=".7"/><rect x="${Math.round(width * .2)}" y="${Math.round(height * .52)}" width="${Math.round(width * .6)}" height="${Math.round(height * .24)}" rx="${Math.round(width * .07)}" fill="#d4d8df" opacity=".84"/><text x="50%" y="90%" fill="#f5f6f8" font-family="Arial,sans-serif" font-size="${Math.round(Math.min(width, height) * .05)}" font-weight="700" text-anchor="middle">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(markup)}`;
}

const initialAssets = [
  { id: '71111111-1111-4111-8111-111111111111', key: 'uploads/2026/08/71111111-1111-4111-8111-111111111111.jpg', filename: 'portrait-reference.jpg', name: 'portrait-reference', mimeType: 'image/jpeg', size: 1832441, width: 800, height: 1000, favorite: true, metadata: {}, createdAt: '2026-08-25T03:00:00Z', updatedAt: '2026-08-25T03:00:00Z', url: poster('PORTRAIT', 800, 1000, '#ff6f91'), downloadUrl: poster('PORTRAIT', 800, 1000, '#ff6f91') },
  { id: '72222222-2222-4222-8222-222222222222', key: 'uploads/2026/08/72222222-2222-4222-8222-222222222222.webp', filename: 'shoreline.webp', name: 'shoreline', mimeType: 'image/webp', size: 944128, width: 1200, height: 800, favorite: false, metadata: {}, createdAt: '2026-08-24T20:00:00Z', updatedAt: '2026-08-24T20:00:00Z', url: poster('SHORELINE', 1200, 800, '#4ab9ff'), downloadUrl: poster('SHORELINE', 1200, 800, '#4ab9ff') },
];
let assets = initialAssets.map((asset) => ({ ...asset }));
const diagnostics = { galleryUrl, screenshots: [], pageErrors: [], uploadFlowCompleted: false };

async function installMocks(page) {
  await page.route('**/api/history?**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], page: { offset: 0, limit: 24, nextOffset: null, hasMore: false }, facets: { models: [] } }) }));
  await page.route('**/api/collections**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ collections: [] }) }));
  await page.route('https://uploads-preview.invalid/**', (route) => route.fulfill({ status: 200, body: '' }));
  await page.route('**/api/uploads?**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() !== 'GET') return route.continue();
    let filtered = [...assets];
    const query = String(url.searchParams.get('search') || '').toLowerCase();
    if (query) filtered = filtered.filter((asset) => asset.name.toLowerCase().includes(query));
    if (url.searchParams.get('favorite') === 'true') filtered = filtered.filter((asset) => asset.favorite);
    if (url.searchParams.get('sort') === 'oldest') filtered.reverse();
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: filtered, page: { limit: 100, offset: 0, nextOffset: null, hasMore: false } }) });
  });
  await page.route('**/api/uploads', async (route) => {
    const request = route.request();
    const method = request.method();
    if (method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: assets, page: { limit: 100, offset: 0, nextOffset: null, hasMore: false } }) });
    const body = request.postDataJSON?.() || {};
    if (method === 'POST' && body.phase === 'complete') {
      const created = { id: '73333333-3333-4333-8333-333333333333', key: body.key, filename: body.filename, name: body.displayName || 'new-upload', mimeType: body.contentType, size: body.size, width: body.width || 1, height: body.height || 1, favorite: false, metadata: {}, createdAt: '2026-08-25T03:10:00Z', updatedAt: '2026-08-25T03:10:00Z', url: poster('NEW UPLOAD', 900, 900, '#73dfa5'), downloadUrl: poster('NEW UPLOAD', 900, 900, '#73dfa5') };
      assets = [created, ...assets.filter((asset) => asset.id !== created.id)];
      diagnostics.uploadFlowCompleted = true;
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ item: created }) });
    }
    if (method === 'POST') {
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ key: 'uploads/2026/08/73333333-3333-4333-8333-333333333333.png', uploadUrl: 'https://uploads-preview.invalid/73333333.png', method: 'PUT', contentType: body.contentType || 'image/png', expiresIn: 300, maxBytes: 26214400 }) });
    }
    if (method === 'PATCH') {
      const current = assets.find((asset) => asset.id === body.id);
      if (!current) return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'Upload not found' }) });
      const next = { ...current, ...(Object.hasOwn(body, 'displayName') ? { name: body.displayName } : {}), ...(Object.hasOwn(body, 'favorite') ? { favorite: Boolean(body.favorite) } : {}) };
      assets = assets.map((asset) => asset.id === next.id ? next : asset);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ item: next }) });
    }
    if (method === 'DELETE') {
      const id = new URL(request.url()).searchParams.get('id');
      assets = assets.filter((asset) => asset.id !== id);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ deleted: true, id }) });
    }
    return route.fulfill({ status: 405, contentType: 'application/json', body: JSON.stringify({ error: 'Method not allowed' }) });
  });
}

const tinyPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII=', 'base64');
const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  desktop.on('pageerror', (error) => diagnostics.pageErrors.push({ surface: 'desktop', text: error?.stack || error?.message || String(error) }));
  await installMocks(desktop);
  await desktop.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await desktop.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const uploadsTab = desktop.getByRole('tab', { name: 'Uploads', exact: true });
  if (await uploadsTab.isDisabled()) throw new Error('Uploads tab is still disabled');
  await uploadsTab.click();
  if (await uploadsTab.getAttribute('aria-selected') !== 'true') throw new Error('Uploads tab did not become active');
  const uploadTile = desktop.getByRole('button', { name: 'Upload', exact: true });
  await uploadTile.waitFor({ state: 'visible' });
  const cards = desktop.locator('.upload-asset-card');
  await cards.nth(1).waitFor({ state: 'visible' });
  if (await cards.count() !== 2) throw new Error(`Expected 2 seeded upload cards, found ${await cards.count()}`);
  await desktop.screenshot({ path: path.join(outputDir, '15-gallery-uploads-desktop.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('15-gallery-uploads-desktop.png');

  await cards.first().locator('.upload-asset-primary').click();
  const detail = desktop.getByRole('dialog', { name: /Preview portrait-reference/ });
  await detail.waitFor({ state: 'visible' });
  await detail.getByRole('button', { name: 'Set as Reference', exact: true }).waitFor({ state: 'visible' });
  await detail.getByRole('button', { name: 'Generate Video', exact: true }).waitFor({ state: 'visible' });
  await desktop.screenshot({ path: path.join(outputDir, '15b-gallery-upload-detail.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('15b-gallery-upload-detail.png');
  await detail.getByRole('button', { name: 'Close upload preview', exact: true }).click();

  await desktop.locator('input[type="file"]').setInputFiles({ name: 'new-reference.png', mimeType: 'image/png', buffer: tinyPng });
  await desktop.getByText('new-reference', { exact: true }).waitFor({ state: 'visible', timeout: 10_000 });
  if (!diagnostics.uploadFlowCompleted) throw new Error('Upload ticket/PUT/finalize flow did not complete');
  if (await cards.count() !== 3) throw new Error(`Uploaded asset did not join the library grid; found ${await cards.count()} cards`);

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark', isMobile: true, hasTouch: true });
  mobile.on('pageerror', (error) => diagnostics.pageErrors.push({ surface: 'mobile', text: error?.stack || error?.message || String(error) }));
  await installMocks(mobile);
  await mobile.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  await mobile.getByRole('tab', { name: 'Uploads', exact: true }).click();
  const mobileCards = mobile.locator('.upload-asset-card');
  await mobileCards.nth(1).waitFor({ state: 'visible' });
  const addBox = await mobile.getByRole('button', { name: 'Upload', exact: true }).boundingBox();
  const firstBox = await mobileCards.first().boundingBox();
  if (!addBox || !firstBox || Math.abs(addBox.width - firstBox.width) > 4 || Math.abs(addBox.x - firstBox.x) < addBox.width * .7) {
    throw new Error(`Mobile Uploads is not a stable two-column asset grid: ${JSON.stringify({ addBox, firstBox })}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '16-gallery-uploads-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('16-gallery-uploads-mobile.png');

  await mobile.getByRole('button', { name: 'Manage', exact: true }).click();
  const manager = mobile.getByRole('toolbar', { name: 'Selected upload actions', exact: true });
  await manager.waitFor({ state: 'visible' });
  const selectButton = mobileCards.first().locator('.upload-asset-primary');
  await selectButton.click();
  if (await selectButton.getAttribute('aria-pressed') !== 'true') throw new Error('Mobile Uploads selection state did not activate');
  if (!(await manager.locator('strong').innerText()).includes('1 selected')) throw new Error('Mobile Uploads manager did not track selected asset');
  const managerBox = await manager.boundingBox();
  if (!managerBox || managerBox.x < 0 || managerBox.x + managerBox.width > 390) throw new Error(`Mobile Uploads manager overflows viewport: ${JSON.stringify(managerBox)}`);
  await mobile.screenshot({ path: path.join(outputDir, '16b-gallery-uploads-mobile-manager.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('16b-gallery-uploads-mobile-manager.png');

  if (diagnostics.pageErrors.length) throw new Error(`Uploads page errors: ${diagnostics.pageErrors.map((entry) => `${entry.surface}: ${entry.text}`).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'uploads-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
