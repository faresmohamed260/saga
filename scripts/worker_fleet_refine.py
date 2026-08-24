from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise SystemExit(f"Expected anchor not found in {path}: {old[:180]!r}")
    write(path, content.replace(old, new, 1))


# Preserve structured worker failure metadata in the browser client so terminal
# credit exhaustion is distinguishable from a generic generation failure.
client_path = "apps/studio/src/generation-client.js"
client = read(client_path)
anchor = """async function responseError(response, fallback) {\n  try {\n    const body = await response.json();\n    const detail = body?.error || body?.detail;\n    if (detail) return `${fallback} (${response.status}): ${detail}`;\n  } catch {}\n  return `${fallback} (${response.status})`;\n}\n"""
addition = anchor + """\nasync function responseException(response, fallback) {\n  let body = {};\n  try { body = await response.json(); } catch {}\n  const detail = body?.error || body?.detail;\n  const error = new Error(detail ? `${fallback} (${response.status}): ${detail}` : `${fallback} (${response.status})`);\n  error.statusCode = response.status;\n  error.errorCode = body?.errorCode || body?.code || null;\n  error.workerState = body?.workerState || body?.worker_state || null;\n  error.worker = body?.worker || null;\n  return error;\n}\n"""
if "async function responseException" not in client:
    if anchor not in client:
        raise SystemExit("generation-client responseError anchor missing")
    client = client.replace(anchor, addition, 1)
client = client.replace("if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit generation'));", "if (response.status !== 202) throw await responseException(response, 'Could not submit generation');", 1)
client = client.replace("if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit video generation'));", "if (response.status !== 202) throw await responseException(response, 'Could not submit video generation');", 1)
client = client.replace("if (!response.ok) throw new Error(await responseError(response, 'Generation failed'));", "if (!response.ok) throw await responseException(response, 'Generation failed');", 1)
write(client_path, client)

# App keeps the provider's terminal worker state/error code instead of flattening
# every failure to `failed`.
replace_once(
    "apps/studio/src/app/App.jsx",
    """    } catch (err) {\n      setJobStatus('failed');\n      setWorkerStatus((current) => ({ ...(current || {}), state: 'failed' }));\n      setError(err instanceof Error ? err.message : 'Generation failed.');\n""",
    """    } catch (err) {\n      setJobStatus('failed');\n      const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || ''))\n        ? String(err.workerState)\n        : 'failed';\n      setWorkerStatus((current) => ({\n        ...(current || {}),\n        ...(err?.worker || {}),\n        state: terminalWorkerState,\n        errorCode: err?.errorCode || null,\n      }));\n      setError(err instanceof Error ? err.message : 'Generation failed.');\n""",
)

# The lifecycle surface explicitly distinguishes standby switching from the
# terminal all-workers-out-of-credit case. Text, not color, carries the meaning.
controls_path = "apps/studio/src/features/create/VideoGenerationControls.jsx"
controls = read(controls_path)
old = """  const normalized = workerStatus?.state || status || (busy ? 'submitting' : 'completed');\n  const [baseTitle, baseDetail] = STATUS_COPY[normalized] || STATUS_COPY.running;\n  const title = normalized === 'generating' || normalized === 'running' ? `Generating ${kind}` : baseTitle;\n  const workerName = workerStatus?.displayName || '';\n  const detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;\n  const terminal = normalized === 'completed' || normalized === 'failed';\n  return (\n    <div className={`saga-generation-progress is-${normalized}`} role=\"status\" aria-live=\"polite\">\n      <div className=\"saga-generation-progress-icon\">\n        {normalized === 'completed' ? <CheckCircle2 size={17} /> : normalized === 'failed' ? <XCircle size={17} /> : <LoaderCircle className=\"spin\" size={17} />}\n"""
new = """  const normalized = workerStatus?.state || status || (busy ? 'submitting' : 'completed');\n  const [baseTitle, baseDetail] = STATUS_COPY[normalized] || STATUS_COPY.running;\n  const workerName = workerStatus?.displayName || '';\n  const failedWorkers = Array.isArray(workerStatus?.failedWorkers) ? workerStatus.failedWorkers : [];\n  const failoverReason = workerStatus?.failoverReason\n    || failedWorkers.find((failure) => failure?.kind === 'credit_exhausted')?.kind\n    || failedWorkers.find((failure) => failure?.kind === 'unavailable')?.kind\n    || '';\n  const allCreditsExhausted = workerStatus?.errorCode === 'ALL_WORKERS_CREDIT_EXHAUSTED';\n  const terminalError = !busy && status === 'failed';\n  let title = normalized === 'generating' || normalized === 'running' ? `Generating ${kind}` : baseTitle;\n  let detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;\n  if (allCreditsExhausted) {\n    title = 'Workers out of credits';\n    detail = 'No worker in this model ecosystem currently has available credits. Try again later or choose another model.';\n  } else if (busy && failoverReason === 'credit_exhausted') {\n    title = 'Switching worker';\n    detail = `The previous worker reached its credit limit. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;\n  } else if (busy && failoverReason === 'unavailable') {\n    title = 'Switching worker';\n    detail = `The previous worker became unavailable. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;\n  }\n  const terminal = normalized === 'completed' || normalized === 'failed' || terminalError;\n  return (\n    <div className={`saga-generation-progress is-${normalized}`} role=\"status\" aria-live=\"polite\">\n      <div className=\"saga-generation-progress-icon\">\n        {normalized === 'completed' ? <CheckCircle2 size={17} /> : terminalError || normalized === 'failed' ? <XCircle size={17} /> : <LoaderCircle className=\"spin\" size={17} />}\n"""
if old not in controls:
    raise SystemExit("VideoGenerationProgress rendering anchor missing")
