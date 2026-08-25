from pathlib import Path


def replace(path, old, new, count=-1):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'missing patch anchor in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')


replace('scripts/modal_worker_fleet.py',
    '    prefetch = "prefetch_klein" if ecosystem_id == "flux2-klein-9b" else "prefetch_ltx25"\n    prefetch_argument = "False" if ecosystem_id == "flux2-klein-9b" else "True"\n',
    '    prefetch = str(ecosystem.get("prefetchFunction") or "").strip()\n    if not prefetch:\n        raise RuntimeError(f"Ecosystem {ecosystem_id} is missing prefetchFunction")\n    prefetch_argument = "True" if bool(ecosystem.get("prefetchArgument")) else "False"\n')

p = Path('apps/studio/api/_workflows.js')
text = p.read_text(encoding='utf-8')
if "'qwen-image-edit-2511'" not in text:
    qwen = """  'qwen-image-edit-2511': {
    id: 'qwen-image-edit-2511',
    kind: 'image',
    mode: 'edit',
    model: 'Qwen Image Edit 2511 · Official BF16',
    provider: 'modal-qwen-image-edit-2511',
    ecosystem: 'qwen-image-edit-2511',
    requiresSourceImage: true,
    supportsMultipleReferences: true,
    automaticOutputSize: true,
    outputMimeType: 'image/png',
    defaults: { negativePrompt: '', seed: 42, steps: 40, cfg: 4.0, megapixels: 1.0 },
    limits: { maxSourceBytes: 25 * 1024 * 1024, minMegapixels: 0.25, maxMegapixels: 4.0 },
  },
"""
    text = text.replace("  'ltx25-redgraft-video': {", qwen + "  'ltx25-redgraft-video': {")
p.write_text(text, encoding='utf-8')

replace('apps/studio/api/_worker-registry.js',
    "  if (workflow?.provider === 'modal-ltx25-redgraft') {",
    "  if (workflow?.provider === 'modal-qwen-image-edit-2511') {\n    const gatewayUrl = process.env.QWEN_IMAGE_EDIT_2511_GATEWAY_URL || '';\n    return gatewayUrl ? normalizeWorker({ id: 'legacy-qwen-image-edit-2511', ecosystem: workflow.ecosystem || 'qwen-image-edit-2511', displayName: 'Qwen Image Edit 2511', gatewayUrl, role: 'primary' }) : null;\n  }\n  if (workflow?.provider === 'modal-ltx25-redgraft') {")

replace('apps/studio/api/_providers.js',
    "async function submitModalLtx25(workflow, input, options = {}) {",
    "async function submitModalQwenImageEdit(workflow, input, options = {}) {\n  const accepted = await submitWithWorkerFailover(workflow, async (worker) => {\n    const response = await fetchWorker(worker, '/jobs/edit', { method: 'POST', body: buildFluxForm(workflow, input) });\n    if (!response.ok) await responseFailure(response, worker, 'Qwen Image Edit 2511 provider submit failed');\n    const payload = await response.json();\n    if (!payload?.call_id) throw providerFailureError('Qwen Image Edit 2511 provider did not return a call id', { status: 502, body: payload, worker });\n    return { callId: payload.call_id, state: payload.worker_state || payload.workerState || 'queued' };\n  }, options);\n  return { providerJobId: encodeProviderJobId(accepted.worker.id, accepted.callId), provider: workflow.provider, status: 'queued', worker: publicWorkerStatus(accepted.worker, accepted.state, { failedWorkers: accepted.failedWorkers }) };\n}\n\nasync function submitModalLtx25(workflow, input, options = {}) {")
replace('apps/studio/api/_providers.js',
    "async function pollModalLtx25(workflow, providerJobId) {",
    "async function pollModalQwenImageEdit(workflow, providerJobId) {\n  const { worker, callId } = workerForProviderJob(workflow, providerJobId);\n  if (!worker || !callId) throw providerFailureError('Assigned Qwen Image Edit 2511 worker is no longer configured', { worker });\n  const response = await fetchWorker(worker, `/jobs/${encodeURIComponent(callId)}`, { method: 'GET', headers: { Accept: 'image/*, application/json' } });\n  if (response.status === 202) { const payload = await pollWorkerJson(response); return { status: 'running', provider: workflow.provider, worker: publicWorkerStatus(worker, payload.worker_state || payload.workerState || 'generating') }; }\n  if (!response.ok) await responseFailure(response, worker, 'Qwen Image Edit 2511 provider poll failed');\n  const contentType = String(response.headers.get('content-type') || workflow.outputMimeType).split(';')[0].trim();\n  if (!contentType.startsWith('image/')) { const error = new Error('Qwen Image Edit 2511 returned a non-image response'); error.statusCode = 502; throw error; }\n  return { status: 'completed', bytes: Buffer.from(await response.arrayBuffer()), contentType, provider: workflow.provider, worker: publicWorkerStatus(worker, 'finalizing') };\n}\n\nasync function pollModalLtx25(workflow, providerJobId) {")
