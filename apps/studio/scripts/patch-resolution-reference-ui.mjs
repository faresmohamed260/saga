import fs from 'node:fs';

function read(path) { return fs.readFileSync(path, 'utf8'); }
function write(path, value) { fs.writeFileSync(path, value); }
function replaceOnce(source, before, after, label) {
  if (!source.includes(before)) throw new Error(`Missing ${label}`);
  return source.replace(before, after);
}
function replaceRegex(source, pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`Missing ${label}`);
  return source.replace(pattern, replacement);
}

const controlsPath = 'apps/studio/src/create-controls.jsx';
let controls = read(controlsPath);

controls = replaceRegex(
  controls,
  /export const IMAGE_RESOLUTIONS = \[[\s\S]*?\];\n\nconst VIDEO_RESOLUTIONS = \[[\s\S]*?\];\n\nconst STORAGE_KEY = 'saga-studio:create-settings:v4';/,
  `export const IMAGE_RESOLUTIONS = [
  { value: 480, label: 'SD', detail: '480 px' },
  { value: 720, label: 'HD', detail: '720 px' },
  { value: 1080, label: 'Full HD', detail: '1080 px' },
  { value: 2048, label: '2K', detail: '2048 px' },
  { value: 3840, label: '4K', detail: '3840 px' },
];

const VIDEO_RESOLUTIONS = [
  { value: '480p', label: 'SD', detail: '480p', preview: '480', dimensions: '896×512' },
  { value: '720p', label: 'HD', detail: '720p', preview: '720', dimensions: '1280×704' },
  { value: '1080p', label: 'Full HD', detail: '1080p', preview: '1080', dimensions: '1920×1088' },
  { value: '2K', label: '2K', detail: '2048 px', preview: '2048', dimensions: '2048×1152' },
  { value: '4K', label: '4K', detail: '3840 px', preview: '3840', dimensions: '3840×2176' },
];

const STORAGE_KEY = 'saga-studio:create-settings:v5';`,
  'resolution preset block',
);

