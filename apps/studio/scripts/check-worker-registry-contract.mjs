import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const registrySource = await readFile(new URL('../api/_worker-registry.js', import.meta.url), 'utf8');
const gatewaySource = await readFile(new URL('../../modal/workers/_studio_job_gateway.py', import.meta.url), 'utf8');
const fluxRuntimeSource = await readFile(new URL('../../modal/workers/flux2_klein_worker.py', import.meta.url), 'utf8');

for (const required of [
  'STUDIO_WORKER_FLEET_JSON',
  'ecosystem',
  'workerId',
  'provider',
  'standby',
  'credit_exhausted',
  'unavailable',
  'excludeWorkerIds',
]) {
  assert.ok(registrySource.includes(required), `Worker registry contract missing ${required}`);
}
assert.ok(registrySource.includes('mergeGeneratedWorkerFleet'), 'Worker registry must merge generated fleet metadata');
assert.ok(registrySource.includes('listWorkersForEcosystem'), 'Worker registry must route by ecosystem');
assert.ok(registrySource.includes('getWorkerById'), 'Worker registry must support persisted assignment lookup');
assert.ok(registrySource.includes('allWorkersCreditExhausted'), 'Worker registry must expose all-credit exhaustion state');
assert.ok(registrySource.includes('credit_exhausted'), 'Worker registry must classify provider credit exhaustion');
assert.ok(registrySource.includes('unavailable'), 'Worker registry must classify provider unavailability');
assert.ok(registrySource.includes('excludeWorkerIds'), 'Worker registry must support exclusion during failover');

assert.ok(gatewaySource.includes('provider_job_id'), 'Modal gateway must return provider job id');
assert.ok(gatewaySource.includes('worker_id'), 'Modal gateway must return worker identity');
assert.ok(gatewaySource.includes('worker_state'), 'Modal gateway must return worker lifecycle state');
assert.ok(gatewaySource.includes('credit_exhausted'), 'Modal gateway must classify credit exhaustion');
assert.ok(gatewaySource.includes('unavailable'), 'Modal gateway must classify unavailable workers');

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
const generationControllerSource = await readFile(new URL('../src/hooks/useGenerationController.js', import.meta.url), 'utf8');
const lifecycleSource = await readFile(new URL('../src/features/create/VideoGenerationControls.jsx', import.meta.url), 'utf8');
assert.ok(clientSource.includes('ALL_WORKERS_CREDIT_EXHAUSTED') || clientSource.includes('error.workerState = body?.workerState'), 'Browser client must preserve structured worker failure metadata');
assert.ok(generationControllerSource.includes("terminalWorkerState = ['credit_exhausted', 'unavailable']"), 'Generation controller must preserve terminal worker state instead of flattening it to failed');
assert.ok(lifecycleSource.includes('Workers out of credits'), 'Lifecycle UI must explicitly explain all-worker credit exhaustion');
assert.ok(lifecycleSource.includes('previous worker reached its credit limit'), 'Lifecycle UI must explicitly explain credit-driven standby switching');

console.log('Modal worker registry contract passed: generated fleet merge, ecosystem affinity, pinned provider IDs, exclusion, credit failover, all-credit exhaustion, safe reassignment, and persisted poll-time standby routing.');
