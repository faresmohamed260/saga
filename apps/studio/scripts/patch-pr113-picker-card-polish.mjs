import { readFile, writeFile } from 'node:fs/promises';

function replaceOnce(source, from, to, label) {
  if (source.includes(to)) return source;
  if (!source.includes(from)) throw new Error(`Missing ${label}`);
  return source.replace(from, to);
}

const createPath = 'src/create-controls.jsx';
let create = await readFile(createPath, 'utf8');

create = replaceOnce(
  create,
  `const VIDEO_RESOLUTIONS = [\n  { value: '480p', label: '480p', detail: 'SD' },\n  { value: '720p', label: '720p', detail: 'HD' },\n  { value: '1080p', label: '1080p', detail: 'Full HD' },\n  { value: '2K', label: '2K', detail: '2048 px' },\n  { value: '4K', label: '4K', detail: '3840 px' },\n];`,
  `const VIDEO_RESOLUTIONS = [\n  { value: '480p', label: 'SD', detail: '480p' },\n  { value: '720p', label: 'HD', detail: '720p' },\n  { value: '1080p', label: 'Full HD', detail: '1080p' },\n  { value: '2K', label: '2K', detail: '2048 px' },\n  { value: '4K', label: '4K', detail: '3840 px' },\n];`,
  'video resolution labels',
);

const morphStart = create.indexOf('function MorphList(');
const morphEnd = create.indexOf('\nfunction PickerShell(', morphStart);
if (morphStart < 0 || morphEnd < 0) throw new Error('Missing MorphList block');
const morphBlock = `function MorphList({ options, value, onChoose, render, ariaLabel, focusWhen = false, onPreview }) {\n  const refs = useRef([]);\n  const [hoverIndex, setHoverIndex] = useState(null);\n  const activeIndex = Math.max(0, options.findIndex((item) => item.value === value));\n  const targetIndex = hoverIndex == null ? activeIndex : hoverIndex;\n  const rowHeight = 32;\n\n  useEffect(() => {\n    if (!focusWhen) return undefined;\n    const timer = window.setTimeout(() => refs.current[activeIndex]?.focus(), 40);\n    return () => window.clearTimeout(timer);\n  }, [focusWhen, activeIndex, options.length]);\n\n  const previewAt = (index) => {\n    setHoverIndex(index);\n    onPreview?.(options[index]);\n  };\n\n  const resetPreview = () => {\n    setHoverIndex(null);\n    onPreview?.(null);\n  };\n\n  const keyDown = (event, index) => {\n    let next = null;\n    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % options.length;\n    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index - 1 + options.length) % options.length;\n    if (event.key === 'Home') next = 0;\n    if (event.key === 'End') next = options.length - 1;\n    if (next != null) {\n      event.preventDefault();\n      refs.current[next]?.focus();\n    }\n    if (event.key === 'Enter' || event.key === ' ') {\n      event.preventDefault();\n      onChoose(options[index]);\n    }\n  };\n\n  return (\n    <div className=\"saga-morph-list\" role=\"menu\" aria-label={ariaLabel} onMouseLeave={resetPreview}>\n      <span\n        className=\"saga-morph-indicator\"\n        style={{ transform: \`translate3d(0, \${targetIndex * rowHeight}px, 0)\`, height: rowHeight }}\n      />\n      {options.map((option, index) => (\n        <button\n          ref={(node) => { refs.current[index] = node; }}\n          type=\"button\"\n          role=\"menuitemradio\"\n          aria-checked={option.value === value}\n          tabIndex={index === activeIndex ? 0 : -1}\n          className={option.value === value ? 'selected' : ''}\n          key={option.value}\n          onMouseEnter={() => previewAt(index)}\n          onFocus={() => previewAt(index)}\n          onKeyDown={(event) => keyDown(event, index)}\n          onClick={() => onChoose(option)}\n        >\n          {render(option)}\n          {option.value === value && <Check className=\"saga-option-check\" size={15} />}\n        </button>\n      ))}\n    </div>\n  );\n}\n`;
create = create.slice(0, morphStart) + morphBlock + create.slice(morphEnd);

create = create.replace('width={420} height={354} className="saga-aspect-picker"', 'width={390} height={370} className="saga-aspect-picker"');
create = create.replace('width={410} height={282} className="saga-resolution-picker"', 'width={390} height={220} className="saga-resolution-picker"');
create = create.replace('width={310} height={238} onClose={() => setOpen(false)}', 'width={300} height={176} className="saga-video-resolution-picker" onClose={() => setOpen(false)}');

