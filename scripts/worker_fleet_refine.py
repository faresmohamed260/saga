from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding='utf-8')

def replace(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise SystemExit(f'anchor missing: {path}: {old[:120]!r}')
    write(path, text.replace(old, new, 1))

# Preserve structured worker error metadata in the browser.
client_path = 'apps/studio/src/generation-client.js'
client = read(client_path)
error_anchor = """async function responseError(response, fallback) {
  try {
    const body = await response.json();
    const detail = body?.error || body?.detail;
    if (detail) return `${fallback} (${response.status}): ${detail}`;
  } catch {}
  return `${fallback} (${response.status})`;
}
"""
if 'async function responseException' not in client:
    if error_anchor not in client:
        raise SystemExit('generation-client error anchor missing')
    client = client.replace(error_anchor, error_anchor + """
async function responseException(response, fallback) {
  let body = {};
  try { body = await response.json(); } catch {}
  const detail = body?.error || body?.detail;
  const error = new Error(detail ? `${fallback} (${response.status}): ${detail}` : `${fallback} (${response.status})`);
  error.statusCode = response.status;
  error.errorCode = body?.errorCode || body?.code || null;
  error.workerState = body?.workerState || body?.worker_state || null;
  error.worker = body?.worker || null;
  return error;
}
""", 1)
client = client.replace("if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit generation'));", "if (response.status !== 202) throw await responseException(response, 'Could not submit generation');", 1)
client = client.replace("if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit video generation'));", "if (response.status !== 202) throw await responseException(response, 'Could not submit video generation');", 1)
client = client.replace("if (!response.ok) throw new Error(await responseError(response, 'Generation failed'));", "if (!response.ok) throw await responseException(response, 'Generation failed');", 1)
write(client_path, client)

replace(
    'apps/studio/src/app/App.jsx',
    """    } catch (err) {
      setJobStatus('failed');
      setWorkerStatus((current) => ({ ...(current || {}), state: 'failed' }));
      setError(err instanceof Error ? err.message : 'Generation failed.');
""",
    """    } catch (err) {
      setJobStatus('failed');
      const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || '')) ? String(err.workerState) : 'failed';
      setWorkerStatus((current) => ({ ...(current || {}), ...(err?.worker || {}), state: terminalWorkerState, errorCode: err?.errorCode || null }));
      setError(err instanceof Error ? err.message : 'Generation failed.');
""",
)

controls_path = 'apps/studio/src/features/create/VideoGenerationControls.jsx'
controls = read(controls_path)
old = """  const normalized = workerStatus?.state || status || (busy ? 'submitting' : 'completed');
  const [baseTitle, baseDetail] = STATUS_COPY[normalized] || STATUS_COPY.running;
  const title = normalized === 'generating' || normalized === 'running' ? `Generating ${kind}` : baseTitle;
  const workerName = workerStatus?.displayName || '';
  const detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;
  const terminal = normalized === 'completed' || normalized === 'failed';
"""
new = """  const normalized = workerStatus?.state || status || (busy ? 'submitting' : 'completed');
  const [baseTitle, baseDetail] = STATUS_COPY[normalized] || STATUS_COPY.running;
  const workerName = workerStatus?.displayName || '';
  const failedWorkers = Array.isArray(workerStatus?.failedWorkers) ? workerStatus.failedWorkers : [];
  const failoverReason = workerStatus?.failoverReason
    || failedWorkers.find((failure) => failure?.kind === 'credit_exhausted')?.kind
    || failedWorkers.find((failure) => failure?.kind === 'unavailable')?.kind
    || '';
  const allCreditsExhausted = workerStatus?.errorCode === 'ALL_WORKERS_CREDIT_EXHAUSTED';
  const terminalError = !busy && status === 'failed';
  let title = normalized === 'generating' || normalized === 'running' ? `Generating ${kind}` : baseTitle;
  let detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;
  if (allCreditsExhausted) {
    title = 'Workers out of credits';
    detail = 'No worker in this model ecosystem currently has available credits. Try again later or choose another model.';
  } else if (busy && failoverReason === 'credit_exhausted') {
    title = 'Switching worker';
    detail = `The previous worker reached its credit limit. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  } else if (busy && failoverReason === 'unavailable') {
    title = 'Switching worker';
    detail = `The previous worker became unavailable. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  }
  const terminal = normalized === 'completed' || normalized === 'failed' || terminalError;
"""
if old not in controls:
    raise SystemExit('lifecycle copy anchor missing')
controls = controls.replace(old, new, 1)
controls = controls.replace("normalized === 'failed' ? <XCircle size={17} />", "terminalError || normalized === 'failed' ? <XCircle size={17} />", 1)
write(controls_path, controls)

# A second accepted request against the single-concurrency ecosystem is queued.
for path in ('integrations/comfyui/flux2_klein_gateway.py', 'integrations/comfyui/ltx23_gateway.py'):
    text = read(path)
    old_state = """    def _submit_state():
        state = str(_state().get("state") or "").strip()
        return "waking" if state in {"", "sleeping", "unknown"} else state
"""
    new_state = """    def _submit_state():
        state = str(_state().get("state") or "").strip()
        if state in {"", "sleeping", "unknown"}:
            return "waking"
        if state in {"generating", "finalizing"}:
            return "queued"
        return state
"""
    if old_state in text:
        text = text.replace(old_state, new_state, 1)
    elif new_state not in text:
        raise SystemExit(f'gateway submit state anchor missing: {path}')
    write(path, text)

# Existing Video visual test now exercises a real credit-to-standby state.
preview_path = 'apps/studio/scripts/capture-video-output-preview.mjs'
preview = read(preview_path)
old_payload = """        workflow: 'ltx25-redgraft-video',
      }),
"""
new_payload = """        workflow: 'ltx25-redgraft-video',
        worker: {
          workerId: 'ltx-standby-01',
          ecosystem: 'ltx25-redgraft',
          displayName: 'REDGraft LTX 2.5 · Standby',
          state: 'waking',
          failedWorkers: [{ workerId: 'ltx-primary-01', kind: 'credit_exhausted', code: 'WORKER_CREDIT_EXHAUSTED' }],
        },
      }),
"""
if old_payload not in preview:
    raise SystemExit('video preview submit payload anchor missing')
preview = preview.replace(old_payload, new_payload, 1)
old_expect = """  const progressText = await progress.innerText();
  if (!/Submitting generation|Generating video|Queued/i.test(progressText)) throw new Error(`Generation feedback did not expose an active state: ${progressText}`);
"""
new_expect = """  const progressText = await progress.innerText();
  if (!/Switching worker/i.test(progressText) || !/reached its credit limit/i.test(progressText) || !/Standby/.test(progressText)) throw new Error(`Worker credit failover feedback is incomplete: ${progressText}`);
"""
if old_expect not in preview:
    raise SystemExit('video preview progress assertion anchor missing')
write(preview_path, preview.replace(old_expect, new_expect, 1))

# Source contract for terminal credit UX and structured errors.
contract_path = 'apps/studio/scripts/check-worker-registry-contract.mjs'
contract = read(contract_path)
marker = "console.log('Modal worker registry contract passed:"
extra = """const clientSource = await readFile(new URL('../src/generation-client.js', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8');
const lifecycleSource = await readFile(new URL('../src/features/create/VideoGenerationControls.jsx', import.meta.url), 'utf8');
assert.ok(clientSource.includes('error.workerState = body?.workerState'), 'Browser client must preserve worker failure metadata');
assert.ok(appSource.includes("terminalWorkerState = ['credit_exhausted', 'unavailable']"), 'App must preserve terminal worker failure state');
assert.ok(lifecycleSource.includes('Workers out of credits'), 'UI must explicitly explain fleet-wide credit exhaustion');
assert.ok(lifecycleSource.includes('previous worker reached its credit limit'), 'UI must explicitly explain credit-driven standby switching');

"""
if extra.strip() not in contract:
    if marker not in contract:
        raise SystemExit('contract insertion anchor missing')
    contract = contract.replace(marker, extra + marker, 1)
write(contract_path, contract)

print('Worker lifecycle UI refinement applied.')
