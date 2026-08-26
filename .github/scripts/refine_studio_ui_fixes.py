from pathlib import Path
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected 1 match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


def regex_once(path, pattern, repl, flags=0):
    p = Path(path)
    text = p.read_text()
    next_text, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{path}: expected 1 regex match, found {count}: {pattern}")
    p.write_text(next_text)


# Put image-model selection inside the Advanced drawer instead of visually overlaying it from the wrapper.
wrapper = "apps/studio/src/features/create/CreateWorkspace.jsx"
replace_once(
    wrapper,
    "  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob, setSteps, setCfg, setNegativePrompt, settingsOpen } = props;",
    "  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob, setSteps, setCfg, setNegativePrompt } = props;",
)
old_wrapper_open = """    <div className={`saga-create-workspace-shell ${settingsOpen && mode !== 'Video' ? 'advanced-has-image-model' : ''}`}>
      {settingsOpen && mode !== 'Video' && (
        <label className="saga-advanced-model-row">
          <span>IMAGE MODEL</span>
          <select aria-label="Image model" value={imageModel} onChange={(event) => chooseImageModel(event.target.value)}>
            <option value="flux2-klein-9b">FLUX.2 Klein 9B</option>
            <option value="qwen-image-edit-2511">Qwen Image Edit 2511</option>
          </select>
          <small>{MODEL_ADVANCED_PRESETS[imageModel].modelLabel}</small>
        </label>
      )}"""
replace_once(wrapper, old_wrapper_open, '    <div className="saga-create-workspace-shell">')
replace_once(
    wrapper,
    "        imageModelName={imageModel === 'qwen-image-edit-2511' ? 'Qwen' : 'FLUX'}\n        imageModelLabel={imageModel === 'qwen-image-edit-2511' ? 'Qwen Image Edit 2511' : 'FLUX.2 Klein 9B'}",
    "        imageModel={imageModel}\n        onImageModelChange={chooseImageModel}\n        imageModelName={imageModel === 'qwen-image-edit-2511' ? 'Qwen' : 'FLUX'}\n        imageModelLabel={imageModel === 'qwen-image-edit-2511' ? 'Qwen Image Edit 2511' : 'FLUX.2 Klein 9B'}",
)

controls = "apps/studio/src/create-controls.jsx"
replace_once(
    controls,
    "    const onPointer = (event) => {\n      if (refs.some((item) => item.current?.contains(event.target))) return;\n      close();\n    };",
    "    const onPointer = (event) => {\n      if (refs.some((item) => item.current?.contains(event.target))) return;\n      if (protectNestedEscape && event.target?.closest?.('[data-advanced-trigger=\"true\"]')) return;\n      close();\n    };",
)
replace_once(
    controls,
    "  open, onClose, anchorRef, mode, imageModelName = 'FLUX', seed, setSeed, steps, setSteps,\n  cfg, setCfg, negativePrompt, setNegativePrompt,",
    "  open, onClose, anchorRef, mode, imageModel = 'flux2-klein-9b', onImageModelChange = () => {}, imageModelName = 'FLUX', seed, setSeed, steps, setSteps,\n  cfg, setCfg, negativePrompt, setNegativePrompt,",
)
replace_once(
    controls,
    "      <div className=\"saga-advanced-body\">\n        {preset ? (",
    """      <div className="saga-advanced-body">
        {!isVideo && (
          <section className="saga-advanced-card saga-model-selector-card">
            <div className="saga-card-title"><strong>Image model</strong><small>Choose the production image-edit ecosystem.</small></div>
            <FancySelect
              label="Image model"
              value={imageModel}
              options={[
                { value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B' },
                { value: 'qwen-image-edit-2511', label: 'Qwen Image Edit 2511' },
              ]}
              onChange={onImageModelChange}
            />
          </section>
        )}
        {preset ? (""",
)
replace_once(
    controls,
    "  imageModelName = 'FLUX', imageModelLabel = 'FLUX.2 Klein 9B',\n}) {",
    "  imageModel = 'flux2-klein-9b', onImageModelChange = () => {},\n  imageModelName = 'FLUX', imageModelLabel = 'FLUX.2 Klein 9B',\n}) {",
)
replace_once(
    controls,
    "          mode={mode}\n          imageModelName={imageModelName}",
    "          mode={mode}\n          imageModel={imageModel}\n          onImageModelChange={onImageModelChange}\n          imageModelName={imageModelName}",
)

