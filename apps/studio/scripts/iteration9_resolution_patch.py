from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def write(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:1000]}")
    path.write_text(text.replace(old, new, 1))


RESOLUTION_PRESETS = r'''export const IMAGE_RESOLUTIONS = [
  { value: 480, label: '480 px' },
  { value: 720, label: '720 px' },
  { value: 1080, label: '1080 px' },
  { value: 2048, label: '2048 px' },
  { value: 3840, label: '3840 px' },
];

// These are the resolutions currently accepted by the REDGraft LTX 2.5
// production workflow. 4K intentionally stays out of this list until the
// runtime capability is enabled.
export const VIDEO_RESOLUTIONS = [
  { value: '480p', label: '480p', shortEdge: 480 },
  { value: '720p', label: '720p', shortEdge: 720 },
  { value: '1080p', label: '1080p', shortEdge: 1080 },
  { value: '2K', label: '2K', shortEdge: 1152 },
];

function ratioValue(aspect, fallback = 1) {
  const match = String(aspect || '').trim().match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) return fallback;
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (!(width > 0) || !(height > 0)) return fallback;
  const ratio = width / height;
  return Number.isFinite(ratio) ? ratio : fallback;
}

function round64(value) {
  return Math.max(64, Math.round(Number(value) / 64) * 64);
}

function even(value) {
  return Math.max(2, Math.round(Number(value) / 2) * 2);
}

export function dimensionsForPreset(aspect, longEdge) {
  const ratio = ratioValue(aspect, 1);
  if (ratio >= 1) return { width: round64(longEdge), height: round64(Number(longEdge) / ratio) };
  return { width: round64(Number(longEdge) * ratio), height: round64(longEdge) };
}

export function videoDeliveryDimensions(resolution, aspect = '16:9') {
  const preset = VIDEO_RESOLUTIONS.find((item) => item.value === resolution) || VIDEO_RESOLUTIONS[2];
  const ratio = ratioValue(aspect, 16 / 9);
  if (ratio >= 1) {
    const height = preset.shortEdge;
    return { width: even(height * ratio), height };
  }
  const width = preset.shortEdge;
  return { width, height: even(width / ratio) };
}

export function formatDimensions(dimensions) {
  if (!dimensions) return '';
  return `${dimensions.width}×${dimensions.height}`;
}
'''


RESOLUTION_CONTRACT = r'''import { readFile } from 'node:fs/promises';
import {
  IMAGE_RESOLUTIONS,
  VIDEO_RESOLUTIONS,
  dimensionsForPreset,
  formatDimensions,
  videoDeliveryDimensions,
} from '../src/features/create/ResolutionPresets.js';

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function expectDimensions(actual, width, height, label) {
  expect(actual.width === width && actual.height === height, `${label}: expected ${width}×${height}, got ${formatDimensions(actual)}`);
}

expect(IMAGE_RESOLUTIONS.map((item) => item.label).join(',') === '480 px,720 px,1080 px,2048 px,3840 px', 'Image resolution labels are not explicit pixel terminology');
expect(VIDEO_RESOLUTIONS.map((item) => item.value).join(',') === '480p,720p,1080p,2K', 'Video resolution capability list must match enabled production resolutions');
expect(!VIDEO_RESOLUTIONS.some((item) => item.value === '4K'), 'Video UI must not advertise disabled 4K generation');

expectDimensions(dimensionsForPreset('1:1', 1080), 1088, 1088, 'Image 1080 px at 1:1');
expectDimensions(dimensionsForPreset('16:9', 2048), 2048, 1152, 'Image 2048 px at 16:9');
expectDimensions(videoDeliveryDimensions('480p', '16:9'), 854, 480, '480p at 16:9');
expectDimensions(videoDeliveryDimensions('720p', '16:9'), 1280, 720, '720p at 16:9');
expectDimensions(videoDeliveryDimensions('1080p', '16:9'), 1920, 1080, '1080p at 16:9');
expectDimensions(videoDeliveryDimensions('1080p', '9:16'), 1080, 1920, '1080p at 9:16');
expectDimensions(videoDeliveryDimensions('1080p', '4:3'), 1440, 1080, '1080p at 4:3');
expectDimensions(videoDeliveryDimensions('2K', '16:9'), 2048, 1152, '2K at 16:9');

const runtimeSource = await readFile(new URL('../../../integrations/comfyui/ltx23_app.py', import.meta.url), 'utf8');
expect(runtimeSource.includes('ENABLED_RESOLUTIONS = {"480p", "720p", "1080p", "2K"}'), 'Runtime enabled-resolution contract changed');
expect(runtimeSource.includes('RESOLUTION_SHORT_EDGES = {"480p": 480, "720p": 720, "1080p": 1080, "2K": 1152, "4K": 2160}'), 'Runtime short-edge contract changed');
expect(runtimeSource.includes('delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)'), 'Runtime no longer finalizes against delivery dimensions');

const workflowSource = await readFile(new URL('../api/_workflows.js', import.meta.url), 'utf8');
expect(workflowSource.includes("resolutions: ['480p', '720p', '1080p', '2K']"), 'Studio workflow capability list changed');

const createSource = await readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8');
expect(!createSource.includes("label: 'Full HD'"), 'Create controls still use Full HD marketing terminology');
expect(createSource.includes('videoDeliveryDimensions(videoResolution, videoAspect)'), 'Video resolution trigger is not using delivery dimensions');

console.log(JSON.stringify({
  ready: true,
  videoResolutions: VIDEO_RESOLUTIONS.map((item) => item.value),
  examples: {
    landscape1080p: formatDimensions(videoDeliveryDimensions('1080p', '16:9')),
    portrait1080p: formatDimensions(videoDeliveryDimensions('1080p', '9:16')),
    reference4x3: formatDimensions(videoDeliveryDimensions('1080p', '4:3')),
  },
}, null, 2));
'''


