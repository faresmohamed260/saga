from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n--- OLD ---\n{old[:800]}")
    path.write_text(text.replace(old, new, 1))


def write_file(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# LTX runtime: extract a poster inside the ffmpeg-equipped Modal runtime and
# return it alongside the delivery MP4.
# ---------------------------------------------------------------------------
replace_once(
    "integrations/comfyui/ltx23_app.py",
    """    if result.returncode != 0 or not final_path.is_file() or final_path.stat().st_size <= 0:
        raise RuntimeError(f\"ffmpeg delivery encode failed: {result.stderr[-3000:]}\")
    return final_path


@app.function(
""",
    """    if result.returncode != 0 or not final_path.is_file() or final_path.stat().st_size <= 0:
        raise RuntimeError(f\"ffmpeg delivery encode failed: {result.stderr[-3000:]}\")
    return final_path


def _create_video_poster(video_path: Path) -> bytes:
    poster_path = video_path.with_name(f\"{video_path.stem}-poster.jpg\")
    command = [
        \"ffmpeg\", \"-y\", \"-hide_banner\", \"-loglevel\", \"error\",
        \"-ss\", \"0.08\",
        \"-i\", str(video_path),
        \"-frames:v\", \"1\",
        \"-q:v\", \"3\",
        str(poster_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not poster_path.is_file() or poster_path.stat().st_size <= 0:
        raise RuntimeError(f\"ffmpeg poster extraction failed: {result.stderr[-3000:]}\")
    return poster_path.read_bytes()


@app.function(
""",
)

replace_once(
    "integrations/comfyui/ltx23_app.py",
    """    ) -> bytes:
        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.
""",
    """    ) -> dict[str, Any]:
        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.
""",
)

replace_once(
    "integrations/comfyui/ltx23_app.py",
    """                    _log(
                        \"ltx25_delivery_ready\",
                        resolution=resolution,
                        aspect_ratio=aspect_ratio,
                        frame_rate=int(frame_rate),
                        duration_seconds=int(duration_seconds),
                        width=delivery_width,
                        height=delivery_height,
                        bytes=final_path.stat().st_size,
                    )
                    return final_path.read_bytes()
""",
    """                    poster_bytes = _create_video_poster(final_path)
                    _log(
                        \"ltx25_delivery_ready\",
                        resolution=resolution,
                        aspect_ratio=aspect_ratio,
                        frame_rate=int(frame_rate),
                        duration_seconds=int(duration_seconds),
                        width=delivery_width,
                        height=delivery_height,
                        bytes=final_path.stat().st_size,
                        poster_bytes=len(poster_bytes),
                    )
                    return {
                        \"video\": final_path.read_bytes(),
                        \"poster\": poster_bytes,
                        \"poster_content_type\": \"image/jpeg\",
                    }
""",
)

# ---------------------------------------------------------------------------
# Gateway: preserve the existing video endpoint and expose the poster on a
# sibling endpoint. Legacy byte-only runtime results remain supported.
# ---------------------------------------------------------------------------
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '    api = FastAPI(title="SAGA REDGraft LTX 2.5 Video Gateway", version="0.3.0")\n',
    '    api = FastAPI(title="SAGA REDGraft LTX 2.5 Video Gateway", version="0.4.0")\n',
)

replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    """    def _worker():
        return modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)()

    @api.get(\"/health\")
""",
    """    def _worker():
        return modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)()

    def _split_result(result):
        if isinstance(result, (bytes, bytearray)):
            return bytes(result), None, None
        if isinstance(result, dict):
            video = result.get(\"video\")
            poster = result.get(\"poster\")
            poster_type = str(result.get(\"poster_content_type\") or \"image/jpeg\")
            if isinstance(video, (bytes, bytearray)) and video:
                normalized_poster = bytes(poster) if isinstance(poster, (bytes, bytearray)) and poster else None
                return bytes(video), normalized_poster, poster_type
        return None, None, None

    @api.get(\"/health\")
""",
)

replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    """    @api.get(\"/jobs/{call_id}\")
    async def poll_video(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            return JSONResponse(status_code=202, content={\"status\": \"running\", \"call_id\": call_id})
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail=\"LTX 2.5 job result expired\") from exc
        except Exception as exc:  # noqa: BLE001
            print({\"event\": \"ltx25_gateway_poll_failed\", \"call_id\": call_id, \"error\": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f\"LTX 2.5 runtime failed: {type(exc).__name__}: {exc}\") from exc
        if not isinstance(result, (bytes, bytearray)) or not result:
            raise HTTPException(status_code=502, detail=\"LTX 2.5 runtime returned an empty video\")
        return Response(content=bytes(result), media_type=\"video/mp4\")

    @api.delete(\"/jobs/{call_id}\")
""",
    """    @api.get(\"/jobs/{call_id}\")
    async def poll_video(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            return JSONResponse(status_code=202, content={\"status\": \"running\", \"call_id\": call_id})
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail=\"LTX 2.5 job result expired\") from exc
        except Exception as exc:  # noqa: BLE001
            print({\"event\": \"ltx25_gateway_poll_failed\", \"call_id\": call_id, \"error\": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f\"LTX 2.5 runtime failed: {type(exc).__name__}: {exc}\") from exc
        video, _, _ = _split_result(result)
        if not video:
            raise HTTPException(status_code=502, detail=\"LTX 2.5 runtime returned an empty video\")
        return Response(content=video, media_type=\"video/mp4\")

    @api.get(\"/jobs/{call_id}/poster\")
    async def poll_video_poster(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            return JSONResponse(status_code=202, content={\"status\": \"running\", \"call_id\": call_id})
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail=\"LTX 2.5 job result expired\") from exc
        except Exception as exc:  # noqa: BLE001
            print({\"event\": \"ltx25_gateway_poster_failed\", \"call_id\": call_id, \"error\": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f\"LTX 2.5 poster fetch failed: {type(exc).__name__}: {exc}\") from exc
        _, poster, poster_type = _split_result(result)
        if not poster:
            raise HTTPException(status_code=404, detail=\"LTX 2.5 poster is unavailable\")
        if not str(poster_type or \"\").startswith(\"image/\"):
            raise HTTPException(status_code=502, detail=\"LTX 2.5 poster has an invalid content type\")
        return Response(content=poster, media_type=poster_type)

    @api.delete(\"/jobs/{call_id}\")
""",
)

# ---------------------------------------------------------------------------
# Studio provider: after the completed MP4 is available, retrieve the poster
# opportunistically. Poster failure does not discard an otherwise valid video.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/api/_providers.js",
    """async function pollModalLtx25(workflow, providerJobId) {
  const response = await fetch(`${getLtx25GatewayUrl()}/jobs/${encodeURIComponent(providerJobId)}`, {
    method: 'GET',
    headers: { Accept: 'video/*, application/json' },
  });
  if (response.status === 202) return { status: 'running', provider: workflow.provider };
  if (!response.ok) {
    const detail = await parseProviderError(response);
    const error = new Error(`REDGraft LTX 2.5 provider poll failed (${response.status})${detail}`);
    error.statusCode = response.status >= 500 ? 502 : response.status;
    throw error;
  }
  const contentType = String(response.headers.get('content-type') || workflow.outputMimeType).split(';')[0].trim();
  if (!contentType.startsWith('video/')) {
    const error = new Error('Generation provider returned a non-video response');
    error.statusCode = 502;
    throw error;
  }
  return {
    status: 'completed',
    bytes: Buffer.from(await response.arrayBuffer()),
    contentType,
    provider: workflow.provider,
  };
}
""",
    """async function pollModalLtx25(workflow, providerJobId) {
  const encodedJobId = encodeURIComponent(providerJobId);
  const response = await fetch(`${getLtx25GatewayUrl()}/jobs/${encodedJobId}`, {
    method: 'GET',
    headers: { Accept: 'video/*, application/json' },
  });
  if (response.status === 202) return { status: 'running', provider: workflow.provider };
  if (!response.ok) {
    const detail = await parseProviderError(response);
    const error = new Error(`REDGraft LTX 2.5 provider poll failed (${response.status})${detail}`);
    error.statusCode = response.status >= 500 ? 502 : response.status;
    throw error;
  }
  const contentType = String(response.headers.get('content-type') || workflow.outputMimeType).split(';')[0].trim();
  if (!contentType.startsWith('video/')) {
    const error = new Error('Generation provider returned a non-video response');
    error.statusCode = 502;
    throw error;
  }

  const bytes = Buffer.from(await response.arrayBuffer());
  let posterBytes = null;
  let posterContentType = null;
  try {
    const posterResponse = await fetch(`${getLtx25GatewayUrl()}/jobs/${encodedJobId}/poster`, {
      method: 'GET',
      headers: { Accept: 'image/*, application/json' },
    });
    if (posterResponse.ok) {
      const candidateType = String(posterResponse.headers.get('content-type') || '').split(';')[0].trim();
      if (candidateType.startsWith('image/')) {
        posterBytes = Buffer.from(await posterResponse.arrayBuffer());
        posterContentType = candidateType;
      }
    } else if (![202, 404, 410].includes(posterResponse.status)) {
      console.error(`REDGraft LTX 2.5 poster fetch failed (${posterResponse.status})`);
    }
  } catch (error) {
    console.error('REDGraft LTX 2.5 poster fetch failed', error);
  }

  return {
    status: 'completed',
    bytes,
    contentType,
    posterBytes,
    posterContentType,
    provider: workflow.provider,
  };
}
""",
)

