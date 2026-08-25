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

async function assertTouchTargets(locator, minimum = 44) {
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    const box = await locator.nth(index).boundingBox();
    if (!box || box.width < minimum || box.height < minimum) {
      throw new Error(`Touch target ${index} is below ${minimum}px: ${JSON.stringify(box)}`);
    }
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  await page.addInitScript(() => {
    const nativeMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = (query) => {
      if (query !== '(hover: hover) and (pointer: fine)') return nativeMatchMedia(query);
      return { matches: true, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; } };
    };
  });
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'desktop', text: error?.stack || error?.message || String(error) }));
  await mockHistory(page);

  await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const cards = page.locator('.gallery-grid .gallery-card');
  await cards.nth(5).waitFor({ state: 'visible', timeout: 10_000 });

  if (await page.getByRole('button', { name: 'History', exact: true }).count()) throw new Error('Legacy History navigation is still visible');
  if (await cards.count() !== rows.length) throw new Error(`Gallery rendered ${await cards.count()} cards instead of ${rows.length}`);
  const modelFilter = page.locator('.gallery-model-filter select');
  const optionLabels = await modelFilter.locator('option').allTextContents();
  if (!optionLabels.includes('LTX Video 2.5') || !optionLabels.includes('FLUX.2 Klein 9B')) throw new Error(`Gallery model filter is missing friendly model names: ${JSON.stringify(optionLabels)}`);
  if (optionLabels.some((label) => /DarkBeast|Sulphur2|INT8|ConvRot|REDGraft/i.test(label))) throw new Error(`Technical model strings leaked into Gallery filter: ${JSON.stringify(optionLabels)}`);
  const videoPreviews = page.locator('.gallery-card video');
  if (await videoPreviews.count() !== 3) throw new Error('Video cards did not render inline video previews');
  for (let index = 0; index < 3; index += 1) {
    const preview = videoPreviews.nth(index);
    if (!(await preview.getAttribute('poster'))) throw new Error(`Video card ${index} is missing its stored poster URL`);
    if (await preview.getAttribute('preload') !== 'none') throw new Error(`Poster-backed video card ${index} should use preload=none`);
    if (await preview.getAttribute('src')) throw new Error(`Poster-backed video card ${index} eagerly attached its MP4 source`);
    if (await preview.getAttribute('data-preview-state') !== 'deferred') throw new Error(`Video card ${index} should start in deferred preview state`);
  }

  const firstBox = await cards.first().boundingBox();
  if (!firstBox || firstBox.width > 230 || firstBox.width < 175) throw new Error(`Gallery card density is outside the intended range: ${JSON.stringify(firstBox)}`);

  if (await page.locator('.gallery-card .media-frame[role="button"]').count()) throw new Error('Gallery media frame still uses button-like role semantics');
  if (await page.locator('.gallery-card button button').count()) throw new Error('Gallery contains nested button elements');
  const primaryButtons = page.locator('.gallery-card .media-frame-primary');
  if (await primaryButtons.count() !== rows.length) throw new Error(`Expected one primary media button per card, found ${await primaryButtons.count()}`);
  if ((await primaryButtons.first().evaluate((element) => element.tagName)) !== 'BUTTON') throw new Error('Primary media action is not a native button');
  if (await primaryButtons.first().getAttribute('aria-pressed') !== null) throw new Error('Browse-mode primary media button should not expose selection state');
  const firstFocusableClass = await cards.first().locator('button').first().getAttribute('class');
  if (!firstFocusableClass?.includes('media-frame-primary')) throw new Error(`Primary media action is not first in card focus order: ${firstFocusableClass}`);

  const searchInput = page.getByRole('searchbox', { name: 'Search prompts' });
  await searchInput.fill('shoreline');
  await page.waitForTimeout(250);
  if (!page.url().includes('#/gallery')) throw new Error('Gallery search unexpectedly changed navigation');
  await page.locator('.gallery-sort select').selectOption('oldest');
  await page.waitForTimeout(250);
  await searchInput.fill('');
  await page.locator('.gallery-sort select').selectOption('newest');

  const compactDensity = page.getByRole('button', { name: 'Compact', exact: true });
  const comfortableDensity = page.getByRole('button', { name: 'Comfortable', exact: true });
  if (await compactDensity.getAttribute('aria-pressed') !== 'true') throw new Error('Gallery must default to Compact density');
  if (await page.locator('.gallery-grid').getAttribute('data-density') !== 'compact') throw new Error('Gallery grid did not expose Compact density');

  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');
  await page.locator('.gallery-grid').screenshot({ path: path.join(outputDir, '10c-gallery-video-posters.png'), animations: 'disabled' });
  diagnostics.screenshots.push('10c-gallery-video-posters.png');

  await comfortableDensity.click();
  if (await comfortableDensity.getAttribute('aria-pressed') !== 'true') throw new Error('Comfortable density did not become active');
  if (await page.locator('.gallery-grid').getAttribute('data-density') !== 'comfortable') throw new Error('Gallery grid did not expose Comfortable density');
  const comfortableBox = await cards.first().boundingBox();
  if (!comfortableBox || comfortableBox.width < 245) throw new Error(`Comfortable density card is too narrow: ${JSON.stringify(comfortableBox)}`);
  if (await page.evaluate(() => localStorage.getItem('saga.galleryDensity')) !== 'comfortable') throw new Error('Gallery density preference was not persisted');
  await page.screenshot({ path: path.join(outputDir, '10e-gallery-comfortable.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10e-gallery-comfortable.png');
  await compactDensity.click();

  await page.keyboard.press('Tab');
  await primaryButtons.first().focus();
  const focusedVideo = cards.first().locator('video');
  await page.waitForFunction((element) => element?.getAttribute('data-preview-state') === 'active', await focusedVideo.elementHandle());
  if (!(await focusedVideo.getAttribute('src'))) throw new Error('Keyboard focus did not attach the deferred video source');
  if (!(await primaryButtons.first().evaluate((element) => element.matches(':focus-visible')))) throw new Error('Primary media action does not receive :focus-visible treatment');
  const primaryFocusStyle = await primaryButtons.first().evaluate((element) => {
    const style = getComputedStyle(element);
    return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  if (primaryFocusStyle.outlineStyle === 'none' || Number.parseFloat(primaryFocusStyle.outlineWidth) < 2) {
    throw new Error(`Primary media focus indicator is not visually strong enough: ${JSON.stringify(primaryFocusStyle)}`);
  }
  await page.screenshot({ path: path.join(outputDir, '10b-gallery-keyboard-focus.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10b-gallery-keyboard-focus.png');

  const overlay = cards.first().locator('.media-actions-overlay');
  const beforeOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));
  await page.locator('body').click({ position: { x: 2, y: 2 } });
  await page.waitForTimeout(220);
  const resetOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));
  if (await focusedVideo.getAttribute('src')) throw new Error('Video source stayed attached after keyboard focus left the card');
  if (await focusedVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Video preview did not return to deferred state after focus left');
  if (beforeOpacity < 0.9) throw new Error(`Gallery actions should be exposed while the card has keyboard focus, opacity=${beforeOpacity}`);
  if (resetOpacity > 0.05) throw new Error(`Gallery actions should hide after keyboard focus leaves the card, opacity=${resetOpacity}`);
  await cards.first().locator('.media-frame').hover();
  await page.waitForTimeout(180);
  const afterOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));
  if (afterOpacity < 0.9) throw new Error(`Gallery actions did not appear over media on hover, opacity=${afterOpacity}`);
  if (!(await focusedVideo.getAttribute('src'))) throw new Error('Desktop hover did not attach the deferred MP4 source');
  if (await focusedVideo.getAttribute('data-preview-state') !== 'active') throw new Error('Desktop hover did not activate video preview state');
  await page.screenshot({ path: path.join(outputDir, '11c-gallery-video-preview-hover.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('11c-gallery-video-preview-hover.png');

  const desktopPrimary = overlay.locator('.media-action-primary:visible');
  if (await desktopPrimary.count() !== 4) throw new Error(`Desktop Gallery should expose exactly 4 immediate actions, found ${await desktopPrimary.count()}`);
  if (await overlay.getByRole('button', { name: 'Delete permanently', exact: true }).count()) throw new Error('Delete is still exposed as an immediate desktop action');

  await page.screenshot({ path: path.join(outputDir, '11-gallery-hover-actions.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('11-gallery-hover-actions.png');

  await overlay.getByRole('button', { name: 'More actions', exact: true }).click();
  const desktopMore = cards.first().locator('.media-actions-popover');
  await desktopMore.waitFor({ state: 'visible' });
  for (const label of ['Reuse settings', 'Add to collection', 'Delete permanently']) {
    await desktopMore.getByRole('menuitem', { name: label, exact: true }).waitFor({ state: 'visible' });
  }
  if (await desktopMore.getByRole('menuitem', { name: 'Edit', exact: true }).count()) throw new Error('Unsupported video Edit action is still exposed in desktop Gallery');
  if (await desktopMore.getByRole('menuitem', { name: 'Download original', exact: true }).isVisible()) {
    throw new Error('Desktop More menu duplicates the already-visible Download action');
  }
  await page.screenshot({ path: path.join(outputDir, '11-gallery-hover-actions.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('11-gallery-hover-actions.png');
  await page.keyboard.press('Escape');
  await desktopMore.waitFor({ state: 'detached' });

  await primaryButtons.nth(1).click();
  const mediaModal = page.locator('.media-modal');
  await mediaModal.waitFor({ state: 'visible' });
  if (!(await mediaModal.innerText()).includes('FLUX.2 Klein 9B')) throw new Error('Media viewer does not expose the friendly model name');
  const details = mediaModal.locator('.media-modal-details');
  await details.locator('summary').click();
  await details.getByText('Model', { exact: true }).waitFor({ state: 'visible' });
  await details.getByText('Implementation', { exact: true }).waitFor({ state: 'visible' });
  await details.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  await details.getByText('Seed', { exact: true }).waitFor({ state: 'visible' });
  if (await cards.nth(1).getByText(/Seed /).count()) throw new Error('Seed leaked back into Gallery card metadata');
  await page.screenshot({ path: path.join(outputDir, '11d-gallery-media-details.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('11d-gallery-media-details.png');
  await mediaModal.locator('.media-modal-close').click();
  await mediaModal.waitFor({ state: 'detached' });

  await page.getByRole('button', { name: 'Manage', exact: true }).click();
  const manager = page.locator('.gallery-manager');
  await manager.waitFor({ state: 'visible' });
  if (await cards.first().locator('.media-actions-overlay').count()) throw new Error('Per-card hover actions remain mounted during Manage mode');
  const selectionIndicators = page.locator('.gallery-card .media-select-toggle');
  if (await selectionIndicators.count() !== rows.length) throw new Error('Manage mode did not render a selection indicator for every card');
  if (await selectionIndicators.first().evaluate((element) => element.tagName) === 'BUTTON') throw new Error('Selection indicator remains a duplicate interactive button');
  if (await selectionIndicators.first().getAttribute('aria-hidden') !== 'true') throw new Error('Visual selection indicator should be hidden from assistive technology');

  const firstSelectButton = cards.nth(0).locator('.media-frame-primary');
  const thirdSelectButton = cards.nth(2).locator('.media-frame-primary');
  if (await firstSelectButton.getAttribute('aria-pressed') !== 'false') throw new Error('Manage-mode primary action does not expose unselected aria-pressed state');
  await firstSelectButton.press('Space');
  if (await firstSelectButton.getAttribute('aria-pressed') !== 'true') throw new Error('Space did not select the first Gallery card');
  await thirdSelectButton.press('Enter');
  if (await thirdSelectButton.getAttribute('aria-pressed') !== 'true') throw new Error('Enter did not select the third Gallery card');
  if (!(await manager.locator('strong').innerText()).includes('2 selected')) throw new Error('Gallery manager did not track two keyboard-selected items');
  for (const label of ['Favorite', 'Download', 'Delete']) {
    const button = manager.getByRole('button', { name: label, exact: true });
    if (await button.isDisabled()) throw new Error(`${label} bulk action stayed disabled after selection`);
  }
  await page.screenshot({ path: path.join(outputDir, '12-gallery-manager.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('12-gallery-manager.png');

  const reduced = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  reduced.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'reduced-motion', text: error?.stack || error?.message || String(error) }));
  await reduced.emulateMedia({ reducedMotion: 'reduce' });
  await mockHistory(reduced);
  await reduced.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await reduced.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const reducedCard = reduced.locator('.gallery-grid .gallery-card').first();
  const reducedVideo = reducedCard.locator('video');
  await reducedCard.locator('.media-frame').hover();
  await reduced.waitForTimeout(180);
  if (await reducedVideo.getAttribute('src')) throw new Error('Reduced-motion mode attached a hover video source');
  if (await reducedVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Reduced-motion mode should keep poster-backed video deferred');
  await reduced.screenshot({ path: path.join(outputDir, '10d-gallery-reduced-motion.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10d-gallery-reduced-motion.png');
  await reduced.close();

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark', hasTouch: true, isMobile: true });
  mobile.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'mobile', text: error?.stack || error?.message || String(error) }));
  await mockHistory(mobile);
  await mobile.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });
  const mobileCards = mobile.locator('.gallery-grid .gallery-card');
  await mobileCards.nth(1).waitFor({ state: 'visible', timeout: 10_000 });
  const mobileFirst = await mobileCards.nth(0).boundingBox();
  const mobileSecond = await mobileCards.nth(1).boundingBox();
  if (!mobileFirst || !mobileSecond || Math.abs(mobileFirst.width - mobileSecond.width) > 3 || Math.abs(mobileFirst.x - mobileSecond.x) < mobileFirst.width * .7) {
    throw new Error(`Mobile Gallery is not a stable two-column grid: ${JSON.stringify({ mobileFirst, mobileSecond })}`);
  }

  const mobileVideo = mobileCards.first().locator('video');
  if (await mobileVideo.getAttribute('src')) throw new Error('Mobile Gallery eagerly attached a poster-backed MP4 source');
  const mobileFineHover = await mobile.evaluate(() => window.matchMedia('(hover: hover) and (pointer: fine)').matches);
  if (mobileFineHover) throw new Error('Touch-emulated Gallery unexpectedly reports fine-hover input capability');
  await mobileCards.first().locator('.media-frame').dispatchEvent('mouseenter');
  await mobile.waitForTimeout(120);
  if (await mobileVideo.getAttribute('src')) throw new Error('Touch Gallery synthetic hover attached a video source');
  if (await mobileVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Touch Gallery should keep video previews poster-only');

  const mobileOverlay = mobileCards.first().locator('.media-actions-overlay');
  const mobileOpacity = Number(await mobileOverlay.evaluate((element) => getComputedStyle(element).opacity));
  if (mobileOpacity < 0.9) throw new Error(`Mobile actions must be visible without hover, opacity=${mobileOpacity}`);
  const mobilePrimary = mobileOverlay.locator('.media-action-primary:visible');
  if (await mobilePrimary.count() !== 3) throw new Error(`Mobile Gallery should expose exactly 3 immediate actions, found ${await mobilePrimary.count()}`);
  await assertTouchTargets(mobilePrimary, 44);
  if (await mobileOverlay.getByRole('button', { name: 'Delete permanently', exact: true }).count()) throw new Error('Delete is still exposed as an immediate mobile action');

  await mobile.screenshot({ path: path.join(outputDir, '13-gallery-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13-gallery-mobile.png');
  await mobile.getByRole('button', { name: 'Gallery layout: compact', exact: true }).click();
  const mobileComfortableGrid = mobile.locator('.gallery-grid');
  if (await mobileComfortableGrid.getAttribute('data-density') !== 'comfortable') throw new Error('Mobile Comfortable density did not activate');
  const mobileComfortableFirst = await mobileCards.first().boundingBox();
  const mobileComfortableSecond = await mobileCards.nth(1).boundingBox();
  if (!mobileComfortableFirst || !mobileComfortableSecond || Math.abs(mobileComfortableFirst.x - mobileComfortableSecond.x) > 3 || mobileComfortableSecond.y <= mobileComfortableFirst.y) {
    throw new Error(`Mobile Comfortable density is not a single-column detail layout: ${JSON.stringify({ mobileComfortableFirst, mobileComfortableSecond })}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '13c-gallery-mobile-comfortable.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13c-gallery-mobile-comfortable.png');
  await mobile.getByRole('button', { name: 'Gallery layout: comfortable', exact: true }).click();

  await mobileOverlay.getByRole('button', { name: 'More actions', exact: true }).click();
  const mobileMore = mobile.locator('.gallery-more-sheet-portal .media-actions-popover');
  await mobileMore.waitFor({ state: 'visible' });
  for (const label of ['Reuse settings', 'Download original', 'Add to collection', 'Delete permanently']) {
    await mobileMore.getByRole('menuitem', { name: label, exact: true }).waitFor({ state: 'visible' });
  }
  if (await mobileMore.getByRole('menuitem', { name: 'Edit', exact: true }).count()) throw new Error('Unsupported video Edit action is still exposed in mobile Gallery');
  await assertTouchTargets(mobileMore.getByRole('menuitem'), 44);
  const moreBox = await mobileMore.boundingBox();
  if (!moreBox || moreBox.x < 0 || moreBox.x + moreBox.width > 390 || moreBox.y < 0 || moreBox.y + moreBox.height > 844) {
    throw new Error(`Mobile More surface overflows viewport: ${JSON.stringify(moreBox)}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '13b-gallery-mobile-more-actions.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13b-gallery-mobile-more-actions.png');
  await mobile.keyboard.press('Escape');
  await mobileMore.waitFor({ state: 'detached' });

  await mobile.getByRole('button', { name: 'Manage', exact: true }).click();
  const mobileManager = mobile.locator('.gallery-manager');
  await mobileManager.waitFor({ state: 'visible' });
  const mobileSelectButton = mobileCards.first().locator('.media-frame-primary');
  await mobileSelectButton.press('Space');
  if (await mobileSelectButton.getAttribute('aria-pressed') !== 'true') throw new Error('Mobile primary selection action did not expose selected state');
  if (!(await mobileManager.locator('strong').innerText()).includes('1 selected')) throw new Error('Mobile Gallery manager did not track keyboard selection');
  const managerBox = await mobileManager.boundingBox();
  if (!managerBox || managerBox.x < 0 || managerBox.x + managerBox.width > 390) throw new Error(`Mobile Gallery manager overflows viewport: ${JSON.stringify(managerBox)}`);
  await mobile.screenshot({ path: path.join(outputDir, '14-gallery-mobile-manager.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('14-gallery-mobile-manager.png');

  if (diagnostics.pageErrors.length) throw new Error(`Gallery page errors: ${diagnostics.pageErrors.map((entry) => `${entry.label}: ${entry.text}`).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'gallery-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
