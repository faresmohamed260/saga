import {
  createGenerationJob,
  getGenerationJob,
  isUuid,
  listGenerationJobs,
  transitionGenerationJob,
} from './_generation-jobs.js';
import { cancelGenerationJob, retryGenerationJob } from '../server/job-actions.js';
import { recoverActiveGenerationJobs } from '../server/job-recovery.js';

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

function clampLimit(value) {
  const parsed = Number.parseInt(String(value || '30'), 10);
  if (!Number.isFinite(parsed)) return 30;
  return Math.min(Math.max(parsed, 1), 100);
}

export const config = { maxDuration: 30 };

export default async function handler(req, res) {
  try {
    if (req.method === 'POST') {
      const body = typeof req.body === 'object' && req.body ? req.body : {};
      const action = safeText(body.action || req.query?.action, 32).toLowerCase();
      if (action === 'cancel') {
        const job = await cancelGenerationJob(body.id);
        return res.status(200).json({ job, action: 'cancelled' });
      }
      if (action === 'retry') {
        const originalId = safeText(body.id, 64);
        const job = await retryGenerationJob(originalId);
        return res.status(201).json({ job, action: 'retried', retryOf: originalId });
      }
      if (action === 'recover') {
        const result = await recoverActiveGenerationJobs();
        return res.status(200).json(result);
      }
      if (action) return res.status(400).json({ error: 'Unknown job action' });

      const job = await createGenerationJob(body);
      return res.status(201).json({ job });
    }

    if (req.method === 'GET') {
      const id = typeof req.query?.id === 'string' ? req.query.id : '';
      if (id) {
        if (!isUuid(id)) return res.status(400).json({ error: 'Invalid job id' });
        const job = await getGenerationJob(id);
        if (!job) return res.status(404).json({ error: 'Job not found' });
        return res.status(200).json({ job });
      }

      const status = safeText(req.query?.status || 'all', 32).toLowerCase();
      if (!['all', 'active', 'queued', 'running', 'completed', 'failed'].includes(status)) {
        return res.status(400).json({ error: 'Invalid status filter' });
      }
      const limit = clampLimit(req.query?.limit);
      const rows = await listGenerationJobs({ status, limit });
      return res.status(200).json({ jobs: Array.isArray(rows) ? rows : [], filter: status, limit });
    }

    if (req.method === 'PATCH') {
      const body = typeof req.body === 'object' && req.body ? req.body : {};
      const job = await transitionGenerationJob(body.id, safeText(body.status, 32), {
        errorMessage: body.errorMessage,
      });
      return res.status(200).json({ job });
    }

    res.setHeader('Allow', 'GET, POST, PATCH');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Generation job request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation job request failed' });
  }
}
