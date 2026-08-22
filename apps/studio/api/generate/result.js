import { getGenerationJob, isUuid, transitionGenerationJob } from '../_generation-jobs.js';
import { pollWorkflow } from '../_providers.js';
import { persistImageJobResult } from '../_result-persistence.js';
import { getWorkflow } from '../_workflows.js';

export const config = { maxDuration: 30 };

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
        generationId: job.id,
        mediaUrl: job.media_url,
        thumbnailUrl: job.thumbnail_url || null,
      });
    }
    if (!job.workflow_id || !job.provider_job_id) return res.status(202).json({ status: job.status || 'queued' });

    const workflow = getWorkflow(job.workflow_id);
    if (!workflow) return res.status(409).json({ error: 'Generation workflow is no longer registered' });

    const result = await pollWorkflow(workflow, job.provider_job_id);
    if (result.status !== 'completed') return res.status(202).json({ status: 'running' });

    const completed = await persistImageJobResult(job, result.bytes, result.contentType || workflow.outputMimeType);
    return res.status(200).json({
      status: 'completed',
      persisted: true,
      generationId: completed.id,
      mediaUrl: completed.media_url,
      thumbnailUrl: completed.thumbnail_url || null,
    });
  } catch (error) {
    if (job?.id && job.status === 'running' && error?.statusCode && error.statusCode !== 500) {
      try {
        await transitionGenerationJob(job.id, 'failed', { errorMessage: error?.message || 'Generation failed' });
      } catch (transitionError) {
        console.error('Could not mark provider job failed', transitionError);
      }
    }
    console.error('Generation result poll failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation result poll failed' });
  }
}