controls = replaceRegex(
  controls,
  /function ResolutionPicker\(\{[\s\S]*?\n\}\n\nfunction DurationPicker/,
  `function ResolutionPicker({
  open, setOpen, anchorRef, imageResolution, setImageResolution, aspect,
  editAuto, setEditAuto, autoInfo,
}) {
  const autoDimensions = parseAutoDimensions(autoInfo?.detail);
  const selectedOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];
  const [previewValue, setPreviewValue] = useState(Number(selectedOption.value));
  useEffect(() => setPreviewValue(Number(selectedOption.value)), [selectedOption.value, open]);
  const previewOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(previewValue)) || selectedOption;
  const dimensions = editAuto ? autoDimensions : dimensionsForPreset(aspect, previewValue);

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className="saga-resolution-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview saga-resolution-preview">
        <div className="saga-resolution-cube">{editAuto ? <Sparkles size={20} /> : previewValue}</div>
        <strong>{editAuto ? 'Auto' : previewOption.label}</strong>
        <small>{editAuto ? autoInfo?.detail : dimensions ? \`${'${dimensions.width}'}×${'${dimensions.height}'}\` : ''}</small>
      </div>
      <MorphList
        focusWhen={open}
        onPreview={(option) => setPreviewValue(option ? Number(option.value) : Number(selectedOption.value))}
        ariaLabel="Resolution"
        options={IMAGE_RESOLUTIONS}
        value={editAuto ? '__none__' : Number(imageResolution)}
        onChoose={(option) => {
          setEditAuto(false);
          setImageResolution(option.value);
          setOpen(false);
        }}
        render={(option) => (
          <>
            <span className="saga-option-label">{option.label}</span>
            <span className="saga-option-detail">{option.detail}</span>
          </>
        )}
      />
    </PickerShell>
  );
}

function VideoResolutionPicker({ open, setOpen, anchorRef, value, setValue }) {
  const selectedOption = VIDEO_RESOLUTIONS.find((item) => item.value === value) || VIDEO_RESOLUTIONS[2];
  const [previewValue, setPreviewValue] = useState(selectedOption.value);
  useEffect(() => setPreviewValue(selectedOption.value), [selectedOption.value, open]);
  const previewOption = VIDEO_RESOLUTIONS.find((item) => item.value === previewValue) || selectedOption;

  return (
    <PickerShell open={open} anchorRef={anchorRef} width={390} height={220} className="saga-video-resolution-picker saga-resolution-picker" onClose={() => setOpen(false)}>
      <div className="saga-picker-preview saga-resolution-preview">
        <div className="saga-resolution-cube">{previewOption.preview}</div>
        <strong>{previewOption.label}</strong>
        <small>{previewOption.dimensions}</small>
      </div>
      <MorphList
        focusWhen={open}
        onPreview={(option) => setPreviewValue(option?.value ?? selectedOption.value)}
        ariaLabel="Video resolution"
        options={VIDEO_RESOLUTIONS}
        value={value}
        onChoose={(option) => {
          setValue(option.value);
          setOpen(false);
        }}
        render={(option) => (
          <>
            <span className="saga-option-label">{option.label}</span>
            <span className="saga-option-detail">{option.detail}</span>
          </>
        )}
      />
    </PickerShell>
  );
}

function DurationPicker`,
  'resolution picker functions',
);

controls = replaceOnce(
  controls,
  "  const imageOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];\n  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;",
  "  const imageOption = IMAGE_RESOLUTIONS.find((item) => item.value === Number(imageResolution)) || IMAGE_RESOLUTIONS[2];\n  const videoOption = VIDEO_RESOLUTIONS.find((item) => item.value === videoResolution) || VIDEO_RESOLUTIONS[2];\n  const primaryRatio = references[0]?.width && references[0]?.height ? references[0].width / references[0].height : 1;",
  'selected resolution options',
);

controls = replaceOnce(
  controls,
  `                    <span className="saga-resolution-badge">{isEdit && editAuto ? 'A' : Number(imageResolution)}</span>
                    <span>{isEdit && editAuto ? 'Auto' : imageOption.label}</span>
                    <ChevronDown size={13} />`,
  `                    {isEdit && editAuto ? <Sparkles size={15} /> : <ImageIcon size={15} />}
                    <span>{isEdit && editAuto ? 'Auto' : imageOption.label}</span>
                    <ChevronDown size={13} />`,
  'image resolution trigger',
);

controls = replaceOnce(
  controls,
  `                    <Video size={15} /><span>{videoResolution}</span><ChevronDown size={13} />`,
  `                    <Video size={15} /><span>{videoOption.label}</span><ChevronDown size={13} />`,
  'video resolution trigger',
);

if (!controls.includes("label: 'Full HD'")) throw new Error('Unified labels were not applied');
if (controls.includes("label: 'Draft'") || controls.includes("label: 'Standard'") || controls.includes("label: 'High'") || controls.includes("label: 'Max'")) throw new Error('Legacy image resolution labels remain');
write(controlsPath, controls);

const appPath = 'apps/studio/src/app/App.jsx';
let app = read(appPath);
app = replaceOnce(app, "  const [imageResolution, setImageResolution] = useState(1024);", "  const [imageResolution, setImageResolution] = useState(1080);", 'default image resolution');
app = replaceOnce(
  app,
  `}\n\nexport default function App() {`,
  `}\n\nfunction promptAfterReferenceRemoval(value, removedIndex) {\n  const next = String(value || '').replace(/@Image\\s+(\\d+)/gi, (match, rawNumber) => {\n    const mentionNumber = Number(rawNumber);\n    const mentionIndex = mentionNumber - 1;\n    if (!Number.isFinite(mentionIndex)) return match;\n    if (mentionIndex === removedIndex) return '';\n    if (mentionIndex > removedIndex) return \`@Image ${'${mentionNumber - 1}'}\`;\n    return \`@Image ${'${mentionNumber}'}\`;\n  });\n  return next\n    .replace(/[ \\t]{2,}/g, ' ')\n    .replace(/\\s+([,.;:!?])/g, '$1')\n    .replace(/ *\\n */g, '\\n')\n    .trim();\n}\n\nexport default function App() {`,
  'prompt cleanup helper',
);
app = replaceOnce(
  app,
  `  const removeReference = (index) => {\n    setReferences((current) => {\n      const target = current[index];\n      if (target?.preview) URL.revokeObjectURL(target.preview);\n      return current.filter((_, itemIndex) => itemIndex !== index);\n    });\n  };`,
  `  const removeReference = (index) => {\n    const target = references[index];\n    if (!target) return;\n    if (target.preview) URL.revokeObjectURL(target.preview);\n    const nextReferences = references.filter((_, itemIndex) => itemIndex !== index);\n    setReferences(nextReferences);\n    setPrompt((current) => promptAfterReferenceRemoval(current, index));\n    if (mode === 'Edit' && nextReferences.length === 0) {\n      setMode('Image');\n      setWorkflowId('default-image');\n      setModelId('saga-image-auto');\n      setError('');\n    }\n  };`,
  'reference removal behavior',
);
write(appPath, app);

const previewPath = 'apps/studio/scripts/capture-ui-preview.mjs';
let preview = read(previewPath);
preview = replaceOnce(
  preview,
  `  const resolutionPreviewBefore = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  await desktop.keyboard.press('ArrowDown');\n  await desktop.waitForTimeout(180);\n  const resolutionPreviewAfter = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  if (resolutionPreviewBefore === resolutionPreviewAfter) throw new Error('Resolution preview did not morph with keyboard focus');\n  await desktop.keyboard.press('Escape');`,
  `  const expectedImageRows = [['SD', '480 px'], ['HD', '720 px'], ['Full HD', '1080 px'], ['2K', '2048 px'], ['4K', '3840 px']];\n  const imageRows = resolutionPicker.getByRole('menuitemradio');\n  if (await imageRows.count() !== expectedImageRows.length) throw new Error('Image resolution picker row count is wrong');\n  for (let index = 0; index < expectedImageRows.length; index += 1) {\n    const [label, detail] = expectedImageRows[index];\n    const row = imageRows.nth(index);\n    if ((await row.locator('.saga-option-label').innerText()).trim() !== label) throw new Error(\`Image label mismatch at ${'${index}'}\`);\n    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(\`Image pixel detail mismatch at ${'${index}'}\`);\n  }\n  const resolutionPreviewBefore = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  const resolutionLabelBefore = (await resolutionPicker.locator('.saga-picker-preview strong').innerText()).trim();\n  await desktop.keyboard.press('ArrowDown');\n  await desktop.waitForTimeout(180);\n  const resolutionPreviewAfter = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  const resolutionLabelAfter = (await resolutionPicker.locator('.saga-picker-preview strong').innerText()).trim();\n  if (resolutionPreviewBefore === resolutionPreviewAfter) throw new Error('Resolution preview did not morph with keyboard focus');\n  if (resolutionLabelBefore === resolutionLabelAfter || resolutionLabelAfter !== '2K') throw new Error(\`Resolution label did not morph with preview: ${'${resolutionLabelBefore}'} -> ${'${resolutionLabelAfter}'}\`);\n  await shot(desktop, '02-image-resolution-picker.png');\n  await desktop.keyboard.press('Escape');`,
  'image picker morph validation',
);
preview = replaceOnce(preview, "/High.*1536 px/i", "/2K.*2048 px/i", 'image resolution selection');
preview = replaceOnce(
  preview,
  `  const videoList = videoResolutionPicker.locator('.saga-morph-list');\n  const videoScroll = await videoList.evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));\n  if (videoScroll.scrollHeight > videoScroll.clientHeight + 1) throw new Error(\`Video resolution picker scrolls: ${'${JSON.stringify(videoScroll)}'}\`);\n  await shot(desktop, '04-video-resolution-picker.png');`,
  `  const videoList = videoResolutionPicker.locator('.saga-morph-list');\n  const videoScroll = await videoList.evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));\n  if (videoScroll.scrollHeight > videoScroll.clientHeight + 1) throw new Error(\`Video resolution picker scrolls: ${'${JSON.stringify(videoScroll)}'}\`);\n  const videoPreview = videoResolutionPicker.locator('.saga-picker-preview');\n  if (await videoPreview.count() !== 1) throw new Error('Video resolution picker is missing the shared preview panel');\n  const videoPreviewLabelBefore = (await videoPreview.locator('strong').innerText()).trim();\n  await videoResolutionPicker.getByRole('menuitemradio', { name: /2K.*2048 px/i }).hover();\n  await desktop.waitForTimeout(180);\n  const videoPreviewLabelAfter = (await videoPreview.locator('strong').innerText()).trim();\n  if (videoPreviewLabelBefore === videoPreviewLabelAfter || videoPreviewLabelAfter !== '2K') throw new Error(\`Video resolution preview did not morph: ${'${videoPreviewLabelBefore}'} -> ${'${videoPreviewLabelAfter}'}\`);\n  await shot(desktop, '04-video-resolution-picker.png');`,
  'video picker preview validation',
);
preview = replaceOnce(
  preview,
  `  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();\n  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });\n  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');`,
  `  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();\n  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });\n  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');\n  await expectText(videoControls.nth(0), 'Full HD', 'Video resolution trigger label');\n  if ((await videoControls.nth(0).innerText()).includes('1080p')) throw new Error('Video resolution trigger still exposes the raw resolution value');`,
  'video trigger label validation',
);
preview = replaceOnce(preview, "  await expectText(desktop.locator('.saga-resolution-trigger'), 'High', 'Persisted image resolution');\n  if ((await desktop.locator('.saga-resolution-badge').innerText()).trim() !== '1536') throw new Error('Persisted resolution badge is truncated');", "  await expectText(desktop.locator('.saga-resolution-trigger'), '2K', 'Persisted image resolution');\n  if ((await desktop.locator('.saga-resolution-trigger').innerText()).includes('2048')) throw new Error('Image resolution trigger still exposes the raw resolution value');", 'persisted image trigger validation');
preview = replaceOnce(
  preview,
  `  const chooserPromise = desktop.waitForEvent('filechooser');\n  await upload.click();\n  const chooser = await chooserPromise;\n  await chooser.setFiles({ name: 'reference.png', mimeType: 'image/png', buffer: referencePng });\n  const refChip = desktop.locator('.saga-reference-chip').first();\n  await refChip.waitFor({ state: 'visible', timeout: 5000 });\n  const richPrompt = desktop.locator('.saga-rich-prompt');\n  await richPrompt.click();\n  await richPrompt.pressSequentially('Put ');\n  await refChip.locator('.saga-reference-main').click();\n  await richPrompt.pressSequentially(' behind the subject');\n  const mention = richPrompt.locator('.mention-token');\n  if (await mention.count() !== 1) throw new Error('Reference click did not insert an inline prompt tag');\n  const promptText = (await richPrompt.innerText()).replace(/\\s+/g, ' ').trim();\n  if (!/Put\\s+Image 1\\s+behind the subject/i.test(promptText)) throw new Error(\`Reference tag was not inserted at the caret: ${'${promptText}'}\`);`,
  `  const chooserPromise = desktop.waitForEvent('filechooser');\n  await upload.click();\n  const chooser = await chooserPromise;\n  await chooser.setFiles({ name: 'reference.png', mimeType: 'image/png', buffer: referencePng });\n  const secondChooserPromise = desktop.waitForEvent('filechooser');\n  await upload.click();\n  const secondChooser = await secondChooserPromise;\n  await secondChooser.setFiles({ name: 'reference-2.png', mimeType: 'image/png', buffer: referencePng });\n  const refChips = desktop.locator('.saga-reference-chip');\n  await refChips.nth(1).waitFor({ state: 'visible', timeout: 5000 });\n  const richPrompt = desktop.locator('.saga-rich-prompt');\n  await richPrompt.click();\n  await richPrompt.pressSequentially('Put ');\n  await refChips.nth(0).locator('.saga-reference-main').click();\n  await richPrompt.pressSequentially(' beside ');\n  await refChips.nth(1).locator('.saga-reference-main').click();\n  await richPrompt.pressSequentially(' behind the subject');\n  const mentions = richPrompt.locator('.mention-token');\n  if (await mentions.count() !== 2) throw new Error('Reference clicks did not insert both inline prompt tags');\n  const promptText = (await richPrompt.innerText()).replace(/\\s+/g, ' ').trim();\n  if (!/Put\\s+Image 1\\s+beside\\s+Image 2\\s+behind the subject/i.test(promptText)) throw new Error(\`Reference tags were not inserted at the caret: ${'${promptText}'}\`);`,
  'multi-reference prompt validation',
);
preview = replaceOnce(
  preview,
  `  await shot(desktop, '06-edit-inline-reference-and-auto.png');\n\n  // More is a sidebar destination, and Create returns to the compact image composer.`,
  `  await shot(desktop, '06-edit-inline-reference-and-auto.png');\n\n  // Removing references cleans prompt tags, renumbers survivors, and exits Edit when the last reference is gone.\n  await refChips.nth(0).locator('.saga-reference-remove').click();\n  await desktop.waitForTimeout(120);\n  if (await desktop.locator('.saga-reference-chip').count() !== 1) throw new Error('Removing one reference did not update the reference strip');\n  const remainingMentions = richPrompt.locator('.mention-token');\n  if (await remainingMentions.count() !== 1) throw new Error('Removed reference tag was not cleaned from the prompt');\n  if (await remainingMentions.first().getAttribute('data-mention') !== '@Image 1') throw new Error('Remaining reference tag was not renumbered to Image 1');\n  await desktop.locator('.saga-reference-chip .saga-reference-remove').click();\n  await desktop.locator('.saga-composer:not(.is-edit)').waitFor({ state: 'visible', timeout: 2500 });\n  const imageModeButton = desktop.locator('.saga-media-toggle button').filter({ hasText: 'Image' });\n  if (await imageModeButton.getAttribute('aria-pressed') !== 'true') throw new Error('Removing the final reference did not return Studio to Image mode');\n  if (await desktop.locator('.saga-reference-chip').count() !== 0) throw new Error('Final reference was not removed');\n  const cleanedPrompt = await desktop.locator('.saga-prompt-shell textarea').inputValue();\n  if (/@Image\\s+\\d+/i.test(cleanedPrompt)) throw new Error(\`Stale reference tag remains after removing all references: ${'${cleanedPrompt}'}\`);\n  await shot(desktop, '06b-reference-removal-cleanup.png');\n\n  // More is a sidebar destination, and Create returns to the compact image composer.`,
  'reference removal interaction validation',
);
write(previewPath, preview);

fs.rmSync('apps/studio/scripts/patch-resolution-reference-ui.mjs');
fs.rmSync('.github/workflows/patch-studio-resolution-reference-ui.yml');
console.log('Applied unified resolution picker and reference cleanup changes.');
