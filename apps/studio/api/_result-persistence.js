import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import sharp from 'sharp';
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

function safeMetadata(value, maxLength) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[^\x20-\x7E]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
}

function objectKeys(job, contentType) {
  const created = new Date(job?.created_at || Date.now());
  const date = Number.isNaN(created.getTime()) ? new Date() : created;
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const ext = contentType === 'image/webp' ? 'webp' : contentType === 'image/jpeg' ? 'jpg' : 'png';
  return {
    original: `generations/${year}/${month}/${job.id}.${ext}`,
    thumbnail: `thumbnails/${year}/${month}/${job.id}.webp`,
  };
}

async function createThumbnail(body) {
  const source = sharp(body, { failOn: 'warning' }).rotate();
  const metadata = await source.metadata();
  const { data, info } = await source
    .clone()
    .resize({ width: 512, height: 512, fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 78, effort: 4 })
    .toBuffer({ resolveWithObject: true });
  return {
    data,
    originalWidth: metadata.width || null,
    originalHeight: metadata.height || null,
    width: info.width || null,
    height: info.height || null,
  };
}

export async function persistImageJobResult(job, bytes, contentType = 'image/png') {
  if (!job?.id) throw new Error('Generation job is required for persistence');
  if (!Buffer.isBuffer(bytes) || !bytes.length) throw new Error('Generated image is empty');
  if (!String(contentType).startsWith('image/')) throw new Error('Only image results are supported');

  if (job.status === 'completed' && job.media_url) return job;
  if (job.status !== 'running') {
    const error = new Error(`Cannot persist generation in ${job.status || 'unknown'} state`);
    error.statusCode = 409;
    throw error;
  }

  const client = getClient();
  if (!client) {
    const error = new Error('R2 storage is not configured');
    error.statusCode = 503;
    throw error;
  }

  const keys = objectKeys(job, contentType);
  const mediaUrl = `/api/media?key=${encodeURIComponent(keys.original)}`;
  await client.send(new PutObjectCommand({
    Bucket: bucket,
    Key: keys.original,
    Body: bytes,
    ContentLength: bytes.length,
    ContentType: contentType,
    CacheControl: 'private, max-age=31536000, immutable',
    Metadata: {
      source: 'saga-studio-orchestrator',
      model: safeMetadata(job.model, 120),
      resolution: safeMetadata(job.resolution, 32),
    },
  }));

  let thumbnail = null;
  let thumbnailUrl = null;
  try {
    thumbnail = await createThumbnail(bytes);
    await client.send(new PutObjectCommand({
      Bucket: bucket,
      Key: keys.thumbnail,
      Body: thumbnail.data,
      ContentLength: thumbnail.data.length,
      ContentType: 'image/webp',
      CacheControl: 'private, max-age=31536000, immutable',
      Metadata: {
        source: 'saga-studio-thumbnail',
        original: safeMetadata(keys.original, 240),
      },
    }));
    thumbnailUrl = `/api/media?key=${encodeURIComponent(keys.thumbnail)}`;
  } catch (error) {
    console.error('Orchestrated thumbnail persistence failed', error);
  }

  const metadata = {
    ...(job.metadata && typeof job.metadata === 'object' ? job.metadata : {}),
    storage: 'cloudflare-r2',
    persistence: 'orchestrator-v1',
    thumbnailFormat: thumbnailUrl ? 'webp' : null,
  };
  const patch = {
    status: 'completed',
    r2_key: keys.original,
    media_url: mediaUrl,
    thumbnail_r2_key: thumbnailUrl ? keys.thumbnail : null,
    thumbnail_url: thumbnailUrl,
    mime_type: contentType,
    width: thumbnail?.originalWidth || null,
    height: thumbnail?.originalHeight || null,
    thumbnail_width: thumbnail?.width || null,
    thumbnail_height: thumbnail?.height || null,
    error_message: null,
    metadata,
    completed_at: new Date().toISOString(),
  };

  const rows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(job.id)}&status=eq.running&select=*`, {
    method: 'PATCH',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify(patch),
  });
  const completed = Array.isArray(rows) ? rows[0] : rows;
  if (completed?.id) return completed;

  const currentRows = await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(job.id)}&select=*&limit=1`, { method: 'GET' });
  const current = Array.isArray(currentRows) ? currentRows[0] : null;
  if (current?.status === 'completed' && current.media_url) return current;

  const error = new Error('Generation result could not be finalized');
  error.statusCode = 409;
  throw error;
}
