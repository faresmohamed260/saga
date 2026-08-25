import { randomUUID } from 'node:crypto';
import { createSourceReadUrl, createSourceUploadUrl, deleteSourceObject, headSourceObject, isLibraryUploadKey } from './_r2.js';
import { supabaseRequest } from './_supabase.js';

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SUPPORTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);

function safeFilename(value) {
  return String(value || 'input.png').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 120) || 'input.png';
}

function cleanDisplayName(value, fallback = 'Untitled upload') {
  const clean = String(value || fallback).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  return (clean || fallback).slice(0, 240);
}

function extensionFor(contentType, filename) {
  if (contentType === 'image/webp') return 'webp';
  if (contentType === 'image/jpeg') return 'jpg';
  if (contentType === 'image/png') return 'png';
  const ext = String(filename || '').split('.').pop()?.toLowerCase();
  return ['png', 'jpg', 'jpeg', 'webp'].includes(ext) ? ext : 'png';
}

function clampLimit(value) {
  const parsed = Number.parseInt(String(value || '60'), 10);
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), 100) : 60;
}

function clampOffset(value) {
  const parsed = Number.parseInt(String(value || '0'), 10);
  return Number.isFinite(parsed) ? Math.max(parsed, 0) : 0;
}

function positiveInteger(value) {
  const parsed = Number.parseInt(String(value || ''), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));
}

async function presentAsset(row) {
  const [url, downloadUrl] = await Promise.all([
    createSourceReadUrl({ key: row.r2_key, expiresIn: 3600 }),
    createSourceReadUrl({ key: row.r2_key, expiresIn: 3600, downloadName: row.filename || row.display_name || 'upload' }),
  ]);
  return {
    id: row.id,
    key: row.r2_key,
    filename: row.filename,
    name: row.display_name,
    mimeType: row.mime_type,
    size: Number(row.size_bytes || 0),
    width: row.width,
    height: row.height,
    favorite: Boolean(row.is_favorite),
    metadata: row.metadata || {},
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    url,
    downloadUrl,
  };
}

async function listUploads(req, res) {
  const limit = clampLimit(req.query?.limit);
  const offset = clampOffset(req.query?.offset);
  const sort = req.query?.sort === 'oldest' ? 'oldest' : 'newest';
  const favoriteOnly = req.query?.favorite === 'true';
  const search = typeof req.query?.search === 'string' ? req.query.search.trim().slice(0, 200) : '';

  const params = new URLSearchParams();
  params.set('select', 'id,r2_key,filename,display_name,mime_type,size_bytes,width,height,is_favorite,metadata,created_at,updated_at');
  params.set('order', sort === 'oldest' ? 'created_at.asc,id.asc' : 'created_at.desc,id.desc');
  params.set('limit', String(limit + 1));
  params.set('offset', String(offset));
  if (favoriteOnly) params.set('is_favorite', 'eq.true');
  if (search) params.set('display_name', `ilike.*${search.replace(/[*,]/g, ' ')}*`);

  const rows = await supabaseRequest(`studio_uploads?${params.toString()}`, { method: 'GET' });
  const allRows = Array.isArray(rows) ? rows : [];
  const hasMore = allRows.length > limit;
  const visibleRows = hasMore ? allRows.slice(0, limit) : allRows;
  const items = await Promise.all(visibleRows.map(presentAsset));
  return res.status(200).json({
    items,
    page: { limit, offset, nextOffset: hasMore ? offset + items.length : null, hasMore },
  });
}

async function createUploadTicket(body, res) {
  const contentType = String(body.contentType || '').split(';')[0].trim().toLowerCase();
  const filename = safeFilename(body.filename);
  const size = Number(body.size || 0);
  if (!SUPPORTED_TYPES.has(contentType)) {
    return res.status(415).json({ error: 'Only PNG, JPEG, and WebP source uploads are supported' });
  }
  if (!Number.isFinite(size) || size <= 0 || size > MAX_UPLOAD_BYTES) {
    return res.status(413).json({ error: 'Source upload must be between 1 byte and 25 MB' });
  }

  const now = new Date();
  const prefix = body.purpose === 'library-upload' ? 'uploads' : 'sources';
  const key = `${prefix}/${now.getUTCFullYear()}/${String(now.getUTCMonth() + 1).padStart(2, '0')}/${randomUUID()}.${extensionFor(contentType, filename)}`;
  const uploadUrl = await createSourceUploadUrl({ key, contentType, expiresIn: 300 });
  return res.status(201).json({
    key,
    uploadUrl,
    method: 'PUT',
    contentType,
    expiresIn: 300,
    maxBytes: MAX_UPLOAD_BYTES,
  });
}

