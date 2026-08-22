import { getGenerationJob, isUuid } from '../_generation-jobs.js';
import { pollWorkflow } from '../_providers.js';
import { getWorkflow } from '../_workflows.js';

export const config = { maxDuration: 30 };

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const jobId = typeof req.query?.jobId === 'string' ? req.query.jobId : '';
    if (!isUuid(jobId)) return res.status(400).json({ error: 'Invalid job id' });

    const job = await getGenerationJob(jobId);
    if (!job) return res.status(404).json({ error: 'Job not found' });
    if (job.status === 'failed') return res.status(409).json({ error: job.error_message || 'Generation failed', status: 'failed' });
    if (job.status === 'completed' && job.media_url) {
      return res.status(200).json({ status: 'completed', persisted: true, mediaUrl: job.media_url, thumbnailUrl: job.thumbnail_url || null });
    }
    if (!job.workflow_id || !job.provider_job_id) return res.status(202).json({ status: job.status || 'queued' });

    const workflow = getWorkflow(job.workflow_id);
    if (!workflow) return res.status(409).json({ error: 'Generation workflow is no longer registered' });

    const result = await pollWorkflow(workflow, job.provider_job_id);
    if (result.status !== 'completed') return res.status(202).json({ status: 'running' });

    res.setHeader('Content-Type', result.contentType || workflow.outputMimeType);
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Saga-Job-Id', job.id);
    res.setHeader('X-Saga-Workflow', workflow.id);
    res.setHeader('X-Saga-Provider', workflow.provider);
    return res.status(200).send(result.bytes);
  } catch (error) {
    console.error('Generation result poll failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation result poll failed' });
  }
}