# Keep the global navigation and Advanced buttons as true toggles; Advanced trigger is protected from outside-dismiss.
app = "apps/studio/src/app/App.jsx"
replace_once(
    app,
    "        <MobileTopbar navigationOpen={navigationOpen} onOpenNavigation={() => setNavigationOpen(true)} onOpenSettings={() => { setSection('Create'); setSettingsOpen(true); }} />",
    "        <MobileTopbar navigationOpen={navigationOpen} settingsOpen={settingsOpen} onOpenNavigation={() => setNavigationOpen((current) => !current)} onOpenSettings={() => { setSection('Create'); setSettingsOpen((current) => !current); }} />",
)

Path("apps/studio/src/components/MobileTopbar.jsx").write_text("""import React from 'react';
import { Menu, SlidersHorizontal } from 'lucide-react';

export default function MobileTopbar({ onOpenNavigation, onOpenSettings, navigationOpen = false, settingsOpen = false }) {
  return (
    <div className="mobile-topbar">
      <button className="icon-button" type="button" data-navigation-trigger="true" aria-label="Toggle navigation" aria-expanded={navigationOpen} onClick={onOpenNavigation}><Menu size={20}/></button>
      <div className="mobile-brand">SAGA Studio</div>
      <button className="icon-button" type="button" data-advanced-trigger="true" aria-label="Advanced settings" aria-expanded={settingsOpen} onClick={onOpenSettings}><SlidersHorizontal size={20}/></button>
    </div>
  );
}
""")

# Remove the now-unused overlay model-selector CSS and keep the drawer itself.
css_path = Path("apps/studio/src/create-workspace-v2.css")
css = css_path.read_text()
css = re.sub(r"\n\.workspace \.advanced-has-image-model \.saga-advanced-body\{[^\n]*\}\n\.workspace \.saga-advanced-model-row\{[\s\S]*?\.workspace \.saga-advanced-model-row small\{[^\n]*\}\n", "\n", css, count=1)
css += """
.workspace .saga-model-selector-card .saga-fancy-select{width:100%}
.workspace .saga-model-selector-card .saga-fancy-select>button{min-height:42px;font-weight:700}
"""
css_path.write_text(css)

mobile_css = Path("apps/studio/src/features/create/create-advanced-mobile.css")
mobile = mobile_css.read_text()
mobile = re.sub(r"\n  \.workspace \.saga-advanced-model-row \{[\s\S]*?\n  \}\n", "\n", mobile, count=1)
mobile_css.write_text(mobile)

# Update static contracts to the requested consistent Generate action and Advanced model dropdown.
generate_contract = "apps/studio/scripts/check-generate-action-contract.mjs"
replace_once(
    generate_contract,
    "requireSource(controls, '<span className=\"saga-submit-label\">{isEdit ? \\\'Edit\\\' : \\\'Generate\\\'}</span>', 'connected generation verb markup');",
    "requireSource(controls, '<span className=\"saga-submit-label\">Generate</span>', 'consistent connected generation verb markup');",
)
replace_once(
    generate_contract,
    "requireSource(visual, \"Edit mode primary action does not expose its principal Edit verb\", 'Edit-mode Playwright assertion');",
    "requireSource(visual, \"Edit mode primary action does not retain the Generate verb\", 'Edit-mode Playwright assertion');",
)

qwen_contract = "apps/studio/scripts/check-qwen-integration-contract.mjs"
replace_once(
    qwen_contract,
    "expect(workspace.includes('aria-label=\"Image model\"') && workspace.includes('<option value=\"flux2-klein-9b\">FLUX.2 Klein 9B</option>') && workspace.includes('<option value=\"qwen-image-edit-2511\">Qwen Image Edit 2511</option>'), 'Advanced Image/Edit UI must expose FLUX and Qwen in a model dropdown');",
    "expect(workspace.includes('imageModel={imageModel}') && workspace.includes('onImageModelChange={chooseImageModel}') && controls.includes('label=\"Image model\"') && controls.includes(\"{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B' }\") && controls.includes(\"{ value: 'qwen-image-edit-2511', label: 'Qwen Image Edit 2511' }\"), 'Advanced Image/Edit UI must expose FLUX and Qwen in a model dropdown');",
)
# The Qwen contract now reads controls too.
replace_once(
    qwen_contract,
    "const [ecosystemsRaw, workflows, presets, workspace, controller, client, runtime, gateway, registry, civitaiPrefetch] = await Promise.all([",
    "const [ecosystemsRaw, workflows, presets, workspace, controls, controller, client, runtime, gateway, registry, civitaiPrefetch] = await Promise.all([",
)
replace_once(
    qwen_contract,
    "  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),\n  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),",
    "  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),\n  readFile(new URL('src/create-controls.jsx', root), 'utf8'),\n  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),",
)

