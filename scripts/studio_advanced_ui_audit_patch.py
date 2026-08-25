#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str, flags: int = re.S) -> str:
    result, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return result


def commit(message: str, *paths: str) -> None:
    subprocess.run(["git", "add", *paths], cwd=ROOT, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        print(f"No changes for {message}")
        return
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)


def phase_steps() -> None:
    controls_path = "apps/studio/src/create-controls.jsx"
    controls = read(controls_path)
    controls = replace_once(
        controls,
        '<span>11 <small>8 + 3</small></span>',
        '<span>11</span>',
        "remove LTX stage arithmetic from Steps value",
    )
    write(controls_path, controls)

    contract_path = "apps/studio/scripts/check-create-advanced-contract.mjs"
    contract = read(contract_path)
    contract = replace_once(
        contract,
        "expect(controls.includes('data-ltx-fixed-steps=\"11\"'), 'LTX fixed 8+3 step recipe must be explicit in Advanced');",
        "expect(controls.includes('data-ltx-fixed-steps=\"11\"'), 'LTX fixed 11-step recipe must be explicit in Advanced');\nexpect(!controls.includes('<small>8 + 3</small>'), 'LTX Steps value must not show internal stage arithmetic beside 11');",
        "update LTX display contract",
    )
    contract = contract.replace(
        "fixed 8+3 recipe, moved video controls",
        "fixed 11-step recipe, moved video controls",
    )
    write(contract_path, contract)
    commit("fix(studio): simplify fixed LTX step display", controls_path, contract_path)


def phase_framerate_popover() -> None:
    controls_path = "apps/studio/src/create-controls.jsx"
    controls = read(controls_path)
    if "from 'react-dom'" not in controls:
        controls = replace_once(
            controls,
            "} from 'react';",
            "} from 'react';\nimport { createPortal } from 'react-dom';",
            "import createPortal",
        )

    fancy = r'''function FancySelect({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const [menuWidth, setMenuWidth] = useState(220);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const popoverRef = useRef(null);
  const optionRefs = useRef([]);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const selected = options[selectedIndex] || options[0];
  const menuHeight = Math.min(260, Math.max(46, options.length * 34 + 10));
  const position = useAnchoredPosition(open, triggerRef, menuWidth, menuHeight);

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  const openMenu = (focusIndex = selectedIndex) => {
    const width = triggerRef.current?.getBoundingClientRect().width;
    setMenuWidth(Math.max(180, Math.round(width || 220)));
    setOpen(true);
    window.setTimeout(() => optionRefs.current[focusIndex]?.focus(), 0);
  };

  useOutsideDismiss(open, [rootRef, popoverRef], () => close(false), triggerRef);

  const move = (index) => {
    const normalized = (index + options.length) % options.length;
    optionRefs.current[normalized]?.focus();
  };

  const handleOptionKeyDown = (event, index) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
    else if (event.key === 'Home') { event.preventDefault(); move(0); }
    else if (event.key === 'End') { event.preventDefault(); move(options.length - 1); }
    else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); }
    else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onChange(options[index].value);
      close(true);
    } else if (event.key === 'Tab') close(false);
  };

  const menu = open && typeof document !== 'undefined' ? createPortal(
    <div
      ref={popoverRef}
      className="saga-fancy-options saga-fancy-options-portal"
      role="listbox"
      aria-label={`${label} options`}
      style={{ position: 'fixed', top: position.top, left: position.left, width: position.width, height: 'auto', maxHeight: position.height }}
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          ref={(node) => { optionRefs.current[index] = node; }}
          type="button"
          role="option"
          aria-selected={option.value === value}
          onKeyDown={(event) => handleOptionKeyDown(event, index)}
          onClick={() => { onChange(option.value); close(true); }}
        >
          <span>{option.label}</span>{option.value === value && <Check size={14} />}
        </button>
      ))}
    </div>,
    document.body,
  ) : null;

  return (
    <div
      className={`saga-fancy-select ${open ? 'open' : ''}`}
      ref={rootRef}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next && (rootRef.current?.contains(next) || popoverRef.current?.contains(next))) return;
        if (open) close(false);
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            openMenu(event.key === 'ArrowUp' ? options.length - 1 : selectedIndex);
          } else if (event.key === 'Escape' && open) {
            event.preventDefault();
            event.stopPropagation();
            close(true);
          }
        }}
        onClick={() => open ? close(false) : openMenu(selectedIndex)}
      >
        <span>{selected?.label}</span><ChevronDown size={14} />
      </button>
      {menu}
    </div>
  );
}

'''
    controls = sub_once(
        controls,
        r"function FancySelect\(\{ label, value, options, onChange \}\) \{.*?\n\}\n\nfunction RangeField",
        fancy + "function RangeField",
        "replace clipped FancySelect with portal",
    )
    write(controls_path, controls)

    css_path = "apps/studio/src/create-workspace-v2.css"
    css = read(css_path)
    css = sub_once(
        css,
        r"\.workspace \.saga-fancy-options\{\n  position:absolute;z-index:40;top:calc\(100% \+ 5px\);left:0;right:0;padding:5px;border:1px solid #303743;border-radius:11px;background:#171c23;box-shadow:0 15px 40px rgba\(0,0,0,.45\);\n\}",
        ".workspace .saga-fancy-options{\n  position:fixed;z-index:2100;padding:5px;border:1px solid #303743;border-radius:11px;background:#171c23;box-shadow:0 15px 40px rgba(0,0,0,.45);overflow:auto;overscroll-behavior:contain;box-sizing:border-box;\n}",
        "make fancy options viewport anchored",
    )
    write(css_path, css)
    commit("fix(studio): portal advanced selects outside scroll clipping", controls_path, css_path)


