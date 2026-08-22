import { readFile, writeFile } from 'node:fs/promises';

const jsxPath = 'src/create-controls.jsx';
const cssPath = 'src/create-controls-interactions.css';
const previewPath = 'scripts/capture-ui-preview.mjs';

function assertIncludes(text, needle, label) {
  if (!text.includes(needle)) throw new Error(`Could not find ${label}`);
}

function replaceOnce(text, before, after, label) {
  assertIncludes(text, before, label);
  return text.replace(before, after);
}

let jsx = await readFile(jsxPath, 'utf8');

// Replace the old select-heavy settings panel with a viewport-anchored advanced panel.
const settingsStart = jsx.indexOf('function SettingsPanel({');
const settingsEnd = jsx.indexOf('\nfunction useAnchoredPickerPosition', settingsStart);
if (settingsStart < 0 || settingsEnd < 0) throw new Error('Could not locate SettingsPanel block');

const settingsBlock = `function clampControl(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function RangeField({ label, help, value, onChange, min, max, step, decimals = 0 }) {
  const parsed = Number(value);
  const safeValue = Number.isFinite(parsed) ? clampControl(parsed, min, max) : min;
  const commit = (raw) => {
    const next = Number(raw);
    if (!Number.isFinite(next)) return;
    const clamped = clampControl(next, min, max);
    onChange(Number(clamped.toFixed(decimals)));
  };

  return <div className="advanced-range-field">
    <div className="advanced-range-heading">
      <div><strong>{label}</strong>{help && <small>{help}</small>}</div>
      <input
        className="advanced-number-input"
        type="number"
        min={min}
        max={max}
        step={step}
        value={safeValue}
        onChange={(event) => commit(event.target.value)}
        aria-label={\`${'${label}'} value\`}
      />
    </div>
    <input
      className="advanced-range-input"
      type="range"
      min={min}
      max={max}
      step={step}
      value={safeValue}
      onChange={(event) => commit(event.target.value)}
      aria-label={label}
    />
    <div className="advanced-range-scale"><span>{min}</span><span>{max}</span></div>
  </div>;
}

function useFloatingSettingsPosition(open, anchorRef, panelRef, desiredWidth = 420) {
  const [position, setPosition] = useState(null);

  useEffect(() => {
    if (!open) {
      setPosition(null);
      return undefined;
    }

    let resizeObserver;
    const update = () => {
      const anchor = anchorRef?.current;
      const panel = panelRef?.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const edge = 12;
      const gap = 10;
      const width = Math.min(desiredWidth, viewportWidth - edge * 2);
      const maxHeight = Math.max(220, viewportHeight - edge * 2);
      const measuredHeight = Math.min(panel?.scrollHeight || 470, maxHeight);
      const spaceAbove = rect.top - edge - gap;
      const spaceBelow = viewportHeight - rect.bottom - edge - gap;
      const openAbove = spaceAbove >= measuredHeight || spaceAbove > spaceBelow;
      const rawTop = openAbove ? rect.top - gap - measuredHeight : rect.bottom + gap;
      const top = Math.max(edge, Math.min(rawTop, viewportHeight - measuredHeight - edge));
      const left = Math.max(edge, Math.min(rect.right - width, viewportWidth - width - edge));
      setPosition({ position: 'fixed', top, left, width, maxHeight });
    };

    const frame = requestAnimationFrame(update);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    if (typeof ResizeObserver !== 'undefined' && panelRef?.current) {
      resizeObserver = new ResizeObserver(update);
      resizeObserver.observe(panelRef.current);
    }
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
      resizeObserver?.disconnect();
    };
  }, [open, anchorRef, panelRef, desiredWidth]);

  return position;
}

function SettingsPanel({
  open, onClose, anchorRef, mode, outputs, setOutputs, seed, setSeed, steps, setSteps, cfg, setCfg,
  workflowId, setWorkflowId, modelId, setModelId,
}) {
  const panelRef = useRef(null);
  const position = useFloatingSettingsPosition(open, anchorRef, panelRef, 420);
  const isEdit = mode === 'Edit';
  const modelOptions = isEdit
    ? [{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B · DarkBeast V2' }]
    : [{ value: 'saga-image-auto', label: 'SAGA Image · Auto' }];

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (panelRef.current?.contains(event.target) || anchorRef?.current?.contains(event.target)) return;
      onClose();
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose();
        requestAnimationFrame(() => anchorRef?.current?.focus());
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open, onClose, anchorRef]);

  if (!open) return null;
  return <div
    ref={panelRef}
    className="composer-settings-popover advanced-settings-only advanced-settings-shell"
    style={position || { visibility: 'hidden' }}
    role="dialog"
    aria-label="Advanced generation settings"
  >
    <div className="advanced-settings-header">
      <div className="advanced-settings-title">
        <span>Generation controls</span>
        <h2>Advanced</h2>
        <p>Fine-tune sampling and execution without duplicating canvas controls.</p>
      </div>
      <button className="square-button advanced-close-button" type="button" onClick={onClose} aria-label="Close advanced settings"><X size={17}/></button>
    </div>

    <div className="advanced-settings-body">
      <div className="advanced-meta-grid">
        <div className="advanced-meta-field">
          <label>Model</label>
          <SelectMenu label="Model" value={modelId} onChange={setModelId} options={modelOptions}/>
        </div>
        {!isEdit && <div className="advanced-meta-field">
          <label>Outputs</label>
          <SelectMenu label="Outputs" value={String(outputs)} onChange={(value) => setOutputs(Number(value))} options={[1, 2, 4].map((value) => ({ value: String(value), label: \`${'${value}'} output${'${value === 1 ? \'\' : \'s\'}'}\` }))}/>
        </div>}
      </div>

      <section className="advanced-settings-card">
        <div className="advanced-section-title"><strong>Sampling</strong><small>Precise controls for reproducibility and guidance.</small></div>
        <div className="advanced-seed-field">
          <div><strong>Seed</strong><small>Use the same seed to reproduce a result.</small></div>
          <div className="advanced-seed-input">
            <input inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} aria-label="Seed"/>
            <button type="button" title="Random seed" aria-label="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={16}/></button>
          </div>
        </div>
        <RangeField label="Steps" help="Sampling iterations" value={steps} onChange={setSteps} min={1} max={50} step={1} decimals={0}/>
        <RangeField label="CFG" help="Prompt guidance strength" value={cfg} onChange={setCfg} min={0} max={20} step={0.1} decimals={1}/>
      </section>

      <section className="advanced-settings-card advanced-execution-card">
        <div className="advanced-section-title"><strong>Execution</strong><small>Backend workflow used for this mode.</small></div>
        <SelectMenu label="Workflow" value={workflowId} onChange={setWorkflowId} options={isEdit ? [{ value: 'flux2-klein-image-edit', label: 'Klein Multi-Reference Edit' }] : [{ value: 'default-image', label: 'Default Image' }]}/>
      </section>

      <button className="reset-button advanced-reset-button" type="button" onClick={() => {
        setOutputs(isEdit ? 1 : 4);
        setSeed('42');
        setSteps(isEdit ? 4 : 30);
        setCfg(isEdit ? 1 : 7);
        setWorkflowId(isEdit ? 'flux2-klein-image-edit' : 'default-image');
        setModelId(isEdit ? 'flux2-klein-9b' : 'saga-image-auto');
      }}><RotateCcw size={17}/> Reset advanced settings</button>
    </div>
  </div>;
}
`;
jsx = jsx.slice(0, settingsStart) + settingsBlock + jsx.slice(settingsEnd);

