import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import sharp from 'sharp';
import { supabaseRequest } from './_supabase.js';

// The REDGraft validation workflow exercises video persistence against live R2/Supabase credentials.
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

function extensionForContentType(contentType) {
  if (contentType === 'image/webp') return 'webp';
  if (contentType === 'image/jpeg') return 'jpg';
  if (contentType === 'video/webm') return 'webm';
  if (contentType === 'video/quicktime') return 'mov';
  if (contentType === 'video/mp4') return 'mp4';
  return 'png';
}

function objectKeys(job, contentType) {
  const created = new Date(job?.created_at || Date.now());
  const date = Number.isNaN(created.getTime()) ? new Date() : created;
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const ext = extensionForContentType(contentType);
  return {
    original: `generations/${year}/${month}/${job.id}.${ext}`,
    thumbnail: `thumbnails/${year}/${month}/${job.id}.webp`,
  };
}

export async function createThumbnail(body) {
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

async function finalizeJob(job, patch) {
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

function assertPersistable(job, bytes) {
  if (!job?.id) throw new Error('Generation job is required for persistence');
  if (!Buffer.isBuffer(bytes) || !bytes.length) throw new Error('Generated media is empty');
  if (job.status === 'completed' && job.media_url) return false;
  if (job.status !== 'running') {
    const error = new Error(`Cannot persist generation in ${job.status || 'unknown'} state`);
    error.statusCode = 409;
    throw error;
  }
  return true;
}

async function putOriginal(client, job, bytes, contentType, key) {
  await client.send(new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    Body: bytes,
    ContentLength: bytes.length,
    ContentType: contentType,
    CacheControl: 'private, max-age=31536000, immutable',
    Metadata: {
      source: 'saga-studio-orchestrator',
      model: safeMetadata(job.model, 120),
      resolution: safeMetadata(job.resolution, 32),
      kind: safeMetadata(job.kind, 24),
    },
  }));
}

async function persistThumbnail(client, job, bytes, keys) {
  const thumbnail = await createThumbnail(bytes);
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
      kind: safeMetadata(job.kind, 24),
    },
  }));
  return {
    thumbnail,
    thumbnailUrl: `/api/media?key=${encodeURIComponent(keys.thumbnail)}`,
  };
}

export async function persistImageJobResult(job, bytes, contentType = 'image/png') {
  if (!String(contentType).startsWith('image/')) throw new Error('Image persistence requires an image result');
  if (!assertPersistable(job, bytes)) return job;

  const client = getClient();
  if (!client) {
    const error = new Error('R2 storage is not configured');
    error.statusCode = 503;
    throw error;
  }

  const keys = objectKeys(job, contentType);
  const mediaUrl = `/api/media?key=${encodeURIComponent(keys.original)}`;
  await putOriginal(client, job, bytes, contentType, keys.original);

  let thumbnail = null;
  let thumbnailUrl = null;
  try {
    ({ thumbnail, thumbnailUrl } = await persistThumbnail(client, job, bytes, keys));
  } catch (error) {
    console.error('Orchestrated thumbnail persistence failed', error);
  }

  const metadata = {
    ...(job.metadata && typeof job.metadata === 'object' ? job.metadata : {}),
    storage: 'cloudflare-r2',
    persistence: 'orchestrator-v1',
    thumbnailFormat: thumbnailUrl ? 'webp' : null,
  };
  return finalizeJob(job, {
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
  });
}

export async function persistVideoJobResult(
  job,
  bytes,
  contentType = 'video/mp4',
  posterBytes = null,
  posterContentType = 'image/jpeg',
) {
  if (!String(contentType).startsWith('video/')) throw new Error('Video persistence requires a video result');
  if (!assertPersistable(job, bytes)) return job;

  const client = getClient();
  if (!client) {
    const error = new Error('R2 storage is not configured');
    error.statusCode = 503;
    throw error;
  }

  const keys = objectKeys(job, contentType);
  const mediaUrl = `/api/media?key=${encodeURIComponent(keys.original)}`;
  await putOriginal(client, job, bytes, contentType, keys.original);

  let thumbnail = null;
  let thumbnailUrl = null;
  if (Buffer.isBuffer(posterBytes) && posterBytes.length && String(posterContentType).startsWith('image/')) {
    try {
      ({ thumbnail, thumbnailUrl } = await persistThumbnail(client, job, posterBytes, keys));
    } catch (error) {
      console.error('Orchestrated video poster persistence failed', error);
    }
  }

  const metadata = {
    ...(job.metadata && typeof job.metadata === 'object' ? job.metadata : {}),
    storage: 'cloudflare-r2',
    persistence: 'orchestrator-v1',
    thumbnailFormat: thumbnailUrl ? 'webp' : null,
    video: {
      ...((job.metadata && typeof job.metadata === 'object' && job.metadata.video) || {}),
      contentType,
      byteLength: bytes.length,
      posterSourceContentType: thumbnailUrl ? String(posterContentType) : null,
    },
  };

  return finalizeJob(job, {
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
  });
}
