function encodeHeader(value) {
  return encodeURIComponent(String(value ?? ''));
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

export async function submitImageEdit({ sourceFile, prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: {
      'Content-Type': sourceFile.type || 'image/png',
      'X-Saga-Workflow': 'flux2-klein-image-edit',
      'X-Saga-Prompt': encodeHeader(prompt),
      'X-Saga-Negative-Prompt': encodeHeader(negativePrompt),
      'X-Saga-Resolution': encodeHeader(resolution),
      'X-Saga-Source-Filename': encodeHeader(sourceFile.name || 'input.png'),
      'X-Saga-Seed': String(seed ?? ''),
      'X-Saga-Steps': String(steps),
      'X-Saga-Cfg': String(cfg),
      'X-Saga-Megapixels': String(megapixels),
    },
    body: sourceFile,
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
  const job = await submitImageEdit(input);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(job.id, options);
  return { job, result };
}
