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

export async function cancelGenerationJob(id) {
  const job = await getGenerationJob(safeText(id, 64));
  if (!job) {
    const error = new Error('Job not found');
    error.statusCode = 404;
    throw error;
  }
  if (!['queued', 'running'].includes(job.status)) {
    const error = new Error('Job is no longer cancellable');
    error.statusCode = 409;
    throw error;
  }
  const workflow = getWorkflow(job.workflow_id);
  if (!workflow) {
    const error = new Error('Generation workflow is no longer registered');
    error.statusCode = 409;
    throw error;
  }
  if (job.provider_job_id) await cancelWorkflow(workflow, job.provider_job_id);
  return markCancelled(job);
}

export async function retryGenerationJob(id) {
  const job = await getGenerationJob(safeText(id, 64));
  if (!job) {
    const error = new Error('Job not found');
    error.statusCode = 404;
    throw error;
  }
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
    return setProviderJobId(retry.id, submitted.providerJobId);
  } catch (error) {
    try {
      await transitionGenerationJob(retry.id, 'failed', { errorMessage: error?.message || 'Retry submit failed' });
    } catch {}
    throw error;
  }
}
