import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { generatedAt: new Date().toISOString(), desktop: [], mobile: [], continuation: [], consoleErrors: [], pageErrors: [] };
const destinations = [
  ['Create', /Create from a reference|Transform your references|Create motion/],
  ['Jobs', 'Jobs & queue'],
  ['Gallery', 'Gallery'],
  ['Favorites', 'Favorites'],
  ['Collections', 'Collections'],
  ['Models', 'Production models'],
  ['Workflows', 'Production workflows'],
  ['Settings', 'Studio settings'],
];

async function mockLibrary(page) {
  await page.route('**/api/history?**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], page: { nextOffset: null, hasMore: false }, facets: { models: [] } }) }));
  await page.route('**/api/favorites', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }));
  await page.route('**/api/collections', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ collections: [] }) }));
  await page.route('**/api/jobs?**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ jobs: [] }) }));
}

async function expectDestination(page, label, heading) {
  if (heading instanceof RegExp) await page.getByRole('heading', { name: heading }).waitFor({ state: 'visible', timeout: 5000 });
  else await page.getByRole('heading', { name: heading, exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  const expectedHash = `#/${label.toLowerCase()}`;
  if (!page.url().endsWith(expectedHash)) throw new Error(`${label} navigation did not update hash to ${expectedHash}: ${page.url()}`);
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, document.body.scrollWidth - document.body.clientWidth));
  if (overflow > 1) throw new Error(`${label} has ${overflow}px horizontal overflow`);
}

async function runDesktop(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'dark', reducedMotion: 'reduce' });
  const page = await context.newPage();
  await mockLibrary(page);
  page.on('console', (message) => { if (message.type() === 'error') diagnostics.consoleErrors.push({ viewport: 'desktop', text: message.text() }); });
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ viewport: 'desktop', text: error?.stack || String(error) }));
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.locator('.saga-create-stage').waitFor({ state: 'visible', timeout: 10000 });

  for (const [label, heading] of destinations) {
    if (label !== 'Create') await page.getByRole('button', { name: label, exact: true }).click();
    await expectDestination(page, label, heading);
    diagnostics.desktop.push({ label, url: page.url() });
    if (['Models', 'Workflows', 'Settings'].includes(label)) {
      await page.screenshot({ path: path.join(outputDir, `navigation-${label.toLowerCase()}-desktop.png`), fullPage: true, animations: 'disabled' });
    }
  }

  const settingsAction = page.getByRole('button', { name: 'Open generation settings', exact: true });
  await settingsAction.click();
  await page.getByRole('dialog', { name: 'Advanced settings' }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Settings generation action did not return to Create');
  await page.keyboard.press('Escape');

  // User journey: a stored Video preference must not override an explicit Image-model launch.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Video' }));
  });
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expectDestination(page, 'Models', 'Production models');
  await page.getByRole('button', { name: 'Start image edit', exact: true }).click();
  await page.getByRole('heading', { name: /Create from a reference|Transform your references/ }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Model launch action did not enter Create');
  if (await page.locator('.saga-composer.is-video').count()) throw new Error('Stored Video preference overrode explicit Image-model launch');
  if (await page.getByRole('button', { name: 'Image', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Image launch did not activate the Image toggle');
  diagnostics.continuation.push({ action: 'model-to-image-edit', url: page.url(), conflictingStoredMode: 'Video', visibleMode: 'Image' });

  // User journey: a stored Image preference must not override an explicit Video-workflow launch.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Image' }));
  });
  await page.getByRole('button', { name: 'Workflows', exact: true }).click();
  await expectDestination(page, 'Workflows', 'Production workflows');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await page.getByRole('heading', { name: 'Create motion', exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Workflow launch action did not enter Video Create');
  if (!await page.locator('.saga-composer.is-video').count()) throw new Error('Workflow launch action did not activate Video mode');
  if (await page.getByRole('button', { name: 'Video', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Video launch did not activate the Video toggle');
  diagnostics.continuation.push({ action: 'workflow-to-video', url: page.url(), conflictingStoredMode: 'Image', visibleMode: 'Video' });

  await context.close();
}

async function runMobile(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark', reducedMotion: 'reduce', hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await mockLibrary(page);
  page.on('console', (message) => { if (message.type() === 'error') diagnostics.consoleErrors.push({ viewport: 'mobile', text: message.text() }); });
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ viewport: 'mobile', text: error?.stack || String(error) }));
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.locator('.saga-create-stage').waitFor({ state: 'visible', timeout: 10000 });

  for (const [label, heading] of destinations.slice(1)) {
    await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    const sidebar = page.locator('.sidebar.open');
    await sidebar.waitFor({ state: 'visible', timeout: 3000 });
    await sidebar.getByRole('button', { name: label, exact: true }).click();
    await expectDestination(page, label, heading);
    if (await page.locator('.sidebar.open').count()) throw new Error(`Mobile navigation did not close after choosing ${label}`);
    diagnostics.mobile.push({ label, url: page.url() });
  }

  await page.locator('.mobile-topbar').getByRole('button', { name: 'Open generation settings', exact: true }).click();
  await page.getByRole('dialog', { name: 'Advanced settings' }).waitFor({ state: 'visible', timeout: 5000 });
  if (!page.url().endsWith('#/create')) throw new Error('Global mobile settings action did not return to Create');
  const dialogBox = await page.getByRole('dialog', { name: 'Advanced settings' }).boundingBox();
  if (!dialogBox || dialogBox.x < -1 || dialogBox.x + dialogBox.width > 391) throw new Error(`Mobile generation settings escape viewport: ${JSON.stringify(dialogBox)}`);
  await page.screenshot({ path: path.join(outputDir, 'navigation-settings-mobile.png'), fullPage: true, animations: 'disabled' });
  await page.keyboard.press('Escape');

  // Mobile user journey: launch Video through navigation and verify the actual composer state.
  await page.evaluate(() => {
    const key = 'saga-studio:create-settings:v6';
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    localStorage.setItem(key, JSON.stringify({ ...saved, mode: 'Image' }));
  });
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  const mobileWorkflowNav = page.locator('.sidebar.open');
  await mobileWorkflowNav.getByRole('button', { name: 'Workflows', exact: true }).click();
  await expectDestination(page, 'Workflows', 'Production workflows');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await page.getByRole('heading', { name: 'Create motion', exact: true }).waitFor({ state: 'visible', timeout: 5000 });
  if (!await page.locator('.saga-composer.is-video').count()) throw new Error('Mobile workflow launch did not activate Video composer state');
  if (await page.getByRole('button', { name: 'Video', exact: true }).getAttribute('aria-pressed') !== 'true') throw new Error('Mobile Video launch did not activate the Video toggle');
  diagnostics.continuation.push({ action: 'mobile-workflow-to-video', url: page.url(), conflictingStoredMode: 'Image', visibleMode: 'Video' });
  await page.screenshot({ path: path.join(outputDir, 'navigation-workflow-video-mobile.png'), fullPage: true, animations: 'disabled' });

  await context.close();
}

const browser = await chromium.launch({ headless: true });
try {
  await runDesktop(browser);
  await runMobile(browser);
  if (diagnostics.pageErrors.length) throw new Error(`Navigation page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'navigation-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