replace('apps/studio/api/_providers.js',
    "  if (workflow.provider === 'modal-flux2-klein') return submitModalFlux2Klein(workflow, normalized, options);\n  if (workflow.provider === 'modal-ltx25-redgraft') return submitModalLtx25(workflow, normalized, options);",
    "  if (workflow.provider === 'modal-flux2-klein') return submitModalFlux2Klein(workflow, normalized, options);\n  if (workflow.provider === 'modal-qwen-image-edit-2511') return submitModalQwenImageEdit(workflow, normalized, options);\n  if (workflow.provider === 'modal-ltx25-redgraft') return submitModalLtx25(workflow, normalized, options);")
replace('apps/studio/api/_providers.js',
    "  if (workflow.provider === 'modal-flux2-klein') return pollModalFlux2Klein(workflow, providerJobId);\n  if (workflow.provider === 'modal-ltx25-redgraft') return pollModalLtx25(workflow, providerJobId);",
    "  if (workflow.provider === 'modal-flux2-klein') return pollModalFlux2Klein(workflow, providerJobId);\n  if (workflow.provider === 'modal-qwen-image-edit-2511') return pollModalQwenImageEdit(workflow, providerJobId);\n  if (workflow.provider === 'modal-ltx25-redgraft') return pollModalLtx25(workflow, providerJobId);")
replace('apps/studio/api/_providers.js',
    "  if (workflow.provider === 'modal-flux2-klein') return cancelProviderJob(worker, 'FLUX.2', workflow, callId);",
    "  if (workflow.provider === 'modal-flux2-klein') return cancelProviderJob(worker, 'FLUX.2', workflow, callId);\n  if (workflow.provider === 'modal-qwen-image-edit-2511') return cancelProviderJob(worker, 'Qwen Image Edit 2511', workflow, callId);")

replace('apps/studio/src/generation-client.js',
    "export async function submitImageEdit({ sourceFile, sourceFiles, sourceKey, sourceKeys, prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {",
    "export async function submitImageEdit({ workflowId = 'flux2-klein-image-edit', sourceFile, sourceFiles, sourceKey, sourceKeys, prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {")
replace('apps/studio/src/generation-client.js', "      workflowId: 'flux2-klein-image-edit',", "      workflowId,")

p = Path('apps/studio/src/features/create/model-presets.js')
text = p.read_text(encoding='utf-8')
if "'qwen-image-edit-2511': Object.freeze" not in text:
    text = text.replace("  'ltx25-redgraft': Object.freeze({", """  'qwen-image-edit-2511': Object.freeze({
    modelId: 'qwen-image-edit-2511', modelLabel: 'Qwen Image Edit 2511 · Official BF16', workflowId: 'qwen-image-edit-2511', workflowLabel: 'Qwen Image Edit 2511', seed: '42', steps: 40, cfg: 4.0, negativePrompt: '', stepsEditable: true, stepsDetail: '40 official inference steps',
  }),
  'ltx25-redgraft': Object.freeze({""")
text = text.replace("export function advancedPresetForMode(mode) {\n  if (mode === 'Image' || mode === 'Edit') return MODEL_ADVANCED_PRESETS['flux2-klein-9b'];", "export function advancedPresetForMode(mode, imageModel = 'flux2-klein-9b') {\n  if (mode === 'Image' || mode === 'Edit') return MODEL_ADVANCED_PRESETS[imageModel] || MODEL_ADVANCED_PRESETS['flux2-klein-9b'];")
p.write_text(text, encoding='utf-8')

replace('apps/studio/src/hooks/useGenerationController.js',
    "export default function useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {",
    "export default function useGenerationController({ mode, isEdit, imageModel = 'flux2-klein-9b', prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {")
replace('apps/studio/src/hooks/useGenerationController.js', "  const runFluxEdit = async () => {", "  const runImageModelEdit = async () => {")
replace('apps/studio/src/hooks/useGenerationController.js',
    "    const { job, result } = await runImageEdit({ sourceFiles: references.map((reference) => reference.file), prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels },",
    "    const workflowId = imageModel === 'qwen-image-edit-2511' ? 'qwen-image-edit-2511' : 'flux2-klein-image-edit';\n    const modelLabel = imageModel === 'qwen-image-edit-2511' ? 'Qwen Image Edit 2511 · Official BF16' : 'FLUX.2 Klein 9B · DarkBeast V2 BFS';\n    const { job, result } = await runImageEdit({ workflowId, sourceFiles: references.map((reference) => reference.file), prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels },")
replace('apps/studio/src/hooks/useGenerationController.js', "model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS'", "model: modelLabel")
replace('apps/studio/src/hooks/useGenerationController.js', "      if (isEdit) await runFluxEdit();", "      if (isEdit) await runImageModelEdit();")