const indicatorBefore = `  const target = itemRefs.current[hoverIndex];
  const indicatorStyle = target ? {
    width: target.offsetWidth,
    height: target.offsetHeight,
    transform: \`translate3d(${'${target.offsetLeft}'}px, ${'${target.offsetTop}'}px, 0)\`,
    opacity: 1,
  } : { opacity: 0 };`;
const indicatorAfter = `  const target = itemRefs.current[hoverIndex];
  const indicatorStyle = target ? {
    left: 7,
    right: 7,
    width: 'auto',
    height: target.offsetHeight,
    transform: \`translate3d(0, ${'${target.offsetTop}'}px, 0)\`,
    opacity: 1,
  } : { left: 7, right: 7, width: 'auto', opacity: 0 };`;
const indicatorMatches = jsx.split(indicatorBefore).length - 1;
if (indicatorMatches !== 2) throw new Error(`Expected 2 picker indicator blocks, found ${indicatorMatches}`);
jsx = jsx.split(indicatorBefore).join(indicatorAfter);

jsx = replaceOnce(
  jsx,
  `  const resolutionButtonRef = useRef(null);\n  const autoInfoBaselineRef = useRef(null);`,
  `  const resolutionButtonRef = useRef(null);\n  const settingsButtonRef = useRef(null);\n  const autoInfoBaselineRef = useRef(null);`,
  'settings button ref insertion',
);

