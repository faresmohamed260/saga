import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  classifyWorkerFailure,
  decodeProviderJobId,
  encodeProviderJobId,
  providerFailureError,
  submitWithWorkerFailover,
  workersForWorkflow,
} from '../api/_worker-registry.js';
import { getWorkflow } from '../api/_workflows.js';

process.env.SAGA_MODAL_WORKER_REGISTRY_JSON = JSON.stringify({ workers: [
  { id: 'flux-primary', ecosystem: 'flux2-klein-9b', gatewayUrl: 'https://primary.example', role: 'primary', enabled: true },
  { id: 'flux-standby', ecosystem: 'flux2-klein-9b', gatewayUrl: 'https://standby.example', role: 'standby', enabled: true },
  { id: 'ltx-primary', ecosystem: 'ltx25-redgraft', gatewayUrl: 'https://ltx.example', role: 'primary', enabled: true },
] });

const flux = getWorkflow('flux2-klein-image-edit');
const ltx = getWorkflow('ltx25-redgraft-video');
assert.equal(flux.ecosystem, 'flux2-klein-9b');
assert.equal(ltx.ecosystem, 'ltx25-redgraft');

const fluxWorkerIds = workersForWorkflow(flux).map((worker) => worker.id);
for (const workerId of ['flux-primary', 'flux-standby', 'flux-primary-01', 'flux-standby-01']) {
  assert.ok(fluxWorkerIds.includes(workerId), `FLUX registry is missing ${workerId}`);
}
const fluxWorkerIdsWithoutFixturePrimary = workersForWorkflow(flux, { excludeWorkerIds: ['flux-primary'] }).map((worker) => worker.id);
assert.ok(!fluxWorkerIdsWithoutFixturePrimary.includes('flux-primary'));
assert.ok(fluxWorkerIdsWithoutFixturePrimary.includes('flux-standby'));
assert.ok(fluxWorkerIdsWithoutFixturePrimary.includes('flux-primary-01'));

const ltxWorkerIds = workersForWorkflow(ltx).map((worker) => worker.id);
for (const workerId of ['ltx-primary', 'ltx-primary-01', 'ltx-standby-01']) {
  assert.ok(ltxWorkerIds.includes(workerId), `LTX registry is missing ${workerId}`);
}

const encoded = encodeProviderJobId('flux-standby', 'fc-123');
assert.deepEqual(decodeProviderJobId(encoded), { workerId: 'flux-standby', callId: 'fc-123', legacy: false });
assert.equal(decodeProviderJobId('fc-legacy').legacy, true);

const creditFailure = classifyWorkerFailure({ status: 402, body: { detail: 'insufficient credits' } });
assert.equal(creditFailure.kind, 'credit_exhausted');
assert.equal(creditFailure.safeToReassign, true);

const disabledFailure = classifyWorkerFailure({ status: 503, body: { detail: 'workspace is disabled' } });
assert.equal(disabledFailure.kind, 'unavailable');
assert.equal(disabledFailure.safeToReassign, true);

const genericServerFailure = classifyWorkerFailure({ status: 503, body: { detail: 'internal server error' } });
assert.equal(genericServerFailure.kind, 'unavailable');
assert.equal(genericServerFailure.safeToReassign, false);

const transportFailure = classifyWorkerFailure({ error: new Error('socket reset') });
assert.equal(transportFailure.retryable, true);
assert.equal(transportFailure.safeToReassign, false);

assert.equal(classifyWorkerFailure({ status: 400, body: { detail: 'prompt is required' } }).retryable, false);

const attempts = [];
const accepted = await submitWithWorkerFailover(flux, async (worker) => {
  attempts.push(worker.id);
  if (worker.id === 'flux-primary') {
    throw providerFailureError('primary out of credits', {
      status: 402,
      body: { errorCode: 'WORKER_CREDIT_EXHAUSTED', workerState: 'credit_exhausted' },
      worker,
    });
  }
  return { callId: 'fc-standby', state: 'waking' };
});
assert.deepEqual(attempts, ['flux-primary', 'flux-primary-01']);
assert.equal(accepted.worker.id, 'flux-primary-01');
assert.equal(accepted.callId, 'fc-standby');
assert.deepEqual(accepted.failedWorkers, [
  { workerId: 'flux-primary', kind: 'credit_exhausted', code: 'WORKER_CREDIT_EXHAUSTED' },
]);

