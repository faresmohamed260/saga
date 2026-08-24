import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import sharp from 'sharp';
import { pollWorkflow } from '../api/_providers.js';
import { createThumbnail } from '../api/_result-persistence.js';

const posterSource = await sharp({
  create: { width: 1920, height: 1080, channels: 3, background: { r: 26, g: 31, b: 44 } },
}).jpeg({ quality: 88 }).toBuffer();
const thumbnail = await createThumbnail(posterSource);
const thumbnailMeta = await sharp(thumbnail.data).metadata();
assert.equal(thumbnail.originalWidth, 1920);
assert.equal(thumbnail.originalHeight, 1080);
assert.equal(thumbnail.width, 512);
assert.equal(thumbnail.height, 288);
assert.equal(thumbnailMeta.format, 'webp');

const expectedVideo = Buffer.from('poster-contract-video');
const expectedPoster = Buffer.from('poster-contract-jpeg');
const requests = [];
let posterAttempts = 0;
const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async (url, options = {}) => {
    const value = String(url);
    requests.push({ url: value, accept: options?.headers?.Accept || '' });
    if (value.endsWith('/jobs/test-call/poster')) {
      posterAttempts += 1;
      if (posterAttempts === 1) {
        return new Response(JSON.stringify({ detail: 'poster temporarily unavailable' }), {
          status: 502,
          headers: { 'content-type': 'application/json' },
        });
      }
      return new Response(expectedPoster, { status: 200, headers: { 'content-type': 'image/jpeg' } });
    }
    if (value.endsWith('/jobs/test-call')) {
      return new Response(expectedVideo, { status: 200, headers: { 'content-type': 'video/mp4' } });
    }
    throw new Error(`Unexpected provider URL: ${value}`);
  };

  const result = await pollWorkflow({
    provider: 'modal-ltx25-redgraft',
    outputMimeType: 'video/mp4',
  }, 'test-call');
  assert.equal(result.status, 'completed');
  assert.deepEqual(result.bytes, expectedVideo);
  assert.equal(result.contentType, 'video/mp4');
  assert.deepEqual(result.posterBytes, expectedPoster);
  assert.equal(result.posterContentType, 'image/jpeg');
  assert.equal(posterAttempts, 2);
  assert.equal(requests.length, 3);
  assert.match(requests[1].url, /\/jobs\/test-call\/poster$/);
  assert.match(requests[2].url, /\/jobs\/test-call\/poster$/);
} finally {
  globalThis.fetch = originalFetch;
}

const [runtimeSource, gatewaySource, resultSource, persistenceSource, cardSource, providerSource] = await Promise.all([
  readFile('../../integrations/comfyui/ltx23_app.py', 'utf8'),
  readFile('../../integrations/comfyui/ltx23_gateway.py', 'utf8'),
  readFile('api/generate/result.js', 'utf8'),
  readFile('api/_result-persistence.js', 'utf8'),
  readFile('src/components/MediaCard.jsx', 'utf8'),
  readFile('api/_providers.js', 'utf8'),
]);
assert.match(runtimeSource, /\) -> bytes:/);
assert.doesNotMatch(runtimeSource, /_create_video_poster/);
assert.match(gatewaySource, /apt_install\("ffmpeg"\)/);
assert.match(gatewaySource, /def _extract_poster\(video: bytes\)/);
assert.match(gatewaySource, /\/jobs\/\{call_id\}\/poster/);
assert.match(resultSource, /result\.posterBytes, result\.posterContentType/);
assert.match(persistenceSource, /thumbnail_r2_key: thumbnailUrl \? keys\.thumbnail : null/);
assert.match(providerSource, /LTX_POSTER_RETRY_DELAYS_MS/);
assert.match(providerSource, /status: 'running'[\s\S]*publicWorkerStatus\(worker, 'finalizing'\)/);
assert.match(cardSource, /src=\{attachedVideoSource \|\| undefined\}/);
assert.match(cardSource, /data-preview-state=\{previewActive \? 'active'/);
assert.match(cardSource, /preload=\{history \? \(item\.thumbnailUrl \? 'none'/);
assert.match(cardSource, /setPreviewHoverCapable\(hoverFine\.matches\)/);
assert.doesNotMatch(cardSource, /innerWidth > 640/);

console.log(JSON.stringify({
  ready: true,
  thumbnail: { format: thumbnailMeta.format, width: thumbnail.width, height: thumbnail.height },
  posterAttempts,
  providerRequests: requests.map((entry) => entry.url.replace(/^https?:\/\/[^/]+/, 'gateway')),
}, null, 2));