jsx = replaceOnce(
  jsx,
  `{isEdit && editAuto ? 'A' : String(imageResolution).slice(0, 2)}`,
  `{isEdit && editAuto ? 'A' : String(imageResolution)}`,
  'full resolution number',
);

jsx = replaceOnce(
  jsx,
  `<button type="button" className={\`grok-icon-button grok-settings-button ${'${settingsOpen ? \'selected\' : \'\'}'}\`} title="Advanced settings" aria-label="Advanced settings"`,
  `<button ref={settingsButtonRef} type="button" className={\`grok-icon-button grok-settings-button ${'${settingsOpen ? \'selected\' : \'\'}'}\`} title="Advanced settings" aria-label="Advanced settings"`,
  'settings trigger ref',
);

jsx = replaceOnce(
  jsx,
  `open={settingsOpen} onClose={() => setSettingsOpen(false)} mode={mode}`,
  `open={settingsOpen} onClose={() => setSettingsOpen(false)} anchorRef={settingsButtonRef} mode={mode}`,
  'settings anchor prop',
);

await writeFile(jsxPath, jsx);

let css = await readFile(cssPath, 'utf8');
const cssMarker = '/* v113 advanced settings redesign + picker geometry */';
if (!css.includes(cssMarker)) {
  css += `\n\n${cssMarker}
.workspace .grok-resolution-icon{
  width:auto!important;
  min-width:34px;
  padding:0 6px;
  font-size:9px;
  font-variant-numeric:tabular-nums;
  letter-spacing:-.02em;
}
.workspace .grok-aspect-morph-indicator,
.workspace .grok-resolution-morph-indicator{
  left:7px!important;
  right:7px!important;
  width:auto!important;
}
.workspace .grok-aspect-list button.active,
.workspace .grok-resolution-list button.active{
  background:rgba(122,92,255,.065);
}
.workspace .grok-resolution-list button>span:nth-child(2){
  min-width:78px!important;
  color:#8992a3!important;
  font-variant-numeric:tabular-nums;
}

.workspace .composer-settings-popover.advanced-settings-shell{
  position:fixed!important;
  right:auto!important;
  bottom:auto!important;
  padding:0;
  overflow:auto;
  overscroll-behavior:contain;
  border:1px solid rgba(255,255,255,.11);
  border-radius:20px;
  background:linear-gradient(180deg,rgba(18,22,30,.985),rgba(11,14,20,.992));
  box-shadow:0 28px 80px rgba(0,0,0,.55),0 0 0 1px rgba(122,92,255,.04),inset 0 1px 0 rgba(255,255,255,.035);
  backdrop-filter:blur(18px);
  z-index:2100;
}
.workspace .advanced-settings-header{
  position:sticky;
  top:0;
  z-index:2;
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  padding:18px 18px 15px;
  border-bottom:1px solid rgba(255,255,255,.07);
  background:linear-gradient(180deg,rgba(19,23,32,.99),rgba(16,20,28,.96));
  backdrop-filter:blur(18px);
}
.workspace .advanced-settings-title{min-width:0}
.workspace .advanced-settings-title>span{
  display:block;
  margin-bottom:5px;
  color:#9588e8;
  font-size:9px;
  font-weight:750;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.workspace .advanced-settings-title h2{
  margin:0;
  color:#f4f5f8;
  font-size:18px;
  line-height:1.15;
  letter-spacing:-.02em;
}
.workspace .advanced-settings-title p{
  margin:6px 0 0;
  color:#7f8999;
  font-size:10px;
  line-height:1.4;
}
.workspace .advanced-close-button{
  flex:none;
  width:31px!important;
  height:31px!important;
  border-radius:10px!important;
  background:#171c25!important;
}
.workspace .advanced-settings-body{
  display:grid;
  gap:12px;
  padding:14px;
}
.workspace .advanced-meta-grid{
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(116px,.42fr);
  gap:10px;
}
.workspace .advanced-meta-grid>.advanced-meta-field:only-child{grid-column:1/-1}
.workspace .advanced-meta-field{
  display:grid;
  gap:6px;
}
.workspace .advanced-meta-field>label{
  color:#7e8795;
  font-size:9px;
  font-weight:700;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.workspace .advanced-settings-shell .compact-native-select{
  min-height:39px;
  border:1px solid rgba(255,255,255,.075);
  border-radius:11px;
  background:#11161e;
}
.workspace .advanced-settings-shell .compact-native-select select{
  min-height:39px;
  padding-left:11px;
  color:#e8ebf0;
  font-size:11px;
}
.workspace .advanced-settings-card{
  padding:13px;
  border:1px solid rgba(255,255,255,.07);
  border-radius:15px;
  background:linear-gradient(180deg,rgba(20,25,34,.92),rgba(15,19,27,.92));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.02);
}
.workspace .advanced-section-title{
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  gap:12px;
  margin-bottom:13px;
}
.workspace .advanced-section-title strong{color:#eceef3;font-size:12px}
.workspace .advanced-section-title small{color:#737d8d;font-size:9px;text-align:right}
.workspace .advanced-seed-field{
  display:grid;
  grid-template-columns:minmax(0,1fr) 148px;
  align-items:center;
  gap:14px;
  padding-bottom:12px;
  margin-bottom:12px;
  border-bottom:1px solid rgba(255,255,255,.06);
}
.workspace .advanced-seed-field>div:first-child strong,
.workspace .advanced-range-heading strong{display:block;color:#dfe3e9;font-size:11px}
.workspace .advanced-seed-field>div:first-child small,
.workspace .advanced-range-heading small{display:block;margin-top:3px;color:#737d8d;font-size:9px}
.workspace .advanced-seed-input{
  display:grid;
  grid-template-columns:minmax(0,1fr) 34px;
  min-height:36px;
  border:1px solid rgba(255,255,255,.075);
  border-radius:10px;
  overflow:hidden;
  background:#0e131a;
}
.workspace .advanced-seed-input input{
  min-width:0;
  width:100%;
  border:0;
  outline:0;
  padding:0 10px;
  background:transparent;
  color:#eef1f5;
  font:inherit;
  font-size:11px;
  font-variant-numeric:tabular-nums;
}
.workspace .advanced-seed-input button{
  border:0;
  border-left:1px solid rgba(255,255,255,.06);
  background:transparent;
  color:#8e98aa;
  display:grid;
  place-items:center;
  cursor:pointer;
}
.workspace .advanced-seed-input button:hover{background:#171d27;color:#d9d4ff}
.workspace .advanced-range-field+ .advanced-range-field{margin-top:14px}
.workspace .advanced-range-heading{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  margin-bottom:8px;
}
.workspace .advanced-number-input{
  width:72px;
  height:32px;
  padding:0 8px;
  border:1px solid rgba(255,255,255,.075);
  border-radius:9px;
  outline:0;
  background:#0e131a;
  color:#f0f2f6;
  text-align:right;
  font:inherit;
  font-size:11px;
  font-variant-numeric:tabular-nums;
}
.workspace .advanced-number-input:focus{border-color:rgba(132,108,255,.55);box-shadow:0 0 0 3px rgba(122,92,255,.08)}
.workspace .advanced-range-input{
  width:100%;
  height:18px;
  margin:0;
  accent-color:#806cff;
  cursor:pointer;
}
.workspace .advanced-range-scale{
  display:flex;
  justify-content:space-between;
  margin-top:1px;
  color:#5e6878;
  font-size:8px;
  font-variant-numeric:tabular-nums;
}
.workspace .advanced-execution-card{padding-bottom:12px}
.workspace .advanced-execution-card .advanced-section-title{margin-bottom:10px}
.workspace .advanced-reset-button{
  min-height:40px;
  margin:0!important;
  border-radius:12px!important;
  border:1px solid rgba(122,92,255,.16)!important;
  background:linear-gradient(180deg,rgba(122,92,255,.08),rgba(122,92,255,.035))!important;
  color:#c9c4e8!important;
}
.workspace .advanced-reset-button:hover{border-color:rgba(122,92,255,.3)!important;background:rgba(122,92,255,.12)!important;color:#f0edff!important}

@media (max-width:720px){
  .workspace .advanced-meta-grid{grid-template-columns:1fr}
  .workspace .advanced-meta-grid>.advanced-meta-field{grid-column:1}
  .workspace .advanced-seed-field{grid-template-columns:1fr;gap:8px}
  .workspace .advanced-settings-header{padding:15px 14px 13px}
  .workspace .advanced-settings-body{padding:11px;gap:10px}
}
`;
}
await writeFile(cssPath, css);

