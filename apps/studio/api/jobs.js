import { supabaseRequest } from './_supabase.js';

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));
}

function parseSeed(value) {
  if (value == null || value === '') return null;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

const allowedTransitions = {
  queued: new Set(['running', 'failed']),
  running: new Set(['completed', 'failed']),
  completed: new Set(),
  failed: new Set(),
};

async function getJob(id) {
  const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}&select=*&limit=1`, { method: 'GET' });
  return Array.isArray(rows) ? rows[0] : null;
}

export default async function handler(req, res) {
  try {
    if (req.method === 'POST') {
      const body = typeof req.body === 'object' && req.body ? req.body : {};
      const kind = body.kind === 'video' ? 'video' : 'image';
      const mode = safeText(body.mode || 'edit', 64);
      const model = safeText(body.model, 240);
      const prompt = safeText(body.prompt, 2000);
      const negativePrompt = safeText(body.negativePrompt, 2000);
      const resolution = safeText(body.resolution, 64);
      const workflowId = safeText(body.workflowId, 160);
      const provider = safeText(body.provider || 'modal', 80);
      const seed = parseSeed(body.seed);

      if (!model) return res.status(400).json({ error: 'Model is required' });
      if (!prompt) return res.status(400).json({ error: 'Prompt is required' });

      const rows = await supabaseRequest('studio_generations?select=*', {
        method: 'POST',
        headers: { Prefer: 'return=representation' },
        body: JSON.stringify({
          status: 'queued',
          kind,
          mode,
          model,
          prompt,
          negative_prompt: negativePrompt,
          resolution,
          seed,
          workflow_id: workflowId || null,
          provider,
          metadata: { source: 'saga-studio', lifecycle: 'job-v1' },
        }),
      });
      const job = Array.isArray(rows) ? rows[0] : rows;
      return res.status(201).json({ job });
    }

    if (req.method === 'GET') {
      const id = typeof req.query?.id === 'string' ? req.query.id : '';
      if (!isUuid(id)) return res.status(400).json({ error: 'Invalid job id' });
      const job = await getJob(id);
      if (!job) return res.status(404).json({ error: 'Job not found' });
      return res.status(200).json({ job });
    }

    if (req.method === 'PATCH') {
      const body = typeof req.body === 'object' && req.body ? req.body : {};
      const id = safeText(body.id, 64);
      const nextStatus = safeText(body.status, 32);
      if (!isUuid(id)) return res.status(400).json({ error: 'Invalid job id' });
      if (!['running', 'completed', 'failed'].includes(nextStatus)) return res.status(400).json({ error: 'Invalid job status' });

      const current = await getJob(id);
      if (!current) return res.status(404).json({ error: 'Job not found' });
      if (current.status !== nextStatus && !allowedTransitions[current.status]?.has(nextStatus)) {
        return res.status(409).json({ error: `Invalid transition ${current.status} -> ${nextStatus}` });
      }

      const patch = { status: nextStatus };
      if (nextStatus === 'running' && !current.started_at) patch.started_at = new Date().toISOString();
      if (nextStatus === 'failed') {
        patch.error_message = safeText(body.errorMessage || 'Generation failed', 2000);
        patch.completed_at = new Date().toISOString();
      }
      if (nextStatus === 'completed') {
        patch.error_message = null;
        patch.completed_at = current.completed_at || new Date().toISOString();
      }

      const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}&select=*`, {
        method: 'PATCH',
        headers: { Prefer: 'return=representation' },
        body: JSON.stringify(patch),
      });
      const job = Array.isArray(rows) ? rows[0] : rows;
      return res.status(200).json({ job });
    }

    res.setHeader('Allow', 'GET, POST, PATCH');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Generation job request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation job request failed' });
  }
}
