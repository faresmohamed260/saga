from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        if new in text:
            return
        raise SystemExit(f'missing fragment in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# generation-client: surface submitted job immediately and support aborting the poller.
replace('apps/studio/src/generation-client.js',
"export async function waitForGeneration(jobId, { intervalMs = 2000, timeoutMs = 30 * 60 * 1000, onStatus, onWorkerStatus } = {}) {",
"export async function waitForGeneration(jobId, { intervalMs = 2000, timeoutMs = 30 * 60 * 1000, onStatus, onWorkerStatus, signal } = {}) {")
replace('apps/studio/src/generation-client.js',
"  while (Date.now() < deadline) {\n    if (onStatus) onStatus('running');",
"  while (Date.now() < deadline) {\n    if (signal?.aborted) throw new DOMException('Generation cancelled', 'AbortError');\n    if (onStatus) onStatus('running');")
replace('apps/studio/src/generation-client.js',
"      cache: 'no-store',\n    });",
"      cache: 'no-store',\n      signal,\n    });")
replace('apps/studio/src/generation-client.js',
"  const submitted = await submitImageEdit(effectiveInput);\n  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);",
"  const submitted = await submitImageEdit(effectiveInput);\n  if (options.onJob) options.onJob(submitted.job);\n  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);")
replace('apps/studio/src/generation-client.js',
"  const submitted = await submitVideoGeneration(input);\n  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);",
"  const submitted = await submitVideoGeneration(input);\n  if (options.onJob) options.onJob(submitted.job);\n  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);")

# App: retain active job identity and cancellation controller.
replace('apps/studio/src/app/App.jsx',
"  const [workerStatus, setWorkerStatus] = useState(null);\n  const [jobs, setJobs] = useState([]);",
"  const [workerStatus, setWorkerStatus] = useState(null);\n  const [activeJob, setActiveJob] = useState(null);\n  const [cancelBusy, setCancelBusy] = useState(false);\n  const generationAbortRef = React.useRef(null);\n  const [jobs, setJobs] = useState([]);")
replace('apps/studio/src/app/App.jsx',
"    }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus });",
"    }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });")
replace('apps/studio/src/app/App.jsx',
"    }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus });",
"    }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });")
replace('apps/studio/src/app/App.jsx',
"  const generate = async (generationOptions = {}) => {\n    if (busy) return;\n    setBusy(true); setError(''); setJobStatus(''); setWorkerStatus(null);\n    try {",
"  const generate = async (generationOptions = {}) => {\n    if (busy) return;\n    const controller = new AbortController();\n    generationAbortRef.current = controller;\n    setBusy(true); setError(''); setJobStatus(''); setWorkerStatus(null); setActiveJob(null); setCancelBusy(false);\n    try {")
replace('apps/studio/src/app/App.jsx',
"    } catch (err) {\n      setJobStatus('failed');\n      const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || '')) ? String(err.workerState) : 'failed';\n      setWorkerStatus((current) => ({ ...(current || {}), ...(err?.worker || {}), state: terminalWorkerState, errorCode: err?.errorCode || null }));\n      setError(err instanceof Error ? err.message : 'Generation failed.');\n    } finally { setBusy(false); }\n  };",
"    } catch (err) {\n      if (err?.name === 'AbortError') {\n        setJobStatus('cancelled');\n        setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' }));\n        setError('');\n      } else {\n        setJobStatus('failed');\n        const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || '')) ? String(err.workerState) : 'failed';\n        setWorkerStatus((current) => ({ ...(current || {}), ...(err?.worker || {}), state: terminalWorkerState, errorCode: err?.errorCode || null }));\n        setError(err instanceof Error ? err.message : 'Generation failed.');\n      }\n    } finally {\n      if (generationAbortRef.current === controller) generationAbortRef.current = null;\n      setBusy(false);\n      setCancelBusy(false);\n    }\n  };\n\n  const viewActiveJob = () => {\n    setJobsFilter('all');\n    setSection('Jobs');\n  };\n\n  const cancelActiveJob = async () => {\n    if (!busy || !activeJob?.id || cancelBusy) return;\n    if (!window.confirm('Cancel this generation? The provider job will be stopped if it is still running.')) return;\n    setCancelBusy(true);\n    setError('');\n    try {\n      const response = await fetch('/api/job-actions', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json' },\n        body: JSON.stringify({ id: activeJob.id, action: 'cancel' }),\n      });\n      const payload = await response.json().catch(() => ({}));\n      if (!response.ok) throw new Error(payload?.error || `Cancel failed (${response.status})`);\n      setActiveJob(payload?.job || activeJob);\n      setJobStatus('cancelled');\n      setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' }));\n      generationAbortRef.current?.abort();\n    } catch (err) {\n      setError(err instanceof Error ? err.message : 'Unable to cancel generation.');\n      setCancelBusy(false);\n    }\n  };")
replace('apps/studio/src/app/App.jsx',
"              error={error} jobStatus={jobStatus} workerStatus={workerStatus} busy={busy} onGenerate={generate} items={visibleItems} renderCard={renderCard}",
"              error={error} jobStatus={jobStatus} workerStatus={workerStatus} activeJob={activeJob} cancelBusy={cancelBusy} busy={busy} onGenerate={generate} onViewJob={viewActiveJob} onCancelJob={cancelActiveJob} items={visibleItems} renderCard={renderCard}")

# CreateWorkspace: pass lifecycle actions to progress surface.
replace('apps/studio/src/features/create/CreateWorkspace.jsx',
"  const { mode, references = [], busy, jobStatus, workerStatus, onGenerate } = props;",
"  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob } = props;")
replace('apps/studio/src/features/create/CreateWorkspace.jsx',
"        <VideoGenerationProgress busy={busy} status={jobStatus} workerStatus={workerStatus} kind={mode === 'Video' ? 'video' : 'image'} />",
"        <VideoGenerationProgress busy={busy} status={jobStatus} workerStatus={workerStatus} activeJob={activeJob} cancelBusy={cancelBusy} onViewJob={onViewJob} onCancelJob={onCancelJob} kind={mode === 'Video' ? 'video' : 'image'} />")

# Progress UI: add real cancellation state, actions, and next-generation settings note.
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"import { Check, CheckCircle2, ChevronDown, Gauge, LoaderCircle, XCircle } from 'lucide-react';",
"import { Check, CheckCircle2, ChevronDown, ExternalLink, Gauge, LoaderCircle, X, XCircle } from 'lucide-react';")
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"  completed: ['Generation ready', 'The completed result has been saved to Gallery.'],\n  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],",
"  completed: ['Generation ready', 'The completed result has been saved to Gallery.'],\n  cancelled: ['Generation cancelled', 'The running provider job was stopped by request.'],\n  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],")
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"export function VideoGenerationProgress({ busy, status, workerStatus, kind = 'video' }) {",
"export function VideoGenerationProgress({ busy, status, workerStatus, activeJob, cancelBusy = false, onViewJob, onCancelJob, kind = 'video' }) {")
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"    if (status !== 'completed' && status !== 'failed') {",
"    if (status !== 'completed' && status !== 'failed' && status !== 'cancelled') {")
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"  const terminal = normalized === 'completed' || normalized === 'failed' || terminalError;",
"  const terminal = normalized === 'completed' || normalized === 'failed' || normalized === 'cancelled' || terminalError;")
replace('apps/studio/src/features/create/VideoGenerationControls.jsx',
"        <div className={`saga-generation-progress-track ${terminal ? 'terminal' : 'indeterminate'}`} aria-hidden=\"true\">\n          <span />\n        </div>\n      </div>\n    </div>",
"        <div className={`saga-generation-progress-track ${terminal ? 'terminal' : 'indeterminate'}`} aria-hidden=\"true\">\n          <span />\n        </div>\n        {busy && <small className=\"saga-generation-next-note\">Changes to settings now apply to your next generation.</small>}\n        {activeJob?.id && (\n          <div className=\"saga-generation-progress-actions\" aria-label=\"Generation actions\">\n            <button type=\"button\" onClick={onViewJob}><ExternalLink size={14} /> View Job</button>\n            {busy && <button type=\"button\" className=\"danger\" disabled={cancelBusy} onClick={onCancelJob}>{cancelBusy ? <LoaderCircle className=\"spin\" size={14} /> : <X size={14} />} {cancelBusy ? 'Cancelling…' : 'Cancel'}</button>}\n          </div>\n        )}\n      </div>\n    </div>")