def apply_create_controls() -> None:
    path = 'apps/studio/src/create-controls.jsx'
    replace_once(
        path,
        "import { AspectPicker, ASPECT_PRESETS } from './features/create/AspectPicker.jsx';\nimport './create-workspace-v2.css';\n\nexport const IMAGE_RESOLUTIONS = [\n  { value: 480, label: 'SD', detail: '480 px' },\n  { value: 720, label: 'HD', detail: '720 px' },\n  { value: 1080, label: 'Full HD', detail: '1080 px' },\n  { value: 2048, label: '2K', detail: '2048 px' },\n  { value: 3840, label: '4K', detail: '3840 px' },\n];\n\nconst VIDEO_RESOLUTIONS = [\n  { value: '480p', label: 'SD', detail: '480p', preview: '480', dimensions: '896×512' },\n  { value: '720p', label: 'HD', detail: '720p', preview: '720', dimensions: '1280×704' },\n  { value: '1080p', label: 'Full HD', detail: '1080p', preview: '1080', dimensions: '1920×1088' },\n  { value: '2K', label: '2K', detail: '2048 px', preview: '2048', dimensions: '2048×1152' },\n  { value: '4K', label: '4K', detail: '3840 px', preview: '3840', dimensions: '3840×2176' },\n];\n\nconst STORAGE_KEY = 'saga-studio:create-settings:v5';\n\nfunction round64(value) {\n  return Math.max(64, Math.round(value / 64) * 64);\n}\n\nexport function dimensionsForPreset(aspect, longEdge) {\n  const preset = ASPECT_PRESETS.find((item) => item.value === aspect) || ASPECT_PRESETS[0];\n  const ratio = preset.ratio;\n  if (ratio >= 1) return { width: round64(longEdge), height: round64(longEdge / ratio) };\n  return { width: round64(longEdge * ratio), height: round64(longEdge) };\n}\n",
        "import { AspectPicker, ASPECT_PRESETS } from './features/create/AspectPicker.jsx';\nimport {\n  IMAGE_RESOLUTIONS, VIDEO_RESOLUTIONS, dimensionsForPreset, formatDimensions, videoDeliveryDimensions,\n} from './features/create/ResolutionPresets.js';\nimport './create-workspace-v2.css';\n\nexport { IMAGE_RESOLUTIONS, dimensionsForPreset };\n\nconst STORAGE_KEY = 'saga-studio:create-settings:v5';\n",
    )

    replace_once(
        path,
        "        <strong>{editAuto ? 'Auto' : previewOption.label}</strong>\n        <small>{editAuto ? autoInfo?.detail : dimensions ? `${dimensions.width}×${dimensions.height}` : ''}</small>",
        "        <strong>{editAuto ? 'Auto' : previewOption.label}</strong>\n        <small>{editAuto ? autoInfo?.detail : dimensions ? `${formatDimensions(dimensions)} at ${aspect}` : ''}</small>",
    )
    replace_once(
        path,
        "        render={(option) => (\n          <>\n            <span className=\"saga-option-label\">{option.label}</span>\n            <span className=\"saga-option-detail\">{option.detail}</span>\n          </>\n        )}\n      />\n    </PickerShell>\n  );\n}\n\nfunction VideoResolutionPicker({ open, setOpen, anchorRef, value, setValue }) {\n  const selectedOption = VIDEO_RESOLUTIONS.find((item) => item.value === value) || VIDEO_RESOLUTIONS[2];\n  const [previewValue, setPreviewValue] = useState(selectedOption.value);\n  useEffect(() => setPreviewValue(selectedOption.value), [selectedOption.value, open]);\n  const previewOption = VIDEO_RESOLUTIONS.find((item) => item.value === previewValue) || selectedOption;\n\n  return (\n    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className=\"saga-video-resolution-picker saga-resolution-picker\" onClose={() => setOpen(false)}>\n      <div className=\"saga-picker-preview saga-resolution-preview\">\n        <div className=\"saga-resolution-cube\">{previewOption.preview}</div>\n        <strong>{previewOption.label}</strong>\n        <small>{previewOption.dimensions}</small>\n      </div>\n      <MorphList\n        focusWhen={open}\n        onPreview={(option) => setPreviewValue(option?.value ?? selectedOption.value)}\n        ariaLabel=\"Video resolution\"\n        options={VIDEO_RESOLUTIONS}\n        value={value}\n        onChoose={(option) => {\n          setValue(option.value);\n          setOpen(false);\n          anchorRef.current?.focus();\n        }}\n        render={(option) => (\n          <>\n            <span className=\"saga-option-label\">{option.label}</span>\n            <span className=\"saga-option-detail\">{option.detail}</span>\n          </>\n        )}\n      />\n    </PickerShell>\n  );\n}\n",
        "        render={(option) => {\n          const optionDimensions = dimensionsForPreset(aspect, Number(option.value));\n          return (\n            <>\n              <span className=\"saga-option-label\">{option.label}</span>\n              <span className=\"saga-option-detail\">{formatDimensions(optionDimensions)}</span>\n            </>\n          );\n        }}\n      />\n    </PickerShell>\n  );\n}\n\nfunction VideoResolutionPicker({ open, setOpen, anchorRef, value, setValue, aspect }) {\n  const selectedOption = VIDEO_RESOLUTIONS.find((item) => item.value === value) || VIDEO_RESOLUTIONS[2];\n  const [previewValue, setPreviewValue] = useState(selectedOption.value);\n  useEffect(() => setPreviewValue(selectedOption.value), [selectedOption.value, open]);\n  const previewOption = VIDEO_RESOLUTIONS.find((item) => item.value === previewValue) || selectedOption;\n  const previewDimensions = videoDeliveryDimensions(previewOption.value, aspect);\n\n  return (\n    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className=\"saga-video-resolution-picker saga-resolution-picker\" onClose={() => setOpen(false)}>\n      <div className=\"saga-picker-preview saga-resolution-preview\">\n        <div className=\"saga-resolution-cube\">{previewOption.label}</div>\n        <strong>{previewOption.label}</strong>\n        <small>{formatDimensions(previewDimensions)} at {aspect}</small>\n      </div>\n      <MorphList\n        focusWhen={open}\n        onPreview={(option) => setPreviewValue(option?.value ?? selectedOption.value)}\n        ariaLabel=\"Video resolution\"\n        options={VIDEO_RESOLUTIONS}\n        value={value}\n        onChoose={(option) => {\n          setValue(option.value);\n          setOpen(false);\n          anchorRef.current?.focus();\n        }}\n        render={(option) => {\n          const optionDimensions = videoDeliveryDimensions(option.value, aspect);\n          return (\n            <>\n              <span className=\"saga-option-label\">{option.label}</span>\n              <span className=\"saga-option-detail\">{formatDimensions(optionDimensions)}</span>\n            </>\n          );\n        }}\n      />\n    </PickerShell>\n  );\n}\n",
    )

    replace_once(
        path,
        "  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,\n}) {",
        "  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,\n  videoAspect = '16:9',\n}) {",
    )
    replace_once(
        path,
        "  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;\n  const imageDimensions = dimensionsForPreset(aspect, Number(imageResolution));\n  const heading =",
        "  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;\n  const imageDimensions = dimensionsForPreset(aspect, Number(imageResolution));\n  const videoDimensions = videoDeliveryDimensions(videoResolution, videoAspect);\n  const heading =",
    )
    replace_once(
        path,
        "                    aria-haspopup=\"menu\"\n                    aria-expanded={resolutionOpen}\n                    onKeyDown=",
        "                    aria-haspopup=\"menu\"\n                    aria-expanded={resolutionOpen}\n                    aria-label={isEdit && editAuto ? `Image resolution Auto, ${autoEditInfo?.detail || 'from reference'}` : `Image resolution ${imageOption.label}, ${formatDimensions(imageDimensions)} at ${aspect}`}\n                    title={isEdit && editAuto ? `Image resolution · Auto · ${autoEditInfo?.detail || 'from reference'}` : `Image resolution · ${imageOption.label} · ${formatDimensions(imageDimensions)} at ${aspect}`}\n                    onKeyDown=",
    )
    replace_once(
        path,
        "                    className={`saga-control-pill ${videoResolutionOpen ? 'active' : ''}`}\n                    aria-haspopup=\"menu\"\n                    aria-expanded={videoResolutionOpen}\n                    onKeyDown=",
        "                    className={`saga-control-pill saga-video-resolution-trigger ${videoResolutionOpen ? 'active' : ''}`}\n                    aria-haspopup=\"menu\"\n                    aria-expanded={videoResolutionOpen}\n                    aria-label={`Video resolution ${videoOption.label}, ${formatDimensions(videoDimensions)} at ${videoAspect}`}\n                    title={`Video resolution · ${videoOption.label} · ${formatDimensions(videoDimensions)} at ${videoAspect}`}\n                    onKeyDown=",
    )
    replace_once(
        path,
        "          value={videoResolution}\n          setValue={setVideoResolution}\n        />",
        "          value={videoResolution}\n          setValue={setVideoResolution}\n          aspect={videoAspect}\n        />",
    )