def phase_image_advanced_and_backend_controls() -> None:
    presets_path = "apps/studio/src/features/create/model-presets.js"
    presets = read(presets_path)
    presets = replace_once(presets, "    cfg: 1.0,\n    stepsEditable: true,", "    cfg: 1.0,\n    negativePrompt: '',\n    stepsEditable: true,", "FLUX negative prompt preset")
    presets = replace_once(presets, "    cfg: 1.0,\n    stepsEditable: false,", "    cfg: 1.0,\n    negativePrompt: '',\n    stepsEditable: false,", "LTX negative prompt preset")
    presets = replace_once(
        presets,
        "export function advancedPresetForMode(mode) {\n  if (mode === 'Edit') return MODEL_ADVANCED_PRESETS['flux2-klein-9b'];\n  if (mode === 'Video') return MODEL_ADVANCED_PRESETS['ltx25-redgraft'];\n  return null;\n}",
        "export function advancedPresetForMode(mode) {\n  if (mode === 'Image' || mode === 'Edit') return MODEL_ADVANCED_PRESETS['flux2-klein-9b'];\n  if (mode === 'Video') return MODEL_ADVANCED_PRESETS['ltx25-redgraft'];\n  return null;\n}",
        "expose FLUX advanced preset in Image setup mode",
    )
    write(presets_path, presets)

    app_path = "apps/studio/src/app/App.jsx"
    app = read(app_path)
    app = replace_once(app, "  const [cfg, setCfg] = useState(1.0);", "  const [cfg, setCfg] = useState(1.0);\n  const [negativePrompt, setNegativePrompt] = useState('');", "add negative prompt state")
    app = replace_once(
        app,
        "  const setCreateMode = (nextMode) => {\n    setMode(nextMode);\n    setError('');\n    const preset = advancedPresetForMode(nextMode);\n    if (preset) {\n      setSeed(preset.seed);\n      setSteps(preset.steps);\n      setCfg(preset.cfg);\n      setWorkflowId(preset.workflowId);\n      setModelId(preset.modelId);\n      return;\n    }\n    if (nextMode === 'Image') {\n      setWorkflowId('default-image');\n      setModelId('saga-image-auto');\n    }\n  };",
        "  const setCreateMode = (nextMode) => {\n    const resolvedMode = nextMode === 'Image' && references.length ? 'Edit' : nextMode;\n    const preserveSampling = resolvedMode === 'Edit' && mode === 'Image';\n    setMode(resolvedMode);\n    setError('');\n    const preset = advancedPresetForMode(resolvedMode);\n    if (preset) {\n      if (!preserveSampling) {\n        setSeed(preset.seed);\n        setSteps(preset.steps);\n        setCfg(preset.cfg);\n        setNegativePrompt(preset.negativePrompt || '');\n      }\n      setWorkflowId(preset.workflowId);\n      setModelId(preset.modelId);\n    }\n  };",
        "make Image setup inherit FLUX and preserve preconfigured sampling",
    )
    app = replace_once(app, "references, seed, steps, cfg, autoEditInfo", "references, seed, steps, cfg, negativePrompt, autoEditInfo", "pass negative prompt to controller")
    app = replace_once(app, "              seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg}", "              seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg} negativePrompt={negativePrompt} setNegativePrompt={setNegativePrompt}", "pass negative prompt to Create workspace")
    write(app_path, app)

    controller_path = "apps/studio/src/hooks/useGenerationController.js"
    controller = read(controller_path)
    controller = replace_once(controller, "seed, steps, cfg, autoEditInfo", "seed, steps, cfg, negativePrompt, autoEditInfo", "controller negative prompt input")
    controller = controller.replace("negativePrompt: '', resolution:", "negativePrompt, resolution:")
    if controller.count("negativePrompt, resolution:") != 1:
        raise RuntimeError("FLUX negative prompt transport patch did not land exactly once")
    controller = controller.replace("prompt: prompt.trim(), resolution: videoResolution", "prompt: prompt.trim(), negativePrompt, resolution: videoResolution")
    if "prompt: prompt.trim(), negativePrompt, resolution: videoResolution" not in controller:
        raise RuntimeError("LTX negative prompt transport patch did not land")
    write(controller_path, controller)

    controls_path = "apps/studio/src/create-controls.jsx"
    controls = read(controls_path)
    controls = replace_once(controls, "  cfg, setCfg, workflowId, setWorkflowId, modelId, setModelId,", "  cfg, setCfg, negativePrompt, setNegativePrompt, workflowId, setWorkflowId, modelId, setModelId,", "AdvancedSettings negative prompt props")
    negative_block = '''
              <label className="saga-negative-prompt">
                <span><strong>Negative prompt</strong><small>Tell the active workflow what to avoid.</small></span>
                <textarea
                  value={negativePrompt}
                  onChange={(event) => setNegativePrompt(event.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder="Optional exclusions…"
                  aria-label="Negative prompt"
                />
              </label>'''
    controls = sub_once(
        controls,
        r'(              <div className="saga-seed-row">.*?
              </div>)',
        lambda match: match.group(1) + negative_block,
        "render backend negative prompt control",
    )
    controls = replace_once(controls, "    setCfg(preset.cfg);\n    setWorkflowId(preset.workflowId);", "    setCfg(preset.cfg);\n    setNegativePrompt(preset.negativePrompt || '');\n    setWorkflowId(preset.workflowId);", "reset negative prompt")
    controls = replace_once(controls, "  seed, setSeed, steps, setSteps, cfg, setCfg,\n  workflowId", "  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,\n  workflowId", "legacy workspace negative prompt props")
    controls = replace_once(controls, "  const isVideo = mode === 'Video';\n  const referenceInputRef", "  const isVideo = mode === 'Video';\n  const isImageSetup = mode === 'Image';\n  const referenceInputRef", "Image setup state")
    controls = replace_once(controls, "  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : mode === 'More' ? 'Creation tools' : 'Imagine worlds';", "  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Prepare an image edit';", "accurate Image heading")
    controls = replace_once(controls, "      const savedMode = ['Image', 'Video', 'More'].includes(saved.mode) ? saved.mode : 'Image';", "      const savedMode = ['Image', 'Video'].includes(saved.mode) ? saved.mode : 'Image';", "remove More persisted mode")
    controls = replace_once(controls, "      if (Number.isFinite(Number(saved.cfg))) setCfg(Math.max(0, Math.min(20, Number(saved.cfg))));", "      if (Number.isFinite(Number(saved.cfg))) setCfg(Math.max(0, Math.min(20, Number(saved.cfg))));\n      if (typeof saved.negativePrompt === 'string') setNegativePrompt(saved.negativePrompt.slice(0, 2000));", "load negative prompt preference")
    controls = replace_once(controls, "      cfg: Number(cfg),\n      workflowId:", "      cfg: Number(cfg),\n      negativePrompt,\n      workflowId:", "persist negative prompt")
    controls = replace_once(controls, "    preferencesReady, mode, isEdit, aspect, imageResolution, outputs, seed, steps, cfg,\n    workflowId", "    preferencesReady, mode, isEdit, aspect, imageResolution, outputs, seed, steps, cfg, negativePrompt,\n    workflowId", "negative prompt persistence dependency")
    controls = sub_once(controls, r"\n  if \(mode === 'More'\) \{.*?\n  \}\n\n  return \(", "\n\n  return (", "remove inert More tools panel")
    controls = replace_once(controls, "          <p>{isEdit ? 'Click a reference to insert it exactly where your cursor is.' : isVideo ? 'Shape the shot, duration, resolution, and audio before generation.' : 'Describe an image, choose the canvas, and iterate.'}</p>", "          <p>{isEdit ? 'Click a reference to insert it exactly where your cursor is.' : isVideo ? 'Shape the shot, duration, resolution, and audio before generation.' : 'Set your image controls now, then add a reference to start the live FLUX edit workflow.'}</p>", "accurate Image setup description")
    controls = replace_once(controls, "          cfg={cfg}\n          setCfg={setCfg}\n          workflowId", "          cfg={cfg}\n          setCfg={setCfg}\n          negativePrompt={negativePrompt}\n          setNegativePrompt={setNegativePrompt}\n          workflowId", "pass negative prompt into Advanced")

    submit_old = '''                title={isEdit ? 'Edit image' : isVideo ? 'Generate video' : 'Generate image'}
                aria-label={isEdit ? 'Edit image' : isVideo ? 'Generate video' : 'Generate image'}
                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio })}
                disabled={busy || (isEdit && references.length === 0)}
              >
                <span className="saga-submit-label">{isEdit ? 'Edit' : 'Generate'}</span>
                <ArrowUp size={18} aria-hidden="true" />'''
    submit_new = '''                title={isImageSetup ? 'Add a reference image to start editing' : isEdit ? 'Edit image' : 'Generate video'}
                aria-label={isImageSetup ? 'Add reference image' : isEdit ? 'Edit image' : 'Generate video'}
                onClick={() => {
                  if (isImageSetup) {
                    referenceInputRef.current?.click();
                    return;
                  }
                  onGenerate({ videoResolution, videoDuration, videoAudio });
                }}
                disabled={busy || (isEdit && references.length === 0)}
              >
                <span className="saga-submit-label">{isImageSetup ? 'Add image' : isEdit ? 'Edit' : 'Generate'}</span>
                {isImageSetup ? <Plus size={18} aria-hidden="true" /> : <ArrowUp size={18} aria-hidden="true" />}'''
    controls = replace_once(controls, submit_old, submit_new, "replace dead Image Generate CTA")

    controls = replace_once(
        controls,
        "onClick={() => setMode('Image')}",
        "onClick={() => { if (visualMode !== 'Image') setMode('Image'); }}",
        "prevent selected Image toggle from dropping Edit mode",
    )
    write(controls_path, controls)

    css_path = "apps/studio/src/create-workspace-v2.css"
    css = read(css_path)
    insert_after = ".workspace .saga-seed-input button{width:33px;height:100%;border:0;border-left:1px solid #2b323d;background:transparent;color:#8993a2;cursor:pointer}\n"
    negative_css = insert_after + ".workspace .saga-negative-prompt{display:block;padding:11px 0 0}\n.workspace .saga-negative-prompt>span{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:7px}\n.workspace .saga-negative-prompt strong{font-size:var(--saga-text-xs);color:#dfe3e9}\n.workspace .saga-negative-prompt small{font-size:8px;color:#687383;text-align:right}\n.workspace .saga-negative-prompt textarea{width:100%;min-height:62px;max-height:140px;box-sizing:border-box;resize:vertical;border:1px solid #2a313b;border-radius:8px;background:#0d1117;color:#fff;font:inherit;font-size:var(--saga-text-xs);line-height:1.45;padding:8px 9px;outline:0}\n.workspace .saga-negative-prompt textarea:focus-visible{outline:var(--saga-focus-ring);outline-offset:2px}\n"
    css = replace_once(css, insert_after, negative_css, "negative prompt styles")
    write(css_path, css)

    commit(
        "feat(studio): expose live image advanced controls and negative prompts",
        presets_path,
        app_path,
        controller_path,
        controls_path,
        css_path,
    )