# Styling kept in final polish layer to avoid destabilizing the existing compact composer CSS.
p = ROOT / 'apps/studio/src/studio-polish.css'
css = p.read_text(encoding='utf-8')
addition = '''\n\n/* Iteration 12 — generation lifecycle actions */\n.workspace .saga-generation-next-note{display:block;margin-top:7px;color:#7f8999;font-size:10px;line-height:1.4}\n.workspace .saga-generation-progress-actions{display:flex;align-items:center;gap:8px;margin-top:9px;flex-wrap:wrap}\n.workspace .saga-generation-progress-actions button{height:30px;display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 10px;border:1px solid rgba(255,255,255,.12);border-radius:9px;background:rgba(255,255,255,.045);color:#cdd3dc;font-size:10px;font-weight:750;cursor:pointer}\n.workspace .saga-generation-progress-actions button:hover{background:rgba(255,255,255,.08);color:#fff}\n.workspace .saga-generation-progress-actions button:focus-visible{outline:2px solid #9f8cff;outline-offset:2px}\n.workspace .saga-generation-progress-actions button.danger{border-color:rgba(255,100,120,.28);color:#ffb4c0;background:rgba(120,20,35,.12)}\n.workspace .saga-generation-progress-actions button.danger:hover{background:rgba(150,28,48,.2)}\n.workspace .saga-generation-progress-actions button:disabled{opacity:.55;cursor:wait}\n@media(max-width:760px){.workspace .saga-generation-progress-actions{width:100%}.workspace .saga-generation-progress-actions button{min-height:36px;flex:1 1 120px}}\n'''
if 'Iteration 12 — generation lifecycle actions' not in css:
    p.write_text(css + addition, encoding='utf-8')

