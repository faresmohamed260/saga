from pathlib import Path
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count} for {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


def regex_once(path, pattern, repl, flags=0):
    p = Path(path)
    text = p.read_text()
    next_text, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{path}: expected one regex match, found {count}: {pattern}")
    p.write_text(next_text)


wrapper = "apps/studio/src/features/create/CreateWorkspace.jsx"
replace_once(wrapper, "import './image-model-selector.css';\n", "")
replace_once(
    wrapper,
    "  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob, setSteps, setCfg, setNegativePrompt } = props;",
    "  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob, setSteps, setCfg, setNegativePrompt, settingsOpen } = props;",
)
old_model_row = """    <div className=\"saga-create-workspace-shell\">\n      {mode !== 'Video' && (\n        <div className=\"saga-image-model-row\" aria-label=\"Image model selection\">\n          <span className=\"saga-image-model-label\">Image model</span>\n          <div className=\"saga-image-model-switch\" role=\"group\" aria-label=\"Image model\">\n            <button type=\"button\" aria-pressed={imageModel === 'flux2-klein-9b'} className={imageModel === 'flux2-klein-9b' ? 'selected' : ''} onClick={() => chooseImageModel('flux2-klein-9b')}>FLUX</button>\n            <button type=\"button\" aria-pressed={imageModel === 'qwen-image-edit-2511'} className={imageModel === 'qwen-image-edit-2511' ? 'selected' : ''} onClick={() => chooseImageModel('qwen-image-edit-2511')}>Qwen</button>\n          </div>\n          <small>{MODEL_ADVANCED_PRESETS[imageModel].modelLabel}</small>\n        </div>\n      )}"""
new_model_row = """    <div className={`saga-create-workspace-shell ${settingsOpen && mode !== 'Video' ? 'advanced-has-image-model' : ''}`}>\n      {settingsOpen && mode !== 'Video' && (\n        <label className=\"saga-advanced-model-row\">\n          <span>IMAGE MODEL</span>\n          <select aria-label=\"Image model\" value={imageModel} onChange={(event) => chooseImageModel(event.target.value)}>\n            <option value=\"flux2-klein-9b\">FLUX.2 Klein 9B</option>\n            <option value=\"qwen-image-edit-2511\">Qwen Image Edit 2511</option>\n          </select>\n          <small>{MODEL_ADVANCED_PRESETS[imageModel].modelLabel}</small>\n        </label>\n      )}"""
replace_once(wrapper, old_model_row, new_model_row)

controls = "apps/studio/src/create-controls.jsx"
replace_once(
    controls,
    "  RotateCcw, SlidersHorizontal, Sparkles, Video, Volume2, VolumeX, X,\n",
    "  RotateCcw, Sparkles, Video, Volume2, VolumeX, X,\n",
)
replace_once(controls, "  const settingsButtonRef = useRef(null);\n", "")
regex_once(
    controls,
    r"\n              <button\n                ref=\{settingsButtonRef\}[\s\S]*?\n              </button>",
    "",
)
replace_once(
    controls,
    "          anchorRef={settingsButtonRef}\n",
    "          anchorRef={isVideo ? videoResolutionButtonRef : aspectButtonRef}\n",
)
replace_once(controls, "  const isImageSetup = mode === 'Image';\n", "")
old_submit = """              {!isImageSetup && (\n              <button\n                type=\"button\"\n                className=\"saga-submit\"\n                title={isEdit ? 'Edit image' : 'Generate video'}\n                aria-label={isEdit ? 'Edit image' : 'Generate video'}\n                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio })}\n                disabled={busy || (isEdit && references.length === 0)}\n              >\n                <span className=\"saga-submit-label\">{isEdit ? 'Edit' : 'Generate'}</span>\n                <ArrowUp size={18} aria-hidden=\"true\" />\n              </button>\n              )}"""
new_submit = """              <button\n                type=\"button\"\n                className=\"saga-submit\"\n                title={isVideo ? 'Generate video' : references.length ? 'Generate image' : 'Add a reference image to generate'}\n                aria-label={isVideo ? 'Generate video' : 'Generate image'}\n                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio })}\n                disabled={busy || (!isVideo && references.length === 0)}\n              >\n                <span className=\"saga-submit-label\">Generate</span>\n                <ArrowUp size={18} aria-hidden=\"true\" />\n              </button>"""
replace_once(controls, old_submit, new_submit)

css = Path("apps/studio/src/create-workspace-v2.css")
css.write_text(css.read_text() + r"""

/* Requested Create/navigation refinements — right drawer, stable actions, no prompt glow. */
.workspace .saga-prompt-shell textarea:focus,
.workspace .saga-prompt-shell textarea:focus-visible,
.workspace .saga-rich-prompt:focus,
.workspace .saga-rich-prompt:focus-visible{
  outline:0!important;
  box-shadow:none!important;
}
.workspace .saga-composer:focus-within{
  border-color:#262c37;
  box-shadow:0 16px 48px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.02);
}
.workspace .saga-composer.is-edit:focus-within{border-color:#30294b}
.workspace .saga-settings-button{display:none!important}
.workspace .saga-advanced-panel{
  top:0!important;
  right:0!important;
  bottom:0!important;
  left:auto!important;
  width:min(440px,calc(100vw - 24px))!important;
  height:100dvh!important;
  max-height:none!important;
  border-radius:0!important;
  border-top:0;
  border-right:0;
  border-bottom:0;
  visibility:visible!important;
  box-shadow:-24px 0 70px rgba(0,0,0,.52),inset 1px 0 0 rgba(255,255,255,.025);
}
.workspace .advanced-has-image-model .saga-advanced-body{padding-top:108px!important}
.workspace .saga-advanced-model-row{
  position:fixed;
  z-index:1705;
  top:112px;
  right:14px;
  width:min(412px,calc(100vw - 52px));
  display:grid;
  grid-template-columns:minmax(0,1fr);
  gap:6px;
  padding:12px;
  border:1px solid #303641;
  border-radius:12px;
  background:#171b22;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}
.workspace .saga-advanced-model-row>span{color:#8b94a3;font-size:9px;font-weight:850;letter-spacing:.12em}
.workspace .saga-advanced-model-row select{
  width:100%;
  min-height:38px;
  padding:0 11px;
  border:1px solid #343b47;
  border-radius:9px;
  background:#11151b;
  color:#eef0f5;
  outline:0;
}
.workspace .saga-advanced-model-row select:focus-visible{outline:var(--saga-focus-ring);outline-offset:2px}
.workspace .saga-advanced-model-row small{color:#737d8d;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(min-width:981px){
  .app-shell.nav-open{grid-template-columns:248px minmax(0,1fr)!important}
  .app-shell.nav-closed{grid-template-columns:0 minmax(0,1fr)!important}
  .app-shell.nav-closed .sidebar{transform:translateX(-102%);opacity:0;pointer-events:none}
}
""")

Path("apps/studio/src/features/create/create-advanced-mobile.css").write_text(
    """@media (max-width: 720px) {
  .workspace .saga-advanced-panel {
    top: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    left: auto !important;
    width: min(92vw, 420px) !important;
    height: 100dvh !important;
    max-height: none !important;
    border-radius: 0 !important;
  }

  .workspace .saga-advanced-body {
    min-height: 0;
    flex: 1 1 auto;
  }

  .workspace .saga-advanced-model-row {
    top: 112px;
    right: 12px;
    width: min(calc(92vw - 24px), 396px);
  }
}
"""
)

Path("apps/studio/src/components/Sidebar.jsx").write_text(
    """import React, { useEffect, useRef } from 'react';
import { Box, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick, title }) {
  return <button type="button" className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} title={title} aria-current={active ? 'page' : undefined}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, open, onClose, onSectionChange }) {
  const sidebarRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (event) => {
      if (sidebarRef.current?.contains(event.target)) return;
      if (event.target?.closest?.('[data-navigation-trigger="true"]')) return;
      onClose();
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  const chooseSection = (label) => {
    onSectionChange(label);
    onClose();
  };

  return (
    <aside
      ref={sidebarRef}
      className={`sidebar ${open ? 'open' : ''}`}
      aria-hidden={!open}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next && !sidebarRef.current?.contains(next)) onClose();
      }}
    >
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button type="button" className="mobile-close" aria-label="Close navigation" onClick={onClose}><ChevronLeft size={19}/></button></div>
      <nav className="nav-group primary-nav" aria-label="Primary navigation">
        {primary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}
      </nav>
      <div className="nav-divider" />
      <nav className="nav-group" aria-label="Catalog navigation">{secondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}</nav>
      <div className="nav-divider" />
      <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => chooseSection('Settings')} />
      <div className="profile-card sidebar-workspace-card">
        <div className="avatar-orb"/>
        <div className="profile-copy">
          <div className="profile-name">Studio workspace</div>
          <div className="profile-email">Status in Jobs &amp; Models</div>
        </div>
      </div>
    </aside>
  );
}
"""
)

Path("apps/studio/src/components/MobileTopbar.jsx").write_text(
    """import React from 'react';
import { Menu, SlidersHorizontal } from 'lucide-react';

export default function MobileTopbar({ onOpenNavigation, onOpenSettings, navigationOpen = false }) {
  return (
    <div className="mobile-topbar">
      <button className="icon-button" type="button" data-navigation-trigger="true" aria-label="Open navigation" aria-expanded={navigationOpen} onClick={onOpenNavigation}><Menu size={20}/></button>
      <div className="mobile-brand">SAGA Studio</div>
      <button className="icon-button" type="button" aria-label="Open generation settings" onClick={onOpenSettings}><SlidersHorizontal size={20}/></button>
    </div>
  );
}
"""
)

app = "apps/studio/src/app/App.jsx"
replace_once(
    app,
    "  const [mobileNav, setMobileNav] = useState(false);\n",
    "  const [navigationOpen, setNavigationOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth > 980);\n",
)
replace_once(
    app,
    '    <div className="app-shell">\n',
    "    <div className={`app-shell ${navigationOpen ? 'nav-open' : 'nav-closed'}`}>\n",
)
old_sidebar = """      <Sidebar
        section={section}
        mobileOpen={mobileNav}
        onCloseMobile={() => setMobileNav(false)}
        onSectionChange={setSection}
      />"""
new_sidebar = """      <Sidebar
        section={section}
        open={navigationOpen}
        onClose={() => setNavigationOpen(false)}
        onSectionChange={setSection}
      />"""
replace_once(app, old_sidebar, new_sidebar)
replace_once(
    app,
    "        <MobileTopbar onOpenNavigation={() => setMobileNav(true)} onOpenSettings={() => { setSection('Create'); setSettingsOpen(true); }} />",
    "        <MobileTopbar navigationOpen={navigationOpen} onOpenNavigation={() => setNavigationOpen(true)} onOpenSettings={() => { setSection('Create'); setSettingsOpen(true); }} />",
)

styles = Path("apps/studio/src/styles.css")
styles.write_text(styles.read_text() + r"""

/* Universal collapsible navigation and persistent Studio topbar. */
.app-shell{transition:grid-template-columns .22s ease}
.sidebar{width:248px;transition:transform .22s ease,opacity .18s ease}
.mobile-close{display:grid!important;place-items:center;width:32px;height:32px;cursor:pointer;border-radius:9px}
.mobile-topbar{
  display:flex;
  height:64px;
  align-items:center;
  justify-content:space-between;
  border-bottom:1px solid rgba(255,255,255,.07);
  position:sticky;
  top:0;
  z-index:45;
  background:rgba(8,10,15,.92);
  backdrop-filter:blur(16px);
}
.mobile-brand{font-weight:700;font-size:16px}
.mobile-topbar .icon-button{width:40px;height:40px;border:0;background:var(--saga-color-surface-2-alt);border-radius:var(--saga-radius-md);color:#dce0e8;display:grid;place-items:center;cursor:pointer}
@media(max-width:980px){
  .sidebar:not(.open){transform:translateX(-102%)}
}
""")

jobs = "apps/studio/src/features/jobs/JobsView.jsx"
replace_once(jobs, "import React from 'react';\n", "import React, { useEffect, useState } from 'react';\n")
replace_once(jobs, "const STATUS_COPY = {\n", "const JOB_PAGE_SIZE = 10;\n\nconst STATUS_COPY = {\n")
replace_once(
    jobs,
    "export default function JobsView({ jobs, filter, loading, error, actionBusyId, onFilterChange, onJobAction }) {\n  return (",
    "export default function JobsView({ jobs, filter, loading, error, actionBusyId, onFilterChange, onJobAction }) {\n  const [visibleCount, setVisibleCount] = useState(JOB_PAGE_SIZE);\n  useEffect(() => setVisibleCount(JOB_PAGE_SIZE), [filter]);\n  const visibleJobs = jobs.slice(0, visibleCount);\n\n  return (",
)
replace_once(
    jobs,
    ": <div style={{ display: 'grid', gap: 12 }}>{jobs.map((job) => {",
    ': <><div className="jobs-list">{visibleJobs.map((job) => {',
)
replace_once(jobs, "<article key={job.id} style={{", '<article className="job-card" key={job.id} style={{')
replace_once(
    jobs,
    "      })}</div>}\n    </section>",
    "      })}</div>\n      {visibleCount < jobs.length && <div className=\"jobs-list-more\"><button type=\"button\" className=\"secondary-button\" onClick={() => setVisibleCount((current) => Math.min(current + JOB_PAGE_SIZE, jobs.length))}>Show more jobs</button><span>Showing {visibleJobs.length} of {jobs.length}</span></div>}\n      </>}\n    </section>",
)

polish = Path("apps/studio/src/studio-polish.css")
polish.write_text(polish.read_text() + r"""

/* Jobs remain finite and viewport-safe instead of rendering the entire history at once. */
.history-view .jobs-list{display:grid;gap:12px;max-width:100%;min-width:0}
.history-view .job-card{max-width:100%;min-width:0;overflow:hidden}
.history-view .job-card>div{min-width:0;max-width:100%}
.history-view .job-card strong{max-width:100%}
.history-view .saga-generation-progress,.history-view .saga-generation-progress-copy{min-width:0;max-width:100%}
.history-view .jobs-list-more{display:flex;align-items:center;justify-content:center;gap:12px;padding:14px 0 4px;color:var(--saga-color-text-subtle);font-size:var(--saga-text-xs)}
.history-view .jobs-list-more .secondary-button{min-height:40px;padding:0 15px}
@media(max-width:720px){.history-view .jobs-list-more{flex-direction:column}.history-view .jobs-list-more .secondary-button{width:100%;justify-content:center}}
""")

qwen_contract = "apps/studio/scripts/check-qwen-integration-contract.mjs"
replace_once(
    qwen_contract,
    "expect(workspace.includes('aria-label=\"Image model\"') && workspace.includes('>FLUX</button>') && workspace.includes('>Qwen</button>'), 'Image/Edit UI must expose FLUX and Qwen model selection');",
    "expect(workspace.includes('aria-label=\"Image model\"') && workspace.includes('<option value=\"flux2-klein-9b\">FLUX.2 Klein 9B</option>') && workspace.includes('<option value=\"qwen-image-edit-2511\">Qwen Image Edit 2511</option>'), 'Advanced Image/Edit UI must expose FLUX and Qwen in a model dropdown');",
)

qwen_preview = Path("apps/studio/scripts/capture-qwen-model-selector-preview.mjs")
preview_text = qwen_preview.read_text()
start = preview_text.index("  const selector = page.getByRole('group', { name: 'Image model', exact: true });")
end_marker = "  diagnostics.fluxRestored = true;"
end = preview_text.index(end_marker, start) + len(end_marker)
replacement = """  await page.getByRole('button', { name: 'Open generation settings', exact: true }).click();
  const selector = page.getByRole('combobox', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX must be the initial image model');
  await selector.selectOption('qwen-image-edit-2511');
  if (await selector.inputValue() !== 'qwen-image-edit-2511') throw new Error('Qwen model selection did not activate');
  await page.getByText('Qwen Image Edit 2511 · Abliterated BF16 + Lightning', { exact: true }).waitFor({ state: 'visible' });
  await page.getByText('Add an image, describe the change, and generate with the live Qwen edit model.', { exact: true }).waitFor({ state: 'visible' });
  await page.getByText('Reset to Qwen defaults', { exact: true }).waitFor({ state: 'visible' });
  diagnostics.qwenSelected = true;
  diagnostics.qwenLabels = true;
  await page.screenshot({ path: path.join(outputDir, 'qwen-model-selector.png'), fullPage: true, animations: 'disabled' });
  await selector.selectOption('flux2-klein-9b');
  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX model selection did not restore');
  await page.getByText('Add an image, describe the change, and generate with the live FLUX edit model.', { exact: true }).waitFor({ state: 'visible' });
  diagnostics.fluxRestored = true;"""
qwen_preview.write_text(preview_text[:start] + replacement + preview_text[end:])

ui_contract = "apps/studio/scripts/check-ui-audit-contract.mjs"
insert_after = "expect(controls.includes('onDrop={handleReferenceDrop}') && controls.includes('Drop images to upload'), 'Create composer must support image drag-and-drop');\n"
addition = "expect(!controls.includes('ref={settingsButtonRef}'), 'Prompt toolbar must not duplicate the global Advanced trigger');\nexpect(controls.includes('<span className=\"saga-submit-label\">Generate</span>') && controls.includes('disabled={busy || (!isVideo && references.length === 0)}'), 'Generate must remain a separate consistent action across Image/Edit/Video');\nexpect(app.includes('navigationOpen') && sidebar.includes('onBlurCapture') && sidebar.includes('handlePointerDown'), 'Sidebar must collapse from desktop/mobile and dismiss outside by pointer or keyboard focus');\n"
replace_once(ui_contract, insert_after, insert_after + addition)

print("Studio UI patch applied successfully")