def phase_ui_audit() -> None:
    sidebar_path = "apps/studio/src/components/Sidebar.jsx"
    write(sidebar_path, '''import React from 'react';
import { Box, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick, title }) {
  return <button type="button" className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} title={title} aria-current={active ? 'page' : undefined}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, mobileOpen, onCloseMobile, onSectionChange }) {
  const chooseSection = (label) => {
    onSectionChange(label);
    onCloseMobile();
  };

  return (
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button type="button" className="mobile-close" aria-label="Close navigation" onClick={onCloseMobile}><ChevronLeft size={19}/></button></div>
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
''')

    models_path = "apps/studio/src/features/catalog/ModelsView.jsx"
    write(models_path, '''import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const models = [
  { name: 'FLUX.2 Klein 9B', detail: 'Reference-based image editing with manual/automatic canvas sizing and multi-reference conditioning.' },
  { name: 'REDGraft LTX 2.5', detail: 'Text-to-video and image-to-video generation with resolution, duration, audio, aspect ratio, frame rate, seed, and CFG controls.' },
];

export default function ModelsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Models" description="Production models currently exposed by the Studio generation registry." />
      <div className="collection-grid">
        {models.map((model) => <article className="collection-card" style={{ padding: 18 }} key={model.name}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>{model.name}</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>{model.detail}</p></article>)}
      </div>
    </section>
  );
}
''')

    workflows_path = "apps/studio/src/features/catalog/WorkflowsView.jsx"
    write(workflows_path, '''import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const workflows = [
  { name: 'Klein Multi-Reference Edit', detail: 'Direct R2 references → Studio orchestration → FLUX.2 Klein worker fleet → persisted R2 image and thumbnail.' },
  { name: 'LTX 2.5 Two-Stage Video', detail: 'Optional R2 image reference → Studio orchestration → REDGraft LTX worker fleet → persisted MP4 and poster.' },
];

export default function WorkflowsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Workflows" description="Registered production generation paths and their current capabilities." />
      <div className="collection-grid">{workflows.map((workflow) => <article className="collection-card" style={{ padding: 18 }} key={workflow.name}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>{workflow.name}</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>{workflow.detail}</p></article>)}</div>
    </section>
  );
}
''')

    settings_path = "apps/studio/src/features/settings/SettingsView.jsx"
    write(settings_path, '''import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Settings" description="Generation controls stay beside the composer so every option is scoped to the active production workflow." action={<button type="button" className="secondary-button" onClick={onOpenGenerationSettings}><SlidersHorizontal size={18}/> Open generation settings</button>} />
      <div className="history-state">Advanced exposes the live workflow's seed, sampling controls, negative prompt, and model-specific output controls. Resolution, duration, and audio remain next to the composer when they are primary generation choices.</div>
    </section>
  );
}
''')

    app_path = "apps/studio/src/app/App.jsx"
    app = read(app_path)
    app = app.replace("  const [advanced, setAdvanced] = useState(true);\n", "")
    app = app.replace("              outputs={outputs} setOutputs={setOutputs} advanced={advanced} setAdvanced={setAdvanced}\n", "              outputs={outputs} setOutputs={setOutputs}\n")
    app = replace_once(app, "        mode={mode}\n        mobileOpen", "        mobileOpen", "remove obsolete mode from Sidebar")
    app = app.replace("        onModeChange={setCreateMode}\n        onClearError={() => setError('')}\n", "")
    write(app_path, app)

    gateway_path = "integrations/comfyui/flux2_klein_gateway.py"
    gateway = read(gateway_path)
    gateway = sub_once(
        gateway,
        r"\n    def _submit_state\(\):\n        state = str\(_state\(\)\.get\(\"state\"\) or \"\"\)\.strip\(\)\n        return \"waking\" if state in \{\"\", \"sleeping\", \"unknown\"\} else state\n\n    def _submit_state\(\):",
        "\n    def _submit_state():",
        "remove duplicated FLUX gateway submit-state helper",
    )
    write(gateway_path, gateway)

    workflow_path = "apps/studio/api/_workflows.js"
    workflows = read(workflow_path)
    # LTX does not consume megapixels; keep the schema honest rather than advertising a phantom default.
    ltx_start = workflows.index("  'ltx25-redgraft-video':")
    before = workflows[:ltx_start]
    after = workflows[ltx_start:]
    after = after.replace("      megapixels: 1.0,\n", "", 1)
    workflows = before + after
    write(workflow_path, workflows)

    css_path = "apps/studio/src/create-workspace-v2.css"
    css = read(css_path)
    css = re.sub(r"\n\.workspace \.saga-more-panel\{[^\n]*\}\n\.workspace \.saga-more-panel strong\{[^\n]*\}\.workspace \.saga-more-panel p\{[^\n]*\}\n", "\n", css, count=1)
    css = css.replace(".workspace .saga-fixed-setting>span small{color:#8c94a2;font-size:9px;font-weight:700}\n", "")
    write(css_path, css)

    contract_path = "apps/studio/scripts/check-ui-audit-contract.mjs"
    write(contract_path, '''import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [controls, presets, app, sidebar, models, workflowsView, settings, controller, client, workflows, gateway] = await Promise.all([
  readFile(new URL('src/create-controls.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('src/components/Sidebar.jsx', root), 'utf8'),
  readFile(new URL('src/features/catalog/ModelsView.jsx', root), 'utf8'),
  readFile(new URL('src/features/catalog/WorkflowsView.jsx', root), 'utf8'),
  readFile(new URL('src/features/settings/SettingsView.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/flux2_klein_gateway.py', root), 'utf8'),
]);

function expect(condition, message) { if (!condition) throw new Error(message); }
expect(!controls.includes('<small>8 + 3</small>'), 'Advanced Steps must show 11 without internal stage arithmetic');
expect(controls.includes("createPortal("), 'Advanced custom selects must render through a viewport portal');
expect(controls.includes('saga-fancy-options-portal'), 'Advanced select portal surface is missing');
expect(/if \(mode === 'Image' \|\| mode === 'Edit'\)/.test(presets), 'Image setup and Edit must share the live FLUX advanced preset');
expect(controls.includes('aria-label="Negative prompt"'), 'Advanced must expose the backend negative-prompt parameter');
expect(controller.includes('negativePrompt, resolution:') && controller.includes('prompt: prompt.trim(), negativePrompt, resolution: videoResolution'), 'Negative prompt must reach both connected workflows');
expect(client.includes('negativePrompt') && client.includes('negativePrompt,'), 'Generation client must transport negative prompt');
expect(controls.includes("isImageSetup ? 'Add image'"), 'Disconnected text-to-image Generate CTA must be replaced by a real add-reference action');
expect(!controls.includes("mode === 'More'") && !sidebar.includes('Additional creation tools') && !sidebar.includes('label="Tools"'), 'Placeholder Tools mode must be removed');
expect(!models.includes('PLANNED') && !models.includes('SAGA Image'), 'Models page must contain only live production models');
expect(workflowsView.includes('Klein Multi-Reference Edit') && workflowsView.includes('LTX 2.5 Two-Stage Video'), 'Workflows page must list both live paths');
expect(settings.includes('negative prompt') && settings.includes('model-specific output controls'), 'Settings help text must match actual controls');
expect((gateway.match(/def _submit_state\(\):/g) || []).length === 1, 'FLUX gateway must not contain duplicate submit-state helpers');
const ltx = workflows.slice(workflows.indexOf("'ltx25-redgraft-video'"));
expect(!/defaults:\s*\{[\s\S]*?megapixels:\s*1\.0/.test(ltx.split('limits:')[0]), 'LTX workflow must not advertise an unused megapixels default');
expect(!app.includes('advanced={advanced}'), 'Dead Advanced state prop must be removed');
console.log('Studio UI audit contract passed: requested controls are fixed, connected backend parameters are exposed, and placeholder/dead surfaces are removed.');
''')

    package_path = "apps/studio/package.json"
    package = read(package_path)
    package = replace_once(package, "node scripts/check-create-advanced-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs", "node scripts/check-create-advanced-contract.mjs && node scripts/check-ui-audit-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs", "wire UI audit contract into build")
    write(package_path, package)

    commit(
        "refactor(studio): remove placeholder surfaces and align live catalog",
        sidebar_path,
        models_path,
        workflows_path,
        settings_path,
        app_path,
        gateway_path,
        workflow_path,
        css_path,
        contract_path,
        package_path,
    )


