import { GENERATED_MODAL_WORKERS } from './_worker-registry.generated.js';

const CREDIT_PATTERNS = [
  'credit', 'credits', 'quota', 'budget', 'billing', 'payment', 'insufficient',
  'spending limit', 'spend limit', 'workspace budget', 'out of funds', 'balance',
];
const UNAVAILABLE_PATTERNS = [
  'workspace is disabled', 'workspace disabled', 'disabled workspace',
  'temporarily unavailable', 'app is stopped', 'app stopped',
];

function cleanText(value) {
  return String(value || '').trim();
}

function normalizeWorker(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  const id = cleanText(raw.id || raw.workerId);
  const ecosystem = cleanText(raw.ecosystem || raw.ecosystemId);
  const gatewayUrl = cleanText(raw.gatewayUrl || raw.gateway_url).replace(/\/$/, '');
  if (!id || !ecosystem || !gatewayUrl) return null;
  return {
    id,
    ecosystem,
    gatewayUrl,
    displayName: cleanText(raw.displayName || raw.display_name) || ecosystem,
    accountLabel: cleanText(raw.accountLabel || raw.account || raw.account_label),
    role: cleanText(raw.role || 'primary').toLowerCase() === 'standby' ? 'standby' : 'primary',
    enabled: raw.enabled !== false,
    version: cleanText(raw.version || 'v1'),
    order: Number.isFinite(Number(raw.order)) ? Number(raw.order) : index,
  };
}

function envWorkers() {
  const raw = cleanText(process.env.SAGA_MODAL_WORKER_REGISTRY_JSON);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    const rows = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.workers) ? parsed.workers : [];
    return rows.map(normalizeWorker).filter(Boolean);
  } catch (error) {
    console.error('Invalid SAGA_MODAL_WORKER_REGISTRY_JSON', error);
    return [];
  }
}

function legacyWorker(workflow) {
  if (workflow?.ecosystem === 'qwen-image-edit-2511') return null;
  if (workflow?.provider === 'modal-flux2-klein') {
    return normalizeWorker({
      id: 'legacy-flux2-klein',
      ecosystem: workflow.ecosystem || 'flux2-klein-9b',
      displayName: 'FLUX.2 Klein 9B',
      gatewayUrl: process.env.FLUX2_KLEIN_GATEWAY_URL || 'https://faresmohamed260--saga-flux2-klein-gateway-web.modal.run',
      role: 'primary',
    });
  }
  if (workflow?.provider === 'modal-ltx25-redgraft') {
    return normalizeWorker({
      id: 'legacy-ltx25-redgraft',
      ecosystem: workflow.ecosystem || 'ltx25-redgraft',
      displayName: 'REDGraft LTX 2.5',
      gatewayUrl: process.env.LTX25_GATEWAY_URL || 'https://faresmohamed260--saga-ltx25-gateway-web.modal.run',
      role: 'primary',
    });
  }
  return null;
}

export function listConfiguredWorkers() {
  const merged = [...envWorkers(), ...(Array.isArray(GENERATED_MODAL_WORKERS) ? GENERATED_MODAL_WORKERS : [])]
    .map(normalizeWorker)
    .filter(Boolean);
  const unique = new Map();
  for (const worker of merged) if (!unique.has(worker.id)) unique.set(worker.id, worker);
  return [...unique.values()];
}

export function workersForWorkflow(workflow, { excludeWorkerIds = [] } = {}) {
  const ecosystem = cleanText(workflow?.ecosystem);
  const excluded = new Set((excludeWorkerIds || []).map(cleanText).filter(Boolean));
  const fleet = listConfiguredWorkers()
    .filter((worker) => worker.enabled && worker.ecosystem === ecosystem);
  const configured = fleet
    .filter((worker) => !excluded.has(worker.id))
    .sort((a, b) => {
      const role = (a.role === 'primary' ? 0 : 1) - (b.role === 'primary' ? 0 : 1);
      return role || a.order - b.order || a.id.localeCompare(b.id);
    });
  if (fleet.length) return configured;
  const legacy = legacyWorker(workflow);
  return legacy && !excluded.has(legacy.id) ? [legacy] : [];
}

export function encodeProviderJobId(workerId, callId) {
  const payload = Buffer.from(JSON.stringify({ v: 1, workerId: cleanText(workerId), callId: cleanText(callId) }), 'utf8').toString('base64url');
  return `saga-worker:${payload}`;
}

export function decodeProviderJobId(providerJobId) {
  const raw = cleanText(providerJobId);
  if (!raw.startsWith('saga-worker:')) return { workerId: '', callId: raw, legacy: true };
  try {
    const payload = JSON.parse(Buffer.from(raw.slice('saga-worker:'.length), 'base64url').toString('utf8'));
    return { workerId: cleanText(payload?.workerId), callId: cleanText(payload?.callId), legacy: false };
  } catch {
    return { workerId: '', callId: raw, legacy: true };
  }
}