# ---------------------------------------------------------------------------
# Persistence: convert the runtime JPEG frame to the same 512px WebP thumbnail
# format as images, store it in R2, and persist its URL/dimensions in Supabase.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/api/_result-persistence.js",
    "async function createThumbnail(body) {\n",
    "export async function createThumbnail(body) {\n",
)

replace_once(
    "apps/studio/api/_result-persistence.js",
    """async function putOriginal(client, job, bytes, contentType, key) {
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

export async function persistImageJobResult(job, bytes, contentType = 'image/png') {
""",
    """async function putOriginal(client, job, bytes, contentType, key) {
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
""",
)

replace_once(
    "apps/studio/api/_result-persistence.js",
    """  let thumbnail = null;
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
""",
    """  let thumbnail = null;
  let thumbnailUrl = null;
  try {
    ({ thumbnail, thumbnailUrl } = await persistThumbnail(client, job, bytes, keys));
  } catch (error) {
    console.error('Orchestrated thumbnail persistence failed', error);
  }
""",
)

replace_once(
    "apps/studio/api/_result-persistence.js",
    """export async function persistVideoJobResult(job, bytes, contentType = 'video/mp4') {
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

  const metadata = {
    ...(job.metadata && typeof job.metadata === 'object' ? job.metadata : {}),
    storage: 'cloudflare-r2',
    persistence: 'orchestrator-v1',
    thumbnailFormat: null,
    video: {
      ...((job.metadata && typeof job.metadata === 'object' && job.metadata.video) || {}),
      contentType,
      byteLength: bytes.length,
    },
  };

  return finalizeJob(job, {
    status: 'completed',
    r2_key: keys.original,
    media_url: mediaUrl,
    thumbnail_r2_key: null,
    thumbnail_url: null,
    mime_type: contentType,
    width: null,
    height: null,
    thumbnail_width: null,
    thumbnail_height: null,
    error_message: null,
    metadata,
    completed_at: new Date().toISOString(),
  });
}
""",
    """export async function persistVideoJobResult(
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
""",
)

replace_once(
    "apps/studio/api/generate/result.js",
    """    const completed = workflow.kind === 'video'
      ? await persistVideoJobResult(job, result.bytes, contentType)
      : await persistImageJobResult(job, result.bytes, contentType);
""",
    """    const completed = workflow.kind === 'video'
      ? await persistVideoJobResult(job, result.bytes, contentType, result.posterBytes, result.posterContentType)
      : await persistImageJobResult(job, result.bytes, contentType);
""",
)

# ---------------------------------------------------------------------------
# Gallery: poster-backed videos start with preload=none. Hover play remains the
# current on-demand load behavior; deeper deferred-src logic stays in Item 06.
# ---------------------------------------------------------------------------
replace_once(
    "apps/studio/src/components/MediaCard.jsx",
    '            preload="metadata"\n',
    "            preload={item.thumbnailUrl ? 'none' : 'metadata'}\n",
)

replace_once(
    "apps/studio/scripts/capture-gallery-preview.mjs",
    """  if (await page.locator('.history-card video').count() !== 3) throw new Error('Video cards did not render inline video previews');

  const firstBox = await cards.first().boundingBox();
""",
    """  const videoPreviews = page.locator('.history-card video');
  if (await videoPreviews.count() !== 3) throw new Error('Video cards did not render inline video previews');
  for (let index = 0; index < 3; index += 1) {
    const preview = videoPreviews.nth(index);
    if (!(await preview.getAttribute('poster'))) throw new Error(`Video card ${index} is missing its stored poster URL`);
    if (await preview.getAttribute('preload') !== 'none') throw new Error(`Poster-backed video card ${index} should use preload=none`);
  }

  const firstBox = await cards.first().boundingBox();
""",
)

