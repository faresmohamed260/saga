let editSizingPreference = { mode: 'auto', aspect: '1:1', resolution: 1024 };

export function setEditSizingPreference(next) {
  editSizingPreference = {
    ...editSizingPreference,
    ...(next || {}),
    mode: next?.mode === 'manual' ? 'manual' : next?.mode === 'auto' ? 'auto' : editSizingPreference.mode,
  };
}

function round64(value) {
  return Math.max(64, Math.round(Number(value || 0) / 64) * 64);
}

function parseAspect(value) {
  const match = String(value || '').match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) return 1;
  const width = Number(match[1]);
  const height = Number(match[2]);
  return width > 0 && height > 0 ? width / height : 1;
}

function manualDimensions(aspect, longEdge) {
  const ratio = parseAspect(aspect);
  const edge = Math.max(512, Math.min(2048, Number(longEdge) || 1024));
  if (ratio >= 1) return { width: round64(edge), height: round64(edge / ratio) };
  return { width: round64(edge * ratio), height: round64(edge) };
}

async function loadImageForCanvas(file) {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(file);
    return {
      image: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      close: () => bitmap.close?.(),
    };
  }

  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error('Could not decode the primary reference for manual aspect sizing.'));
      image.src = url;
    });
    return {
      image,
      width: image.naturalWidth || image.width,
      height: image.naturalHeight || image.height,
      close: () => {},
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function preparePrimaryCanvas(file, aspect, resolution) {
  if (!file || typeof document === 'undefined') return file;
  const targetRatio = parseAspect(aspect);
  const target = manualDimensions(aspect, resolution);
  const source = await loadImageForCanvas(file);
  try {
    const sourceRatio = source.width / Math.max(1, source.height);
    let sx = 0;
    let sy = 0;
    let sw = source.width;
    let sh = source.height;
    if (sourceRatio > targetRatio) {
      sw = source.height * targetRatio;
      sx = (source.width - sw) / 2;
    } else if (sourceRatio < targetRatio) {
      sh = source.width / targetRatio;
      sy = (source.height - sh) / 2;
    }

    const canvas = document.createElement('canvas');
    canvas.width = target.width;
    canvas.height = target.height;
    const context = canvas.getContext('2d', { alpha: true });
    if (!context) throw new Error('Could not prepare the manual edit canvas.');
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = 'high';
    context.drawImage(source.image, sx, sy, sw, sh, 0, 0, target.width, target.height);

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Could not encode the manual edit canvas.')), 'image/webp', 0.96);
    });
    const baseName = String(file.name || 'input').replace(/\.[^.]+$/, '');
    return new File([blob], `${baseName}-saga-canvas.webp`, { type: 'image/webp', lastModified: Date.now() });
  } finally {
    source.close();
  }
}

async function applyEditSizing(input) {
  if (editSizingPreference.mode !== 'manual') return input;

  const dimensions = manualDimensions(editSizingPreference.aspect, editSizingPreference.resolution);
  const megapixels = Math.max(0.25, Math.min(4, (dimensions.width * dimensions.height) / 1_000_000));
  const files = Array.from(input.sourceFiles?.length ? input.sourceFiles : input.sourceFile ? [input.sourceFile] : []);
  if (files.length) files[0] = await preparePrimaryCanvas(files[0], editSizingPreference.aspect, editSizingPreference.resolution);

  return {
    ...input,
    sourceFile: files[0] || input.sourceFile,
    sourceFiles: files.length ? files : input.sourceFiles,
    resolution: `${dimensions.width} × ${dimensions.height} · Manual`,
    megapixels,
  };
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    const detail = body?.error || body?.detail;
    if (detail) return `${fallback} (${response.status}): ${detail}`;
  } catch {}
  return `${fallback} (${response.status})`;
}

export async function uploadSourceFile(sourceFile) {
  const ticketResponse = await fetch('/api/uploads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: sourceFile.name || 'input.png',
      contentType: sourceFile.type || 'image/png',
      size: sourceFile.size,
      purpose: 'generation-source',
    }),
  });
  if (!ticketResponse.ok) throw new Error(await responseError(ticketResponse, 'Could not prepare source upload'));
  const ticket = await ticketResponse.json();
  if (!ticket?.uploadUrl || !ticket?.key) throw new Error('Source upload ticket is incomplete.');

  const uploadResponse = await fetch(ticket.uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': ticket.contentType || sourceFile.type || 'application/octet-stream' },
    body: sourceFile,
  });
  if (!uploadResponse.ok) throw new Error(`Direct source upload failed (${uploadResponse.status})`);
  return { key: ticket.key, contentType: ticket.contentType || sourceFile.type || 'application/octet-stream', filename: sourceFile.name || 'input.png' };
}