# Browser review: initial Image keeps a separate disabled Generate control, Advanced is a right drawer, and Edit says Generate.
preview = "apps/studio/scripts/capture-ui-preview.mjs"
replace_once(
    preview,
    "  if (await desktop.locator('.saga-submit').count()) throw new Error('Image setup still exposes a wide submit-style Add image action');",
    "  const imageGenerate = desktop.locator('.saga-submit');\n  await imageGenerate.waitFor({ state: 'visible' });\n  if ((await imageGenerate.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Image setup primary action must retain the Generate verb');\n  if (!(await imageGenerate.isDisabled())) throw new Error('Image setup Generate must remain disabled until a reference is attached');",
)
replace_once(
    preview,
    "  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });",
    "  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings', exact: true });",
)
replace_once(
    preview,
    "  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');\n  const panelBox = await advanced.boundingBox();\n  const viewport = desktop.viewportSize();\n  if (!panelBox || !viewport || panelBox.x < 8 || panelBox.y < 8 || panelBox.x + panelBox.width > viewport.width - 8 || panelBox.y + panelBox.height > viewport.height - 8) throw new Error(`Advanced panel out of viewport: ${JSON.stringify(panelBox)}`);",
    "  if (await advanced.locator('select').count()) throw new Error('Native select found inside advanced settings');\n  await advanced.getByRole('button', { name: 'Image model', exact: true }).waitFor({ state: 'visible' });\n  const panelBox = await advanced.boundingBox();\n  const viewport = desktop.viewportSize();\n  if (!panelBox || !viewport || panelBox.x < 0 || panelBox.y < 0 || Math.abs(panelBox.x + panelBox.width - viewport.width) > 2 || Math.abs(panelBox.height - viewport.height) > 2) throw new Error(`Advanced right drawer is not viewport-aligned: ${JSON.stringify(panelBox)}`);",
)
replace_once(
    preview,
    "Edit mode primary action does not expose its principal Edit verb",
    "Edit mode primary action does not retain the Generate verb",
)
replace_once(
    preview,
    "if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Edit') throw new Error('Edit mode primary action does not retain the Generate verb');",
    "if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Edit mode primary action does not retain the Generate verb');",
)

# Qwen browser preview now drives the custom Advanced dropdown instead of a top-level/native selector.
qwen_preview = "apps/studio/scripts/capture-qwen-model-selector-preview.mjs"
qp = Path(qwen_preview).read_text()
old = """  await page.getByRole('button', { name: 'Open generation settings', exact: true }).click();
  const selector = page.getByRole('combobox', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX must be the initial image model');
  await selector.selectOption('qwen-image-edit-2511');
  if (await selector.inputValue() !== 'qwen-image-edit-2511') throw new Error('Qwen model selection did not activate');"""
new = """  await page.getByRole('button', { name: 'Advanced settings', exact: true }).click();
  const selector = page.getByRole('button', { name: 'Image model', exact: true });
  await selector.waitFor({ state: 'visible', timeout: 20_000 });
  if (!(await selector.innerText()).includes('FLUX.2 Klein 9B')) throw new Error('FLUX must be the initial image model');
  await selector.click();
  await page.getByRole('option', { name: 'Qwen Image Edit 2511', exact: true }).click();
  if (!(await selector.innerText()).includes('Qwen Image Edit 2511')) throw new Error('Qwen model selection did not activate');"""
if old not in qp:
    raise SystemExit('qwen preview initial selector block not found')
qp = qp.replace(old, new, 1)
qp = qp.replace("  await selector.selectOption('flux2-klein-9b');\n  if (await selector.inputValue() !== 'flux2-klein-9b') throw new Error('FLUX model selection did not restore');", "  await selector.click();\n  await page.getByRole('option', { name: 'FLUX.2 Klein 9B', exact: true }).click();\n  if (!(await selector.innerText()).includes('FLUX.2 Klein 9B')) throw new Error('FLUX model selection did not restore');", 1)
Path(qwen_preview).write_text(qp)

print('Refinement patch applied')
