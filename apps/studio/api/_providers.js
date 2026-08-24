import {
  encodeProviderJobId,
  providerFailureError,
  publicWorkerStatus,
  submitWithWorkerFailover,
  workerForProviderJob,
} from './_worker-registry.js';

function safeNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function safeBoolean(value, fallback) {
  if (typeof value === 'boolean') return value;
  const text = String(value ?? '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(text)) return true;
  if (['0', 'false', 'no', 'off'].includes(text)) return false;
  return fallback;
}

function normalizeAspectRatio(value, fallback = '16:9') {
  const text = String(value || fallback).trim();
  const match = text.match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) {
    const error = new Error(`Unsupported video aspect ratio: ${text || 'empty'}`);
    error.statusCode = 400;
    throw error;
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  const ratio = width / height;
  if (!Number.isFinite(ratio) || ratio < 0.4 || ratio > 2.5) {
    const error = new Error(`Video aspect ratio is outside the supported range: ${text}`);
    error.statusCode = 400;
    throw error;
  }
  return `${width}:${height}`;
}

function buildFluxForm(workflow, input) {
  const form = new FormData();
  input.sources.forEach((source, index) => {
    form.append('image_files', new Blob([source.bytes], { type: source.contentType || 'image/png' }), source.filename || `input-${index + 1}.png`);
  });
  form.append('prompt', input.prompt);
  form.append('negative_prompt', input.negativePrompt || workflow.defaults.negativePrompt);
  form.append('seed', String(input.seed));
  form.append('steps', String(input.steps));
  form.append('cfg', String(input.cfg));
  form.append('megapixels', String(input.megapixels));
  return form;
}

function buildLtx25Form(workflow, input) {
  const form = new FormData();
  const source = input.sources[0];
  if (source) form.append('image_file', new Blob([source.bytes], { type: source.contentType || 'image/png' }), source.filename || 'input.png');
  form.append('prompt', input.prompt);
  form.append('negative_prompt', input.negativePrompt || workflow.defaults.negativePrompt);
  form.append('seed', String(input.seed));
  form.append('resolution', input.resolution);
  form.append('duration_seconds', String(input.durationSeconds));
  form.append('audio_enabled', String(input.audioEnabled));
  form.append('aspect_ratio', input.aspectRatio);
  form.append('frame_rate', String(input.frameRate));
  return form;
}

function normalizeSources(workflow, rawInput) {
  const rawSources = Array.isArray(rawInput.sources) && rawInput.sources.length
    ? rawInput.sources
    : [{ bytes: rawInput.sourceBytes, contentType: rawInput.sourceContentType, filename: rawInput.sourceFilename }];
  const sources = rawSources.map((source, index) => {
    const bytes = Buffer.isBuffer(source?.bytes) ? source.bytes : Buffer.from(source?.bytes || []);
    if (bytes.length > workflow.limits.maxSourceBytes) {
      const error = new Error(`Reference Image ${index + 1} exceeds ${workflow.limits.maxSourceBytes} byte workflow limit`);
      error.statusCode = 413;
      throw error;
    }
    return {
      bytes,
      contentType: String(source?.contentType || 'image/png'),
      filename: String(source?.filename || `input-${index + 1}.png`).slice(0, 240),
    };
  }).filter((source) => source.bytes.length);
  if (workflow.requiresSourceImage && !sources.length) {
    const error = new Error('At least one reference image is required');
    error.statusCode = 400;
    throw error;
  }
  if (!workflow.supportsMultipleReferences && sources.length > 1) {
    const error = new Error('This workflow accepts only one reference image');
    error.statusCode = 400;
    throw error;
  }
  return sources;
}

function normalizeInput(workflow, rawInput) {
  if (!workflow) {
    const error = new Error('Unknown workflow');
    error.statusCode = 404;
    throw error;
  }
  const sources = normalizeSources(workflow, rawInput);
  const prompt = String(rawInput.prompt || '').trim();
  if (!prompt) {
    const error = new Error('Prompt is required');
    error.statusCode = 400;
    throw error;
  }
  const normalized = {
    sources,
    prompt: prompt.slice(0, 2400),
    negativePrompt: String(rawInput.negativePrompt || workflow.defaults.negativePrompt).slice(0, 2000),
    seed: Number.isSafeInteger(Number(rawInput.seed)) ? Number(rawInput.seed) : workflow.defaults.seed,
    steps: clamp(Math.round(safeNumber(rawInput.steps, workflow.defaults.steps)), 1, 50),
    cfg: safeNumber(rawInput.cfg, workflow.defaults.cfg),
    megapixels: clamp(safeNumber(rawInput.megapixels, workflow.defaults.megapixels), workflow.limits.minMegapixels, workflow.limits.maxMegapixels),
  };
  if (workflow.kind === 'video') {
    const allowedResolutions = workflow.limits.resolutions || [];
    const requestedResolution = String(rawInput.resolution || workflow.defaults.resolution || '').trim();
    if (!allowedResolutions.includes(requestedResolution)) {
      const error = new Error(`Unsupported video resolution: ${requestedResolution || 'empty'}`);
      error.statusCode = 400;
      throw error;
    }
    normalized.resolution = requestedResolution;
    normalized.durationSeconds = clamp(Math.round(safeNumber(rawInput.durationSeconds, workflow.defaults.durationSeconds)), workflow.limits.minDurationSeconds, workflow.limits.maxDurationSeconds);
    normalized.audioEnabled = safeBoolean(rawInput.audioEnabled, workflow.defaults.audioEnabled);
    normalized.aspectRatio = normalizeAspectRatio(rawInput.aspectRatio, workflow.defaults.aspectRatio);
    const requestedFrameRate = Math.round(safeNumber(rawInput.frameRate, workflow.defaults.frameRate));
    if (!(workflow.limits.frameRates || []).includes(requestedFrameRate)) {
      const error = new Error(`Unsupported video frame rate: ${requestedFrameRate}`);
      error.statusCode = 400;
      throw error;
    }
    normalized.frameRate = requestedFrameRate;
  }
  return normalized;
}

async function parseProviderError(response) {
  let body = {};
  try { body = await response.json(); } catch { body = {}; }
  const detail = body?.detail || body?.error || '';
  return { body, detail: detail ? `: ${detail}` : '' };
}

async function fetchWorker(worker, path, init) {
  try {
    return await fetch(`${worker.gatewayUrl}${path}`, init);
  } catch (cause) {
    throw providerFailureError(`Worker ${worker.id} could not be reached`, { cause, worker });
  }
}

async function responseFailure(response, worker, label) {
  const parsed = await parseProviderError(response);
  throw providerFailureError(`${label} (${response.status})${parsed.detail}`, {
    status: response.status,
    body: parsed.body,
    worker,
  });
}

async function submitModalFlux2Klein(workflow, input, options = {}) {
  const accepted = await submitWithWorkerFailover(workflow, async (worker) => {
    const response = await fetchWorker(worker, '/jobs/edit', { method: 'POST', body: buildFluxForm(workflow, input) });
    if (!response.ok) await responseFailure(response, worker, 'FLUX.2 provider submit failed');
    const payload = await response.json();
    if (!payload?.call_id) throw providerFailureError('FLUX.2 provider did not return a call id', { status: 502, body: payload, worker });
    return { callId: payload.call_id, state: payload.worker_state || payload.workerState || 'queued' };
  }, options);
  return {
    providerJobId: encodeProviderJobId(accepted.worker.id, accepted.callId),
    provider: workflow.provider,
    status: 'queued',
    worker: publicWorkerStatus(accepted.worker, accepted.state, { failedWorkers: accepted.failedWorkers }),
  };
}

async function submitModalLtx25(workflow, input, options = {}) {
  const accepted = await submitWithWorkerFailover(workflow, async (worker) => {
    const response = await fetchWorker(worker, '/jobs/video', { method: 'POST', body: buildLtx25Form(workflow, input) });
    if (!response.ok) await responseFailure(response, worker, 'REDGraft LTX 2.5 provider submit failed');
    const payload = await response.json();
    if (!payload?.call_id) throw providerFailureError('REDGraft LTX 2.5 provider did not return a call id', { status: 502, body: payload, worker });
    return { callId: payload.call_id, state: payload.worker_state || payload.workerState || 'queued' };
  }, options);
  return {
    providerJobId: encodeProviderJobId(accepted.worker.id, accepted.callId),
    provider: workflow.provider,
    status: 'queued',
    worker: publicWorkerStatus(accepted.worker, accepted.state, { failedWorkers: accepted.failedWorkers }),
  };
}

async function pollWorkerJson(response) {
  try { return await response.json(); } catch { return {}; }
}

async function pollModalFlux2Klein(workflow, providerJobId) {
  const { worker, callId } = workerForProviderJob(workflow, providerJobId);
  if (!worker || !callId) throw providerFailureError('Assigned FLUX.2 worker is no longer configured', { worker });
  const response = await fetchWorker(worker, `/jobs/${encodeURIComponent(callId)}`, { method: 'GET', headers: { Accept: 'image/*, application/json' } });
  if (response.status === 202) {
    const payload = await pollWorkerJson(response);
    return { status: 'running', provider: workflow.provider, worker: publicWorkerStatus(worker, payload.worker_state || payload.workerState || 'generating') };
  }
  if (!response.ok) await responseFailure(response, worker, 'FLUX.2 provider poll failed');
  const contentType = String(response.headers.get('content-type') || workflow.outputMimeType).split(';')[0].trim();
  if (!contentType.startsWith('image/')) {
    const error = new Error('Generation provider returned a non-image response');
    error.statusCode = 502;
    throw error;
  }
  return {
    status: 'completed',
    bytes: Buffer.from(await response.arrayBuffer()),
    contentType,
    provider: workflow.provider,
    worker: publicWorkerStatus(worker, 'finalizing'),
  };
}

async function pollModalLtx25(workflow, providerJobId) {
  const { worker, callId } = workerForProviderJob(workflow, providerJobId);
  if (!worker || !callId) throw providerFailureError('Assigned REDGraft LTX 2.5 worker is no longer configured', { worker });
  const encodedJobId = encodeURIComponent(callId);
  const response = await fetchWorker(worker, `/jobs/${encodedJobId}`, { method: 'GET', headers: { Accept: 'video/*, application/json' } });
  if (response.status === 202) {
    const payload = await pollWorkerJson(response);
    return { status: 'running', provider: workflow.provider, worker: publicWorkerStatus(worker, payload.worker_state || payload.workerState || 'generating') };
  }
  if (!response.ok) await responseFailure(response, worker, 'REDGraft LTX 2.5 provider poll failed');
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
    const posterResponse = await fetchWorker(worker, `/jobs/${encodedJobId}/poster`, { method: 'GET', headers: { Accept: 'image/*, application/json' } });
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
    worker: publicWorkerStatus(worker, 'finalizing'),
  };
}