export async function uploadSourceFiles(sourceFiles) {
  const files = Array.from(sourceFiles || []).filter(Boolean);
  if (!files.length) throw new Error('At least one reference image is required.');
  return Promise.all(files.map((file) => uploadSourceFile(file)));
}

export async function submitImageEdit({ sourceFile, sourceFiles, sourceKey, sourceKeys, prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {
  const files = Array.from(sourceFiles?.length ? sourceFiles : sourceFile ? [sourceFile] : []);
  let uploaded = [];

  if (Array.isArray(sourceKeys) && sourceKeys.length) {
    uploaded = sourceKeys.map((key, index) => ({
      key,
      contentType: files[index]?.type || 'image/png',
      filename: files[index]?.name || `input-${index + 1}.png`,
    }));
  } else if (sourceKey) {
    uploaded = [{ key: sourceKey, contentType: files[0]?.type || 'image/png', filename: files[0]?.name || 'input.png' }];
  } else {
    uploaded = await uploadSourceFiles(files);
  }

  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflowId: 'flux2-klein-image-edit',
      sourceKeys: uploaded.map((item) => item.key),
      sourceFilenames: uploaded.map((item) => item.filename),
      sourceContentTypes: uploaded.map((item) => item.contentType),
      sourceKey: uploaded[0]?.key,
      sourceFilename: uploaded[0]?.filename,
      prompt,
      negativePrompt,
      resolution,
      seed,
      steps,
      cfg,
      megapixels,
    }),
  });
  if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit generation'));
  const payload = await response.json();
  if (!payload?.job?.id) throw new Error('Generation submit did not return a job id.');
  return payload.job;
}

export async function submitVideoGeneration({
  sourceFile = null,
  sourceKey = '',
  prompt,
  negativePrompt = '',
  resolution = '480p',
  durationSeconds = 5,
  audioEnabled = true,
  seed = 42,
}) {
  let uploaded = null;
  if (sourceKey) {
    uploaded = {
      key: sourceKey,
      contentType: sourceFile?.type || 'image/png',
      filename: sourceFile?.name || 'input.png',
    };
  } else if (sourceFile) {
    uploaded = await uploadSourceFile(sourceFile);
  }

  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflowId: 'ltx25-redgraft-video',
      sourceKeys: uploaded ? [uploaded.key] : [],
      sourceFilenames: uploaded ? [uploaded.filename] : [],
      sourceContentTypes: uploaded ? [uploaded.contentType] : [],
      prompt,
      negativePrompt,
      resolution,
      durationSeconds,
      audioEnabled,
      seed,
    }),
  });
  if (response.status !== 202) throw new Error(await responseError(response, 'Could not submit video generation'));
  const payload = await response.json();
  if (!payload?.job?.id) throw new Error('Video generation submit did not return a job id.');
  return payload.job;
}

export async function waitForGeneration(jobId, { intervalMs = 2000, timeoutMs = 30 * 60 * 1000, onStatus } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (onStatus) onStatus('running');
    const response = await fetch(`/api/generate/result?jobId=${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (response.status === 202) {
      await sleep(intervalMs);
      continue;
    }
    if (!response.ok) throw new Error(await responseError(response, 'Generation failed'));
    const payload = await response.json();
    if (payload?.status !== 'completed' || !payload?.persisted || !payload?.mediaUrl) {
      throw new Error('Generation completed without persisted media.');
    }
    if (onStatus) onStatus('completed');
    return payload;
  }
  throw new Error('Generation is still running after 30 minutes.');
}

export async function runImageEdit(input, options = {}) {
  if (options.onStatus) options.onStatus(editSizingPreference.mode === 'manual' ? 'preparing' : 'uploading');
  const effectiveInput = await applyEditSizing(input);
  if (options.onStatus) options.onStatus('uploading');
  const job = await submitImageEdit(effectiveInput);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(job.id, options);
  return { job, result };
}

export async function runVideoGeneration(input, options = {}) {
  if (options.onStatus) options.onStatus(input?.sourceFile ? 'uploading' : 'submitting');
  const job = await submitVideoGeneration(input);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(job.id, {
    timeoutMs: 55 * 60 * 1000,
    ...options,
  });
  return { job, result };
}
