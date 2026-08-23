from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:1000]}")
    path.write_text(text.replace(old, new, 1))


def mark_progress() -> None:
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '''**Iteration 6 — lazy/deferred Gallery video previews**\n\n- Status: `[x]` complete\n- Completed item: **06**\n- Next item: **07 — merge Auto + aspect ratio into one clear Aspect control**\n- Rule: do not start Item 07 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.\n''',
        '''**Iteration 7 — unified Video Aspect control**\n\n- Status: `[~]` in progress\n- Working item: **07**\n- Rule: replace the separate Auto + ratio controls with one explicit Aspect control that exposes automatic/manual mode, effective ratio, and reference provenance; preserve keyboard behavior and validate desktop/mobile GitHub visual previews before completion.\n''',
    )
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '- [ ] **07. Merge Auto + aspect ratio into one clear Aspect control.** Example states: `Aspect · Auto 16:9`, `Aspect · Auto 4:3 · From reference`, or manual ratio.\n',
        '- [~] **07. Merge Auto + aspect ratio into one clear Aspect control.** Example states: `Aspect · Auto 16:9`, `Aspect · Auto 4:3 · From reference`, or manual ratio. **Iteration 7 in progress.**\n',
    )
    print("Iteration 7 marked in progress")


def apply_product() -> None:
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, Sparkles, XCircle } from 'lucide-react';",
        "import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, XCircle } from 'lucide-react';",
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "function CompactPicker({ label, value, options, onChoose, leading }) {",
        "function CompactPicker({ label, value, displayValue = value, title, options, onChoose, leading }) {",
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''        aria-label={label}\n        aria-haspopup="menu"\n        aria-expanded={open}\n''',
        '''        aria-label={label}\n        aria-haspopup="menu"\n        aria-expanded={open}\n        title={title}\n''',
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''        {leading}<span>{value}</span><ChevronDown size={13} />\n''',
        '''        {leading}<span>{displayValue}</span><ChevronDown size={13} />\n''',
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''              <span><strong>{option.value}</strong>{option.label && <small>{option.label}</small>}</span>\n''',
        '''              <span><strong>{option.displayValue || option.value}</strong>{option.label && <small>{option.label}</small>}</span>\n''',
    )

    old_controls = '''export function VideoOutputControls({\n  autoAspect,\n  setAutoAspect,\n  manualAspect,\n  setManualAspect,\n  effectiveAspect,\n  referenceInfo,\n  frameRate,\n  setFrameRate,\n}) {\n  const aspectValue = autoAspect ? effectiveAspect : manualAspect;\n  const aspectIconRatio = aspectRatioValue(aspectValue, referenceInfo.ratio || 16 / 9);\n  return (\n    <div className="saga-video-extra-controls" aria-label="Video output controls">\n      <button\n        type="button"\n        className={`saga-auto-toggle ${autoAspect ? 'active' : ''}`}\n        aria-pressed={autoAspect}\n        title={referenceInfo.fromReference ? `Use reference aspect ratio (${referenceInfo.value})` : 'Use reference aspect ratio when an image is attached; otherwise 16:9'}\n        onClick={() => setAutoAspect((current) => !current)}\n      >\n        <Sparkles size={15} /><span>Auto</span>\n      </button>\n      <CompactPicker\n        label="Video aspect ratio"\n        value={aspectValue}\n        leading={<span className="saga-aspect-icon" style={{ aspectRatio: String(aspectIconRatio) }} />}\n        options={VIDEO_ASPECT_PRESETS}\n        onChoose={(value) => {\n          setManualAspect(value);\n          setAutoAspect(false);\n        }}\n      />\n      <CompactPicker\n        label="Video frame rate"\n        value={`${frameRate} fps`}\n        leading={<Gauge size={15} />}\n        options={VIDEO_FRAME_RATES.map((fps) => ({ value: `${fps} fps` }))}\n        onChoose={(value) => setFrameRate(Number.parseInt(value, 10) || 24)}\n      />\n    </div>\n  );\n}\n'''
    new_controls = '''export function VideoOutputControls({\n  autoAspect,\n  setAutoAspect,\n  manualAspect,\n  setManualAspect,\n  effectiveAspect,\n  referenceInfo,\n  frameRate,\n  setFrameRate,\n}) {\n  const aspectSelection = autoAspect ? '__auto__' : manualAspect;\n  const aspectValue = autoAspect ? effectiveAspect : manualAspect;\n  const aspectIconRatio = aspectRatioValue(aspectValue, referenceInfo.ratio || 16 / 9);\n  const aspectDisplay = autoAspect\n    ? `Aspect · Auto ${aspectValue}${referenceInfo.fromReference ? ' · Ref' : ''}`\n    : `Aspect · ${manualAspect}`;\n  const aspectTitle = autoAspect\n    ? referenceInfo.fromReference\n      ? `Aspect · Auto ${aspectValue} · From reference`\n      : `Aspect · Auto ${aspectValue} · Follows an attached reference when available`\n    : `Aspect · Manual ${manualAspect}`;\n  const aspectOptions = [\n    {\n      value: '__auto__',\n      displayValue: 'Auto',\n      label: referenceInfo.fromReference\n        ? `${referenceInfo.value} · From reference`\n        : '16:9 default · Follows reference when attached',\n    },\n    ...VIDEO_ASPECT_PRESETS,\n  ];\n\n  return (\n    <div className="saga-video-extra-controls" aria-label="Video output controls">\n      <CompactPicker\n        label="Video aspect"\n        value={aspectSelection}\n        displayValue={aspectDisplay}\n        title={aspectTitle}\n        leading={<span className="saga-aspect-icon" style={{ aspectRatio: String(aspectIconRatio) }} />}\n        options={aspectOptions}\n        onChoose={(value) => {\n          if (value === '__auto__') {\n            setAutoAspect(true);\n            return;\n          }\n          setManualAspect(value);\n          setAutoAspect(false);\n        }}\n      />\n      <CompactPicker\n        label="Video frame rate"\n        value={`${frameRate} fps`}\n        leading={<Gauge size={15} />}\n        options={VIDEO_FRAME_RATES.map((fps) => ({ value: `${fps} fps` }))}\n        onChoose={(value) => setFrameRate(Number.parseInt(value, 10) || 24)}\n      />\n    </div>\n  );\n}\n'''
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        old_controls,
        new_controls,
    )

    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  const auto = extras.locator('.saga-auto-toggle');\n  const pickers = extras.locator('.saga-control-pill');\n  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);\n  if (await auto.getAttribute('aria-pressed') !== 'true') throw new Error('Video Auto aspect should default on');\n  if (!(await aspect.innerText()).includes('16:9')) throw new Error(`Default video aspect is not 16:9: ${await aspect.innerText()}`);\n  if (!(await fps.innerText()).includes('24 fps')) throw new Error(`Default video frame rate is not 24 fps: ${await fps.innerText()}`);\n''',
        '''  if (await extras.locator('.saga-auto-toggle').count()) throw new Error('Video still exposes a separate Auto aspect button');\n  const pickers = extras.locator('.saga-control-pill');\n  if (await pickers.count() !== 2) throw new Error(`Video output controls should expose Aspect + FPS only, found ${await pickers.count()}`);\n  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);\n  if (!/Aspect\\s*·\\s*Auto\\s+16:9/.test(await aspect.innerText())) throw new Error(`Unified Aspect control does not show default Auto 16:9: ${await aspect.innerText()}`);\n  if (!/Follows an attached reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Default Aspect tooltip does not explain Auto behavior: ${await aspect.getAttribute('title')}`);\n  if (!(await fps.innerText()).includes('24 fps')) throw new Error(`Default video frame rate is not 24 fps: ${await fps.innerText()}`);\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        "  const aspectMenu = page.getByRole('menu', { name: 'Video aspect ratio' });\n",
        "  const aspectMenu = page.getByRole('menu', { name: 'Video aspect' });\n",
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  await page.keyboard.press('Home');\n  for (let step = 0; step < 4; step += 1) await page.keyboard.press('ArrowDown');\n  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');\n  await page.keyboard.press('Enter');\n  if (await auto.getAttribute('aria-pressed') !== 'false') throw new Error('Choosing a manual video aspect did not disable Auto');\n  if (!(await aspect.innerText()).includes('9:16')) throw new Error('Manual video aspect did not update to 9:16');\n''',
        '''  const autoOption = aspectMenu.getByRole('menuitemradio').first();\n  if (await autoOption.getAttribute('aria-checked') !== 'true') throw new Error('Unified Aspect menu does not mark Auto as selected by default');\n  await page.keyboard.press('Home');\n  for (let step = 0; step < 5; step += 1) await page.keyboard.press('ArrowDown');\n  if (!/9:16/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Video aspect keyboard navigation did not reach 9:16');\n  await page.keyboard.press('Enter');\n  if (/Auto/.test(await aspect.innerText())) throw new Error(`Choosing a manual aspect did not leave Auto mode: ${await aspect.innerText()}`);\n  if (!/Aspect\\s*·\\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual video aspect did not update to 9:16: ${await aspect.innerText()}`);\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  await auto.click();\n  if (await auto.getAttribute('aria-pressed') !== 'true') throw new Error('Video Auto aspect did not re-enable');\n  if (!(await aspect.innerText()).includes('4:3')) throw new Error(`Auto aspect did not inherit the 800x600 reference ratio: ${await aspect.innerText()}`);\n''',
        '''  await aspect.focus();\n  await page.keyboard.press('Enter');\n  await aspectMenu.waitFor({ state: 'visible' });\n  await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1500 });\n  await page.keyboard.press('Home');\n  if (!/^Auto/.test(await page.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the Auto aspect option');\n  await page.keyboard.press('Enter');\n  if (!/Aspect\\s*·\\s*Auto\\s+4:3\\s*·\\s*Ref/.test(await aspect.innerText())) throw new Error(`Auto aspect did not inherit the 800x600 reference ratio: ${await aspect.innerText()}`);\n  if (!/From reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Reference provenance is not exposed by the unified Aspect control: ${await aspect.getAttribute('title')}`);\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  if (!(await aspect.innerText()).includes('16:9')) throw new Error('Auto aspect did not fall back to 16:9 after removing the reference');\n\n  const prompt = page.locator('.saga-prompt-shell textarea');\n''',
        '''  if (!/Aspect\\s*·\\s*Auto\\s+16:9/.test(await aspect.innerText())) throw new Error(`Auto aspect did not fall back to 16:9 after removing the reference: ${await aspect.innerText()}`);\n\n  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark', hasTouch: true, isMobile: true });\n  mobile.on('pageerror', (error) => diagnostics.pageErrors.push(error?.stack || error?.message || String(error)));\n  await mobile.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });\n  await mobile.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });\n  await mobile.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();\n  const mobileExtras = mobile.locator('.saga-video-extra-controls');\n  await mobileExtras.waitFor({ state: 'visible', timeout: 3000 });\n  if (await mobileExtras.locator('.saga-auto-toggle').count()) throw new Error('Mobile Video still exposes a separate Auto aspect button');\n  const mobileAspect = mobileExtras.locator('.saga-control-pill').first();\n  if (!/Aspect\\s*·\\s*Auto\\s+16:9/.test(await mobileAspect.innerText())) throw new Error(`Mobile unified Aspect state is unclear: ${await mobileAspect.innerText()}`);\n  const mobileAspectBox = await mobileAspect.boundingBox();\n  if (!mobileAspectBox || mobileAspectBox.x < 0 || mobileAspectBox.x + mobileAspectBox.width > 390) throw new Error(`Mobile Aspect control is clipped: ${JSON.stringify(mobileAspectBox)}`);\n  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05g-video-output-controls-mobile.png');\n  await mobile.close();\n\n  const prompt = page.locator('.saga-prompt-shell textarea');\n''',
    )

    print("Iteration 7 product patch applied")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["progress", "product"])
    args = parser.parse_args()
    if args.mode == "progress":
        mark_progress()
    else:
        apply_product()


if __name__ == "__main__":
    main()
