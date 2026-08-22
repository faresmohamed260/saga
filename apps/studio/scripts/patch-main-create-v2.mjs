import { readFile, writeFile } from 'node:fs/promises';

// Idempotent remote patch used by the PR visual iteration workflow.
const mainPath = 'src/main.jsx';
let main = await readFile(mainPath, 'utf8');

const oldNav = `<nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => { setSection(label); setMobileNav(false); }} />)}</nav>`;
const newNav = `<nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label && (label !== 'Create' || mode !== 'More')} onClick={() => { setSection(label); if (label === 'Create' && mode === 'More') setMode('Image'); setMobileNav(false); }} />)}<NavItem icon={Sparkles} label="More" active={section === 'Create' && mode === 'More'} onClick={() => { setSection('Create'); setMode('More'); setError(''); setMobileNav(false); }} /></nav>`;
if (main.includes(oldNav)) main = main.replace(oldNav, newNav);
else if (!main.includes(newNav)) throw new Error('Primary nav target not found');

const oldMode = `mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else { setSteps(30); setCfg(7); setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}`;
const newMode = `mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else if (nextMode === 'Video') { setWorkflowId('video-planned'); setModelId('saga-video-auto'); } else if (nextMode === 'Image') { setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}`;
if (main.includes(oldMode)) main = main.replace(oldMode, newMode);
else if (!main.includes(newMode)) throw new Error('CreateWorkspace mode target not found');
await writeFile(mainPath, main);

const createPath = 'src/create-controls.jsx';
let create = await readFile(createPath, 'utf8');

const signatureOld = `function MorphList({ options, value, onChoose, render, ariaLabel }) {`;
const signatureNew = `function MorphList({ options, value, onChoose, render, ariaLabel, focusWhen = false }) {`;
if (create.includes(signatureOld)) create = create.replace(signatureOld, signatureNew);
else if (!create.includes(signatureNew)) throw new Error('MorphList signature target not found');

const effectOld = `  useEffect(() => {\n    const frame = requestAnimationFrame(() => refs.current[activeIndex]?.focus());\n    return () => cancelAnimationFrame(frame);\n  }, [activeIndex, options.length]);`;
const effectNew = `  useEffect(() => {\n    if (!focusWhen) return undefined;\n    const frame = requestAnimationFrame(() => refs.current[activeIndex]?.focus());\n    return () => cancelAnimationFrame(frame);\n  }, [focusWhen, activeIndex, options.length]);`;
if (create.includes(effectOld)) create = create.replace(effectOld, effectNew);
else if (!create.includes('if (!focusWhen) return undefined;')) throw new Error('MorphList focus effect target not found');

for (const label of ['Aspect ratio', 'Resolution', 'Video resolution']) {
  const oldCall = `<MorphList\n        ariaLabel="${label}"`;
  const newCall = `<MorphList\n        focusWhen={open}\n        ariaLabel="${label}"`;
  if (create.includes(oldCall)) create = create.replace(oldCall, newCall);
  else if (!create.includes(newCall)) throw new Error(`${label} focus prop target not found`);
}

const persistNeedle = `      workflowId,\n      modelId,\n      editAuto,`;
const persistReplacement = `      workflowId: isEdit ? 'default-image' : workflowId,\n      modelId: isEdit ? 'saga-image-auto' : modelId,\n      editAuto,`;
if (create.includes(persistNeedle)) create = create.replace(persistNeedle, persistReplacement);
else if (!create.includes("workflowId: isEdit ? 'default-image' : workflowId")) throw new Error('Persistence target not found');
await writeFile(createPath, create);

const cssPath = 'src/create-workspace-v2.css';
let css = await readFile(cssPath, 'utf8');
const shellRule = `@media(min-width:901px){\n  .app-shell{grid-template-columns:248px minmax(0,1fr)!important;}\n}\n`;
if (!css.includes('grid-template-columns:248px minmax(0,1fr)!important')) css = `${shellRule}\n${css}`;
await writeFile(cssPath, css);
