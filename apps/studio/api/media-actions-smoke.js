import { supabaseRequest } from './_supabase.js';

const PROD = 'https://studio.faresuniform.uk';
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6K1sAAAAASUVORK5CYII=', 'base64');

async function exists(url) {
  const response = await fetch(url, { method: 'GET' });
  return { status: response.status, ok: response.ok, contentType: response.headers.get('content-type') };
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET only' });

  let generationId = null;
  let originalUrl = null;
  let thumbnailUrl = null;
  try {
    const upload = await fetch(`${PROD}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'image/png',
        'X-Saga-Model': encodeURIComponent('Smoke Test · Media Actions'),
        'X-Saga-Resolution': encodeURIComponent('1 px'),
        'X-Saga-Prompt': encodeURIComponent('Disposable media actions smoke test'),
        'X-Saga-Seed': '123456789',
      },
      body: PNG,
    });
    const uploadBody = await upload.json().catch(() => ({}));
    if (!upload.ok || !uploadBody?.generationId) throw new Error(`Upload failed (${upload.status}): ${uploadBody?.error || 'missing generationId'}`);

    generationId = uploadBody.generationId;
    originalUrl = `${PROD}${uploadBody.url}`;
    thumbnailUrl = uploadBody.thumbnailUrl ? `${PROD}${uploadBody.thumbnailUrl}` : null;

    const beforeOriginal = await exists(originalUrl);
    const beforeThumbnail = thumbnailUrl ? await exists(thumbnailUrl) : null;
    const beforeRows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(generationId)}&select=id,r2_key,thumbnail_r2_key,prompt,seed,model`, { method: 'GET' });

    const deletion = await fetch(`${PROD}/api/generations?id=${encodeURIComponent(generationId)}`, { method: 'DELETE' });
    const deletionBody = await deletion.json().catch(() => ({}));
    if (!deletion.ok) throw new Error(`Delete failed (${deletion.status}): ${deletionBody?.error || 'unknown error'}`);

    const afterOriginal = await exists(originalUrl);
    const afterThumbnail = thumbnailUrl ? await exists(thumbnailUrl) : null;
    const afterRows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(generationId)}&select=id`, { method: 'GET' });

    const checks = {
      uploadCreatedGeneration: Boolean(generationId),
      originalReadableBeforeDelete: beforeOriginal.ok,
      thumbnailReadableBeforeDelete: Boolean(beforeThumbnail?.ok),
      databaseRowExistsBeforeDelete: Array.isArray(beforeRows) && beforeRows.length === 1,
      deleteReturnedSuccess: deletionBody?.deleted === true,
      originalGoneAfterDelete: afterOriginal.status === 404,
      thumbnailGoneAfterDelete: afterThumbnail?.status === 404,
      databaseRowGoneAfterDelete: Array.isArray(afterRows) && afterRows.length === 0,
    };
    const passed = Object.values(checks).every(Boolean);
    return res.status(passed ? 200 : 500).json({ passed, generationId, checks, before: { original: beforeOriginal, thumbnail: beforeThumbnail, row: beforeRows?.[0] || null }, after: { original: afterOriginal, thumbnail: afterThumbnail, rowCount: Array.isArray(afterRows) ? afterRows.length : null } });
  } catch (error) {
    return res.status(500).json({ passed: false, generationId, originalUrl, thumbnailUrl, error: error?.message || String(error) });
  }
}
