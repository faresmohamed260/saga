import { readFile, writeFile } from 'node:fs/promises';

// Final one-shot remote patch used by the PR visual iteration workflow.
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
const morphNeedle = `  const targetIndex = hoverIndex == null ? activeIndex : hoverIndex;\n  const rowHeight = 42;\n\n  const keyDown = (event, index) => {`;
const morphReplacement = `  const targetIndex = hoverIndex == null ? activeIndex : hoverIndex;\n  const rowHeight = 42;\n\n  useEffect(() => {\n    const frame = requestAnimationFrame(() => refs.current[activeIndex]?.focus());\n    return () => cancelAnimationFrame(frame);\n  }, [activeIndex, options.length]);\n\n  const keyDown = (event, index) => {`;
if (create.includes(morphNeedle)) create = create.replace(morphNeedle, morphReplacement);
else if (!create.includes('refs.current[activeIndex]?.focus()')) throw new Error('MorphList focus target not found');

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
