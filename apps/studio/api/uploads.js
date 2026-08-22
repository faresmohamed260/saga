import { randomUUID } from 'node:crypto';
import { createSourceUploadUrl } from './_r2.js';

function safeFilename(value) {
  return String(value || 'input.png').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 120);
}

function extensionFor(contentType, filename) {
  if (contentType === 'image/webp') return 'webp';
  if (contentType === 'image/jpeg') return 'jpg';
  if (contentType === 'image/png') return 'png';
  const ext = String(filename || '').split('.').pop()?.toLowerCase();
  return ['png', 'jpg', 'jpeg', 'webp'].includes(ext) ? ext : 'png';
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const body = typeof req.body === 'object' && req.body ? req.body : {};
    const contentType = String(body.contentType || '').split(';')[0].trim().toLowerCase();
    const filename = safeFilename(body.filename);
    const size = Number(body.size || 0);
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(contentType)) {
      return res.status(415).json({ error: 'Only PNG, JPEG, and WebP source uploads are supported' });
    }
    if (!Number.isFinite(size) || size <= 0 || size > 25 * 1024 * 1024) {
      return res.status(413).json({ error: 'Source upload must be between 1 byte and 25 MB' });
    }

    const now = new Date();
    const key = `sources/${now.getUTCFullYear()}/${String(now.getUTCMonth() + 1).padStart(2, '0')}/${randomUUID()}.${extensionFor(contentType, filename)}`;
    const uploadUrl = await createSourceUploadUrl({ key, contentType, expiresIn: 300 });
    return res.status(201).json({
      key,
      uploadUrl,
      method: 'PUT',
      contentType,
      expiresIn: 300,
      maxBytes: 25 * 1024 * 1024,
    });
  } catch (error) {
    console.error('Source upload ticket failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Could not create source upload ticket' });
  }
}