export function workerForProviderJob(workflow, providerJobId) {
  const decoded = decodeProviderJobId(providerJobId);
  if (decoded.legacy) return { worker: legacyWorker(workflow) || workersForWorkflow(workflow)[0] || null, callId: decoded.callId };
  const worker = listConfiguredWorkers().find((candidate) => candidate.id === decoded.workerId)
    || workersForWorkflow(workflow).find((candidate) => candidate.id === decoded.workerId)
    || null;
  return { worker, callId: decoded.callId };
}

function errorText({ body, error } = {}) {
  const pieces = [];
  if (body && typeof body === 'object') pieces.push(body.error, body.detail, body.errorCode, body.code, body.workerState, body.worker_state);
  else pieces.push(body);
  if (error) pieces.push(error.message, error.name, error.cause?.message);
  return pieces.filter(Boolean).join(' ').toLowerCase();
}

export function classifyWorkerFailure({ status = 0, body = null, error = null } = {}) {
  const text = errorText({ body, error });
  const explicitState = cleanText(body?.workerState || body?.worker_state).toLowerCase();
  const explicitCode = cleanText(body?.errorCode || body?.code).toUpperCase();
  const credit = Number(status) === 402
    || explicitState === 'credit_exhausted'
    || explicitCode === 'WORKER_CREDIT_EXHAUSTED'
    || CREDIT_PATTERNS.some((pattern) => text.includes(pattern));
  if (credit) {
    return { retryable: true, safeToReassign: true, kind: 'credit_exhausted', code: 'WORKER_CREDIT_EXHAUSTED' };
  }

  const explicitUnavailable = explicitState === 'unavailable'
    || explicitCode === 'WORKER_UNAVAILABLE'
    || UNAVAILABLE_PATTERNS.some((pattern) => text.includes(pattern));
  if (explicitUnavailable) {
    return { retryable: true, safeToReassign: true, kind: 'unavailable', code: 'WORKER_UNAVAILABLE' };
  }

  if (Number(status) === 429) {
    return { retryable: true, safeToReassign: false, kind: 'unavailable', code: 'WORKER_UNAVAILABLE' };
  }
  if (Number(status) >= 500 || error) {
    return { retryable: true, safeToReassign: false, kind: 'unavailable', code: 'WORKER_UNAVAILABLE' };
  }
  return { retryable: false, safeToReassign: false, kind: 'failed', code: 'PROVIDER_FAILED' };
}

export function providerFailureError(message, { status = 0, body = null, cause = null, worker = null } = {}) {
  const classification = classifyWorkerFailure({ status, body, error: cause });
  const error = new Error(message);
  error.statusCode = classification.retryable ? 503 : (Number(status) >= 400 ? Number(status) : 502);
  error.errorCode = classification.code;
  error.workerState = classification.kind;
  error.workerFailure = classification;
  error.safeToReassign = classification.safeToReassign;
  error.workerId = worker?.id || '';
  error.ecosystem = worker?.ecosystem || '';
  error.providerStatus = Number(status) || 0;
  error.providerBody = body && typeof body === 'object' ? body : null;
  if (cause) error.cause = cause;
  return error;
}

export async function submitWithWorkerFailover(workflow, operation, { excludeWorkerIds = [] } = {}) {
  const workers = workersForWorkflow(workflow, { excludeWorkerIds });
  if (!workers.length) {
    const error = new Error(`No worker is configured for ${workflow?.ecosystem || workflow?.id || 'workflow'}`);
    error.statusCode = 503;
    error.errorCode = 'NO_WORKER_CONFIGURED';
    error.workerState = 'unavailable';
    throw error;
  }
  const failures = [];
  for (let index = 0; index < workers.length; index += 1) {
    const worker = workers[index];
    try {
      const result = await operation(worker, index);
      return { ...result, worker, failedWorkers: failures };
    } catch (error) {
      const failure = error?.workerFailure || classifyWorkerFailure({ error });
      failures.push({ workerId: worker.id, kind: failure.kind, code: failure.code });
      if (!failure.retryable) throw error;
      console.error('Modal worker failed; trying standby when available', {
        ecosystem: workflow?.ecosystem,
        workerId: worker.id,
        kind: failure.kind,
        code: failure.code,
      });
    }
  }
  const exhausted = failures.length > 0 && failures.every((failure) => failure.kind === 'credit_exhausted');
  const error = new Error(exhausted
    ? `All configured workers for ${workflow?.ecosystem || workflow?.id} have exhausted their available credits`
    : `No configured worker for ${workflow?.ecosystem || workflow?.id} is currently available`);
  error.statusCode = 503;
  error.errorCode = exhausted ? 'ALL_WORKERS_CREDIT_EXHAUSTED' : 'NO_WORKER_AVAILABLE';
  error.workerState = exhausted ? 'credit_exhausted' : 'unavailable';
  error.failures = failures;
  throw error;
}

export function publicWorkerStatus(worker, state = 'queued', extra = {}) {
  return {
    workerId: worker?.id || '',
    ecosystem: worker?.ecosystem || '',
    displayName: worker?.displayName || worker?.ecosystem || 'Generation worker',
    state: cleanText(state || 'queued') || 'queued',
    role: worker?.role || 'primary',
    ...extra,
  };
}