def apply_wrapper() -> None:
    replace_once(
        'apps/studio/src/features/create/CreateWorkspace.jsx',
        "      <LegacyCreateWorkspace {...props} onGenerate={handleGenerate} />",
        "      <LegacyCreateWorkspace {...props} videoAspect={effectiveAspect} onGenerate={handleGenerate} />",
    )


def apply_ui_tests() -> None:
    path = 'apps/studio/scripts/capture-ui-preview.mjs'
    replace_once(
        path,
        "  const expectedImageRows = [['SD', '480 px'], ['HD', '720 px'], ['Full HD', '1080 px'], ['2K', '2048 px'], ['4K', '3840 px']];",
        "  const expectedImageRows = [['480 px', '512×512'], ['720 px', '704×704'], ['1080 px', '1088×1088'], ['2048 px', '2048×2048'], ['3840 px', '3840×3840']];",
    )
    replace_once(path, "    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Image pixel detail mismatch at ${index}`);", "    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Image delivery detail mismatch at ${index}`);")
    replace_once(path, "  if (resolutionLabelBefore === resolutionLabelAfter || resolutionLabelAfter !== '2K') throw new Error(`Resolution label did not morph with preview: ${resolutionLabelBefore} -> ${resolutionLabelAfter}`);", "  if (resolutionLabelBefore === resolutionLabelAfter || resolutionLabelAfter !== '2048 px') throw new Error(`Resolution label did not morph with preview: ${resolutionLabelBefore} -> ${resolutionLabelAfter}`);")
    replace_once(path, "  await resolutionPicker.getByRole('menuitemradio', { name: /2K.*2048 px/i }).click();", "  await resolutionPicker.getByRole('menuitemradio', { name: /2048 px.*2048×2048/i }).click();")
    replace_once(
        path,
        "  await expectText(videoControls.nth(0), 'Full HD', 'Video resolution trigger label');\n  if ((await videoControls.nth(0).innerText()).includes('1080p')) throw new Error('Video resolution trigger still exposes the raw resolution value');\n  const videoResolutionTrigger = videoControls.nth(0);",
        "  const videoResolutionTrigger = desktop.locator('.saga-video-resolution-trigger');\n  await expectText(videoResolutionTrigger, '1080p', 'Video resolution trigger label');\n  if ((await videoResolutionTrigger.innerText()).includes('Full HD')) throw new Error('Video resolution trigger still uses Full HD terminology');\n  const videoResolutionTitle = await videoResolutionTrigger.getAttribute('title') || '';\n  if (!/1920×1080 at 16:9/.test(videoResolutionTitle)) throw new Error(`Video resolution trigger does not expose exact delivery context: ${videoResolutionTitle}`);",
    )
    replace_once(
        path,
        "  const expectedVideoRows = [['SD', '480p'], ['HD', '720p'], ['Full HD', '1080p'], ['2K', '2048 px'], ['4K', '3840 px']];",
        "  const expectedVideoRows = [['480p', '854×480'], ['720p', '1280×720'], ['1080p', '1920×1080'], ['2K', '2048×1152']];",
    )
    replace_once(path, "    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Video pixel detail mismatch at ${index}`);", "    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(`Video delivery detail mismatch at ${index}`);")
    replace_once(path, "  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048 px/i }).hover();", "  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048×1152/i }).hover();")
    replace_once(
        path,
        "  if (videoPreviewLabelBefore === videoPreviewLabelAfter || videoPreviewLabelAfter !== '2K') throw new Error(`Video resolution preview did not morph: ${videoPreviewLabelBefore} -> ${videoPreviewLabelAfter}`);\n  await shot(desktop, '04-video-resolution-picker.png');\n  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K.*3840 px/i }).click();",
        "  if (videoPreviewLabelBefore === videoPreviewLabelAfter || videoPreviewLabelAfter !== '2K') throw new Error(`Video resolution preview did not morph: ${videoPreviewLabelBefore} -> ${videoPreviewLabelAfter}`);\n  if ((await videoPreview.locator('small').innerText()).trim() !== '2048×1152 at 16:9') throw new Error(`Video preview does not expose delivery dimensions + aspect: ${await videoPreview.locator('small').innerText()}`);\n  if (await videoResolutionPicker.getByRole('menuitemradio', { name: /4K/i }).count()) throw new Error('Video picker advertises unsupported 4K output');\n  await shot(desktop, '04-video-resolution-picker.png');\n  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048×1152/i }).click();",
    )
    replace_once(path, "  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(0), '4K', 'Persisted video resolution');", "  await expectText(desktop.locator('.saga-video-resolution-trigger'), '2K', 'Persisted video resolution');")
    replace_once(path, "  await expectText(desktop.locator('.saga-resolution-trigger'), '2K', 'Persisted image resolution');\n  if ((await desktop.locator('.saga-resolution-trigger').innerText()).includes('2048')) throw new Error('Image resolution trigger still exposes the raw resolution value');", "  await expectText(desktop.locator('.saga-resolution-trigger'), '2048 px', 'Persisted image resolution');\n  const imageResolutionTitle = await desktop.locator('.saga-resolution-trigger').getAttribute('title') || '';\n  if (!/2048×1152 at 16:9/.test(imageResolutionTitle)) throw new Error(`Image resolution trigger lacks exact canvas context: ${imageResolutionTitle}`);")


