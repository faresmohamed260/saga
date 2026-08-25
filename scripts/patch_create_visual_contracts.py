from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_between(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f'missing start marker: {label}')
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f'missing end marker: {label}')
    return text[:start] + replacement + text[end:]

# Update the broad Create visual contract without weakening unrelated picker/edit/tools coverage.
path = ROOT / 'apps/studio/scripts/capture-ui-preview.mjs'
text = path.read_text(encoding='utf-8')

needle = "  recordDiagnostics(desktop, 'desktop');\n  await waitForStudio(desktop);\n"
replacement = """  recordDiagnostics(desktop, 'desktop');
  await desktop.route('**/api/favorites', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const dataUrl = `data:image/png;base64,${referencePng.toString('base64')}`;
    const shapes = [[1080, 1440], [1440, 1080], [1080, 1080], [2048, 1152]];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: shapes.map(([width, height], index) => ({
          id: `00000000-0000-4000-8000-00000000000${index + 1}`,
          status: 'completed',
          kind: 'image',
          mode: 'edit',
          model: 'FLUX.2 Klein 9B',
          prompt: `Favorite generation ${index + 1}`,
          media_url: dataUrl,
          thumbnail_url: dataUrl,
          mime_type: 'image/png',
          resolution: '1080 px',
          width,
          height,
          seed: 42 + index,
          workflow_id: 'flux2-klein-image-edit',
          metadata: { execution: { steps: 4, cfg: 1.0 } },
          is_favorite: true,
          created_at: new Date(Date.UTC(2026, 7, 25, 3, index)).toISOString(),
        })),
      }),
    });
  });
  await waitForStudio(desktop);
  await desktop.locator('.saga-output-slot').first().waitFor({ state: 'visible', timeout: 3000 });
"""
if text.count(needle) != 1:
    raise RuntimeError(f'favorites route marker count={text.count(needle)}')
text = text.replace(needle, replacement, 1)

text = replace_between(
    text,
    '  // Advanced settings: custom dropdowns, continuous sampling values, viewport-safe panel.\n',
    '  // Video mode and all requested controls.\n',
    """  // Advanced settings in original Image mode must not expose controls with no live workflow.
  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });
  await settingsButton.click();
  const advanced = desktop.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');
  const panelBox = await advanced.boundingBox();
  const viewport = desktop.viewportSize();
  if (!panelBox || !viewport || panelBox.x < 8 || panelBox.y < 8 || panelBox.x + panelBox.width > viewport.width - 8 || panelBox.y + panelBox.height > viewport.height - 8) throw new Error(`Advanced panel out of viewport: ${JSON.stringify(panelBox)}`);
  await advanced.getByText('No production image workflow connected', { exact: true }).waitFor({ state: 'visible' });
  if (await advanced.locator('input[aria-label="Steps value"]').count()) throw new Error('Disconnected Image mode still exposes Steps');
  if (await advanced.locator('input[aria-label="CFG value"]').count()) throw new Error('Disconnected Image mode still exposes CFG');
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await settingsButton.click();
  await expectHidden(advanced, 'Advanced settings');

""",
    'image advanced block',
)

text = replace_between(
    text,
    '  // Switch back to Image and verify image + advanced values also persisted.\n',
    '  // Direct + upload auto-enters Edit, reference click inserts inline at the caret, Auto is toggleable.\n',
    """  // Switch back to Image and verify image canvas preferences persist while inert sampling stays hidden.
  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' }).click();
  await expectText(desktop.locator('.saga-resolution-trigger'), '2048 px', 'Persisted image resolution');
  const imageResolutionTitle = await desktop.locator('.saga-resolution-trigger').getAttribute('title') || '';
  if (!/2048×1152 at 16:9/.test(imageResolutionTitle)) throw new Error(`Image resolution trigger lacks exact canvas context: ${imageResolutionTitle}`);
  await expectText(desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') }), '16:9', 'Persisted aspect');
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('No production image workflow connected', { exact: true }).waitFor({ state: 'visible' });
  await settingsButton.click();

""",
    'advanced persistence block',
)

