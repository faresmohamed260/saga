import assert from 'node:assert/strict';
import { classifyWorkerFailure, decodeProviderJobId, encodeProviderJobId, workersForWorkflow } from '../api/_worker-registry.js';
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
assert.deepEqual(workersForWorkflow(ltx).map((worker) => worker.id), ['ltx-primary']);

const encoded = encodeProviderJobId('flux-standby', 'fc-123');
assert.deepEqual(decodeProviderJobId(encoded), { workerId: 'flux-standby', callId: 'fc-123', legacy: false });
assert.equal(decodeProviderJobId('fc-legacy').legacy, true);

assert.equal(classifyWorkerFailure({ status: 402, body: { detail: 'insufficient credits' } }).kind, 'credit_exhausted');
assert.equal(classifyWorkerFailure({ status: 503, body: { detail: 'workspace is disabled' } }).kind, 'unavailable');
assert.equal(classifyWorkerFailure({ status: 400, body: { detail: 'prompt is required' } }).retryable, false);
console.log('Modal worker registry contract passed: ecosystem affinity, primary/standby ordering, pinned provider IDs, and credit/unavailable classification.');
