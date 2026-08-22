import { readFile, writeFile } from 'node:fs/promises';

// One-shot remote patch used by the PR visual iteration workflow.
const path = 'src/main.jsx';
let source = await readFile(path, 'utf8');

const oldNav = `<nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => { setSection(label); setMobileNav(false); }} />)}</nav>`;
const newNav = `<nav className="nav-group primary-nav">{navPrimary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label && (label !== 'Create' || mode !== 'More')} onClick={() => { setSection(label); if (label === 'Create' && mode === 'More') setMode('Image'); setMobileNav(false); }} />)}<NavItem icon={Sparkles} label="More" active={section === 'Create' && mode === 'More'} onClick={() => { setSection('Create'); setMode('More'); setError(''); setMobileNav(false); }} /></nav>`;
if (!source.includes(oldNav)) throw new Error('Primary nav target not found');
source = source.replace(oldNav, newNav);

const oldMode = `mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else { setSteps(30); setCfg(7); setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}`;
const newMode = `mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else if (nextMode === 'Video') { setWorkflowId('video-planned'); setModelId('saga-video-auto'); } else if (nextMode === 'Image') { setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}`;
if (!source.includes(oldMode)) throw new Error('CreateWorkspace mode target not found');
source = source.replace(oldMode, newMode);

await writeFile(path, source);