needle = "  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not toggle back on');\n  await shot(desktop, '06-edit-inline-reference-and-auto.png');\n"
replacement = """  if (await autoToggle.getAttribute('aria-pressed') !== 'true') throw new Error('Edit Auto did not toggle back on');

  // FLUX Advanced defaults are real production values and Reset restores them.
  await settingsButton.click();
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  const fluxSteps = advanced.locator('input[aria-label="Steps value"]');
  const fluxCfg = advanced.locator('input[aria-label="CFG value"]');
  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error(`FLUX preset is not 4 steps / CFG 1.0: ${await fluxSteps.inputValue()} / ${await fluxCfg.inputValue()}`);
  await fluxSteps.fill('7');
  await fluxCfg.fill('1.8');
  await advanced.getByRole('button', { name: 'Reset to FLUX defaults', exact: true }).click();
  if (await fluxSteps.inputValue() !== '4' || await fluxCfg.inputValue() !== '1') throw new Error('FLUX Reset did not restore 4 / 1.0');
  await settingsButton.click();
  await shot(desktop, '06-edit-inline-reference-and-auto.png');
"""
if text.count(needle) != 1:
    raise RuntimeError('FLUX advanced insertion marker missing')
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding='utf-8')

# Replace the old inline-Aspect/FPS video preview with an Advanced-panel contract.
path = ROOT / 'apps/studio/scripts/capture-video-output-preview.mjs'
path.write_text(r'''import { chromium } from 'playwright';
import sharp from 'sharp';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.UI_PREVIEW_URL || 'http://127.0.0.1:4173/#/create';
const createUrl = /#\//.test(baseUrl) ? baseUrl.replace(/#\/.*$/, '#/create') : `${baseUrl.replace(/\/$/, '')}/#/create`;
const outputDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
await mkdir(outputDir, { recursive: true });
const diagnostics = { createUrl, generatedAt: new Date().toISOString(), screenshots: [], pageErrors: [], submitted: null };
const referencePng = await sharp({ create: { width: 800, height: 600, channels: 4, background: { r: 35, g: 38, b: 56, alpha: 1 } } }).png().toBuffer();

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'dark' });
try {
  const page = await context.newPage();
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));
  await context.route('**/api/favorites', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }));
  await context.route('**/api/generate', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    diagnostics.submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        job: { id: '77777777-7777-4777-8777-777777777777' },
        status: 'running', workflow: 'ltx25-redgraft-video',
        worker: { workerId: 'ltx-standby-01', ecosystem: 'ltx25-redgraft', displayName: 'REDGraft LTX 2.5 · Standby', state: 'waking', failedWorkers: [] },
      }),
    });
  });
  await context.route('**/api/generate/result?**', async (route) => route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'running' }) }));

  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await page.locator('.saga-composer.is-video').waitFor({ state: 'visible' });

  if (await page.locator('.saga-video-extra-controls').count()) throw new Error('Video Aspect/FPS still render in the prompt toolbar');
  if (await page.locator('.saga-toolbar-left [data-shared-aspect-picker="true"]').count()) throw new Error('Inline Video Aspect trigger still exists');
  if (await page.locator('.saga-toolbar-left .saga-fancy-select').count()) throw new Error('Inline Video FPS picker still exists');

  const settings = page.getByRole('button', { name: 'Advanced settings', exact: true });
  await settings.click();
  const advanced = page.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  await advanced.getByText('REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', { exact: true }).waitFor({ state: 'visible' });
  const fixedSteps = advanced.locator('[data-ltx-fixed-steps="11"]');
  if (!/11\s+8 \+ 3/.test((await fixedSteps.innerText()).replace(/\s+/g, ' '))) throw new Error(`LTX fixed recipe is unclear: ${await fixedSteps.innerText()}`);
  const cfg = advanced.locator('input[aria-label="CFG value"]');
  if (await cfg.inputValue() !== '1') throw new Error(`LTX CFG default is not 1.0: ${await cfg.inputValue()}`);
  if (await advanced.locator('input[aria-label="Steps value"]').count()) throw new Error('LTX exposes an editable Steps control despite its fixed custom-sigma recipe');

  const aspect = advanced.getByRole('button', { name: 'Video aspect', exact: true });
  const fps = advanced.locator('.saga-fancy-select').filter({ has: advanced.getByRole('button', { name: 'Video frame rate', exact: true }) });
  const fpsTrigger = fps.locator(':scope > button');
  if (!/Aspect\s*·\s*Auto\s+16:9/.test(await aspect.innerText())) throw new Error(`LTX Auto aspect default is wrong: ${await aspect.innerText()}`);
  if (!(await fpsTrigger.innerText()).includes('24 fps')) throw new Error(`LTX FPS default is not 24: ${await fpsTrigger.innerText()}`);
  await page.screenshot({ path: path.join(outputDir, '05b-video-output-controls.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05b-video-output-controls.png');

  await aspect.focus();
  await page.keyboard.press('ArrowDown');
  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });
  await aspectMenu.waitFor({ state: 'visible' });
  await page.keyboard.press('Home');
  for (let index = 0; index < 5; index += 1) await page.keyboard.press('ArrowDown');
  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');
  await page.keyboard.press('Enter');
  if (!/Aspect\s*·\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual Video aspect did not update: ${await aspect.innerText()}`);
  const resolution = page.locator('.saga-video-resolution-trigger');
  if (!/1080×1920 at 9:16/.test(await resolution.getAttribute('title') || '')) throw new Error(`Video resolution did not follow moved Aspect control: ${await resolution.getAttribute('title')}`);

  await fpsTrigger.focus();
  await page.keyboard.press('Space');
  const fpsListbox = page.getByRole('listbox', { name: 'Video frame rate' });
  await fpsListbox.waitFor({ state: 'visible' });
  await page.keyboard.press('End');
  const fps30 = fpsListbox.getByRole('option', { name: '30 fps', exact: true });
  if (!(await fps30.evaluate((element) => element === document.activeElement))) throw new Error('Frame-rate keyboard navigation did not reach 30 fps');
  await page.screenshot({ path: path.join(outputDir, '05f-video-picker-keyboard-focus.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05f-video-picker-keyboard-focus.png');
  await page.keyboard.press('Enter');
  if (!(await fpsTrigger.innerText()).includes('30 fps')) throw new Error('Frame-rate selection did not update to 30 fps');

  // Auto aspect remains reference-aware even though the control moved into Advanced.
  await settings.click();
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload reference images', exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: 'reference-4x3.png', mimeType: 'image/png', buffer: referencePng });
  await page.locator('.saga-reference-chip').waitFor({ state: 'visible', timeout: 5000 });
  await settings.click();
  await advanced.waitFor({ state: 'visible' });
  const aspectWithReference = advanced.getByRole('button', { name: 'Video aspect', exact: true });
  await aspectWithReference.click();
  const autoOption = page.getByRole('menu', { name: 'Video aspect' }).getByRole('menuitemradio').first();
  await autoOption.click();
  if (!/Auto\s+4:3\s*·\s*From reference/.test(await aspectWithReference.innerText())) throw new Error(`Auto aspect did not follow 4:3 reference: ${await aspectWithReference.innerText()}`);

  // CFG is editable and reaches the actual generation request; fixed steps remain 11.
  await cfg.fill('1.4');
  await settings.click();
  const prompt = page.locator('.saga-prompt-shell textarea');
  await prompt.fill('A slow cinematic camera move through a sunlit coastal landscape');
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await page.waitForTimeout(450);
  if (!diagnostics.submitted) throw new Error('Video generation request was not submitted');
  if (Number(diagnostics.submitted.steps) !== 11) throw new Error(`Video request did not send fixed 11 steps: ${JSON.stringify(diagnostics.submitted)}`);
  if (Number(diagnostics.submitted.cfg) !== 1.4) throw new Error(`Video request did not send edited CFG: ${JSON.stringify(diagnostics.submitted)}`);
  if (Number(diagnostics.submitted.frameRate) !== 30) throw new Error(`Video request did not send selected 30 fps: ${JSON.stringify(diagnostics.submitted)}`);
  if (diagnostics.submitted.aspectRatio !== '4:3') throw new Error(`Video request did not send Auto reference aspect: ${JSON.stringify(diagnostics.submitted)}`);
  if (diagnostics.submitted.workflowId !== 'ltx25-redgraft-video') throw new Error(`Video request did not use the production LTX workflow: ${JSON.stringify(diagnostics.submitted)}`);

  // Mobile: Aspect/FPS stay out of the composer and remain accessible in Advanced.
  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await mobile.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });
  await mobile.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  if (await mobile.locator('.saga-toolbar-left [data-shared-aspect-picker="true"]').count()) throw new Error('Mobile Video still shows inline Aspect');
  await mobile.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const mobileAdvanced = mobile.locator('.saga-advanced-panel');
  await mobileAdvanced.waitFor({ state: 'visible' });
  const mobileBox = await mobileAdvanced.boundingBox();
  if (!mobileBox || mobileBox.x < 0 || mobileBox.y < 0 || mobileBox.x + mobileBox.width > 390 || mobileBox.y + mobileBox.height > 844) throw new Error(`Mobile Advanced leaves viewport: ${JSON.stringify(mobileBox)}`);
  await mobileAdvanced.getByRole('button', { name: 'Video aspect', exact: true }).waitFor({ state: 'visible' });
  await mobileAdvanced.getByRole('button', { name: 'Video frame rate', exact: true }).waitFor({ state: 'visible' });
  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('05g-video-output-controls-mobile.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.join(' | ')}`);
} finally {
  await writeFile(path.join(outputDir, 'video-output-diagnostics.json'), JSON.stringify(diagnostics, null, 2));
  await context.close();
  await browser.close();
}
''', encoding='utf-8')