await assert.rejects(
  () => submitWithWorkerFailover(flux, async (worker) => {
    throw providerFailureError(`${worker.id} out of credits`, {
      status: 402,
      body: { errorCode: 'WORKER_CREDIT_EXHAUSTED', workerState: 'credit_exhausted' },
      worker,
    });
  }),
  (error) => error?.errorCode === 'ALL_WORKERS_CREDIT_EXHAUSTED' && error?.workerState === 'credit_exhausted',
);

assert.equal(classifyWorkerFailure({ status: 429, body: { detail: 'rate limited' } }).safeToReassign, false, 'Generic 429 must not duplicate an accepted generation during poll-time failover');

process.env.SAGA_MODAL_WORKER_REGISTRY_JSON = JSON.stringify({ workers: [
  { id: 'only-primary', ecosystem: 'flux2-klein-9b', gatewayUrl: 'https://only.example', role: 'primary', enabled: true },
] });
const configuredAfterExclusion = workersForWorkflow(flux, { excludeWorkerIds: ['only-primary'] });
assert.ok(configuredAfterExclusion.length > 0, 'Generated FLUX workers should remain configured after excluding the env fixture');
assert.ok(configuredAfterExclusion.every((worker) => worker.id !== 'only-primary' && worker.id !== 'legacy-flux2-klein'), 'Configured fleets must not fall through to the legacy modal-01 worker after exclusions');

const fluxRuntimeSource = await readFile(new URL('../../../integrations/comfyui/flux2_klein_app.py', import.meta.url), 'utf8');
assert.ok(fluxRuntimeSource.includes('RUNTIME_SECRETS = [modal.Secret.from_dict'), 'Flux worker must inject deployment-time model credentials as Modal secrets');
assert.ok(fluxRuntimeSource.includes('secrets=RUNTIME_SECRETS'), 'Flux prefetch/runtime must receive deployment-time model credentials');

const resultSource = await readFile(new URL('../api/generate/result.js', import.meta.url), 'utf8');
for (const required of [
  'MAX_WORKER_FAILOVERS',
  'shouldReassignWorker',
  'safeToReassign',
  'reassignToStandby',
  'excludeWorkerIds',
  'workerFailoverHistory',
  'updateGenerationWorkerAssignment',
]) {
  assert.ok(resultSource.includes(required), `Poll-time failover contract missing ${required}`);
}
assert.ok(resultSource.includes("['credit_exhausted', 'unavailable']"), 'Poll-time reassignment must stay limited to explicit safe worker states');

const submitSource = await readFile(new URL('../api/generate.js', import.meta.url), 'utf8');
assert.ok(submitSource.includes('assignedWorkerId'), 'Initial submit must persist the accepted worker assignment');
assert.ok(submitSource.includes('workerFailoverHistory'), 'Initial submit must persist failed primary attempts');
assert.ok(submitSource.includes('updateGenerationWorkerAssignment'), 'Initial submit must atomically persist worker provider id + metadata');

const clientSource = await readFile(new URL('../src/generation-client.js', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8');
const lifecycleSource = await readFile(new URL('../src/features/create/VideoGenerationControls.jsx', import.meta.url), 'utf8');
assert.ok(clientSource.includes('ALL_WORKERS_CREDIT_EXHAUSTED') || clientSource.includes('error.workerState = body?.workerState'), 'Browser client must preserve structured worker failure metadata');
assert.ok(appSource.includes("terminalWorkerState = ['credit_exhausted', 'unavailable']"), 'App must preserve terminal worker state instead of flattening it to failed');
assert.ok(lifecycleSource.includes('Workers out of credits'), 'Lifecycle UI must explicitly explain all-worker credit exhaustion');
assert.ok(lifecycleSource.includes('previous worker reached its credit limit'), 'Lifecycle UI must explicitly explain credit-driven standby switching');

console.log('Modal worker registry contract passed: generated fleet merge, ecosystem affinity, pinned provider IDs, exclusion, credit failover, all-credit exhaustion, safe reassignment, and persisted poll-time standby routing.');
