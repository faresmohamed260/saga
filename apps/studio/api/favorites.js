import { supabaseRequest } from './_supabase.js';
import qwenReleaseProofHandler from '../server/qwen-release-proof.js';

const GENERATION_SELECT = 'id,status,kind,mode,model,prompt,negative_prompt,r2_key,media_url,thumbnail_r2_key,thumbnail_url,mime_type,resolution,width,height,thumbnail_width,thumbnail_height,duration_ms,seed,workflow_id,error_message,metadata,is_favorite,created_at,completed_at';

export default async function handler(req, res) {
  try {
    if (req.method === 'GET' && req.query?.qwenReleaseProof === 'qwen-civitai-deployment-readiness') {
      return qwenReleaseProofHandler({ ...req, query: { confirm: 'qwen-civitai-deployment-readiness' } }, res);
    }

    if (req.method === 'GET') {
      const rows = await supabaseRequest(`studio_generations?select=${encodeURIComponent(GENERATION_SELECT)}&is_favorite=eq.true&order=created_at.desc&limit=100`, { method: 'GET' });
      return res.status(200).json({ items: Array.isArray(rows) ? rows : [] });
    }

    if (req.method === 'PATCH') {
      const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
      const id = String(body.id || '').trim();
      const isFavorite = Boolean(body.isFavorite);
      if (!/^[0-9a-f-]{36}$/i.test(id)) return res.status(400).json({ error: 'Invalid generation id' });

      const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}&select=id,is_favorite`, {
        method: 'PATCH',
        headers: { Prefer: 'return=representation' },
        body: JSON.stringify({ is_favorite: isFavorite }),
      });
      const generation = Array.isArray(rows) ? rows[0] : null;
      if (!generation) return res.status(404).json({ error: 'Generation not found' });
      return res.status(200).json({ generation });
    }

    res.setHeader('Allow', 'GET, PATCH');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Favorites request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Favorites request failed' });
  }
}
