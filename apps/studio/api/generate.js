import {
  createGenerationJob,
  setProviderJobId,
  transitionGenerationJob,
} from './_generation-jobs.js';
import { submitWorkflow } from './_providers.js';
import { getWorkflow, listWorkflows } from './_workflows.js';

export const config = { maxDuration: 60 };

function decodeHeader(value) {
  const raw = String(value || '');
  if (!raw) return '';
  try { return decodeURIComponent(raw); } catch { return raw; }
}

function parseNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

async function readBody(req, limit) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > limit) {
      const error = new Error('Source image is too large for this workflow');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (req.method === 'GET') return res.status(200).json({ workflows: listWorkflows() });

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  let job = null;
  try {
    const workflowId = String(req.headers['x-saga-workflow'] || '').trim();
    const workflow = getWorkflow(workflowId);
    if (!workflow) return res.status(404).json({ error: 'Unknown generation workflow' });

    const contentType = String(req.headers['content-type'] || 'application/octet-stream').split(';')[0].trim();
    if (workflow.requiresSourceImage && !contentType.startsWith('image/')) {
      return res.status(415).json({ error: 'This workflow requires an image source' });
    }

    const prompt = decodeHeader(req.headers['x-saga-prompt']).trim().slice(0, 2000);
    const negativePrompt = decodeHeader(req.headers['x-saga-negative-prompt']).trim().slice(0, 2000);
    const resolution = decodeHeader(req.headers['x-saga-resolution']).trim().slice(0, 64);
    const sourceFilename = decodeHeader(req.headers['x-saga-source-filename']).trim().slice(0, 240) || 'input.png';
    const seed = Number.parseInt(String(req.headers['x-saga-seed'] || workflow.defaults.seed), 10);
    const steps = parseNumber(req.headers['x-saga-steps'], workflow.defaults.steps);
    const cfg = parseNumber(req.headers['x-saga-cfg'], workflow.defaults.cfg);
    const megapixels = parseNumber(req.headers['x-saga-megapixels'], workflow.defaults.megapixels);

    if (!prompt) return res.status(400).json({ error: 'Prompt is required' });

    const sourceBytes = await readBody(req, workflow.limits.maxSourceBytes);
    if (workflow.requiresSourceImage && !sourceBytes.length) {
      return res.status(400).json({ error: 'Source image is empty' });
    }

    job = await createGenerationJob({
      kind: workflow.kind,
      mode: workflow.mode,
      model: workflow.model,
      prompt,
      negativePrompt,
      resolution,
      seed,
      workflowId: workflow.id,
      provider: workflow.provider,
    });
    await transitionGenerationJob(job.id, 'running');

    const submitted = await submitWorkflow(workflow, {
      sourceBytes,
      sourceContentType: contentType,
      sourceFilename,
      prompt,
      negativePrompt,
      seed,
      steps,
      cfg,
      megapixels,
    });
    const updatedJob = await setProviderJobId(job.id, submitted.providerJobId);

    return res.status(202).json({
      job: updatedJob,
      status: 'running',
      workflow: workflow.id,
      provider: workflow.provider,
    });
  } catch (error) {
    if (job?.id) {
      try {
        await transitionGenerationJob(job.id, 'failed', { errorMessage: error?.message || 'Generation submit failed' });
      } catch (transitionError) {
        console.error('Could not mark generation job failed', transitionError);
      }
    }
    console.error('Generation orchestration submit failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation submit failed' });
  }
}
