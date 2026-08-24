import {
  getGenerationJob,
  isUuid,
  transitionGenerationJob,
  updateGenerationWorkerAssignment,
} from '../_generation-jobs.js';
import { pollWorkflow, submitWorkflow } from '../_providers.js';
import { readSourceObject } from '../_r2.js';
import { decodeProviderJobId } from '../_worker-registry.js';
import { persistImageJobResult, persistVideoJobResult } from '../_result-persistence.js';
import { getWorkflow } from '../_workflows.js';

export const config = { maxDuration: 30 };

const MAX_WORKER_FAILOVERS = 3;

function objectValue(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function failoverHistory(job) {
  return arrayValue(objectValue(job?.metadata).workerFailoverHistory)
    .filter((entry) => entry && typeof entry === 'object')
    .slice(-MAX_WORKER_FAILOVERS);
}

function shouldReassignWorker(error) {
  return Boolean(
    error?.safeToReassign
    && ['credit_exhausted', 'unavailable'].includes(String(error?.workerState || '')),
  );
}

async function rebuildSources(job, workflow) {
  const metadata = objectValue(job?.metadata);
  const keys = arrayValue(metadata.sourceR2Keys).filter(Boolean);
  if (!keys.length && metadata.sourceR2Key) keys.push(metadata.sourceR2Key);
  if (!keys.length) return [];
  const filenames = arrayValue(metadata.sourceFilenames);
  const sources = [];
  for (let index = 0; index < keys.length; index += 1) {
    const source = await readSourceObject(keys[index], workflow.limits.maxSourceBytes);
    sources.push({
      bytes: source.bytes,
      contentType: source.contentType,
      filename: filenames[index] || `input-${index + 1}.png`,
      key: keys[index],
    });
  }
  return sources;
}

async function standbyRetryInput(job, workflow) {
  const metadata = objectValue(job?.metadata);
  const execution = objectValue(metadata.execution);
  const sources = await rebuildSources(job, workflow);
  if (workflow.requiresSourceImage && !sources.length) return null;
  const prompt = sources.length > 1
    ? `Reference images are numbered in upload order from Image 1 through Image ${sources.length}. Image 1 is the primary canvas that determines output shape.\n\n${job.prompt || ''}`
    : String(job.prompt || '');
  const primary = sources[0] || { bytes: Buffer.alloc(0), contentType: '', filename: '' };
  return {
    sources,
    sourceBytes: primary.bytes,
    sourceContentType: primary.contentType,
    sourceFilename: primary.filename,
    prompt,
    negativePrompt: job.negative_prompt || '',
    resolution: execution.resolution || job.resolution || workflow.defaults.resolution,
    seed: job.seed ?? workflow.defaults.seed,
    steps: execution.steps ?? workflow.defaults.steps,
    cfg: execution.cfg ?? workflow.defaults.cfg,
    megapixels: execution.megapixels ?? workflow.defaults.megapixels,
    durationSeconds: execution.durationSeconds ?? workflow.defaults.durationSeconds,
    audioEnabled: execution.audioEnabled ?? workflow.defaults.audioEnabled,
    aspectRatio: execution.aspectRatio ?? workflow.defaults.aspectRatio,
    frameRate: execution.frameRate ?? workflow.defaults.frameRate,
  };
}

async function reassignToStandby(job, workflow, error) {
  if (!shouldReassignWorker(error)) return null;
  const history = failoverHistory(job);
  if (history.length >= MAX_WORKER_FAILOVERS) return null;

  const current = decodeProviderJobId(job.provider_job_id);
  if (!current.workerId) return null;
  const excluded = new Set([current.workerId]);
  for (const entry of history) {
    if (entry.fromWorkerId) excluded.add(String(entry.fromWorkerId));
    if (entry.workerId) excluded.add(String(entry.workerId));
  }

  const retryInput = await standbyRetryInput(job, workflow);
  if (!retryInput) return null;
  const submitted = await submitWorkflow(workflow, retryInput, { excludeWorkerIds: [...excluded] });
  const at = new Date().toISOString();
  const nextHistory = [
    ...history,
    {
      fromWorkerId: current.workerId,
      reason: error.workerState || 'unavailable',
      errorCode: error.errorCode || null,
      at,
    },
    ...arrayValue(submitted.worker?.failedWorkers).map((failure) => ({
      fromWorkerId: failure.workerId,
      reason: failure.kind || 'unavailable',
      errorCode: failure.code || null,
      at,
    })),
  ].slice(-MAX_WORKER_FAILOVERS);

  await updateGenerationWorkerAssignment(job.id, submitted.providerJobId, {
    workerFailoverHistory: nextHistory,
    assignedWorkerId: submitted.worker?.workerId || null,
    lastWorkerFailoverAt: at,
  });

  return {
    ...submitted.worker,
    state: submitted.worker?.state === 'sleeping' ? 'waking' : (submitted.worker?.state || 'waking'),
    failoverFrom: current.workerId,
    failoverReason: error.workerState || 'unavailable',
  };
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  let job = null;
  try {
    const jobId = typeof req.query?.jobId === 'string' ? req.query.jobId : '';
    if (!isUuid(jobId)) return res.status(400).json({ error: 'Invalid job id' });

    job = await getGenerationJob(jobId);
    if (!job) return res.status(404).json({ error: 'Job not found' });
    if (job.status === 'failed') return res.status(409).json({ error: job.error_message || 'Generation failed', status: 'failed' });
    if (job.status === 'completed' && job.media_url) {
      return res.status(200).json({
        status: 'completed',
        persisted: true,
        kind: job.kind || null,
        generationId: job.id,
        mediaUrl: job.media_url,
        thumbnailUrl: job.thumbnail_url || null,
      });
    }
    if (!job.workflow_id || !job.provider_job_id) {
      return res.status(202).json({ status: job.status || 'queued', workerState: 'queued', ecosystem: job.metadata?.ecosystem || null });
    }

    const workflow = getWorkflow(job.workflow_id);
    if (!workflow) return res.status(409).json({ error: 'Generation workflow is no longer registered' });

    const result = await pollWorkflow(workflow, job.provider_job_id);
    if (result.status !== 'completed') {
      return res.status(202).json({
        status: 'running',
        workerState: result.worker?.state || 'generating',
        worker: result.worker || null,
        ecosystem: workflow.ecosystem || null,
      });
    }

    const contentType = result.contentType || workflow.outputMimeType;
    const completed = workflow.kind === 'video'
      ? await persistVideoJobResult(job, result.bytes, contentType, result.posterBytes, result.posterContentType)
      : await persistImageJobResult(job, result.bytes, contentType);
    return res.status(200).json({
      status: 'completed',
      persisted: true,
      kind: workflow.kind,
      generationId: completed.id,
      mediaUrl: completed.media_url,
      thumbnailUrl: completed.thumbnail_url || null,
    });
  } catch (caught) {
    let error = caught;
    if (job?.id && job.status === 'running' && job.workflow_id && job.provider_job_id) {
      const workflow = getWorkflow(job.workflow_id);
      if (workflow && shouldReassignWorker(error)) {
        try {
          const worker = await reassignToStandby(job, workflow, error);
          if (worker) {
            return res.status(202).json({
              status: 'running',
              workerState: worker.state || 'waking',
              worker,
              ecosystem: workflow.ecosystem || null,
              failover: true,
            });
          }
        } catch (failoverError) {
          error = failoverError;
        }
      }
    }

    if (job?.id && job.status === 'running' && error?.statusCode && error.statusCode !== 500) {
      try {
        await transitionGenerationJob(job.id, 'failed', { errorMessage: error?.message || 'Generation failed' });
      } catch (transitionError) {
        console.error('Could not mark provider job failed', transitionError);
      }
    }
    console.error('Generation result poll failed', error);
    return res.status(error?.statusCode || 500).json({
      error: error?.message || 'Generation result poll failed',
      errorCode: error?.errorCode || null,
      workerState: error?.workerState || null,
    });
  }
}
