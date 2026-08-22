import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = {
  baseUrl,
  generatedAt: new Date().toISOString(),
  screenshots: [],
  consoleErrors: [],
  pageErrors: [],
};

const referencePng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

function recordDiagnostics(page, label) {
  page.on('console', (message) => {
    if (message.type() === 'error') diagnostics.consoleErrors.push({ label, text: message.text() });
  });
  page.on('pageerror', (error) => {
    diagnostics.pageErrors.push({ label, text: error?.stack || error?.message || String(error) });
  });
}

async function waitForStudio(page) {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.composer-panel-v4').waitFor({ state: 'visible', timeout: 20_000 });
  await page.waitForTimeout(500);
}

async function shot(page, filename) {
  const filePath = path.join(outputDir, filename);
  await page.screenshot({ path: filePath, fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push(filename);
}

async function assertHidden(locator, label) {
  await locator.waitFor({ state: 'hidden', timeout: 3_000 }).catch(() => {
    throw new Error(`${label} did not collapse`);
  });
}

async function assertCount(locator, expected, label) {
  const count = await locator.count();
  if (count !== expected) throw new Error(`${label}: expected ${expected}, got ${count}`);
}

const browser = await chromium.launch({ headless: true });

try {
  const desktop = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
  });
  recordDiagnostics(desktop, 'desktop');
  await waitForStudio(desktop);

  await assertCount(desktop.locator('.grok-mic-button'), 0, 'Mic control');
  await assertCount(desktop.getByRole('button', { name: 'Speed', exact: true }), 0, 'Speed shortcut');
  await assertCount(desktop.getByRole('button', { name: 'Quality', exact: true }), 0, 'Quality shortcut');
  await shot(desktop, '01-create-image-clean.png');

  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });
  await settingsButton.click();
  const settings = desktop.locator('.composer-settings-popover');
  await settings.waitFor({ state: 'visible' });
  await settings.getByText('Seed', { exact: true }).waitFor({ state: 'visible' });
  await settings.getByText('Steps', { exact: true }).waitFor({ state: 'visible' });
  await settings.getByText('CFG', { exact: true }).waitFor({ state: 'visible' });
  await assertCount(settings.getByText('Aspect Ratio', { exact: true }), 0, 'Redundant aspect setting');
  await assertCount(settings.getByText('Resolution', { exact: true }), 0, 'Redundant resolution setting');
  await shot(desktop, '02-create-advanced-settings.png');
  await settingsButton.click();
  await assertHidden(settings, 'Advanced settings');

  const aspectButton = desktop.locator('.grok-aspect-button');
  await aspectButton.focus();
  await aspectButton.press('ArrowDown');
  const aspectMenu = desktop.locator('.grok-aspect-popover');
  await aspectMenu.waitFor({ state: 'visible' });
  await aspectMenu.locator('[role="menuitemradio"]').first().press('ArrowDown');
  await shot(desktop, '03-create-aspect-keyboard.png');
  await desktop.mouse.click(1320, 900);
  await assertHidden(aspectMenu, 'Aspect picker');

  const resolutionButton = desktop.locator('.grok-resolution-button');
  await resolutionButton.focus();
  await resolutionButton.press('Enter');
  const resolutionMenu = desktop.locator('.grok-resolution-popover');
  await resolutionMenu.waitFor({ state: 'visible' });
  await resolutionMenu.locator('[role="menuitemradio"]').first().press('ArrowDown');
  await shot(desktop, '04-create-resolution-keyboard.png');
  await desktop.mouse.click(1320, 900);
  await assertHidden(resolutionMenu, 'Resolution picker');

  await desktop.getByRole('button', { name: 'Edit', exact: true }).click();
  await desktop.locator('.grok-auto-choice').waitFor({ state: 'visible' });
  await assertCount(desktop.locator('.add-reference-tile'), 0, 'Redundant Add references tile');
  await shot(desktop, '05-create-edit-empty.png');

  const uploadButton = desktop.getByRole('button', { name: 'Upload reference images', exact: true });
  const chooserPromise = desktop.waitForEvent('filechooser');
  await uploadButton.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference.png', mimeType: 'image/png', buffer: referencePng });
  await desktop.locator('.reference-tile').waitFor({ state: 'visible', timeout: 5_000 });
  await assertCount(desktop.locator('.grok-plus-popover'), 0, 'Plus popover');
  await assertCount(desktop.locator('.add-reference-tile'), 0, 'Add references tile after upload');
  await shot(desktop, '06-create-edit-reference-uploaded.png');

  await desktop.locator('.grok-resolution-button').click();
  const editResolutionMenu = desktop.locator('.grok-resolution-popover');
  await editResolutionMenu.waitFor({ state: 'visible' });
  await shot(desktop, '07-create-edit-auto-resolution.png');
  await desktop.mouse.click(1320, 900);
  await assertHidden(editResolutionMenu, 'Edit resolution picker');

  const mobile = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
  });
  recordDiagnostics(mobile, 'mobile');
  await waitForStudio(mobile);
  await shot(mobile, '08-create-mobile.png');

  if (diagnostics.pageErrors.length) {
    throw new Error(`Page errors detected: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
  }
} finally {
  await writeFile(path.join(outputDir, 'diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