replace_once(
    "apps/studio/scripts/capture-gallery-preview.mjs",
    """  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');

  await page.keyboard.press('Tab');
""",
    """  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');
  await page.locator('.gallery-grid').screenshot({ path: path.join(outputDir, '10c-gallery-video-posters.png'), animations: 'disabled' });
  diagnostics.screenshots.push('10c-gallery-video-posters.png');

  await page.keyboard.press('Tab');
""",
)

# ---------------------------------------------------------------------------
# Deterministic non-GPU contract test: provider fetch, poster conversion, source
# contract, and Gallery poster-first behavior.
# ---------------------------------------------------------------------------
write_file(
    "apps/studio/scripts/check-video-poster-contract.mjs",
    """import assert from 'node:assert/strict';
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
const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async (url, options = {}) => {
    const value = String(url);
    requests.push({ url: value, accept: options?.headers?.Accept || '' });
    if (value.endsWith('/jobs/test-call/poster')) {
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
  assert.equal(requests.length, 2);
  assert.match(requests[1].url, /\/jobs\/test-call\/poster$/);
} finally {
  globalThis.fetch = originalFetch;
}

const [runtimeSource, gatewaySource, resultSource, persistenceSource, cardSource] = await Promise.all([
  readFile('../../integrations/comfyui/ltx23_app.py', 'utf8'),
  readFile('../../integrations/comfyui/ltx23_gateway.py', 'utf8'),
  readFile('../api/generate/result.js', 'utf8'),
  readFile('../api/_result-persistence.js', 'utf8'),
  readFile('../src/components/MediaCard.jsx', 'utf8'),
]);
assert.match(runtimeSource, /\"poster_content_type\": \"image\/jpeg\"/);
assert.match(runtimeSource, /_create_video_poster\(final_path\)/);
assert.match(gatewaySource, /\/jobs\/\{call_id\}\/poster/);
assert.match(resultSource, /result\.posterBytes, result\.posterContentType/);
assert.match(persistenceSource, /thumbnail_r2_key: thumbnailUrl \? keys\.thumbnail : null/);
assert.match(cardSource, /preload=\{item\.thumbnailUrl \? 'none' : 'metadata'\}/);

console.log(JSON.stringify({
  ready: true,
  thumbnail: { format: thumbnailMeta.format, width: thumbnail.width, height: thumbnail.height },
  providerRequests: requests.map((entry) => entry.url.replace(/^https?:\/\/[^/]+/, 'gateway')),
}, null, 2));
""",
)

replace_once(
    "apps/studio/package.json",
    '    "build": "node scripts/check-workflow-contract.mjs && vite build",\n',
    '    "build": "node scripts/check-workflow-contract.mjs && vite build",\n    "test:poster": "node scripts/check-video-poster-contract.mjs",\n',
)

replace_once(
    ".github/workflows/studio-ci.yml",
    """      - run: npm run build
      - name: Guard Vercel Hobby function count
""",
    """      - run: npm run build
      - run: npm run test:poster
      - name: Guard Vercel Hobby function count
""",
)