create = replaceOnce(
  create,
  `      <MorphList\n        focusWhen={open}\n        ariaLabel="Aspect ratio"`,
  `      <MorphList\n        focusWhen={open}\n        onPreview={(option) => setPreview(option?.ratio ?? displayRatio)}\n        ariaLabel="Aspect ratio"`,
  'aspect hover preview',
);
create = replaceOnce(
  create,
  `      <MorphList\n        focusWhen={open}\n        ariaLabel="Resolution"`,
  `      <MorphList\n        focusWhen={open}\n        onPreview={(option) => setPreviewValue(option ? Number(option.value) : Number(imageResolution))}\n        ariaLabel="Resolution"`,
  'resolution hover preview',
);

create = replaceOnce(
  create,
  `                  <button\n                    type="button"\n                    className={\`saga-audio-toggle \${videoAudio ? 'active' : ''}\`}\n                    aria-pressed={videoAudio}\n                    title={videoAudio ? 'Audio enabled' : 'Audio disabled'}\n                    onClick={() => setVideoAudio((current) => !current)}\n                  >\n                    {videoAudio ? <Volume2 size={17} /> : <VolumeX size={17} />}\n                    <span>{videoAudio ? 'Audio' : 'Muted'}</span>\n                  </button>`,
  `                  <button\n                    type="button"\n                    className={\`saga-audio-toggle \${videoAudio ? 'active' : ''}\`}\n                    aria-pressed={videoAudio}\n                    aria-label={videoAudio ? 'Disable audio' : 'Enable audio'}\n                    title={videoAudio ? 'Audio enabled' : 'Audio disabled'}\n                    onClick={() => setVideoAudio((current) => !current)}\n                  >\n                    {videoAudio ? <Volume2 size={17} /> : <VolumeX size={17} />}\n                  </button>`,
  'circular audio button',
);

await writeFile(createPath, create);

const cssPath = 'src/create-workspace-v2.css';
let css = await readFile(cssPath, 'utf8');

css = replaceOnce(
  css,
  `.workspace .saga-control-pill,\n.workspace .saga-auto-toggle,\n.workspace .saga-audio-toggle{\n  height:34px;display:flex;align-items:center;justify-content:center;gap:7px;padding:0 11px;border:1px solid #272d37;border-radius:11px;background:#151920;color:#d5d9e0;font-size:11px;font-weight:700;white-space:nowrap;cursor:pointer;transition:.18s ease;\n}\n.workspace .saga-control-pill:hover,.workspace .saga-control-pill.active,.workspace .saga-audio-toggle:hover{background:#1d222b;border-color:#3b4350;color:#fff}\n.workspace .saga-auto-toggle.active{background:#261f42;border-color:#5844a8;color:#f1edff;box-shadow:inset 0 0 0 1px rgba(156,137,255,.12)}\n.workspace .saga-auto-toggle:not(.active){color:#7d8695;background:#14181e}\n.workspace .saga-audio-toggle.active{color:#ece9ff;background:#1f1c2c;border-color:#423861}`,
  `.workspace .saga-control-pill,\n.workspace .saga-auto-toggle{\n  height:34px;display:flex;align-items:center;justify-content:center;gap:7px;padding:0 11px;border:1px solid #272d37;border-radius:11px;background:#151920;color:#d5d9e0;font-size:11px;font-weight:700;white-space:nowrap;cursor:pointer;transition:.18s ease;\n}\n.workspace .saga-control-pill:hover,.workspace .saga-control-pill.active{background:#1d222b;border-color:#3b4350;color:#fff}\n.workspace .saga-auto-toggle.active{background:#261f42;border-color:#5844a8;color:#f1edff;box-shadow:inset 0 0 0 1px rgba(156,137,255,.12)}\n.workspace .saga-auto-toggle:not(.active){color:#7d8695;background:#14181e}\n.workspace .saga-audio-toggle{width:36px;height:36px;flex:0 0 36px;display:grid;place-items:center;padding:0;border:1px solid #272d37;border-radius:50%;background:#151920;color:#aeb6c2;cursor:pointer;transition:.18s ease}\n.workspace .saga-audio-toggle:hover{background:#20252d;border-color:#3b4350;color:#fff}\n.workspace .saga-audio-toggle.active{color:#ece9ff;background:#241f38;border-color:#554887;box-shadow:inset 0 0 0 1px rgba(156,137,255,.08)}`,
  'audio/control css',
);

