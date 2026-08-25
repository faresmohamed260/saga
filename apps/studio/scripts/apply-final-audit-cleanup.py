from pathlib import Path
import json
import subprocess

studio = Path.cwd()
repo = studio.parents[1]


def replace(path, old, new, count=1):
    p = repo / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'missing anchor in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')


controls = 'apps/studio/src/create-controls.jsx'
replace(
    controls,
    "  open, onClose, anchorRef, mode, outputs, setOutputs, seed, setSeed, steps, setSteps,\n  cfg, setCfg, negativePrompt, setNegativePrompt, workflowId, setWorkflowId, modelId, setModelId,\n",
    "  open, onClose, anchorRef, mode, seed, setSeed, steps, setSteps,\n  cfg, setCfg, negativePrompt, setNegativePrompt,\n",
)
replace(controls, "                setWorkflowId(preset.workflowId);\n                setModelId(preset.modelId);\n", "")
replace(
    controls,
    "function OutputWall({ items, renderCard }) {\n  return (\n    <section className=\"saga-output-wall\" aria-label=\"Generation outputs\">\n      {items.map((item, index) => (\n        <div className={`saga-output-slot saga-output-slot-${index % 6}`} key={item.id}>\n          {renderCard(item, false)}\n        </div>\n      ))}\n    </section>\n  );\n}",
    "function OutputWall({ items, renderCard }) {\n  if (!items.length) return null;\n  return (\n    <section className=\"saga-recent-work\" aria-label=\"Recent work\">\n      <div className=\"saga-stage-heading saga-results-heading\">\n        <span>RECENT WORK</span>\n        <h2>Your latest creations</h2>\n        <p>Current-session results appear first, followed by relevant Favorites for quick reuse.</p>\n      </div>\n      <div className=\"saga-output-wall\">\n        {items.map((item, index) => (\n          <div className={`saga-output-slot saga-output-slot-${index % 6}`} key={item.id}>\n            {renderCard(item, false)}\n          </div>\n        ))}\n      </div>\n    </section>\n  );\n}",
)
replace(
    controls,
    "  aspect, setAspect, imageResolution, setImageResolution, outputs, setOutputs,\n  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,\n  workflowId, setWorkflowId, modelId, setModelId, settingsOpen, setSettingsOpen, autoEditInfo,\n",
    "  aspect, setAspect, imageResolution, setImageResolution,\n  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,\n  settingsOpen, setSettingsOpen, autoEditInfo,\n",
)
replace(controls, "      if ([1, 2, 4].includes(Number(saved.outputs))) setOutputs(Number(saved.outputs));\n", "")
replace(controls, "      if (typeof saved.workflowId === 'string') setWorkflowId(saved.workflowId);\n      if (typeof saved.modelId === 'string') setModelId(saved.modelId);\n", "")
replace(controls, "      outputs: Number(outputs),\n", "")
replace(controls, "      workflowId: isEdit ? 'default-image' : workflowId,\n      modelId: isEdit ? 'saga-image-auto' : modelId,\n", "")
replace(
    controls,
    "    preferencesReady, mode, isEdit, aspect, imageResolution, outputs, seed, steps, cfg, negativePrompt,\n    workflowId, modelId, editAuto, videoResolution, videoDuration, videoAudio,\n",
    "    preferencesReady, mode, isEdit, aspect, imageResolution, seed, steps, cfg, negativePrompt,\n    editAuto, videoResolution, videoDuration, videoAudio,\n",
)
replace(controls, "          outputs={outputs}\n          setOutputs={setOutputs}\n", "")
replace(controls, "          workflowId={workflowId}\n          setWorkflowId={setWorkflowId}\n          modelId={modelId}\n          setModelId={setModelId}\n", "")