let preview = await readFile(previewPath, 'utf8');
const previewStart = preview.indexOf('  const aspectButton = desktop.locator(\'.grok-aspect-button\');');
const previewEnd = preview.indexOf('\n  await desktop.getByRole(\'button\', { name: \'Edit\', exact: true }).click();', previewStart);
if (previewStart < 0 || previewEnd < 0) throw new Error('Could not locate desktop picker test block');
const previewBlock = `  const aspectButton = desktop.locator('.grok-aspect-button');
  await aspectButton.focus();
  await aspectButton.press('ArrowDown');
  const aspectMenu = desktop.locator('.grok-aspect-popover');
  await aspectMenu.waitFor({ state: 'visible' });
  const aspectSelected = aspectMenu.locator('[role="menuitemradio"][aria-checked="true"]');
  const aspectIndicator = aspectMenu.locator('.grok-aspect-morph-indicator');
  const aspectSelectedBox = await aspectSelected.boundingBox();
  const aspectIndicatorBox = await aspectIndicator.boundingBox();
  if (!aspectSelectedBox || !aspectIndicatorBox || Math.abs(aspectSelectedBox.x - aspectIndicatorBox.x) > 3 || Math.abs((aspectSelectedBox.x + aspectSelectedBox.width) - (aspectIndicatorBox.x + aspectIndicatorBox.width)) > 3) {
    throw new Error('Aspect picker default selection indicator does not span the full row');
  }
  await shot(desktop, '03-create-aspect-default-selection.png');
  await aspectMenu.locator('[role="menuitemradio"]').first().press('ArrowDown');
  await desktop.keyboard.press('Escape');
  await assertHidden(aspectMenu, 'Aspect picker');

  const resolutionButton = desktop.locator('.grok-resolution-button');
  await resolutionButton.focus();
  await resolutionButton.press('Enter');
  const resolutionMenu = desktop.locator('.grok-resolution-popover');
  await resolutionMenu.waitFor({ state: 'visible' });
  const resolutionSelected = resolutionMenu.locator('[role="menuitemradio"][aria-checked="true"]');
  const resolutionIndicator = resolutionMenu.locator('.grok-resolution-morph-indicator');
  const resolutionSelectedBox = await resolutionSelected.boundingBox();
  const resolutionIndicatorBox = await resolutionIndicator.boundingBox();
  if (!resolutionSelectedBox || !resolutionIndicatorBox || Math.abs(resolutionSelectedBox.x - resolutionIndicatorBox.x) > 3 || Math.abs((resolutionSelectedBox.x + resolutionSelectedBox.width) - (resolutionIndicatorBox.x + resolutionIndicatorBox.width)) > 3) {
    throw new Error('Resolution picker default selection indicator does not span the full row');
  }
  await shot(desktop, '04-create-resolution-default-selection.png');
  await resolutionMenu.getByRole('menuitemradio', { name: /HD.*1024 px/i }).click();
  const resolutionBadgeText = (await desktop.locator('.grok-resolution-icon').first().innerText()).trim();
  if (resolutionBadgeText !== '1024') throw new Error(\`Resolution toolbar badge expected 1024, got ${'${resolutionBadgeText}'}\`);
  await shot(desktop, '05-create-hd-toolbar.png');

  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings' });
  await settingsButton.click();
  const settingsPanel = desktop.locator('.advanced-settings-shell');
  await settingsPanel.waitFor({ state: 'visible' });
  const settingsBox = await settingsPanel.boundingBox();
  const viewport = desktop.viewportSize();
  if (!settingsBox || !viewport || settingsBox.x < 8 || settingsBox.y < 8 || settingsBox.x + settingsBox.width > viewport.width - 8 || settingsBox.y + settingsBox.height > viewport.height - 8) {
    throw new Error(\`Advanced settings panel is out of bounds: ${'${JSON.stringify(settingsBox)}'}\`);
  }
  if (await settingsPanel.locator('select[aria-label="Steps"]').count()) throw new Error('Steps is still a preset select');
  if (await settingsPanel.locator('select[aria-label="CFG"]').count()) throw new Error('CFG is still a preset select');
  const stepsRange = settingsPanel.locator('input[type="range"][aria-label="Steps"]');
  const cfgRange = settingsPanel.locator('input[type="range"][aria-label="CFG"]');
  await stepsRange.fill('17');
  await cfgRange.fill('2.7');
  if (await stepsRange.inputValue() !== '17') throw new Error('Steps range did not accept a continuous value');
  if (await cfgRange.inputValue() !== '2.7') throw new Error('CFG range did not accept a continuous value');
  await shot(desktop, '06-create-advanced-settings-redesign.png');
  await desktop.mouse.click(1320, 900);
  await assertHidden(settingsPanel, 'Advanced settings');
`;
preview = preview.slice(0, previewStart) + previewBlock + preview.slice(previewEnd);

// Renumber later screenshots only for readability; functionality is unaffected.
preview = preview
  .replaceAll("'05-create-edit-empty.png'", "'07-create-edit-empty.png'")
  .replaceAll("'06-create-edit-reference-uploaded.png'", "'08-create-edit-reference-uploaded.png'")
  .replaceAll("'06-create-edit-auto-aspect.png'", "'09-create-edit-auto-aspect.png'")
  .replaceAll("'07-create-edit-auto-resolution.png'", "'10-create-edit-auto-resolution.png'")
  .replaceAll("'08-create-mobile.png'", "'11-create-mobile.png'");

await writeFile(previewPath, preview);
console.log('Applied Create picker, resolution badge, advanced settings, and visual QA fixes.');
