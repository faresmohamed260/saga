import { supabaseRequest } from './_supabase.js';

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

export function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));
}

export function parseSeed(value) {
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

export async function getGenerationJob(id) {
  if (!isUuid(id)) return null;
  const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}&select=*&limit=1`, { method: 'GET' });
  return Array.isArray(rows) ? rows[0] : null;
}

export async function createGenerationJob(input) {
  const kind = input.kind === 'video' ? 'video' : 'image';
  const mode = safeText(input.mode || 'edit', 64);
  const model = safeText(input.model, 240);
  const prompt = safeText(input.prompt, 2000);
  const negativePrompt = safeText(input.negativePrompt, 2000);
  const resolution = safeText(input.resolution, 64);
  const workflowId = safeText(input.workflowId, 160);
  const provider = safeText(input.provider || 'modal', 80);
  const seed = parseSeed(input.seed);

  if (!model) {
    const error = new Error('Model is required');
    error.statusCode = 400;
    throw error;
  }
  if (!prompt) {
    const error = new Error('Prompt is required');
    error.statusCode = 400;
    throw error;
  }

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
  return Array.isArray(rows) ? rows[0] : rows;
}

export async function transitionGenerationJob(id, nextStatus, { errorMessage = '' } = {}) {
  if (!isUuid(id)) {
    const error = new Error('Invalid job id');
    error.statusCode = 400;
    throw error;
  }
  if (!['running', 'completed', 'failed'].includes(nextStatus)) {
    const error = new Error('Invalid job status');
    error.statusCode = 400;
    throw error;
  }

  const current = await getGenerationJob(id);
  if (!current) {
    const error = new Error('Job not found');
    error.statusCode = 404;
    throw error;
  }
  if (current.status !== nextStatus && !allowedTransitions[current.status]?.has(nextStatus)) {
    const error = new Error(`Invalid transition ${current.status} -> ${nextStatus}`);
    error.statusCode = 409;
    throw error;
  }

  const patch = { status: nextStatus };
  if (nextStatus === 'running' && !current.started_at) patch.started_at = new Date().toISOString();
  if (nextStatus === 'failed') {
    patch.error_message = safeText(errorMessage || 'Generation failed', 2000);
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
  return Array.isArray(rows) ? rows[0] : rows;
}

export async function listGenerationJobs({ status = 'all', limit = 30 } = {}) {
  const params = new URLSearchParams();
  params.set('select', 'id,status,kind,mode,model,prompt,negative_prompt,resolution,seed,workflow_id,provider,error_message,metadata,created_at,started_at,completed_at,r2_key,media_url,thumbnail_url');
  params.set('order', 'created_at.desc,id.desc');
  params.set('limit', String(Math.min(Math.max(Number(limit) || 30, 1), 100)));
  params.set('metadata', 'cs.{"lifecycle":"job-v1"}');
  if (status === 'active') params.set('status', 'in.(queued,running)');
  else if (['queued', 'running', 'completed', 'failed'].includes(status)) params.set('status', `eq.${status}`);
  return supabaseRequest(`studio_generations?${params.toString()}`, { method: 'GET' });
}
