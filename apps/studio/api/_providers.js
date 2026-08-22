function safeNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

async function executeModalFlux2Klein(workflow, input) {
  const baseUrl = String(
    process.env.FLUX2_KLEIN_GATEWAY_URL ||
    process.env.VITE_FLUX2_KLEIN_API_URL ||
    'https://faresmohamed260--saga-flux2-klein-gateway-web.modal.run',
  ).replace(/\/$/, '');

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

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 280_000);
  try {
    const response = await fetch(`${baseUrl}/edit`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = '';
      try {
        const body = await response.json();
        detail = body?.detail ? `: ${body.detail}` : '';
      } catch {}
      const error = new Error(`FLUX.2 provider failed (${response.status})${detail}`);
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
      bytes: Buffer.from(await response.arrayBuffer()),
      contentType,
      provider: workflow.provider,
    };
  } catch (error) {
    if (error?.name === 'AbortError') {
      const timeoutError = new Error('Generation provider timed out');
      timeoutError.statusCode = 504;
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function executeWorkflow(workflow, rawInput) {
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

  const normalized = {
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

  if (workflow.provider === 'modal-flux2-klein') {
    return executeModalFlux2Klein(workflow, normalized);
  }

  const error = new Error(`Unsupported provider: ${workflow.provider}`);
  error.statusCode = 501;
  throw error;
}
