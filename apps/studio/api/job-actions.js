import {
  createGenerationJob,
  getGenerationJob,
  setProviderJobId,
  transitionGenerationJob,
} from './_generation-jobs.js';
import { cancelWorkflow, submitWorkflow } from './_providers.js';
import { readSourceObject, isSourceKey } from './_r2.js';
import { supabaseRequest } from './_supabase.js';
import { getWorkflow } from './_workflows.js';

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

async function markCancelled(job) {
  const metadata = {
    ...(job.metadata && typeof job.metadata === 'object' ? job.metadata : {}),
    cancelled: true,
    cancelledAt: new Date().toISOString(),
  };
  const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(job.id)}&status=in.(queued,running)&select=*`, {
    method: 'PATCH',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify({
      status: 'failed',
      error_message: 'Cancelled by user',
      metadata,
      completed_at: new Date().toISOString(),
    }),
  });
  const cancelled = Array.isArray(rows) ? rows[0] : rows;
  if (!cancelled) {
    const error = new Error('Job is no longer cancellable');
    error.statusCode = 409;
    throw error;
  }
  return cancelled;
}

async function retryJob(job) {
  if (job.status !== 'failed') {
    const error = new Error('Only failed or cancelled jobs can be retried');
    error.statusCode = 409;
    throw error;
  }
  const workflow = getWorkflow(job.workflow_id);
  if (!workflow) {
    const error = new Error('Generation workflow is no longer registered');
    error.statusCode = 409;
    throw error;
  }

  const metadata = job.metadata && typeof job.metadata === 'object' ? job.metadata : {};
  const sourceKey = safeText(metadata.sourceR2Key, 300);
  if (workflow.requiresSourceImage && !isSourceKey(sourceKey)) {
    const error = new Error('This job cannot be retried because its source input is unavailable');
    error.statusCode = 409;
    throw error;
  }

  let sourceBytes = Buffer.alloc(0);
  let sourceContentType = safeText(metadata.sourceContentType, 120) || 'application/octet-stream';
  if (sourceKey) {
    const source = await readSourceObject(sourceKey, workflow.limits.maxSourceBytes);
    sourceBytes = source.bytes;
    sourceContentType = source.contentType;
  }

  const execution = metadata.execution && typeof metadata.execution === 'object' ? metadata.execution : {};
  const steps = Number.isFinite(Number(execution.steps)) ? Number(execution.steps) : workflow.defaults.steps;
  const cfg = Number.isFinite(Number(execution.cfg)) ? Number(execution.cfg) : workflow.defaults.cfg;
  const megapixels = Number.isFinite(Number(execution.megapixels)) ? Number(execution.megapixels) : workflow.defaults.megapixels;
  const sourceFilename = safeText(metadata.sourceFilename, 240) || 'input.png';

  let retry = await createGenerationJob({
    kind: workflow.kind,
    mode: workflow.mode,
    model: job.model || workflow.model,
    prompt: job.prompt,
    negativePrompt: job.negative_prompt,
    resolution: job.resolution,
    seed: job.seed,
    workflowId: workflow.id,
    provider: workflow.provider,
    metadata: {
      inputTransport: sourceKey ? 'r2' : metadata.inputTransport || 'inline',
      sourceR2Key: sourceKey || null,
      sourceContentType,
      sourceFilename,
      execution: { steps, cfg, megapixels },
      retryOf: job.id,
    },
  });

  try {
    retry = await transitionGenerationJob(retry.id, 'running');
    const submitted = await submitWorkflow(workflow, {
      sourceBytes,
      sourceContentType,
      sourceFilename,
      prompt: job.prompt,
      negativePrompt: job.negative_prompt,
      seed: job.seed,
      steps,
      cfg,
      megapixels,
    });
    retry = await setProviderJobId(retry.id, submitted.providerJobId);
    return retry;
  } catch (error) {
    try {
      await transitionGenerationJob(retry.id, 'failed', { errorMessage: error?.message || 'Retry submit failed' });
    } catch {}
    throw error;
  }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const body = typeof req.body === 'object' && req.body ? req.body : {};
    const id = safeText(body.id, 64);
    const action = safeText(body.action, 32).toLowerCase();
    const job = await getGenerationJob(id);
    if (!job) return res.status(404).json({ error: 'Job not found' });

    if (action === 'cancel') {
      if (!['queued', 'running'].includes(job.status)) return res.status(409).json({ error: 'Job is no longer cancellable' });
      const workflow = getWorkflow(job.workflow_id);
      if (!workflow) return res.status(409).json({ error: 'Generation workflow is no longer registered' });
      if (job.provider_job_id) await cancelWorkflow(workflow, job.provider_job_id);
      const cancelled = await markCancelled(job);
      return res.status(200).json({ job: cancelled, action: 'cancelled' });
    }

    if (action === 'retry') {
      const retried = await retryJob(job);
      return res.status(201).json({ job: retried, action: 'retried', retryOf: job.id });
    }

    return res.status(400).json({ error: 'Unknown job action' });
  } catch (error) {
    console.error('Generation job action failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation job action failed' });
  }
}