# ---------------------------------------------------------------------------
# Live REDGraft smoke coverage is updated so poster extraction/persistence will
# be verified automatically once the external Modal workspace is enabled again.
# ---------------------------------------------------------------------------
replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """          if not isinstance(result, (bytes, bytearray)) or len(result) < 100_000:
              raise SystemExit(f\"Invalid video result: {type(result)} bytes={len(result) if hasattr(result, '__len__') else 'n/a'}\")
          open('/tmp/ltx25-smoke.mp4', 'wb').write(result)
          print({\"bytes\": len(result)})
""",
    """          video = result.get('video') if isinstance(result, dict) else result
          poster = result.get('poster') if isinstance(result, dict) else None
          if not isinstance(video, (bytes, bytearray)) or len(video) < 100_000:
              raise SystemExit(f\"Invalid video result: {type(video)} bytes={len(video) if hasattr(video, '__len__') else 'n/a'}\")
          if not isinstance(poster, (bytes, bytearray)) or len(poster) < 5_000:
              raise SystemExit(f\"Invalid video poster: {type(poster)} bytes={len(poster) if hasattr(poster, '__len__') else 'n/a'}\")
          open('/tmp/ltx25-smoke.mp4', 'wb').write(video)
          open('/tmp/ltx25-smoke-poster.jpg', 'wb').write(poster)
          print({\"bytes\": len(video), \"poster_bytes\": len(poster)})
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """          if not isinstance(result, (bytes, bytearray)) or len(result) < 100_000:
              raise SystemExit(f\"Invalid audio video result: {type(result)} bytes={len(result) if hasattr(result, '__len__') else 'n/a'}\")
          open('/tmp/ltx25-audio.mp4', 'wb').write(result)
          print({\"bytes\": len(result)})
""",
    """          video = result.get('video') if isinstance(result, dict) else result
          poster = result.get('poster') if isinstance(result, dict) else None
          if not isinstance(video, (bytes, bytearray)) or len(video) < 100_000:
              raise SystemExit(f\"Invalid audio video result: {type(video)} bytes={len(video) if hasattr(video, '__len__') else 'n/a'}\")
          if not isinstance(poster, (bytes, bytearray)) or len(poster) < 5_000:
              raise SystemExit(f\"Invalid audio video poster: {type(poster)} bytes={len(poster) if hasattr(poster, '__len__') else 'n/a'}\")
          open('/tmp/ltx25-audio.mp4', 'wb').write(video)
          open('/tmp/ltx25-audio-poster.jpg', 'wb').write(poster)
          print({\"bytes\": len(video), \"poster_bytes\": len(poster)})
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """              open('/tmp/ltx25-i2v.mp4', 'wb').write(polled.content)
              open('/tmp/ltx25-i2v-submit.json', 'w', encoding='utf-8').write(json.dumps(submitted, indent=2))
              print({\"bytes\": len(polled.content), \"call_id\": call_id})
              break
""",
    """              open('/tmp/ltx25-i2v.mp4', 'wb').write(polled.content)
              poster = requests.get(f\"{base}/jobs/{call_id}/poster\", timeout=180)
              poster.raise_for_status()
              if not poster.headers.get('content-type', '').startswith('image/') or len(poster.content) < 5_000:
                  raise SystemExit(f\"Gateway poster is invalid: type={poster.headers.get('content-type')} bytes={len(poster.content)}\")
              open('/tmp/ltx25-i2v-poster.jpg', 'wb').write(poster.content)
              open('/tmp/ltx25-i2v-submit.json', 'w', encoding='utf-8').write(json.dumps(submitted, indent=2))
              print({\"bytes\": len(polled.content), \"poster_bytes\": len(poster.content), \"call_id\": call_id})
              break
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """            /tmp/ltx25-smoke.mp4
            /tmp/ltx25-ffprobe.json
            /tmp/ltx25-audio.mp4
            /tmp/ltx25-audio-ffprobe.json
            /tmp/ltx25-i2v.mp4
            /tmp/ltx25-i2v-ffprobe.json
""",
    """            /tmp/ltx25-smoke.mp4
            /tmp/ltx25-smoke-poster.jpg
            /tmp/ltx25-ffprobe.json
            /tmp/ltx25-audio.mp4
            /tmp/ltx25-audio-poster.jpg
            /tmp/ltx25-audio-ffprobe.json
            /tmp/ltx25-i2v.mp4
            /tmp/ltx25-i2v-poster.jpg
            /tmp/ltx25-i2v-ffprobe.json
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """          const bytes = fs.readFileSync('/tmp/ltx25-artifact/ltx25-smoke.mp4');
          const bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();
""",
    """          const bytes = fs.readFileSync('/tmp/ltx25-artifact/ltx25-smoke.mp4');
          const posterBytes = fs.readFileSync('/tmp/ltx25-artifact/ltx25-smoke-poster.jpg');
          const bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """          let job = null;
          let key = null;
          try {
""",
    """          let job = null;
          let key = null;
          let thumbnailKey = null;
          try {
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """            const completed = await persistVideoJobResult(job, bytes, 'video/mp4');
            key = completed.r2_key;
            if (completed.status !== 'completed') throw new Error(`Unexpected persisted status: ${completed.status}`);
            if (completed.mime_type !== 'video/mp4') throw new Error(`Unexpected persisted MIME type: ${completed.mime_type}`);
            if (!key || !key.endsWith('.mp4')) throw new Error(`Unexpected R2 key: ${key}`);
            if (!completed.media_url?.includes(encodeURIComponent(key))) throw new Error(`Unexpected media URL: ${completed.media_url}`);
            if (completed.metadata?.storage !== 'cloudflare-r2') throw new Error('Completed row is missing Cloudflare R2 storage metadata');
            if (Number(completed.metadata?.video?.byteLength) !== bytes.length) throw new Error('Persisted byteLength metadata does not match video bytes');

            const head = await client.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
            if (head.ContentType !== 'video/mp4') throw new Error(`R2 object has wrong content type: ${head.ContentType}`);
            if (Number(head.ContentLength) !== bytes.length) throw new Error(`R2 object length mismatch: ${head.ContentLength} != ${bytes.length}`);

            console.log(JSON.stringify({
              ready: true,
              jobId: completed.id,
              status: completed.status,
              r2Key: key,
              mediaUrl: completed.media_url,
              contentType: head.ContentType,
              contentLength: head.ContentLength,
              storage: completed.metadata?.storage,
            }, null, 2));
""",
    """            const completed = await persistVideoJobResult(job, bytes, 'video/mp4', posterBytes, 'image/jpeg');
            key = completed.r2_key;
            thumbnailKey = completed.thumbnail_r2_key;
            if (completed.status !== 'completed') throw new Error(`Unexpected persisted status: ${completed.status}`);
            if (completed.mime_type !== 'video/mp4') throw new Error(`Unexpected persisted MIME type: ${completed.mime_type}`);
            if (!key || !key.endsWith('.mp4')) throw new Error(`Unexpected R2 key: ${key}`);
            if (!thumbnailKey || !thumbnailKey.endsWith('.webp')) throw new Error(`Unexpected thumbnail R2 key: ${thumbnailKey}`);
            if (!completed.media_url?.includes(encodeURIComponent(key))) throw new Error(`Unexpected media URL: ${completed.media_url}`);
            if (!completed.thumbnail_url?.includes(encodeURIComponent(thumbnailKey))) throw new Error(`Unexpected thumbnail URL: ${completed.thumbnail_url}`);
            if (completed.metadata?.storage !== 'cloudflare-r2') throw new Error('Completed row is missing Cloudflare R2 storage metadata');
            if (completed.metadata?.thumbnailFormat !== 'webp') throw new Error('Completed row is missing WebP thumbnail metadata');
            if (Number(completed.metadata?.video?.byteLength) !== bytes.length) throw new Error('Persisted byteLength metadata does not match video bytes');

            const head = await client.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
            if (head.ContentType !== 'video/mp4') throw new Error(`R2 object has wrong content type: ${head.ContentType}`);
            if (Number(head.ContentLength) !== bytes.length) throw new Error(`R2 object length mismatch: ${head.ContentLength} != ${bytes.length}`);
            const thumbnailHead = await client.send(new HeadObjectCommand({ Bucket: bucket, Key: thumbnailKey }));
            if (thumbnailHead.ContentType !== 'image/webp') throw new Error(`R2 thumbnail has wrong content type: ${thumbnailHead.ContentType}`);
            if (Number(thumbnailHead.ContentLength) <= 0) throw new Error('R2 thumbnail is empty');

            console.log(JSON.stringify({
              ready: true,
              jobId: completed.id,
              status: completed.status,
              r2Key: key,
              thumbnailR2Key: thumbnailKey,
              mediaUrl: completed.media_url,
              thumbnailUrl: completed.thumbnail_url,
              contentType: head.ContentType,
              contentLength: head.ContentLength,
              thumbnailContentType: thumbnailHead.ContentType,
              thumbnailContentLength: thumbnailHead.ContentLength,
              storage: completed.metadata?.storage,
            }, null, 2));
""",
)

replace_once(
    ".github/workflows/test-ltx23-modal01.yml",
    """              try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key || inferred })); } catch (error) { console.error('R2 validation cleanup failed', error); }
              try { await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(job.id)}`, { method: 'DELETE' }); } catch (error) { console.error('Supabase validation cleanup failed', error); }
""",
    """              try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key || inferred })); } catch (error) { console.error('R2 validation cleanup failed', error); }
              if (thumbnailKey) {
                try { await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: thumbnailKey })); } catch (error) { console.error('R2 thumbnail validation cleanup failed', error); }
              }
              try { await supabaseRequest(`studio_generations?id=eq.${encodeURIComponent(job.id)}`, { method: 'DELETE' }); } catch (error) { console.error('Supabase validation cleanup failed', error); }
""",
)

print("Iteration 5 stored-poster patch applied successfully")