contract = 'apps/studio/scripts/check-create-advanced-contract.mjs'
replace(contract, "expect(!controls.includes('if (isEdit) setOutputs(1)'), 'FLUX preset reset must not silently change output count');\n", "")
replace(
    contract,
    "expect(/item\\.kind === 'video'[\\s\\S]*?setSteps\\(11\\)[\\s\\S]*?setCfg\\(1\\)[\\s\\S]*?ltx25-redgraft-video/.test(await readFile(new URL('src/hooks/useMediaActions.js', root), 'utf8')), 'Reusing a video must restore the LTX production preset');",
    "expect(/item\\.kind === 'video'[\\s\\S]*?setSteps\\(11\\)[\\s\\S]*?setCfg\\(1\\)/.test(await readFile(new URL('src/hooks/useMediaActions.js', root), 'utf8')), 'Reusing a video must restore the LTX production sampling preset');",
)
replace(
    contract,
    "console.log('Create Advanced contract passed: production presets, live LTX CFG transport, fixed 11-step recipe, moved video controls, single audio button, and Favorites-backed Create wall are wired.');",
    "expect(!app.includes('setWorkflowId') && !app.includes('setModelId') && !controls.includes('saved.workflowId') && !controls.includes('saved.modelId'), 'Dead workflow/model presentation state must stay removed from Create');\nexpect(!app.includes('setOutputs') && !controls.includes('saved.outputs'), 'Dead output-count presentation state must stay removed from Create');\nexpect(controls.includes('aria-label=\\\"Recent work\\\"') && controls.includes('Current-session results appear first'), 'Create results must explain session-first Recent work semantics');\nconsole.log('Create Advanced contract passed: production presets, live LTX CFG transport, fixed 11-step recipe, dead presentation plumbing removed, and Recent work is explicit.');",
)

# Light visual spacing for the new Recent work heading.
css = repo / 'apps/studio/src/create-workspace-v2.css'
css_text = css.read_text(encoding='utf-8')
if '.saga-results-heading' not in css_text:
    css_text += "\n.saga-recent-work { margin-top: 34px; }\n.saga-results-heading { margin-bottom: 14px; }\n.saga-results-heading h2 { font-size: clamp(18px, 2vw, 24px); margin: 3px 0 4px; }\n.saga-results-heading p { max-width: 680px; }\n@media (max-width: 760px) { .saga-recent-work { margin-top: 26px; } }\n"
    css.write_text(css_text, encoding='utf-8')

# Record the proven milestone without falsely closing the still-running final audit.
doc = repo / 'docs/studio-ui-ux-benchmark-audit.md'
doc_text = doc.read_text(encoding='utf-8')
doc_text = doc_text.replace('Status: **ACTIVE**', 'Status: **ACTIVE — final audit phase**', 1)
marker = '## Progress log\n\n'
entry = (
    '- 2026-08-25: Studio Browser UX Review #19 passed production build/contracts and the Chromium interaction/visual suite, covering Create/Edit/Video/Advanced, Gallery and manager, Uploads, Jobs, keyboard interactions, responsive widths, reduced motion and touch behavior. The workflow cleanup commit advanced the branch beyond its original trigger.\n'
    '- 2026-08-25: Removed dead Create `outputs`, `workflowId`, and `modelId` React/localStorage plumbing that did not control production execution. Create now labels its mixed session/Favorites surface as Recent work, with session results first. Jobs keeps status/model/progress primary and moves provider/timestamps into Technical details.\n'
)
if entry not in doc_text and marker in doc_text:
    doc_text = doc_text.replace(marker, marker + entry, 1)
doc.write_text(doc_text, encoding='utf-8')

# Remove temporary GitHub helper workflow if it still exists.
helper = repo / '.github/workflows/studio-audit-milestone-cleanup.yml'
if helper.exists():
    helper.unlink()

# Remove this one-shot hook from package.json and then remove this script itself.
pkg = studio / 'package.json'
payload = json.loads(pkg.read_text(encoding='utf-8'))
payload.get('scripts', {}).pop('postinstall', None)
pkg.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
self_path = Path(__file__)
self_path.unlink()

subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=repo, check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=repo, check=True)
subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
status = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=repo)
if status.returncode != 0:
    subprocess.run(['git', 'commit', '-m', 'refactor(studio): finish Create audit cleanup'], cwd=repo, check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:studio/advanced-ui-audit'], cwd=repo, check=True)
