import { DeleteObjectCommand, S3Client } from '@aws-sdk/client-s3';
import sharp from 'sharp';

const bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();
const targetOrigin = String(process.env.SAGA_STUDIO_SMOKE_TARGET || 'https://studio.faresuniform.uk').replace(/\/$/, '');

function getR2Client() {
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

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const client = getR2Client();
  if (!client) return res.status(503).json({ ok: false, stage: 'config', error: 'R2 not configured' });

  const prompt = 'SAGA automated media smoke test';
  const model = 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
  const seed = '424242';
  let upload = null;

  try {
    const fixture = await sharp({
      create: {
        width: 96,
        height: 64,
        channels: 3,
        background: { r: 38, g: 48, b: 66 },
      },
    }).png().toBuffer();

    const uploadResponse = await fetch(`${targetOrigin}/api/media`, {
      method: 'POST',
      headers: {
        'content-type': 'image/png',
        'x-saga-model': encodeURIComponent(model),
        'x-saga-resolution': encodeURIComponent('smoke 96x64'),
        'x-saga-prompt': encodeURIComponent(prompt),
        'x-saga-seed': seed,
      },
      body: fixture,
    });

    const uploadText = await uploadResponse.text();
    try { upload = JSON.parse(uploadText); } catch { upload = { raw: uploadText }; }
    if (!uploadResponse.ok) return res.status(uploadResponse.status).json({ ok: false, stage: 'upload', upload });

    const historyResponse = await fetch(`${targetOrigin}/api/history?limit=20`, { headers: { accept: 'application/json' } });
    const history = await historyResponse.json();
    const row = Array.isArray(history?.items) ? history.items.find((item) => item.id === upload.generationId) : null;

    let thumbnailCheck = null;
    if (row?.thumbnail_url) {
      const response = await fetch(`${targetOrigin}${row.thumbnail_url}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      thumbnailCheck = { ok: response.ok, status: response.status, contentType: response.headers.get('content-type'), bytes: bytes.length };
    }

    let originalCheck = null;
    if (row?.media_url) {
      const response = await fetch(`${targetOrigin}${row.media_url}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      originalCheck = { ok: response.ok, status: response.status, contentType: response.headers.get('content-type'), bytes: bytes.length };
    }

    const checks = {
      historyPersisted: Boolean(row),
      prompt: row?.prompt === prompt,
      seed: String(row?.seed ?? '') === seed,
      model: row?.model === model,
      thumbnailRecorded: Boolean(row?.thumbnail_r2_key && row?.thumbnail_url),
      thumbnailDimensions: row?.thumbnail_width === 96 && row?.thumbnail_height === 64,
      originalDimensions: row?.width === 96 && row?.height === 64,
      thumbnailReadable: Boolean(thumbnailCheck?.ok && thumbnailCheck?.contentType === 'image/webp' && thumbnailCheck?.bytes > 0),
      originalReadable: Boolean(originalCheck?.ok && originalCheck?.contentType === 'image/png' && originalCheck?.bytes > 0),
    };
    const ok = Object.values(checks).every(Boolean);

    if (upload?.key) {
      try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: upload.key })); } catch {}
    }
    if (upload?.thumbnailKey) {
      try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: upload.thumbnailKey })); } catch {}
    }

    return res.status(ok ? 200 : 500).json({
      ok,
      targetOrigin,
      generationId: upload?.generationId || null,
      checks,
      upload: {
        key: upload?.key || null,
        thumbnailKey: upload?.thumbnailKey || null,
        historyPersisted: Boolean(upload?.historyPersisted),
      },
      row: row ? {
        id: row.id,
        prompt: row.prompt,
        seed: row.seed,
        model: row.model,
        width: row.width,
        height: row.height,
        thumbnailWidth: row.thumbnail_width,
        thumbnailHeight: row.thumbnail_height,
        thumbnailR2Key: row.thumbnail_r2_key,
      } : null,
      thumbnailCheck,
      originalCheck,
      cleanup: { r2Original: Boolean(upload?.key), r2Thumbnail: Boolean(upload?.thumbnailKey), database: 'pending external cleanup' },
    });
  } catch (error) {
    if (upload?.key) {
      try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: upload.key })); } catch {}
    }
    if (upload?.thumbnailKey) {
      try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: upload.thumbnailKey })); } catch {}
    }
    return res.status(500).json({ ok: false, stage: 'exception', targetOrigin, error: error?.message || String(error) });
  }
}
