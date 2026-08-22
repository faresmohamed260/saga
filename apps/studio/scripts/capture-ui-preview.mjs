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
  await page.waitForTimeout(700);
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

const browser = await chromium.launch({ headless: true });

try {
  const desktop = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
  });
  recordDiagnostics(desktop, 'desktop');
  await waitForStudio(desktop);
  await shot(desktop, '01-create-image-default.png');

  const plusButton = desktop.locator('button[title="Add or adjust"]');
  await plusButton.click();
  const plusMenu = desktop.locator('.grok-plus-popover');
  await plusMenu.waitFor({ state: 'visible' });
  await shot(desktop, '02-create-plus-menu.png');
  await desktop.mouse.click(1320, 900);
  await assertHidden(plusMenu, 'Plus menu');

  const aspectButton = desktop.locator('.grok-aspect-button');
  await aspectButton.focus();
  await aspectButton.press('ArrowDown');
  const aspectMenu = desktop.locator('.grok-aspect-popover');
  await aspectMenu.waitFor({ state: 'visible' });
  await aspectMenu.locator('[role="menuitemradio"]').first().press('ArrowDown');
  await shot(desktop, '03-create-aspect-keyboard.png');
  await desktop.keyboard.press('Escape');
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
  await shot(desktop, '05-create-edit-auto.png');

  await desktop.locator('.grok-aspect-button').click();
  await desktop.locator('.grok-aspect-popover').waitFor({ state: 'visible' });
  await shot(desktop, '06-create-edit-auto-aspect.png');
  await desktop.keyboard.press('Escape');

  await desktop.locator('.grok-resolution-button').click();
  await desktop.locator('.grok-resolution-popover').waitFor({ state: 'visible' });
  await shot(desktop, '07-create-edit-auto-resolution.png');
  await desktop.keyboard.press('Escape');

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