# Extend visual preview contract with View Job / Cancel / next-generation copy.
p = ROOT / 'apps/studio/scripts/capture-video-output-preview.mjs'
text = p.read_text(encoding='utf-8')
route_anchor = "  await page.route('**/api/generate/result?**', async (route) => {\n"
if "**/api/job-actions" not in text:
    insert = "  await page.route('**/api/job-actions', async (route) => {\n    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ job: { id: '77777777-7777-4777-8777-777777777777', status: 'failed', metadata: { cancelled: true } }, action: 'cancelled' }) });\n  });\n  await page.route('**/api/jobs?**', async (route) => {\n    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ jobs: [{ id: '77777777-7777-4777-8777-777777777777', status: 'running', prompt: 'A slow cinematic camera move through a sunlit coastal landscape', kind: 'video', mode: 'video', model: 'REDGraft LTX 2.5' }] }) });\n  });\n"
    text = text.replace(route_anchor, insert + route_anchor, 1)
old = "  if (!/Switching worker/i.test(progressText) || !/reached its credit limit/i.test(progressText) || !/Standby/.test(progressText)) throw new Error(`Worker credit failover feedback is incomplete: ${progressText}`);\n  await page.screenshot({ path: path.join(outputDir, '05e-video-generation-progress.png'), fullPage: true, animations: 'disabled' });"
new = "  if (!/Switching worker/i.test(progressText) || !/reached its credit limit/i.test(progressText) || !/Standby/.test(progressText)) throw new Error(`Worker credit failover feedback is incomplete: ${progressText}`);\n  if (!/Changes to settings now apply to your next generation/i.test(progressText)) throw new Error(`Running-job settings guidance is missing: ${progressText}`);\n  if (await progress.getByRole('button', { name: 'View Job' }).count() !== 1) throw new Error('Running progress is missing View Job');\n  if (await progress.getByRole('button', { name: 'Cancel' }).count() !== 1) throw new Error('Running progress is missing Cancel');\n  await page.screenshot({ path: path.join(outputDir, '05e-video-generation-progress.png'), fullPage: true, animations: 'disabled' });"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('preview assertion fragment not found')
# Test View Job navigation, return, then cancellation terminal state.
needle = "  diagnostics.screenshots.push('05e-video-generation-progress.png');\n\n  if (diagnostics.pageErrors.length)"
replacement = "  diagnostics.screenshots.push('05e-video-generation-progress.png');\n  await progress.getByRole('button', { name: 'View Job' }).click();\n  await page.waitForURL(/#\\/jobs$/);\n  await page.getByText('Jobs & queue', { exact: true }).waitFor({ state: 'visible' });\n  await page.goto(createUrl, { waitUntil: 'domcontentloaded' });\n  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();\n  await page.locator('.saga-prompt-shell textarea').fill('A second lifecycle cancellation test');\n  page.once('dialog', (dialog) => dialog.accept());\n  await page.getByRole('button', { name: /Generate/i }).click();\n  const cancelProgress = page.locator('.saga-generation-progress');\n  await cancelProgress.getByRole('button', { name: 'Cancel' }).waitFor({ state: 'visible', timeout: 5000 });\n  await cancelProgress.getByRole('button', { name: 'Cancel' }).click();\n  await page.waitForFunction(() => /Generation cancelled/i.test(document.querySelector('.saga-generation-progress')?.innerText || ''), null, { timeout: 5000 });\n  if (!/Generation cancelled/i.test(await cancelProgress.innerText())) throw new Error('Cancelled job did not expose terminal cancellation feedback');\n\n  if (diagnostics.pageErrors.length)"
if needle in text:
    text = text.replace(needle, replacement, 1)
elif replacement not in text:
    raise SystemExit('preview ending fragment not found')
p.write_text(text, encoding='utf-8')

# Mark Item 12 in progress and record scope in canonical checklist; completion happens after visual review.
replace('docs/studio-ui-polish-checklist.md',
"- [ ] **12. Improve generation lifecycle feedback.** Only expose real backend stages, add View Job and Cancel if supported, and clarify that setting edits during a running job apply to the next generation.",
"- [~] **12. Improve generation lifecycle feedback.** Real worker-backed stages are implemented; this iteration adds View Job, real Cancel, and explicit guidance that edits during a running job apply to the next generation. Pending visual/CI review before completion.")
print('Iteration 12 patch applied.')
