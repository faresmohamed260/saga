import { supabaseRequest } from './_supabase.js';

function clampLimit(value) {
  const parsed = Number.parseInt(String(value || '24'), 10);
  if (!Number.isFinite(parsed)) return 24;
  return Math.min(Math.max(parsed, 1), 100);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const limit = clampLimit(req.query?.limit);
    const kind = typeof req.query?.kind === 'string' ? req.query.kind : '';
    const model = typeof req.query?.model === 'string' ? req.query.model : '';

    const params = new URLSearchParams();
    params.set('select', 'id,status,kind,mode,model,prompt,negative_prompt,r2_key,media_url,mime_type,resolution,width,height,duration_ms,seed,workflow_id,error_message,metadata,created_at,completed_at');
    params.set('order', 'created_at.desc');
    params.set('limit', String(limit));
    if (kind === 'image' || kind === 'video') params.set('kind', `eq.${kind}`);
    if (model) params.set('model', `eq.${model}`);

    const rows = await supabaseRequest(`studio_generations?${params.toString()}`, { method: 'GET' });
    return res.status(200).json({ items: Array.isArray(rows) ? rows : [] });
  } catch (error) {
    console.error('History fetch failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'History fetch failed' });
  }
}
