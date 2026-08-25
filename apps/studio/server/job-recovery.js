import { getWorkflow } from '../api/_workflows.js';
import { listGenerationJobs, transitionGenerationJob, updateGenerationWorkerAssignment } from '../api/_generation-jobs.js';
import { pollWorkflow } from '../api/_providers.js';
import { persistImageJobResult, persistVideoJobResult } from '../api/_result-persistence.js';

const STALE_WITHOUT_PROVIDER_MS = 2 * 60 * 1000;

function ageMs(value) {
  const time = new Date(value || 0).getTime();
  return Number.isFinite(time) ? Date.now() - time : Number.POSITIVE_INFINITY;
}

async function failInterrupted(job, message) {
  try {
    return await transitionGenerationJob(job.id, 'failed', { errorMessage: message });
  } catch (error) {
    if (error?.statusCode === 409) return null;
    throw error;
  }
}

async function persistRecoveredWorkerState(job, worker) {
  if (!job?.id || !job?.provider_job_id || !worker?.state) return;
  const current = job.metadata?.workerRuntime && typeof job.metadata.workerRuntime === 'object'
    ? job.metadata.workerRuntime
    : {};
  if (current.state === worker.state && current.workerId === worker.workerId) return;
  try {
    await updateGenerationWorkerAssignment(job.id, job.provider_job_id, {
      assignedWorkerId: worker.workerId || job.metadata?.assignedWorkerId || null,
      workerRuntime: { ...worker, updatedAt: new Date().toISOString() },
    });
  } catch (error) {
    if (error?.statusCode !== 409) throw error;
  }
}

async function persistRecoveredResult(job, workflow, result) {
  if (job.kind === 'video') {
    return persistVideoJobResult(
      job,
      result.bytes,
      result.contentType || workflow.outputMimeType,
      result.posterBytes || null,
      result.posterContentType || 'image/jpeg',
    );
  }
  return persistImageJobResult(job, result.bytes, result.contentType || workflow.outputMimeType);
}

async function recoverJob(job) {
  if (!job?.id || !['queued', 'running'].includes(job.status)) return { id: job?.id, outcome: 'ignored' };

  if (!job.provider_job_id) {
    const referenceTime = job.started_at || job.created_at;
    if (ageMs(referenceTime) < STALE_WITHOUT_PROVIDER_MS) return { id: job.id, outcome: 'waiting' };
    const message = job.status === 'queued'
      ? 'Generation submission was interrupted before provider execution started. Retry the job.'
      : 'Generation execution was interrupted before a provider job id was recorded. Retry the job.';
    await failInterrupted(job, message);
    return { id: job.id, outcome: 'failed', reason: 'missing-provider-job-id' };
  }

  const workflow = getWorkflow(job.workflow_id);
  if (!workflow) {
    await failInterrupted(job, 'Generation workflow is no longer registered. Retry with an available workflow.');
    return { id: job.id, outcome: 'failed', reason: 'workflow-missing' };
  }

  try {
    const result = await pollWorkflow(workflow, job.provider_job_id);
    if (result.status !== 'completed') {
      await persistRecoveredWorkerState(job, result.worker || { state: 'generating' });
      return { id: job.id, outcome: 'running' };
    }
    const completed = await persistRecoveredResult(job, workflow, result);
    return {
      id: job.id,
      outcome: 'completed',
      mediaUrl: completed.media_url,
      thumbnailUrl: completed.thumbnail_url || null,
    };
  } catch (error) {
    const statusCode = Number(error?.statusCode || 500);
    if (statusCode >= 400 && statusCode < 500 && statusCode !== 408 && statusCode !== 429) {
      await failInterrupted(job, error?.message || 'Provider job could not be recovered.');
      return { id: job.id, outcome: 'failed', reason: error?.message || 'provider-error' };
    }
    console.error('Generation recovery poll failed', job.id, error);
    return { id: job.id, outcome: 'deferred' };
  }
}

export async function recoverActiveGenerationJobs() {
  const active = await listGenerationJobs({ status: 'active', limit: 20 });
  const jobs = Array.isArray(active) ? active : [];
  const results = [];
  for (const job of jobs) results.push(await recoverJob(job));
  const summary = results.reduce((counts, result) => {
    counts[result.outcome] = (counts[result.outcome] || 0) + 1;
    return counts;
  }, {});
  return { checked: jobs.length, summary, results };
}
