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
  if (options.onStatus) options.onStatus('uploading');
  const job = await submitImageEdit(input);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(job.id, options);
  return { job, result };
}
