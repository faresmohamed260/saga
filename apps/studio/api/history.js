import { supabaseRequest } from './_supabase.js';

function clampLimit(value) {
  const parsed = Number.parseInt(String(value || '24'), 10);
  if (!Number.isFinite(parsed)) return 24;
  return Math.min(Math.max(parsed, 1), 100);
}

function clampOffset(value) {
  const parsed = Number.parseInt(String(value || '0'), 10);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(parsed, 0);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const limit = clampLimit(req.query?.limit);
    const offset = clampOffset(req.query?.offset);
    const kind = typeof req.query?.kind === 'string' ? req.query.kind : '';
    const model = typeof req.query?.model === 'string' ? req.query.model : '';

    const params = new URLSearchParams();
    params.set('select', 'id,status,kind,mode,model,prompt,negative_prompt,r2_key,media_url,thumbnail_r2_key,thumbnail_url,mime_type,resolution,width,height,thumbnail_width,thumbnail_height,duration_ms,seed,workflow_id,provider,error_message,metadata,is_favorite,created_at,started_at,completed_at');
    params.set('order', 'created_at.desc,id.desc');
    params.set('limit', String(limit + 1));
    params.set('offset', String(offset));
    params.set('status', 'eq.completed');
    if (kind === 'image' || kind === 'video') params.set('kind', `eq.${kind}`);
    if (model) params.set('model', `eq.${model}`);

    const [rows, modelRows] = await Promise.all([
      supabaseRequest(`studio_generations?${params.toString()}`, { method: 'GET' }),
      supabaseRequest('studio_generations?select=model&status=eq.completed&model=not.is.null&order=model.asc&limit=500', { method: 'GET' }),
    ]);

    const allRows = Array.isArray(rows) ? rows : [];
    const hasMore = allRows.length > limit;
    const items = hasMore ? allRows.slice(0, limit) : allRows;
    const models = [...new Set((Array.isArray(modelRows) ? modelRows : []).map((row) => row.model).filter(Boolean))];

    return res.status(200).json({
      items,
      page: {
        limit,
        offset,
        nextOffset: hasMore ? offset + items.length : null,
        hasMore,
      },
      facets: { models },
    });
  } catch (error) {
    console.error('History fetch failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'History fetch failed' });
  }
}