def phase_preview_contract() -> None:
    path = "apps/studio/scripts/capture-ui-preview.mjs"
    text = read(path)
    text = replace_once(
        text,
        "  // Core composition: no old mode navbar, centered composer, additional creation Tools live in the sidebar.\n  if (await desktop.locator('.create-mode-tabs,.mode-tabs').count()) throw new Error('Old Create mode navbar is still rendered');\n  await desktop.getByRole('button', { name: 'Tools', exact: true }).waitFor({ state: 'visible' });",
        "  // Core composition: no old mode navbar or placeholder Tools surface; Image is a real FLUX setup state.\n  if (await desktop.locator('.create-mode-tabs,.mode-tabs').count()) throw new Error('Old Create mode navbar is still rendered');\n  if (await desktop.getByRole('button', { name: 'Tools', exact: true }).count()) throw new Error('Placeholder Tools navigation is still rendered');",
        "update sidebar visual contract",
    )
    text = replace_once(
        text,
        "  if ((await primarySubmit.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Desktop primary action does not expose the Generate verb');\n  if (await primarySubmit.getAttribute('aria-label') !== 'Generate image') throw new Error('Desktop primary action lost its mode-specific accessible name');",
        "  if ((await primarySubmit.locator('.saga-submit-label').innerText()).trim() !== 'Add image') throw new Error('Image setup primary action must request a real reference image');\n  if (await primarySubmit.getAttribute('aria-label') !== 'Add reference image') throw new Error('Image setup primary action lost its accessible name');",
        "update Image setup primary action visual contract",
    )
    text = text.replace("Desktop Generate action is not visually promoted", "Desktop primary action is not visually promoted")
    text = text.replace("Desktop Generate action styling is not sufficiently primary", "Desktop primary action styling is not sufficiently primary")
    text = text.replace("await expectStrongFocus(primarySubmit, 'Generate primary action');", "await expectStrongFocus(primarySubmit, 'Image setup primary action');")
    old = '''  // Advanced settings in original Image mode must not expose controls with no live workflow.
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
  await expectHidden(advanced, 'Advanced settings');'''
    new = '''  // Image setup Advanced must expose the real FLUX controls that will be used after a reference is attached.
  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });
  await settingsButton.click();
  const advanced = desktop.locator('.saga-advanced-panel');
  await advanced.waitFor({ state: 'visible' });
  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');
  const panelBox = await advanced.boundingBox();
  const viewport = desktop.viewportSize();
  if (!panelBox || !viewport || panelBox.x < 8 || panelBox.y < 8 || panelBox.x + panelBox.width > viewport.width - 8 || panelBox.y + panelBox.height > viewport.height - 8) throw new Error(`Advanced panel out of viewport: ${JSON.stringify(panelBox)}`);
  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="Steps value"]').waitFor({ state: 'visible' });
  await advanced.locator('input[aria-label="CFG value"]').waitFor({ state: 'visible' });
  await advanced.locator('textarea[aria-label="Negative prompt"]').waitFor({ state: 'visible' });
  await shot(desktop, '03-advanced-custom-dropdown.png');
  await settingsButton.click();
  await expectHidden(advanced, 'Advanced settings');'''
    text = replace_once(text, old, new, "update Image advanced visual contract")

    # Ensure the video frame-rate dropdown is fully inside the viewport and all backend-supported FPS choices are visible.
    anchor = "  // Video mode and all requested controls."
    if anchor not in text:
        raise RuntimeError("video section anchor missing")
    # Patch the first frame-rate interaction assertion if the newer capture already contains one; otherwise append a dedicated check before the next screenshot close.
    if "Frame-rate option 30 fps is clipped" not in text:
        marker = "  await shot(desktop, '05-video-advanced-settings.png');"
        if marker in text:
            check = '''  const fpsTrigger = advanced.getByRole('button', { name: 'Video frame rate', exact: true });
  await fpsTrigger.click();
  const fpsMenu = desktop.getByRole('listbox', { name: 'Video frame rate options' });
  await fpsMenu.waitFor({ state: 'visible' });
  for (const label of ['24 fps', '25 fps', '30 fps']) await fpsMenu.getByRole('option', { name: label, exact: true }).waitFor({ state: 'visible' });
  const fpsBox = await fpsMenu.boundingBox();
  const fpsViewport = desktop.viewportSize();
  if (!fpsBox || !fpsViewport || fpsBox.x < 4 || fpsBox.y < 4 || fpsBox.x + fpsBox.width > fpsViewport.width - 4 || fpsBox.y + fpsBox.height > fpsViewport.height - 4) throw new Error(`Frame-rate option 30 fps is clipped: ${JSON.stringify(fpsBox)}`);
  await desktop.keyboard.press('Escape');
'''
            text = text.replace(marker, check + marker, 1)
    write(path, text)
    commit("test(studio): cover repaired Advanced interactions", path)


def main() -> None:
    phase_steps()
    phase_framerate_popover()
    phase_image_advanced_and_backend_controls()
    phase_ui_audit()
    phase_preview_contract()


if __name__ == "__main__":
    main()
