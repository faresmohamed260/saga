function safeNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function getModalGatewayUrl() {
  return String(
    process.env.FLUX2_KLEIN_GATEWAY_URL ||
    'https://faresmohamed260--saga-flux2-klein-gateway-web.modal.run',
  ).replace(/\/$/, '');
}

function buildFluxForm(workflow, input) {
  const form = new FormData();
  form.append(
    'image_file',
    new Blob([input.sourceBytes], { type: input.sourceContentType || 'image/png' }),
    input.sourceFilename || 'input.png',
  );
  form.append('prompt', input.prompt);
  form.append('negative_prompt', input.negativePrompt || workflow.defaults.negativePrompt);
  form.append('seed', String(input.seed));
  form.append('steps', String(input.steps));
  form.append('cfg', String(input.cfg));
  form.append('megapixels', String(input.megapixels));
  return form;
}

function normalizeInput(workflow, rawInput) {
  if (!workflow) {
    const error = new Error('Unknown workflow');
    error.statusCode = 404;
    throw error;
  }

  const sourceBytes = Buffer.isBuffer(rawInput.sourceBytes)
    ? rawInput.sourceBytes
    : Buffer.from(rawInput.sourceBytes || []);

  if (workflow.requiresSourceImage && !sourceBytes.length) {
    const error = new Error('Source image is required');
    error.statusCode = 400;
    throw error;
  }
  if (sourceBytes.length > workflow.limits.maxSourceBytes) {
    const error = new Error(`Source image exceeds ${workflow.limits.maxSourceBytes} byte workflow limit`);
    error.statusCode = 413;
    throw error;
  }

  const prompt = String(rawInput.prompt || '').trim();
  if (!prompt) {
    const error = new Error('Prompt is required');
    error.statusCode = 400;
    throw error;
  }

  return {
    sourceBytes,
    sourceContentType: String(rawInput.sourceContentType || 'image/png'),
    sourceFilename: String(rawInput.sourceFilename || 'input.png').slice(0, 240),
    prompt: prompt.slice(0, 2000),
    negativePrompt: String(rawInput.negativePrompt || workflow.defaults.negativePrompt).slice(0, 2000),
    seed: Number.isSafeInteger(Number(rawInput.seed)) ? Number(rawInput.seed) : workflow.defaults.seed,
    steps: clamp(Math.round(safeNumber(rawInput.steps, workflow.defaults.steps)), 1, 50),
    cfg: safeNumber(rawInput.cfg, workflow.defaults.cfg),
    megapixels: clamp(
      safeNumber(rawInput.megapixels, workflow.defaults.megapixels),
      workflow.limits.minMegapixels,
      workflow.limits.maxMegapixels,
    ),
  };
}

async function submitModalFlux2Klein(workflow, input) {
  const response = await fetch(`${getModalGatewayUrl()}/jobs/edit`, {
    method: 'POST',
    body: buildFluxForm(workflow, input),
  });
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : '';
    } catch {}
    const error = new Error(`FLUX.2 provider submit failed (${response.status})${detail}`);
    error.statusCode = response.status >= 500 ? 502 : response.status;
    throw error;
  }
  const payload = await response.json();
  if (!payload?.call_id) {
    const error = new Error('FLUX.2 provider did not return a call id');
    error.statusCode = 502;
    throw error;
  }
  return { providerJobId: payload.call_id, provider: workflow.provider, status: payload.status || 'queued' };
}

async function pollModalFlux2Klein(workflow, providerJobId) {
  const response = await fetch(`${getModalGatewayUrl()}/jobs/${encodeURIComponent(providerJobId)}`, {
    method: 'GET',
    headers: { Accept: 'image/*, application/json' },
  });
  if (response.status === 202) return { status: 'running', provider: workflow.provider };
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : '';
    } catch {}
    const error = new Error(`FLUX.2 provider poll failed (${response.status})${detail}`);
    error.statusCode = response.status >= 500 ? 502 : response.status;
    throw error;
  }
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
  };
}

async function cancelModalFlux2Klein(workflow, providerJobId) {
  const response = await fetch(`${getModalGatewayUrl()}/jobs/${encodeURIComponent(providerJobId)}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.detail ? `: ${body.detail}` : '';
    } catch {}
    const error = new Error(`FLUX.2 provider cancel failed (${response.status})${detail}`);
    error.statusCode = response.status >= 500 ? 502 : response.status;
    throw error;
  }
  return { status: 'cancelled', provider: workflow.provider };
}

export async function submitWorkflow(workflow, rawInput) {
  const normalized = normalizeInput(workflow, rawInput);
  if (workflow.provider === 'modal-flux2-klein') return submitModalFlux2Klein(workflow, normalized);
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
  if (workflow.provider === 'modal-flux2-klein') return cancelModalFlux2Klein(workflow, providerJobId);
  const error = new Error(`Unsupported provider: ${workflow.provider}`);
  error.statusCode = 501;
  throw error;
}