def apply_video_tests() -> None:
    path = 'apps/studio/scripts/capture-video-output-preview.mjs'
    replace_once(
        path,
        "  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);",
        "  const aspect = pickers.nth(0);\n  const fps = pickers.nth(1);\n  const resolution = page.locator('.saga-video-resolution-trigger');\n  await resolution.waitFor({ state: 'visible' });\n  if ((await resolution.innerText()).trim() !== '1080p') throw new Error(`Video resolution trigger should use 1080p terminology: ${await resolution.innerText()}`);\n  if (!/1920×1080 at 16:9/.test(await resolution.getAttribute('title') || '')) throw new Error(`Default Video resolution context is not exact: ${await resolution.getAttribute('title')}`);",
    )
    replace_once(
        path,
        "  if (!/Aspect\\s*·\\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual video aspect did not update to 9:16: ${await aspect.innerText()}`);\n\n  await fps.focus();",
        "  if (!/Aspect\\s*·\\s*9:16/.test(await aspect.innerText())) throw new Error(`Manual video aspect did not update to 9:16: ${await aspect.innerText()}`);\n  if (!/1080×1920 at 9:16/.test(await resolution.getAttribute('title') || '')) throw new Error(`Portrait resolution context did not follow Aspect: ${await resolution.getAttribute('title')}`);\n  await resolution.click();\n  const resolutionMenu = page.getByRole('menu', { name: 'Video resolution' });\n  await resolutionMenu.waitFor({ state: 'visible' });\n  const resolutionSurface = page.locator('.saga-video-resolution-picker');\n  if ((await resolutionSurface.locator('.saga-picker-preview small').innerText()).trim() !== '1080×1920 at 9:16') throw new Error(`Portrait delivery preview is incorrect: ${await resolutionSurface.locator('.saga-picker-preview small').innerText()}`);\n  if (await resolutionMenu.getByRole('menuitemradio', { name: /4K/i }).count()) throw new Error('Video resolution menu exposes disabled 4K');\n  await page.screenshot({ path: path.join(outputDir, '05h-video-resolution-portrait.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05h-video-resolution-portrait.png');\n  await page.keyboard.press('Escape');\n\n  await fps.focus();",
    )
    replace_once(
        path,
        "  if (!/From reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Reference provenance is not exposed by the unified Aspect control: ${await aspect.getAttribute('title')}`);",
        "  if (!/From reference/.test(await aspect.getAttribute('title') || '')) throw new Error(`Reference provenance is not exposed by the unified Aspect control: ${await aspect.getAttribute('title')}`);\n  if (!/1440×1080 at 4:3/.test(await resolution.getAttribute('title') || '')) throw new Error(`Reference-derived resolution context is incorrect: ${await resolution.getAttribute('title')}`);",
    )
    replace_once(
        path,
        "  if (!/Aspect\\s*·\\s*Auto\\s+16:9/.test(await aspect.innerText())) throw new Error(`Auto aspect did not fall back to 16:9 after removing the reference: ${await aspect.innerText()}`);",
        "  if (!/Aspect\\s*·\\s*Auto\\s+16:9/.test(await aspect.innerText())) throw new Error(`Auto aspect did not fall back to 16:9 after removing the reference: ${await aspect.innerText()}`);\n  if (!/1920×1080 at 16:9/.test(await resolution.getAttribute('title') || '')) throw new Error(`Resolution context did not return to 16:9 after reference removal: ${await resolution.getAttribute('title')}`);",
    )
    replace_once(
        path,
        "  const mobileAspect = mobileExtras.locator('.saga-control-pill').first();",
        "  const mobileAspect = mobileExtras.locator('.saga-control-pill').first();\n  const mobileResolution = mobile.locator('.saga-video-resolution-trigger');\n  if ((await mobileResolution.innerText()).trim() !== '1080p') throw new Error(`Mobile Video resolution terminology is inconsistent: ${await mobileResolution.innerText()}`);\n  if (!/1920×1080 at 16:9/.test(await mobileResolution.getAttribute('title') || '')) throw new Error(`Mobile Video resolution context is incomplete: ${await mobileResolution.getAttribute('title')}`);",
    )