async function completeLibraryUpload(body, res) {
  const key = String(body.key || '');
  if (!isLibraryUploadKey(key)) return res.status(400).json({ error: 'Invalid library upload key' });

  const filename = safeFilename(body.filename);
  const displayName = cleanDisplayName(body.displayName, String(body.filename || 'Untitled upload').replace(/\.[^.]+$/, ''));
  const expectedType = String(body.contentType || '').split(';')[0].trim().toLowerCase();
  const expectedSize = Number(body.size || 0);
  if (!SUPPORTED_TYPES.has(expectedType)) return res.status(415).json({ error: 'Unsupported library upload type' });
  if (!Number.isFinite(expectedSize) || expectedSize <= 0 || expectedSize > MAX_UPLOAD_BYTES) return res.status(413).json({ error: 'Invalid library upload size' });

  const existingParams = new URLSearchParams({ select: 'id,r2_key,filename,display_name,mime_type,size_bytes,width,height,is_favorite,metadata,created_at,updated_at', r2_key: `eq.${key}`, limit: '1' });
  const existingRows = await supabaseRequest(`studio_uploads?${existingParams.toString()}`, { method: 'GET' });
  if (Array.isArray(existingRows) && existingRows[0]) return res.status(200).json({ item: await presentAsset(existingRows[0]) });

  const object = await headSourceObject(key);
  if (object.size <= 0 || object.size > MAX_UPLOAD_BYTES || object.size !== expectedSize) {
    return res.status(409).json({ error: 'Uploaded object size does not match the upload ticket' });
  }
  if (object.contentType !== expectedType) {
    return res.status(409).json({ error: 'Uploaded object type does not match the upload ticket' });
  }

  const rows = await supabaseRequest('studio_uploads?select=*', {
    method: 'POST',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify({
      r2_key: key,
      filename,
      display_name: displayName,
      mime_type: expectedType,
      size_bytes: expectedSize,
      width: positiveInteger(body.width),
      height: positiveInteger(body.height),
      metadata: { etag: object.etag || null, source: 'gallery-upload' },
    }),
  });
  const row = Array.isArray(rows) ? rows[0] : rows;
  return res.status(201).json({ item: await presentAsset(row) });
}

async function updateUpload(req, res) {
  const body = typeof req.body === 'object' && req.body ? req.body : {};
  const id = String(body.id || req.query?.id || '');
  if (!isUuid(id)) return res.status(400).json({ error: 'Valid upload id is required' });

  const patch = { updated_at: new Date().toISOString() };
  if (Object.hasOwn(body, 'displayName')) patch.display_name = cleanDisplayName(body.displayName);
  if (Object.hasOwn(body, 'favorite')) patch.is_favorite = Boolean(body.favorite);
  if (Object.keys(patch).length === 1) return res.status(400).json({ error: 'No upload changes were supplied' });

  const rows = await supabaseRequest(`studio_uploads?id=eq.${encodeURIComponent(id)}&select=*`, {
    method: 'PATCH',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify(patch),
  });
  const row = Array.isArray(rows) ? rows[0] : rows;
  if (!row) return res.status(404).json({ error: 'Upload not found' });
  return res.status(200).json({ item: await presentAsset(row) });
}

async function deleteUpload(req, res) {
  const id = String(req.query?.id || req.body?.id || '');
  if (!isUuid(id)) return res.status(400).json({ error: 'Valid upload id is required' });

  const rows = await supabaseRequest(`studio_uploads?id=eq.${encodeURIComponent(id)}&select=id,r2_key&limit=1`, { method: 'GET' });
  const row = Array.isArray(rows) ? rows[0] : null;
  if (!row) return res.status(404).json({ error: 'Upload not found' });

  await deleteSourceObject(row.r2_key);
  await supabaseRequest(`studio_uploads?id=eq.${encodeURIComponent(id)}`, { method: 'DELETE' });
  return res.status(200).json({ deleted: true, id });
}

export default async function handler(req, res) {
  try {
    if (req.method === 'GET') return await listUploads(req, res);
    if (req.method === 'POST') {
      const body = typeof req.body === 'object' && req.body ? req.body : {};
      if (body.phase === 'complete') return await completeLibraryUpload(body, res);
      return await createUploadTicket(body, res);
    }
    if (req.method === 'PATCH') return await updateUpload(req, res);
    if (req.method === 'DELETE') return await deleteUpload(req, res);
    res.setHeader('Allow', 'GET, POST, PATCH, DELETE');
    return res.status(405).json({ error: 'Method not allowed' });
  } catch (error) {
    console.error('Uploads library request failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Uploads library request failed' });
  }
}