write(controls_path, controls.replace(old, new, 1))

# Gateway submission state is job-specific: an accepted request against a
# sleeping worker is waking, while a request accepted while the single-concurrency
# worker is active is genuinely queued.
for gateway_path in ("integrations/comfyui/flux2_klein_gateway.py", "integrations/comfyui/ltx23_gateway.py"):
    gateway = read(gateway_path)
    old_state = """    def _submit_state():\n        state = str(_state().get(\"state\") or \"\").strip()\n        return \"waking\" if state in {\"\", \"sleeping\", \"unknown\"} else state\n"""
    new_state = """    def _submit_state():\n        state = str(_state().get(\"state\") or \"\").strip()\n        if state in {\"\", \"sleeping\", \"unknown\"}:\n            return \"waking\"\n        if state in {\"generating\", \"finalizing\"}:\n            return \"queued\"\n        return state\n"""
    if old_state in gateway:
        gateway = gateway.replace(old_state, new_state, 1)
    elif new_state not in gateway:
        raise SystemExit(f"Gateway submit-state anchor missing: {gateway_path}")
    write(gateway_path, gateway)

# Make the existing remote visual preview prove the worker lifecycle and terminal
# credit-exhaustion UX rather than only the old generic 'running' state.
preview_path = "apps/studio/scripts/capture-video-output-preview.mjs"
preview = read(preview_path)
preview = preview.replace(
    """  await page.route('**/api/generate', async (route) => {\n    if (route.request().method() !== 'POST') return route.continue();\n    await new Promise((resolve) => setTimeout(resolve, 350));\n    await route.fulfill({\n      status: 202,\n      contentType: 'application/json',\n      body: JSON.stringify({\n        job: { id: '77777777-7777-4777-8777-777777777777' },\n        status: 'running',\n        workflow: 'ltx25-redgraft-video',\n      }),\n    });\n  });\n  await page.route('**/api/generate/result?**', async (route) => {\n    await new Promise((resolve) => setTimeout(resolve, 250));\n    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'running' }) });\n  });\n""",
    """  let mockGenerationScenario = 'lifecycle';\n  let workerPollCount = 0;\n  await page.route('**/api/generate', async (route) => {\n    if (route.request().method() !== 'POST') return route.continue();\n    await new Promise((resolve) => setTimeout(resolve, 350));\n    if (mockGenerationScenario === 'credits') {\n      return route.fulfill({\n        status: 503,\n        contentType: 'application/json',\n        body: JSON.stringify({\n          error: 'All configured workers for ltx25-redgraft have exhausted their available credits',\n          errorCode: 'ALL_WORKERS_CREDIT_EXHAUSTED',\n          workerState: 'credit_exhausted',\n        }),\n      });\n    }\n    await route.fulfill({\n      status: 202,\n      contentType: 'application/json',\n      body: JSON.stringify({\n        job: { id: '77777777-7777-4777-8777-777777777777' },\n        status: 'running',\n        workflow: 'ltx25-redgraft-video',\n        worker: {\n          workerId: 'ltx-standby-01',\n          ecosystem: 'ltx25-redgraft',\n          displayName: 'REDGraft LTX 2.5 · Standby',\n          state: 'waking',\n          failedWorkers: [{ workerId: 'ltx-primary-01', kind: 'credit_exhausted', code: 'WORKER_CREDIT_EXHAUSTED' }],\n        },\n      }),\n    });\n  });\n  await page.route('**/api/generate/result?**', async (route) => {\n    workerPollCount += 1;\n    await new Promise((resolve) => setTimeout(resolve, workerPollCount === 1 ? 900 : 250));\n    const state = workerPollCount === 1 ? 'loading' : 'generating';\n    await route.fulfill({\n      status: 202,\n      contentType: 'application/json',\n      body: JSON.stringify({\n        status: 'running',\n        workerState: state,\n        worker: { workerId: 'ltx-standby-01', ecosystem: 'ltx25-redgraft', displayName: 'REDGraft LTX 2.5 · Standby', state },\n      }),\n    });\n  });\n""",
    1,
)
old_progress = """  const progress = page.locator('.saga-generation-progress');\n  await progress.waitFor({ state: 'visible', timeout: 3000 });\n  const progressText = await progress.innerText();\n  if (!/Submitting generation|Generating video|Queued/i.test(progressText)) throw new Error(`Generation feedback did not expose an active state: ${progressText}`);\n  await page.screenshot({ path: path.join(outputDir, '05e-video-generation-progress.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05e-video-generation-progress.png');\n\n  if (diagnostics.pageErrors.length) throw new Error(`Video output page errors: ${diagnostics.pageErrors.join(' | ')}`);\n"""
new_progress = """  const progress = page.locator('.saga-generation-progress');\n  await progress.waitFor({ state: 'visible', timeout: 3000 });\n  await page.getByText('Switching worker', { exact: true }).waitFor({ state: 'visible', timeout: 3000 });\n  let progressText = await progress.innerText();\n  if (!/previous worker reached its credit limit/i.test(progressText) || !/Standby/.test(progressText)) throw new Error(`Credit failover feedback is incomplete: ${progressText}`);\n  await page.screenshot({ path: path.join(outputDir, '05e-video-generation-progress.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05e-video-generation-progress.png');\n  await page.getByText('Loading model', { exact: true }).waitFor({ state: 'visible', timeout: 5000 });\n  await page.screenshot({ path: path.join(outputDir, '05k-worker-loading.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05k-worker-loading.png');\n\n  mockGenerationScenario = 'credits';\n  workerPollCount = 0;\n  await page.reload({ waitUntil: 'domcontentloaded' });\n  await page.locator('.saga-composer').waitFor({ state: 'visible', timeout: 20_000 });\n  await page.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();\n  await page.locator('.saga-prompt-shell textarea').fill('A quiet cinematic landscape at dusk');\n  await page.getByRole('button', { name: /Generate/i }).click();\n  const creditProgress = page.locator('.saga-generation-progress');\n  await page.getByText('Workers out of credits', { exact: true }).waitFor({ state: 'visible', timeout: 5000 });\n  progressText = await creditProgress.innerText();\n  if (!/No worker in this model ecosystem currently has available credits/i.test(progressText)) throw new Error(`Terminal credit feedback is incomplete: ${progressText}`);\n  await page.screenshot({ path: path.join(outputDir, '05l-workers-credit-exhausted.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('05l-workers-credit-exhausted.png');\n\n  if (diagnostics.pageErrors.length) throw new Error(`Video output page errors: ${diagnostics.pageErrors.join(' | ')}`);\n"""
if old_progress not in preview:
    raise SystemExit("Video preview progress anchor missing")
