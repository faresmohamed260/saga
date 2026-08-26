import assert from 'node:assert/strict';
import {
  providerFailureError,
  submitWithWorkerFailover,
  workersForWorkflow,
} from '../api/_worker-registry.js';
import { getWorkflow } from '../api/_workflows.js';

process.env.SAGA_MODAL_WORKER_REGISTRY_JSON = JSON.stringify({ workers: [
  { id: 'qwen-fixture-primary', ecosystem: 'qwen-image-edit-2511', gatewayUrl: 'https://qwen-primary.example', role: 'primary', enabled: true },
  { id: 'qwen-fixture-standby', ecosystem: 'qwen-image-edit-2511', gatewayUrl: 'https://qwen-standby.example', role: 'standby', enabled: true },
] });

const qwen = getWorkflow('qwen-image-edit-2511');
assert.equal(qwen.ecosystem, 'qwen-image-edit-2511');
assert.equal(qwen.defaults?.steps, 4);
assert.equal(qwen.defaults?.cfg, 1.0);

const configured = workersForWorkflow(qwen);
for (const workerId of ['qwen-fixture-primary', 'qwen-fixture-standby', 'qwen-primary-01', 'qwen-standby-01']) {
  assert.ok(configured.some((worker) => worker.id === workerId), `Qwen registry is missing ${workerId}`);
}
assert.ok(configured.every((worker) => worker.ecosystem === 'qwen-image-edit-2511'), 'Qwen routing must remain ecosystem-affine');

const attempts = [];
const accepted = await submitWithWorkerFailover(qwen, async (worker) => {
  attempts.push({ id: worker.id, role: worker.role });
  if (worker.role === 'primary') {
    throw providerFailureError(`${worker.id} unavailable`, {
      status: 503,
      body: { errorCode: 'WORKER_UNAVAILABLE', workerState: 'unavailable', detail: 'workspace is disabled' },
      worker,
    });
  }
  return { callId: 'fc-qwen-standby', state: 'waking' };
});

assert.ok(attempts.length >= 3, `Expected Qwen primary attempts followed by standby, got ${JSON.stringify(attempts)}`);
assert.ok(attempts.slice(0, -1).every((attempt) => attempt.role === 'primary'), `Qwen must exhaust primaries before standby: ${JSON.stringify(attempts)}`);
assert.equal(attempts.at(-1)?.role, 'standby');
assert.equal(accepted.worker.role, 'standby');
assert.equal(accepted.callId, 'fc-qwen-standby');
assert.ok(accepted.failedWorkers.length >= 2, 'Qwen failover must retain failed primary history');
assert.ok(accepted.failedWorkers.every((entry) => entry.kind === 'unavailable'));

const withoutPrimary = workersForWorkflow(qwen, { excludeWorkerIds: configured.filter((worker) => worker.role === 'primary').map((worker) => worker.id) });
assert.ok(withoutPrimary.length >= 2, 'Qwen standby pool must remain available after excluding primaries');
assert.ok(withoutPrimary.every((worker) => worker.role === 'standby' && worker.ecosystem === 'qwen-image-edit-2511'));

console.log('Qwen worker routing contract passed: ecosystem affinity, 4-step defaults, primary exhaustion, standby selection, and failover history.');
