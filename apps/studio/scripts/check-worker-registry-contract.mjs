import assert from 'node:assert/strict';
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
assert.deepEqual(workersForWorkflow(flux).map((worker) => worker.id), ['flux-primary', 'flux-standby']);
assert.deepEqual(workersForWorkflow(flux, { excludeWorkerIds: ['flux-primary'] }).map((worker) => worker.id), ['flux-standby']);
assert.deepEqual(workersForWorkflow(ltx).map((worker) => worker.id), ['ltx-primary']);

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
assert.deepEqual(attempts, ['flux-primary', 'flux-standby']);
assert.equal(accepted.worker.id, 'flux-standby');
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

console.log('Modal worker registry contract passed: ecosystem affinity, pinned provider IDs, exclusion, credit failover, all-credit exhaustion, and safe reassignment classification.');