css = css.replace('.workspace .saga-aspect-picker,.workspace .saga-resolution-picker{display:grid;grid-template-columns:145px 1fr}', '.workspace .saga-aspect-picker,.workspace .saga-resolution-picker{display:grid;grid-template-columns:132px 1fr}');
css = css.replace('.workspace .saga-morph-list{position:relative;min-width:0;padding:8px;overflow:auto}', '.workspace .saga-morph-list{position:relative;min-width:0;padding:7px;overflow:hidden}');
css = css.replace('position:absolute;left:7px;right:7px;top:8px;', 'position:absolute;left:7px;right:7px;top:7px;');
css = css.replace('position:relative;z-index:1;width:100%;height:42px;display:grid;', 'position:relative;z-index:1;width:100%;height:32px;display:grid;');
css = css.replace('grid-template-columns:minmax(68px,1fr) minmax(64px,92px) 18px;', 'grid-template-columns:minmax(62px,1fr) minmax(68px,96px) 18px;');
css = css.replace('.workspace .saga-option-key,.workspace .saga-option-label{font-size:11px;', '.workspace .saga-option-key,.workspace .saga-option-label{font-size:10px;');
css = css.replace('.workspace .saga-option-detail{font-size:9px;', '.workspace .saga-option-detail{font-size:9px;');

const outputStart = css.indexOf('.workspace .saga-output-wall{');
const outputEnd = css.indexOf('\n@media(max-width:1000px){', outputStart);
if (outputStart < 0 || outputEnd < 0) throw new Error('Missing output wall CSS block');
const outputBlock = `.workspace .saga-output-wall{\n  width:min(780px,100%);\n  margin:54px auto 0;\n  column-count:3;\n  column-gap:10px;\n}\n.workspace .saga-output-slot{\n  width:100%;\n  display:inline-block;\n  margin:0 0 10px;\n  break-inside:avoid;\n  overflow:hidden;\n  border-radius:16px;\n  vertical-align:top;\n}\n.workspace .saga-output-slot-0{aspect-ratio:4/5}\n.workspace .saga-output-slot-1{aspect-ratio:3/4}\n.workspace .saga-output-slot-2{aspect-ratio:1/1}\n.workspace .saga-output-slot-3{aspect-ratio:4/5}\n.workspace .saga-output-slot-4{aspect-ratio:1/1}\n.workspace .saga-output-slot-5{aspect-ratio:3/4}\n.workspace .saga-output-wall .media-card{width:100%;height:100%;min-height:0;border-radius:16px;overflow:hidden;background:#0e1217;border:1px solid #242a33;box-sizing:border-box;position:relative}\n.workspace .saga-output-wall .media-frame{width:100%!important;height:100%!important;min-width:100%!important;min-height:100%!important;aspect-ratio:auto!important;border-radius:0!important;position:relative;background-size:cover!important;background-position:center!important}\n.workspace .saga-output-wall .size-badge{opacity:0;transform:translateY(-4px);transition:.18s ease}\n.workspace .saga-output-wall .card-actions{\n  position:absolute!important;left:8px!important;right:8px!important;bottom:8px!important;z-index:8!important;display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;align-items:center!important;gap:4px!important;padding:6px!important;box-sizing:border-box!important;border:1px solid rgba(255,255,255,.09)!important;border-radius:12px!important;background:rgba(10,12,16,.82)!important;backdrop-filter:blur(14px);opacity:0;transform:translateY(7px);pointer-events:none;transition:opacity .18s ease,transform .18s ease;\n}\n.workspace .saga-output-wall .card-actions button{width:100%;min-width:0;height:30px;border-radius:8px!important}\n.workspace .saga-output-wall .media-card:hover .card-actions,\n.workspace .saga-output-wall .media-card:focus-within .card-actions,\n.workspace .saga-output-wall .media-card:hover .size-badge{opacity:1;transform:none;pointer-events:auto}\n`;
css = css.slice(0, outputStart) + outputBlock + css.slice(outputEnd);

