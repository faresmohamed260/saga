import { getWorkflow } from './_workflows.js';
import { workersForWorkflow } from './_worker-registry.js';

export const config = { maxDuration: 10 };

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  const workflow = getWorkflow(req.body?.workflowId);
  if (!workflow) return res.status(404).json({ error: 'Unknown generation workflow' });
  const worker = workersForWorkflow(workflow)[0];
  if (!worker) return res.status(202).json({ status: 'unavailable', ecosystem: workflow.ecosystem });
  try {
    const response = await fetch(`${worker.gatewayUrl}/warm`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(4500),
    });
    return res.status(202).json({ status: response.ok ? 'waking' : 'requested', ecosystem: workflow.ecosystem, workerId: worker.id });
  } catch {
    return res.status(202).json({ status: 'requested', ecosystem: workflow.ecosystem, workerId: worker.id });
  }
}