def apply_package() -> None:
    replace_once(
        'apps/studio/package.json',
        '    "build": "node scripts/check-workflow-contract.mjs && vite build",',
        '    "build": "node scripts/check-workflow-contract.mjs && node scripts/check-resolution-contract.mjs && vite build",',
    )


def validate_source() -> None:
    create = read('apps/studio/src/create-controls.jsx')
    wrapper = read('apps/studio/src/features/create/CreateWorkspace.jsx')
    helper = read('apps/studio/src/features/create/ResolutionPresets.js')
    ui_test = read('apps/studio/scripts/capture-ui-preview.mjs')
    video_test = read('apps/studio/scripts/capture-video-output-preview.mjs')
    checks = {
        'Full HD removed from Create controls': "label: 'Full HD'" not in create,
        'Video trigger is explicit': 'saga-video-resolution-trigger' in create and '<span>{videoOption.label}</span>' in create,
        'Video uses delivery dimensions': 'videoDeliveryDimensions(videoResolution, videoAspect)' in create,
        'Wrapper passes effective aspect': 'videoAspect={effectiveAspect}' in wrapper,
        '4K excluded from video presets': "value: '4K'" not in helper,
        'Portrait test added': '05h-video-resolution-portrait.png' in video_test,
        'UI test rejects video 4K': 'Video picker advertises unsupported 4K output' in ui_test,
    }
    failed = [label for label, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError('Iteration 9 source validation failed: ' + ', '.join(failed))
    print('Iteration 9 source validation passed')


def apply_product() -> None:
    helper_path = ROOT / 'apps/studio/src/features/create/ResolutionPresets.js'
    contract_path = ROOT / 'apps/studio/scripts/check-resolution-contract.mjs'
    if helper_path.exists() or contract_path.exists():
        raise RuntimeError('Iteration 9 helper/contract already exist unexpectedly')
    write('apps/studio/src/features/create/ResolutionPresets.js', RESOLUTION_PRESETS)
    write('apps/studio/scripts/check-resolution-contract.mjs', RESOLUTION_CONTRACT)
    apply_create_controls()
    apply_wrapper()
    apply_ui_tests()
    apply_video_tests()
    apply_package()
    validate_source()
    print('Iteration 9 resolution product patch applied')


if __name__ == '__main__':
    apply_product()
