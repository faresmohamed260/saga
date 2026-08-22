import { supabaseRequest } from './_supabase.js';

const GENERATION_SELECT = 'id,status,kind,mode,model,prompt,negative_prompt,r2_key,media_url,thumbnail_r2_key,thumbnail_url,mime_type,resolution,width,height,thumbnail_width,thumbnail_height,duration_ms,seed,workflow_id,error_message,metadata,is_favorite,created_at,completed_at';

function validUuid(value) {
  return /^[0-9a-f-]{36}$/i.test(String(value || '').trim());
}

export default async function handler(req, res) {
  try {
    if (req.method === 'GET') {
      const collectionId = String(req.query?.collectionId || '').trim();
      if (!validUuid(collectionId)) return res.status(400).json({ error: 'Invalid collection id' });
      const memberships = await supabaseRequest(`studio_collection_items?select=generation_id,created_at&collection_id=eq.${encodeURIComponent(collectionId)}&order=created_at.desc`, { method: 'GET' });
      const ids = (Array.isArray(memberships) ? memberships : []).map((item) => item.generation_id).filter(Boolean);
      if (!ids.length) return res.status(200).json({ items: [] });
      const rows = await supabaseRequest(`studio_generations?select=${encodeURIComponent(GENERATION_SELECT)}&id=in.(${ids.map(encodeURIComponent).join(',')})`, { method: 'GET' });
      const rowMap = new Map((Array.isArray(rows) ? rows : []).map((row) => [row.id, row]));
      return res.status(200).json({ items: ids.map((id) => rowMap.get(id)).filter(Boolean) });
    }

    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const collectionId = String(body.collectionId || '').trim();
    const generationId = String(body.generationId || '').trim();
    if (!validUuid(collectionId) || !validUuid(generationId)) return res.status(400).json({ error: 'Invalid collection or generation id' });

    if (req.method === 'POST') {
      await supabaseRequest('studio_collection_items?on_conflict=collection_id,generation_id', {
        method: 'POST',
        headers: { Prefer: 'resolution=ignore-duplicates,return=minimal' },
        body: JSON.stringify({ collection_id: collectionId, generation_id: generationId }),
      });
      await supabaseRequest(`studio_collections?id=eq.${encodeURIComponent(collectionId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ updated_at: new Date().toISOString() }),
      });
      return res.status(204).end();
    }

    if (req.method === 'DELETE') {
      await supabaseRequest(`studio_collection_items?collection_id=eq.${encodeURIComponent(collectionId)}&generation_id=eq.${encodeURIComponent(generationId)}`, { method: 'DELETE' });
      await supabaseRequest(`studio_collections?id=eq.${encodeURIComponent(collectionId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ updated_at: new Date().toISOString() }),
      });
      return res.status(204).end();
    }

    res.setHeader('Allow', 'GET, POST, DELETE');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Collection items request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Collection items request failed' });
  }
}
