import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { randomUUID } from 'node:crypto';
import { insertGeneration } from './_supabase.js';

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

function safeMetadata(value, maxLength) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[^\x20-\x7E]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
}

function safeText(value, maxLength) {
  return String(value || '').trim().slice(0, maxLength);
}

function parseSeed(value) {
  if (value == null || value === '') return null;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

async function readBody(req, limit = 6 * 1024 * 1024) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > limit) {
      const error = new Error('Payload too large');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

function generationKey(contentType) {
  const now = new Date();
  const year = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, '0');
  const ext = contentType === 'image/webp' ? 'webp' : contentType === 'image/jpeg' ? 'jpg' : 'png';
  return `generations/${year}/${month}/${randomUUID()}.${ext}`;
}

export default async function handler(req, res) {
  const client = getClient();
  if (!client) {
    res.status(503).json({ error: 'R2 storage is not configured' });
    return;
  }

  if (req.method === 'POST') {
    try {
      const contentType = String(req.headers['content-type'] || 'image/png').split(';')[0].trim();
      if (!contentType.startsWith('image/')) {
        res.status(415).json({ error: 'Only image uploads are supported' });
        return;
      }
      const body = await readBody(req);
      if (!body.length) {
        res.status(400).json({ error: 'Empty upload' });
        return;
      }

      const key = generationKey(contentType);
      const model = safeText(req.headers['x-saga-model'] || 'flux2-klein-9b', 240);
      const resolution = safeText(req.headers['x-saga-resolution'] || '', 64);
      const prompt = safeText(req.headers['x-saga-prompt'] || '', 2000);
      const negativePrompt = safeText(req.headers['x-saga-negative-prompt'] || '', 2000);
      const seed = parseSeed(req.headers['x-saga-seed']);
      const mediaUrl = `/api/media?key=${encodeURIComponent(key)}`;

      await client.send(new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: body,
        ContentLength: body.length,
        ContentType: contentType,
        CacheControl: 'private, max-age=31536000, immutable',
        Metadata: {
          source: 'saga-studio',
          model: safeMetadata(model, 120),
          resolution: safeMetadata(resolution, 32),
        },
      }));

      let generation = null;
      try {
        generation = await insertGeneration({
          status: 'completed',
          kind: 'image',
          mode: 'edit',
          model,
          prompt,
          negative_prompt: negativePrompt,
          r2_key: key,
          media_url: mediaUrl,
          mime_type: contentType,
          resolution,
          seed,
          workflow_id: 'flux2-klein-image-edit',
          metadata: { source: 'saga-studio', storage: 'cloudflare-r2' },
          completed_at: new Date().toISOString(),
        });
      } catch (historyError) {
        console.error('Generation history insert failed', historyError);
      }

      res.status(201).json({
        key,
        url: mediaUrl,
        persisted: true,
        generationId: generation?.id || null,
        historyPersisted: Boolean(generation?.id),
      });
    } catch (error) {
      console.error('R2 upload failed', error);
      res.status(error?.statusCode || error?.$metadata?.httpStatusCode || 500).json({ error: error?.message || 'R2 upload failed' });
    }
    return;
  }

  if (req.method === 'GET') {
    const key = typeof req.query?.key === 'string' ? req.query.key : '';
    if (!key || !key.startsWith('generations/')) {
      res.status(400).json({ error: 'Invalid media key' });
      return;
    }
    try {
      const object = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
      res.setHeader('Content-Type', object.ContentType || 'application/octet-stream');
      res.setHeader('Cache-Control', 'private, max-age=86400');
      if (object.ContentLength != null) res.setHeader('Content-Length', String(object.ContentLength));
      for await (const chunk of object.Body) res.write(chunk);
      res.end();
    } catch (error) {
      console.error('R2 read failed', error);
      const status = error?.$metadata?.httpStatusCode === 404 || error?.name === 'NoSuchKey' ? 404 : 500;
      res.status(status).json({ error: status === 404 ? 'Media not found' : 'R2 read failed' });
    }
    return;
  }

  res.setHeader('Allow', 'GET, POST');
  res.status(405).json({ error: 'Method not allowed' });
}
