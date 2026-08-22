import { DeleteObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { supabaseRequest } from './_supabase.js';

const bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();

function getClient() {
  const accountId = String(process.env.R2_ACCOUNT_ID || '').trim();
  const accessKeyId = String(process.env.R2_ACCESS_KEY_ID || '').trim();
  const secretAccessKey = String(process.env.R2_SECRET_ACCESS_KEY || '').trim();
  if (!accountId || !accessKeyId || !secretAccessKey) return null;
  return new S3Client({
    region: 'auto',
    endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
    credentials: { accessKeyId, secretAccessKey },
    requestChecksumCalculation: 'WHEN_REQUIRED',
    responseChecksumValidation: 'WHEN_REQUIRED',
  });
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));
}

export default async function handler(req, res) {
  if (req.method !== 'DELETE') {
    res.setHeader('Allow', 'DELETE');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const id = typeof req.query?.id === 'string' ? req.query.id : '';
  if (!isUuid(id)) return res.status(400).json({ error: 'Invalid generation id' });

  const client = getClient();
  if (!client) return res.status(503).json({ error: 'R2 storage is not configured' });

  try {
    const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}&select=id,r2_key,thumbnail_r2_key&limit=1`, { method: 'GET' });
    const generation = Array.isArray(rows) ? rows[0] : null;
    if (!generation) return res.status(404).json({ error: 'Generation not found' });

    const keys = [generation.r2_key, generation.thumbnail_r2_key].filter(Boolean);
    const failures = [];
    for (const key of keys) {
      try {
        await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key }));
      } catch (error) {
        console.error('R2 delete failed', { key, error });
        failures.push(key);
      }
    }
    if (failures.length) return res.status(502).json({ error: 'Could not delete all media objects', failedKeys: failures });

    await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: { Prefer: 'return=minimal' },
    });

    return res.status(200).json({ deleted: true, id });
  } catch (error) {
    console.error('Generation delete failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation delete failed' });
  }
}