# Audio contract now verifies a single circular control with no pseudo-button label.
path = ROOT / 'apps/studio/scripts/capture-audio-state-preview.mjs'
text = path.read_text(encoding='utf-8')
text = re.sub(r"\nasync function pseudoContent\(locator, pseudo\) \{.*?\n\}\n", "\n", text, count=1, flags=re.S)
text = text.replace("  if (await pseudoContent(audio, '::after') !== 'Audio On') throw new Error('Desktop Audio On text is not visible');\n", "  const afterContent = await audio.evaluate((element) => getComputedStyle(element, '::after').content);\n  if (afterContent && afterContent !== 'none' && afterContent !== 'normal') throw new Error(`Audio renders a duplicate pseudo-button label: ${afterContent}`);\n")
text = re.sub(r"  const desktopMargin = Number\.parseFloat\(await audio\.evaluate\(\(element\) => getComputedStyle\(element\)\.marginRight\)\);\n  if \(desktopMargin < 60\) throw new Error\(`Desktop Audio control does not reserve enough room for its explicit state badge: \$\{desktopMargin\}`\);\n", "  const desktopMargin = Number.parseFloat(await audio.evaluate((element) => getComputedStyle(element).marginRight));\n  if (desktopMargin > 4) throw new Error(`Desktop Audio control still reserves space for a removed duplicate badge: ${desktopMargin}`);\n", text)
text = text.replace("  if (await pseudoContent(audio, '::before') !== 'Audio on · Generate with sound') throw new Error('Focused Audio tooltip does not explain the On state');\n", "  const onTooltip = await audio.evaluate((element) => getComputedStyle(element, '::before').content.replace(/^['\"]|['\"]$/g, ''));\n  if (onTooltip !== 'Audio on · Generate with sound') throw new Error('Focused Audio tooltip does not explain the On state');\n")
text = text.replace("  if (await pseudoContent(audio, '::after') !== 'Audio Off') throw new Error('Desktop Audio Off text is not visible');\n  if (await pseudoContent(audio, '::before') !== 'Audio off · Generate without sound') throw new Error('Audio Off tooltip did not update with explanatory copy');\n", "  const offTooltip = await audio.evaluate((element) => getComputedStyle(element, '::before').content.replace(/^['\"]|['\"]$/g, ''));\n  if (offTooltip !== 'Audio off · Generate without sound') throw new Error('Audio Off tooltip did not update with explanatory copy');\n")
text = text.replace("  if (await pseudoContent(mobileAudio, '::after') !== 'On') throw new Error('Mobile Audio On state is not compact and explicit');\n", "  const mobileAfter = await mobileAudio.evaluate((element) => getComputedStyle(element, '::after').content);\n  if (mobileAfter && mobileAfter !== 'none' && mobileAfter !== 'normal') throw new Error(`Mobile Audio renders a duplicate pseudo-label: ${mobileAfter}`);\n")
text = re.sub(r"  const mobileMargin = Number\.parseFloat\(await mobileAudio\.evaluate\(\(element\) => getComputedStyle\(element\)\.marginRight\)\);\n  if \(mobileMargin < 28 \|\| mobileMargin > 40\) throw new Error\(`Mobile Audio state badge spacing is outside the intended compact range: \$\{mobileMargin\}`\);\n", "  const mobileMargin = Number.parseFloat(await mobileAudio.evaluate((element) => getComputedStyle(element).marginRight));\n  if (mobileMargin > 4) throw new Error(`Mobile Audio still reserves room for a removed duplicate badge: ${mobileMargin}`);\n", text)
text = text.replace("  if (await mobileAudio.getAttribute('aria-pressed') !== 'false' || await pseudoContent(mobileAudio, '::after') !== 'Off') {\n    throw new Error('Mobile Audio Off state is not explicit after toggle');\n  }\n", "  if (await mobileAudio.getAttribute('aria-pressed') !== 'false') throw new Error('Mobile Audio did not toggle off');\n")
path.write_text(text, encoding='utf-8')

print('Create visual contracts updated for production-aware Advanced settings.')