preview = preview.replace(old_progress, new_progress, 1)
write(preview_path, preview)

# Extend the deterministic worker contract to protect the browser's structured
# terminal credit state and the designed UI copy.
contract_path = "apps/studio/scripts/check-worker-registry-contract.mjs"
contract = read(contract_path)
marker = "console.log('Modal worker registry contract passed:"
addition = """\nconst clientSource = await readFile(new URL('../src/generation-client.js', import.meta.url), 'utf8');\nconst appSource = await readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8');\nconst lifecycleSource = await readFile(new URL('../src/features/create/VideoGenerationControls.jsx', import.meta.url), 'utf8');\nassert.ok(clientSource.includes('ALL_WORKERS_CREDIT_EXHAUSTED') || clientSource.includes('error.workerState = body?.workerState'), 'Browser client must preserve structured worker failure metadata');\nassert.ok(appSource.includes("terminalWorkerState = ['credit_exhausted', 'unavailable']"), 'App must preserve terminal worker state instead of flattening it to failed');\nassert.ok(lifecycleSource.includes('Workers out of credits'), 'Lifecycle UI must explicitly explain all-worker credit exhaustion');\nassert.ok(lifecycleSource.includes('previous worker reached its credit limit'), 'Lifecycle UI must explicitly explain credit-driven standby switching');\n"""
if addition.strip() not in contract:
    if marker not in contract:
        raise SystemExit("Worker contract final marker missing")
    contract = contract.replace(marker, addition + "\n" + marker, 1)
write(contract_path, contract)

print('Worker lifecycle UI refinement applied.')