replace('apps/studio/src/app/App.jsx', "  const [mode, setMode] = useState(initialCreateMode);", "  const [mode, setMode] = useState(initialCreateMode);\n  const [imageModel, setImageModel] = useState('flux2-klein-9b');")
replace('apps/studio/src/app/App.jsx', "    const preset = advancedPresetForMode(resolvedMode);", "    const preset = advancedPresetForMode(resolvedMode, imageModel);")
replace('apps/studio/src/app/App.jsx',
    "  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });",
    "  const setImageModelWithPreset = (nextModel) => { setImageModel(nextModel); const preset = advancedPresetForMode(mode, nextModel); if (preset) { setSteps(preset.steps); setCfg(preset.cfg); setNegativePrompt(preset.negativePrompt || ''); } };\n  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, imageModel, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });")
replace('apps/studio/src/app/App.jsx', "              mode={mode} setMode={setCreateMode}", "              mode={mode} setMode={setCreateMode} imageModel={imageModel} setImageModel={setImageModelWithPreset}")

replace('apps/studio/src/create-controls.jsx', "  open, onClose, anchorRef, mode, seed, setSeed, steps, setSteps,", "  open, onClose, anchorRef, mode, imageModel, seed, setSeed, steps, setSteps,")
replace('apps/studio/src/create-controls.jsx', "  const preset = advancedPresetForMode(mode);", "  const preset = advancedPresetForMode(mode, imageModel);")
replace('apps/studio/src/create-controls.jsx', "  mode, setMode, prompt, setPrompt, references, onAddReferences, onRemoveReference,", "  mode, setMode, imageModel = 'flux2-klein-9b', setImageModel = () => {}, prompt, setPrompt, references, onAddReferences, onRemoveReference,")
replace('apps/studio/src/create-controls.jsx', "              <MediaModeToggle mode={mode} setMode={setMode} />", """              <MediaModeToggle mode={mode} setMode={setMode} />
              {!isVideo && (
                <div className="saga-image-model-switch" role="group" aria-label="Image model">
                  <button type="button" aria-pressed={imageModel === 'flux2-klein-9b'} className={imageModel === 'flux2-klein-9b' ? 'selected' : ''} onClick={() => setImageModel('flux2-klein-9b')}>FLUX</button>
                  <button type="button" aria-pressed={imageModel === 'qwen-image-edit-2511'} className={imageModel === 'qwen-image-edit-2511' ? 'selected' : ''} onClick={() => setImageModel('qwen-image-edit-2511')}>Qwen</button>
                </div>
              )}""")
replace('apps/studio/src/create-controls.jsx', "                mode={mode} seed={seed}", "                mode={mode} imageModel={imageModel} seed={seed}")

css = Path('apps/studio/src/create-workspace-v2.css')
text = css.read_text(encoding='utf-8')
if '.saga-image-model-switch' not in text:
    text += """

.saga-image-model-switch { display:inline-flex; align-items:center; gap:2px; padding:3px; min-height:38px; border:1px solid var(--line,rgba(255,255,255,.11)); border-radius:999px; background:rgba(255,255,255,.035); }
.saga-image-model-switch button { min-height:32px; padding:0 12px; border:0; border-radius:999px; background:transparent; color:var(--muted,#a7a7ad); font:inherit; font-size:12px; font-weight:650; cursor:pointer; }
.saga-image-model-switch button.selected { background:rgba(255,255,255,.11); color:var(--text,#f5f5f7); }
.saga-image-model-switch button:focus-visible { outline:2px solid currentColor; outline-offset:2px; }
@media (max-width:640px) { .saga-image-model-switch button { min-width:48px; min-height:38px; padding:0 10px; } }
"""
css.write_text(text, encoding='utf-8')

replace('.github/workflows/modal-worker-inventory.yml', '  push:\n    branches: [studio/video-gallery-ux]', '  push:\n    branches: [studio/video-gallery-ux, studio/qwen-image-edit-2511]')
replace('.github/workflows/modal-worker-inventory.yml', '      - uses: actions/checkout@v4\n        with:\n          ref: studio/video-gallery-ux', '      - uses: actions/checkout@v4')

doc = Path('docs/modal-worker-fleet-design.md')
text = doc.read_text(encoding='utf-8')
if 'Qwen Image Edit 2511 (official BF16)' not in text:
    text = text.replace('| REDGraft LTX 2.5 | `ltx-primary-01` | `ltx-standby-01` |', '| REDGraft LTX 2.5 | `ltx-primary-01` | `ltx-standby-01` |\n| Qwen Image Edit 2511 (official BF16) | `qwen-primary-01` | `qwen-standby-01` |')
    text += "\n## Qwen Image Edit 2511\n\nQwen uses the official `Qwen/Qwen-Image-Edit-2511` BF16 Diffusers checkpoint without quantization. The runtime uses `QwenImageEditPlusPipeline`, defaults to 40 inference steps, true CFG 4.0, guidance scale 1.0, and an H100-class worker profile. Studio exposes FLUX and Qwen as explicit image-edit model choices while preserving upload, drag/drop, multi-reference, lifecycle, persistence, Gallery, cancellation, and fleet failover behavior.\n"
doc.write_text(text, encoding='utf-8')

print('Qwen integration patch applied')
