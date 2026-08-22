import {
  createGenerationJob,
  getGenerationJob,
  setProviderJobId,
  transitionGenerationJob,
} from '../api/_generation-jobs.js';
import { cancelWorkflow, submitWorkflow } from '../api/_providers.js';
import { readSourceObject, isSourceKey } from '../api/_r2.js';
import { supabaseRequest } from '../api/_supabase.js';
import { getWorkflow } from '../api/_workflows.js';

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

function safeTextArray(value, maxLength) {
  return Array.isArray(value) ? value.map((item) => safeText(item, maxLength)).filter(Boolean) : [];
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
  let sourceKeys = safeTextArray(metadata.sourceR2Keys, 300);
  const legacySourceKey = safeText(metadata.sourceR2Key, 300);
  if (!sourceKeys.length && legacySourceKey) sourceKeys = [legacySourceKey];
  if (workflow.requiresSourceImage && (!sourceKeys.length || sourceKeys.some((key) => !isSourceKey(key)))) {
    const error = new Error('This job cannot be retried because one or more source inputs are unavailable');
    error.statusCode = 409;
    throw error;
  }

  const sourceFilenames = safeTextArray(metadata.sourceFilenames, 240);
  const sourceContentTypes = safeTextArray(metadata.sourceContentTypes, 120);
  const sources = [];
  for (let index = 0; index < sourceKeys.length; index += 1) {
    const source = await readSourceObject(sourceKeys[index], workflow.limits.maxSourceBytes);
    sources.push({
      bytes: source.bytes,
      contentType: source.contentType,
      filename: sourceFilenames[index] || (index === 0 ? safeText(metadata.sourceFilename, 240) : '') || `input-${index + 1}.png`,
      key: sourceKeys[index],
    });
  }

  const execution = metadata.execution && typeof metadata.execution === 'object' ? metadata.execution : {};
  const steps = Number.isFinite(Number(execution.steps)) ? Number(execution.steps) : workflow.defaults.steps;
  const cfg = Number.isFinite(Number(execution.cfg)) ? Number(execution.cfg) : workflow.defaults.cfg;
  const megapixels = Number.isFinite(Number(execution.megapixels)) ? Number(execution.megapixels) : workflow.defaults.megapixels;
  const primary = sources[0] || { bytes: Buffer.alloc(0), contentType: safeText(metadata.sourceContentType, 120) || 'application/octet-stream', filename: safeText(metadata.sourceFilename, 240) || 'input.png' };

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
      inputTransport: sourceKeys.length ? 'r2' : metadata.inputTransport || 'inline',
      sourceR2Key: sourceKeys[0] || null,
      sourceR2Keys: sourceKeys,
      sourceContentType: primary.contentType,
      sourceContentTypes: sources.map((source) => source.contentType),
      sourceFilename: primary.filename,
      sourceFilenames: sources.map((source) => source.filename),
      referenceCount: sources.length,
      primaryReferenceIndex: sources.length ? 0 : null,
      automaticOutputSize: Boolean(workflow.automaticOutputSize),
      execution: { steps, cfg, megapixels },
      retryOf: job.id,
    },
  });

  try {
    retry = await transitionGenerationJob(retry.id, 'running');
    const retryPrompt = sources.length > 1
      ? `Reference images are numbered in upload order from Image 1 through Image ${sources.length}. Image 1 is the primary canvas that determines output shape.\n\n${job.prompt}`
      : job.prompt;
    const submitted = await submitWorkflow(workflow, {
      sources,
      sourceBytes: primary.bytes,
      sourceContentType: primary.contentType,
      sourceFilename: primary.filename,
      prompt: retryPrompt,
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