async function cancelProviderJob(worker, providerLabel, workflow, callId) {
  const response = await fetchWorker(worker, `/jobs/${encodeURIComponent(callId)}`, { method: 'DELETE', headers: { Accept: 'application/json' } });
  if (!response.ok) await responseFailure(response, worker, `${providerLabel} provider cancel failed`);
  return { status: 'cancelled', provider: workflow.provider, worker: publicWorkerStatus(worker, 'ready') };
}

export async function submitWorkflow(workflow, rawInput, options = {}) {
  const normalized = normalizeInput(workflow, rawInput);
  if (workflow.provider === 'modal-flux2-klein') return submitModalFlux2Klein(workflow, normalized, options);
  if (workflow.provider === 'modal-ltx25-redgraft') return submitModalLtx25(workflow, normalized, options);
  const error = new Error(`Unsupported provider: ${workflow.provider}`);
  error.statusCode = 501;
  throw error;
}

export async function pollWorkflow(workflow, providerJobId) {
  if (!workflow) {
    const error = new Error('Unknown workflow');
    error.statusCode = 404;
    throw error;
  }
  if (!providerJobId) {
    const error = new Error('Provider job id is required');
    error.statusCode = 400;
    throw error;
  }
  if (workflow.provider === 'modal-flux2-klein') return pollModalFlux2Klein(workflow, providerJobId);
  if (workflow.provider === 'modal-ltx25-redgraft') return pollModalLtx25(workflow, providerJobId);
  const error = new Error(`Unsupported provider: ${workflow.provider}`);
  error.statusCode = 501;
  throw error;
}

export async function cancelWorkflow(workflow, providerJobId) {
  if (!workflow) {
    const error = new Error('Unknown workflow');
    error.statusCode = 404;
    throw error;
  }
  if (!providerJobId) return { status: 'cancelled', provider: workflow.provider };
  const { worker, callId } = workerForProviderJob(workflow, providerJobId);
  if (!worker || !callId) throw providerFailureError('Assigned worker is no longer configured', { worker });
  if (workflow.provider === 'modal-flux2-klein') return cancelProviderJob(worker, 'FLUX.2', workflow, callId);
  if (workflow.provider === 'modal-ltx25-redgraft') return cancelProviderJob(worker, 'REDGraft LTX 2.5', workflow, callId);
  const error = new Error(`Unsupported provider: ${workflow.provider}`);
  error.statusCode = 501;
  throw error;
}