css = css.replace('.workspace .saga-control-pill,.workspace .saga-auto-toggle,.workspace .saga-audio-toggle{height:32px;padding:0 8px}\n  .workspace .saga-audio-toggle span{display:none}', '.workspace .saga-control-pill,.workspace .saga-auto-toggle{height:32px;padding:0 8px}\n  .workspace .saga-audio-toggle{width:32px;height:32px;flex-basis:32px}');
css = css.replace('.workspace .saga-output-wall{margin-top:34px;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:150px;gap:7px}\n  .workspace .saga-output-slot{grid-column:span 1!important;grid-row:span 1!important}\n  .workspace .saga-output-slot:nth-child(3n+1){grid-row:span 2!important}', '.workspace .saga-output-wall{margin-top:34px;column-count:2;column-gap:7px}\n  .workspace .saga-output-slot{margin-bottom:7px}');

await writeFile(cssPath, css);

const qaPath = 'scripts/capture-ui-preview.mjs';
let qa = await readFile(qaPath, 'utf8');

qa = replaceOnce(
  qa,
  `  await resolutionPicker.waitFor({ state: 'visible' });\n  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });\n  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });\n  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });\n  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });\n  const focusedRole = await desktop.evaluate(() => document.activeElement?.getAttribute('role'));\n  if (focusedRole !== 'menuitemradio') throw new Error(\`Resolution picker did not focus selected option: \${focusedRole}\`);\n  await desktop.keyboard.press('ArrowDown');\n  await desktop.keyboard.press('Escape');`,
  `  await resolutionPicker.waitFor({ state: 'visible' });\n  await desktop.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitemradio', null, { timeout: 1000 });\n  const focusedRole = await desktop.evaluate(() => document.activeElement?.getAttribute('role'));\n  if (focusedRole !== 'menuitemradio') throw new Error(\`Resolution picker did not focus selected option: \${focusedRole}\`);\n  const resolutionPreviewBefore = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  await desktop.keyboard.press('ArrowDown');\n  await desktop.waitForTimeout(180);\n  const resolutionPreviewAfter = (await resolutionPicker.locator('.saga-resolution-cube').innerText()).trim();\n  if (resolutionPreviewBefore === resolutionPreviewAfter) throw new Error('Resolution preview did not morph with keyboard focus');\n  await desktop.keyboard.press('Escape');`,
  'resolution morph QA',
);

qa = replaceOnce(
  qa,
  `  await aspectPicker.waitFor({ state: 'visible' });\n  await shot(desktop, '02-image-aspect-picker.png');\n  await desktop.locator('.saga-stage-heading').click();`,
  `  await aspectPicker.waitFor({ state: 'visible' });\n  const aspectList = aspectPicker.locator('.saga-morph-list');\n  const aspectScroll = await aspectList.evaluate((el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }));\n  if (aspectScroll.scrollHeight > aspectScroll.clientHeight + 1) throw new Error(\`Aspect picker still scrolls: \${JSON.stringify(aspectScroll)}\`);\n  const aspectPreviewBefore = await aspectPicker.locator('.saga-preview-shape').boundingBox();\n  await aspectPicker.getByRole('menuitemradio', { name: /16:9.*Widescreen/i }).hover();\n  await desktop.waitForTimeout(200);\n  const aspectPreviewAfter = await aspectPicker.locator('.saga-preview-shape').boundingBox();\n  if (!aspectPreviewBefore || !aspectPreviewAfter || (Math.abs(aspectPreviewBefore.width - aspectPreviewAfter.width) < 3 && Math.abs(aspectPreviewBefore.height - aspectPreviewAfter.height) < 3)) throw new Error('Aspect preview did not morph on hover');\n  await shot(desktop, '02-image-aspect-picker.png');\n  await desktop.locator('.saga-stage-heading').click();`,
  'aspect morph/scroll QA',
);

