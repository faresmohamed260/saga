import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { randomUUID } from 'node:crypto';
import sharp from 'sharp';
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

function decodeHeader(value) {
  const raw = String(value || '');
  if (!raw) return '';
  try { return decodeURIComponent(raw); } catch { return raw; }
}

function safeText(value, maxLength) { return String(value || '').trim().slice(0, maxLength); }

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

function generationKeys(contentType) {
  const now = new Date();
  const year = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, '0');
  const id = randomUUID();
  const ext = contentType === 'image/webp' ? 'webp' : contentType === 'image/jpeg' ? 'jpg' : 'png';
  return { original: `generations/${year}/${month}/${id}.${ext}`, thumbnail: `thumbnails/${year}/${month}/${id}.webp` };
}

async function createThumbnail(body) {
  const source = sharp(body, { failOn: 'warning' }).rotate();
  const metadata = await source.metadata();
  const { data, info } = await source.clone().resize({ width: 512, height: 512, fit: 'inside', withoutEnlargement: true }).webp({ quality: 78, effort: 4 }).toBuffer({ resolveWithObject: true });
  return { data, originalWidth: metadata.width || null, originalHeight: metadata.height || null, width: info.width || null, height: info.height || null };
}

export default async function handler(req, res) {
  const client = getClient();
  if (!client) return res.status(503).json({ error: 'R2 storage is not configured' });

  if (req.method === 'POST') {
    try {
      const contentType = String(req.headers['content-type'] || 'image/png').split(';')[0].trim();
      if (!contentType.startsWith('image/')) return res.status(415).json({ error: 'Only image uploads are supported' });
      const body = await readBody(req);
      if (!body.length) return res.status(400).json({ error: 'Empty upload' });

      const keys = generationKeys(contentType);
      const model = safeText(decodeHeader(req.headers['x-saga-model']) || 'flux2-klein-9b', 240);
      const resolution = safeText(decodeHeader(req.headers['x-saga-resolution']), 64);
      const prompt = safeText(decodeHeader(req.headers['x-saga-prompt']), 2000);
      const negativePrompt = safeText(decodeHeader(req.headers['x-saga-negative-prompt']), 2000);
      const seed = parseSeed(req.headers['x-saga-seed']);
      const mediaUrl = `/api/media?key=${encodeURIComponent(keys.original)}`;

      await client.send(new PutObjectCommand({
        Bucket: bucket,
        Key: keys.original,
        Body: body,
        ContentLength: body.length,
        ContentType: contentType,
        CacheControl: 'private, max-age=31536000, immutable',
        Metadata: { source: 'saga-studio', model: safeMetadata(model, 120), resolution: safeMetadata(resolution, 32) },
      }));

      let thumbnail = null;
      let thumbnailUrl = null;
      try {
        thumbnail = await createThumbnail(body);
        await client.send(new PutObjectCommand({
          Bucket: bucket,
          Key: keys.thumbnail,
          Body: thumbnail.data,
          ContentLength: thumbnail.data.length,
          ContentType: 'image/webp',
          CacheControl: 'private, max-age=31536000, immutable',
          Metadata: { source: 'saga-studio-thumbnail', original: safeMetadata(keys.original, 240) },
        }));
        thumbnailUrl = `/api/media?key=${encodeURIComponent(keys.thumbnail)}`;
      } catch (thumbnailError) {
        console.error('Thumbnail generation/upload failed', thumbnailError);
      }

      let generation = null;
      try {
        generation = await insertGeneration({
          status: 'completed', kind: 'image', mode: 'edit', model, prompt, negative_prompt: negativePrompt,
          r2_key: keys.original, media_url: mediaUrl, thumbnail_r2_key: thumbnailUrl ? keys.thumbnail : null,
          thumbnail_url: thumbnailUrl, mime_type: contentType, resolution,
          width: thumbnail?.originalWidth || null, height: thumbnail?.originalHeight || null,
          thumbnail_width: thumbnail?.width || null, thumbnail_height: thumbnail?.height || null,
          seed, workflow_id: 'flux2-klein-image-edit',
          metadata: { source: 'saga-studio', storage: 'cloudflare-r2', thumbnailFormat: thumbnailUrl ? 'webp' : null },
          completed_at: new Date().toISOString(),
        });
      } catch (historyError) {
        console.error('Generation history insert failed', historyError);
      }

      return res.status(201).json({ key: keys.original, url: mediaUrl, thumbnailKey: thumbnailUrl ? keys.thumbnail : null, thumbnailUrl, persisted: true, generationId: generation?.id || null, historyPersisted: Boolean(generation?.id) });
    } catch (error) {
      console.error('R2 upload failed', error);
      return res.status(error?.statusCode || error?.$metadata?.httpStatusCode || 500).json({ error: error?.message || 'R2 upload failed' });
    }
  }

  if (req.method === 'GET') {
    const key = typeof req.query?.key === 'string' ? req.query.key : '';
    const allowed = key.startsWith('generations/') || key.startsWith('thumbnails/');
    if (!key || !allowed) return res.status(400).json({ error: 'Invalid media key' });
    try {
      const object = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
      res.setHeader('Content-Type', object.ContentType || 'application/octet-stream');
      res.setHeader('Cache-Control', 'private, max-age=86400');
      if (req.query?.download === '1') {
        const filename = key.split('/').pop() || 'saga-media';
        res.setHeader('Content-Disposition', `attachment; filename="${filename.replace(/["\\]/g, '_')}"`);
      }
      if (object.ContentLength != null) res.setHeader('Content-Length', String(object.ContentLength));
      for await (const chunk of object.Body) res.write(chunk);
      res.end();
    } catch (error) {
      console.error('R2 read failed', error);
      const status = error?.$metadata?.httpStatusCode === 404 || error?.name === 'NoSuchKey' ? 404 : 500;
      return res.status(status).json({ error: status === 404 ? 'Media not found' : 'R2 read failed' });
    }
    return;
  }

  res.setHeader('Allow', 'GET, POST');
  return res.status(405).json({ error: 'Method not allowed' });
}
