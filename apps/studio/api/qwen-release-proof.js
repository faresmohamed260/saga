import { URL } from 'node:url';
import { deflateSync } from 'node:zlib';

import generateHandler from './generate.js';
import resultHandler from './generate/result.js';
import historyHandler from './history.js';
import jobsHandler from './jobs.js';
import mediaHandler from './media.js';
import uploadsHandler from './uploads.js';

export const config = { maxDuration: 300 };

function makeResponse() {
  const chunks = [];
  return {
    statusCode: 200,
    headers: {},
    body: undefined,
    binary: Buffer.alloc(0),
    status(code) { this.statusCode = code; return this; },
    setHeader(name, value) { this.headers[String(name).toLowerCase()] = String(value); },
    json(payload) { this.body = payload; return payload; },
    write(chunk) { chunks.push(Buffer.from(chunk)); },
    end(chunk) {
      if (chunk) chunks.push(Buffer.from(chunk));
      this.binary = Buffer.concat(chunks);
      return this.binary;
    },
  };
}

async function call(handler, { method = 'GET', body = {}, query = {}, headers = {} } = {}) {
  const res = makeResponse();
  const req = { method, body, query, headers };
  await handler(req, res);
  return res;
}

function png(width = 256, height = 256) {
  const rows = [];
  for (let y = 0; y < height; y += 1) {
    const row = Buffer.alloc(1 + width * 3);
    row[0] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = 1 + x * 3;
      row[offset] = 48 + Math.floor((x * 96) / width);
      row[offset + 1] = 62 + Math.floor((y * 72) / height);
      row[offset + 2] = 112;
    }
    rows.push(row);
  }

  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    return c >>> 0;
  });
  const crc32 = (data) => {
    let c = 0xffffffff;
    for (const byte of data) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const kind = Buffer.from(type, 'ascii');
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([kind, data])));
    return Buffer.concat([length, kind, data, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.set([8, 2, 0, 0, 0], 8);
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(Buffer.concat(rows), { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  if (req.query?.confirm !== 'qwen-civitai-deployment-readiness') {
    return res.status(404).json({ error: 'Not found' });
  }

  const startedAt = new Date().toISOString();
  const source = png();
  const filename = `qwen-release-proof-${Date.now()}.png`;

  try {
    const ticket = await call(uploadsHandler, {
      method: 'POST',
      body: { filename, contentType: 'image/png', size: source.length, purpose: 'generation-source' },
    });
    if (ticket.statusCode !== 201 || !ticket.body?.uploadUrl || !ticket.body?.key) {
      throw new Error(`Upload ticket failed: ${ticket.statusCode} ${JSON.stringify(ticket.body)}`);
    }

    const uploaded = await fetch(ticket.body.uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': 'image/png' },
      body: source,
    });
    if (!uploaded.ok) throw new Error(`R2 source PUT failed: ${uploaded.status}`);

    const submitted = await call(generateHandler, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: {
        workflowId: 'qwen-image-edit-2511',
        sourceKeys: [ticket.body.key],
        sourceFilenames: [filename],
        sourceContentTypes: ['image/png'],
        prompt: 'SAGA deployment-readiness proof: preserve the reference composition and turn it into a clean editorial poster with a centered white circle.',
        negativePrompt: '',
        seed: 42,
        steps: 4,
        cfg: 1.0,
        megapixels: 0.25,
      },
    });
    if (submitted.statusCode !== 202 || !submitted.body?.job?.id) {
      throw new Error(`Qwen submit failed: ${submitted.statusCode} ${JSON.stringify(submitted.body)}`);
    }
    const jobId = submitted.body.job.id;
    const workerId = submitted.body.worker?.workerId || null;
    if (!['qwen-primary-01', 'qwen-standby-01'].includes(workerId)) {
      throw new Error(`Unexpected Qwen worker: ${workerId}`);
    }

    let completed = null;
    const deadline = Date.now() + 240000;
    while (Date.now() < deadline) {
      const polled = await call(resultHandler, { method: 'GET', query: { jobId } });
      if (polled.statusCode === 202) {
        await new Promise((resolve) => setTimeout(resolve, 4000));
        continue;
      }
      if (polled.statusCode !== 200) {
        throw new Error(`Qwen result failed: ${polled.statusCode} ${JSON.stringify(polled.body)}`);
      }
      completed = polled.body;
      break;
    }
    if (!completed?.persisted || completed.generationId !== jobId || !completed.mediaUrl) {
      throw new Error(`Qwen result was not persisted: ${JSON.stringify(completed)}`);
    }

    const jobs = await call(jobsHandler, { method: 'GET', query: { id: jobId } });
    if (jobs.statusCode !== 200 || jobs.body?.job?.status !== 'completed' || jobs.body?.job?.workflow_id !== 'qwen-image-edit-2511') {
      throw new Error(`Jobs verification failed: ${jobs.statusCode} ${JSON.stringify(jobs.body)}`);
    }
    const persistedJob = jobs.body.job;
    if (persistedJob.model !== 'Qwen Image Edit 2511 · Abliterated BF16 + Lightning') {
      throw new Error(`Jobs reports wrong model: ${persistedJob.model}`);
    }

    const gallery = await call(historyHandler, {
      method: 'GET',
      query: {
        limit: '100',
        kind: 'image',
        model: persistedJob.model,
        after: startedAt,
      },
    });
    const galleryItem = gallery.body?.items?.find((item) => item.id === jobId);
    if (gallery.statusCode !== 200 || !galleryItem || galleryItem.status !== 'completed' || galleryItem.workflow_id !== 'qwen-image-edit-2511') {
      throw new Error(`Gallery verification failed: ${gallery.statusCode} items=${gallery.body?.items?.length || 0}`);
    }

    const mediaKey = new URL(completed.mediaUrl, 'https://studio.invalid').searchParams.get('key');
    const media = await call(mediaHandler, { method: 'GET', query: { key: mediaKey }, headers: {} });
    const contentType = media.headers['content-type'] || '';
    if (media.statusCode !== 200 || !contentType.startsWith('image/') || media.binary.length < 10000 || !media.binary.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
      throw new Error(`Persisted media verification failed: status=${media.statusCode} type=${contentType} bytes=${media.binary.length}`);
    }

    return res.status(200).json({
      ready: true,
      workflow: 'qwen-image-edit-2511',
      model: persistedJob.model,
      jobId,
      generationId: completed.generationId,
      workerId,
      ecosystem: submitted.body.ecosystem,
      persisted: true,
      jobsVerified: true,
      galleryVerified: true,
      mediaVerified: true,
      mediaBytes: media.binary.length,
      mediaContentType: contentType,
      checkpoint: { source: 'civitai', versionId: 2553500, fileId: 2443737 },
      acceleration: { profile: 'lightning-lora-4step-bf16', steps: 4, cfg: 1.0 },
      sourceKey: ticket.body.key,
      r2Key: persistedJob.r2_key,
      startedAt,
      completedAt: persistedJob.completed_at,
    });
  } catch (error) {
    console.error('Qwen release proof failed', error);
    return res.status(error?.statusCode || 500).json({ ready: false, error: error?.message || 'Qwen release proof failed' });
  }
}
