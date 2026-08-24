import { GetObjectCommand } from '@aws-sdk/client-s3';
import { getR2Client, r2Bucket } from './_r2.js';
import { supabaseRequest } from './_supabase.js';

const MAX_ITEMS = 100;
const MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024;
const isUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''));

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function dosDateTime(date = new Date()) {
  const year = Math.max(1980, date.getFullYear());
  return { time: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2), date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate() };
}
function zipStore(entries) {
  const localParts = [], centralParts = [];
  let offset = 0;
  const stamp = dosDateTime();
  for (const entry of entries) {
    const name = Buffer.from(entry.name.replace(/[^a-zA-Z0-9._-]/g, '_'));
    const data = entry.data, crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(stamp.time, 10); local.writeUInt16LE(stamp.date, 12);
    local.writeUInt32LE(crc, 14); local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22); local.writeUInt16LE(name.length, 26);
    localParts.push(local, name, data);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6); central.writeUInt16LE(stamp.time, 12); central.writeUInt16LE(stamp.date, 14);
    central.writeUInt32LE(crc, 16); central.writeUInt32LE(data.length, 20); central.writeUInt32LE(data.length, 24); central.writeUInt16LE(name.length, 28); central.writeUInt32LE(offset, 42);
    centralParts.push(central, name);
    offset += local.length + name.length + data.length;
  }
  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10); end.writeUInt32LE(centralSize, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...localParts, ...centralParts, end]);
}
async function objectBuffer(client, key) {
  const object = await client.send(new GetObjectCommand({ Bucket: r2Bucket, Key: key }));
  const chunks = [];
  for await (const chunk of object.Body) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); return res.status(405).json({ error: 'Method not allowed' }); }
  const ids = [...new Set(Array.isArray(req.body?.ids) ? req.body.ids.filter(isUuid) : [])];
  if (!ids.length) return res.status(400).json({ error: 'No valid generation ids supplied' });
  if (ids.length > MAX_ITEMS) return res.status(413).json({ error: `Batch download supports up to ${MAX_ITEMS} items` });
  const client = getR2Client();
  if (!client) return res.status(503).json({ error: 'R2 storage is not configured' });
  try {
    const filter = ids.map((id) => `"${id}"`).join(',');
    const rows = await supabaseRequest(`studio_generations?id=in.(${filter})&status=eq.completed&select=id,r2_key,kind`, { method: 'GET' });
    const byId = new Map((Array.isArray(rows) ? rows : []).map((row) => [row.id, row]));
    const entries = [];
    let total = 0;
    for (const id of ids) {
      const row = byId.get(id);
      if (!row?.r2_key) continue;
      const data = await objectBuffer(client, row.r2_key);
      total += data.length;
      if (total > MAX_ARCHIVE_BYTES) return res.status(413).json({ error: 'Selected media exceeds the 1 GB batch archive limit' });
      const extension = String(row.r2_key).split('.').pop() || (row.kind === 'video' ? 'mp4' : 'png');
      entries.push({ name: `saga-${row.kind || 'media'}-${row.id}.${extension}`, data });
    }
    if (!entries.length) return res.status(404).json({ error: 'No downloadable media found for the selected items' });
    const archive = zipStore(entries), date = new Date().toISOString().slice(0, 10);
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="saga-gallery-${date}.zip"`);
    res.setHeader('Content-Length', String(archive.length));
    return res.status(200).send(archive);
  } catch (error) {
    console.error('Batch download failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Batch download failed' });
  }
}
