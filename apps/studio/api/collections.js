import { supabaseRequest } from './_supabase.js';

function cleanName(value) {
  return String(value || '').trim().slice(0, 120);
}

export default async function handler(req, res) {
  try {
    if (req.method === 'GET') {
      const collections = await supabaseRequest('studio_collections?select=id,name,created_at,updated_at&order=updated_at.desc', { method: 'GET' });
      const items = await supabaseRequest('studio_collection_items?select=collection_id,generation_id,created_at&order=created_at.desc', { method: 'GET' });
      const generations = await supabaseRequest('studio_generations?select=id,thumbnail_url,media_url,kind&order=created_at.desc&limit=500', { method: 'GET' });
      const generationMap = new Map((Array.isArray(generations) ? generations : []).map((row) => [row.id, row]));
      const collectionItems = Array.isArray(items) ? items : [];
      const result = (Array.isArray(collections) ? collections : []).map((collection) => {
        const members = collectionItems.filter((item) => item.collection_id === collection.id);
        const coverGeneration = members.map((item) => generationMap.get(item.generation_id)).find(Boolean) || null;
        return {
          ...collection,
          itemCount: members.length,
          coverUrl: coverGeneration?.thumbnail_url || (coverGeneration?.kind === 'image' ? coverGeneration?.media_url : '') || '',
        };
      });
      return res.status(200).json({ collections: result });
    }

    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});

    if (req.method === 'POST') {
      const name = cleanName(body.name);
      if (!name) return res.status(400).json({ error: 'Collection name is required' });
      const rows = await supabaseRequest('studio_collections?select=*', {
        method: 'POST',
        headers: { Prefer: 'return=representation' },
        body: JSON.stringify({ name }),
      });
      return res.status(201).json({ collection: Array.isArray(rows) ? rows[0] : rows });
    }

    const id = String(body.id || req.query?.id || '').trim();
    if (!/^[0-9a-f-]{36}$/i.test(id)) return res.status(400).json({ error: 'Invalid collection id' });

    if (req.method === 'PATCH') {
      const name = cleanName(body.name);
      if (!name) return res.status(400).json({ error: 'Collection name is required' });
      const rows = await supabaseRequest(`studio_collections?id=eq.${encodeURIComponent(id)}&select=*`, {
        method: 'PATCH',
        headers: { Prefer: 'return=representation' },
        body: JSON.stringify({ name, updated_at: new Date().toISOString() }),
      });
      return res.status(200).json({ collection: Array.isArray(rows) ? rows[0] : rows });
    }

    if (req.method === 'DELETE') {
      await supabaseRequest(`studio_collections?id=eq.${encodeURIComponent(id)}`, { method: 'DELETE' });
      return res.status(204).end();
    }

    res.setHeader('Allow', 'GET, POST, PATCH, DELETE');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Collections request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Collections request failed' });
  }
}