qa = replaceOnce(
  qa,
  `  for (const label of ['480p', '720p', '1080p', '2K', '4K']) await videoResolutionPicker.getByRole('menuitemradio', { name: new RegExp(label, 'i') }).waitFor({ state: 'visible' });\n  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K/i }).click();`,
  `  const expectedVideoRows = [['SD', '480p'], ['HD', '720p'], ['Full HD', '1080p'], ['2K', '2048 px'], ['4K', '3840 px']];\n  const videoRows = videoResolutionPicker.getByRole('menuitemradio');\n  if (await videoRows.count() !== expectedVideoRows.length) throw new Error('Video resolution picker row count is wrong');\n  for (let index = 0; index < expectedVideoRows.length; index += 1) {\n    const [label, detail] = expectedVideoRows[index];\n    const row = videoRows.nth(index);\n    if ((await row.locator('.saga-option-label').innerText()).trim() !== label) throw new Error(\`Video label mismatch at \${index}\`);\n    if ((await row.locator('.saga-option-detail').innerText()).trim() !== detail) throw new Error(\`Video pixel detail mismatch at \${index}\`);\n  }\n  await videoResolutionPicker.getByRole('menuitemradio', { name: /4K.*3840 px/i }).click();`,
  'video resolution QA',
);

qa = replaceOnce(
  qa,
  `  const audioToggle = desktop.locator('.saga-audio-toggle');\n  if (!(await audioToggle.getAttribute('aria-pressed') === 'true')) throw new Error('Video audio should default on');\n  await audioToggle.click();\n  if (!(await audioToggle.getAttribute('aria-pressed') === 'false')) throw new Error('Video audio toggle did not turn off');\n  await shot(desktop, '04-video-controls.png');`,
  `  const audioToggle = desktop.locator('.saga-audio-toggle');\n  if (!(await audioToggle.getAttribute('aria-pressed') === 'true')) throw new Error('Video audio should default on');\n  const audioBox = await audioToggle.boundingBox();\n  if (!audioBox || Math.abs(audioBox.width - audioBox.height) > 1 || audioBox.width > 38) throw new Error(\`Audio toggle is not circular: \${JSON.stringify(audioBox)}\`);\n  if ((await audioToggle.innerText()).trim()) throw new Error('Audio toggle should be icon-only');\n  await audioToggle.click();\n  if (!(await audioToggle.getAttribute('aria-pressed') === 'false')) throw new Error('Video audio toggle did not turn off');\n  await shot(desktop, '04-video-controls.png');`,
  'audio button QA',
);

qa = replaceOnce(
  qa,
  `  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(1), '23s', 'Persisted video duration');\n  await expectText(desktop.locator('.saga-audio-toggle'), 'Muted', 'Persisted audio state');`,
  `  await expectText(desktop.locator('.saga-toolbar-left .saga-control-pill').nth(1), '23s', 'Persisted video duration');\n  if (await desktop.locator('.saga-audio-toggle').getAttribute('aria-pressed') !== 'false') throw new Error('Persisted audio state did not remain muted');`,
  'audio persistence QA',
);

qa = replaceOnce(
  qa,
  `  const firstCard = slots.nth(0).locator('.media-card');\n  const cardActions = firstCard.locator('.card-actions');\n  const beforeOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);`,
  `  const firstCard = slots.nth(0).locator('.media-card');\n  const firstFrame = firstCard.locator('.media-frame');\n  const firstCardBox = await firstCard.boundingBox();\n  const firstFrameBox = await firstFrame.boundingBox();\n  if (!firstCardBox || !firstFrameBox || Math.abs(firstCardBox.width - firstFrameBox.width) > 2 || Math.abs(firstCardBox.height - firstFrameBox.height) > 2) throw new Error(\`Output frame is misaligned inside card: card=\${JSON.stringify(firstCardBox)} frame=\${JSON.stringify(firstFrameBox)}\`);\n  const cardActions = firstCard.locator('.card-actions');\n  const beforeOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);`,
  'output frame alignment QA',
);

qa = replaceOnce(
  qa,
  `  const afterOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);\n  if (Number(afterOpacity) < 0.9) throw new Error(\`Output actions did not appear on hover, opacity=\${afterOpacity}\`);\n  await shot(desktop, '07-output-wall-hover.png');`,
  `  const afterOpacity = await cardActions.evaluate((el) => getComputedStyle(el).opacity);\n  if (Number(afterOpacity) < 0.9) throw new Error(\`Output actions did not appear on hover, opacity=\${afterOpacity}\`);\n  const actionBox = await cardActions.boundingBox();\n  if (!actionBox || actionBox.x < firstCardBox.x + 6 || actionBox.x + actionBox.width > firstCardBox.x + firstCardBox.width - 6) throw new Error(\`Output action bar is not aligned to its card: \${JSON.stringify(actionBox)}\`);\n  await shot(desktop, '07-output-wall-hover.png');`,
  'output nav alignment QA',
);

await writeFile(qaPath, qa);
