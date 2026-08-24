import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });

const diagnostics = { baseUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [] };

async function waitForStudio(page, label) {
  page.on('pageerror', (error) => diagnostics.pageErrors.push({ label, text: error?.stack || error?.message || String(error) }));
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await page.locator('.saga-composer.is-video').waitFor({ state: 'visible', timeout: 5_000 });
}

async function pseudoContent(locator, pseudo) {
  return locator.evaluate((element, target) => getComputedStyle(element, target).content.replace(/^['"]|['"]$/g, ''), pseudo);
}

async function expectFocusRing(locator, label) {
  const result = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      focusVisible: element.matches(':focus-visible'),
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
    };
  });
  if (!result.focusVisible || result.outlineStyle === 'none' || Number.parseFloat(result.outlineWidth) < 2) {
    throw new Error(`${label} focus indicator is not strong enough: ${JSON.stringify(result)}`);
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  await waitForStudio(desktop, 'desktop');
  const audio = desktop.locator('.saga-audio-toggle');
  await audio.waitFor({ state: 'visible' });

  if (await audio.getAttribute('aria-pressed') !== 'true') throw new Error('Audio should default to aria-pressed=true');
  if (await audio.getAttribute('aria-label') !== 'Disable audio') throw new Error('Audio On accessible action label is wrong');
  if (await audio.getAttribute('title') !== 'Audio enabled') throw new Error('Audio On native tooltip copy is wrong');
  if (await pseudoContent(audio, '::after') !== 'Audio On') throw new Error('Desktop Audio On text is not visible');
  const desktopBox = await audio.boundingBox();
  if (!desktopBox || desktopBox.width < 80 || desktopBox.height < 32) throw new Error(`Desktop Audio control is not a clear pill: ${JSON.stringify(desktopBox)}`);

  await audio.focus();
  await expectFocusRing(audio, 'Audio control');
  if (await pseudoContent(audio, '::before') !== 'Audio on · Generate with sound') throw new Error('Focused Audio tooltip does not explain the On state');
  const tooltipOpacity = Number(await audio.evaluate((element) => getComputedStyle(element, '::before').opacity));
  if (tooltipOpacity < 0.9) throw new Error(`Audio tooltip should be visible on focus, opacity=${tooltipOpacity}`);
  await desktop.screenshot({ path: path.join(outputDir, '05i-video-audio-on.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05i-video-audio-on.png');

  await desktop.keyboard.press('Space');
  if (await audio.getAttribute('aria-pressed') !== 'false') throw new Error('Space did not toggle Audio Off');
  if (await audio.getAttribute('aria-label') !== 'Enable audio') throw new Error('Audio Off accessible action label is wrong');
  if (await audio.getAttribute('title') !== 'Audio disabled') throw new Error('Audio Off native tooltip copy is wrong');
  if (await pseudoContent(audio, '::after') !== 'Audio Off') throw new Error('Desktop Audio Off text is not visible');
  if (await pseudoContent(audio, '::before') !== 'Audio off · Generate without sound') throw new Error('Audio Off tooltip did not update with explanatory copy');
  await desktop.screenshot({ path: path.join(outputDir, '05j-video-audio-off.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05j-video-audio-off.png');

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  await waitForStudio(mobile, 'mobile');
  const mobileAudio = mobile.locator('.saga-audio-toggle');
  await mobileAudio.waitFor({ state: 'visible' });
  if (await pseudoContent(mobileAudio, '::after') !== 'On') throw new Error('Mobile Audio On state is not compact and explicit');
  const mobileBox = await mobileAudio.boundingBox();
  const toolbarBox = await mobile.locator('.saga-toolbar').boundingBox();
  if (!mobileBox || !toolbarBox) throw new Error('Could not measure mobile Audio control');
  if (mobileBox.width < 50 || mobileBox.width > 72 || mobileBox.height < 32) throw new Error(`Mobile Audio pill is outside compact target geometry: ${JSON.stringify(mobileBox)}`);
  if (mobileBox.x < toolbarBox.x || mobileBox.x + mobileBox.width > toolbarBox.x + toolbarBox.width + 1) throw new Error('Mobile Audio control overflows the toolbar');
  await mobileAudio.click();
  if (await mobileAudio.getAttribute('aria-pressed') !== 'false' || await pseudoContent(mobileAudio, '::after') !== 'Off') {
    throw new Error('Mobile Audio Off state is not explicit after toggle');
  }
  await mobile.screenshot({ path: path.join(outputDir, '09b-mobile-video-audio-off.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('09b-mobile-video-audio-off.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'audio-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await browser.close();
}
