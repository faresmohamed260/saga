import { uploadSourceFiles, waitForGeneration } from '../../generation-client.js';

async function responseException(response, fallback) {
  let body = {};
  try { body = await response.json(); } catch {}
  const detail = body?.error || body?.detail;
  const error = new Error(detail ? `${fallback} (${response.status}): ${detail}` : `${fallback} (${response.status})`);
  error.statusCode = response.status;
  error.errorCode = body?.errorCode || body?.code || null;
  error.workerState = body?.workerState || body?.worker_state || null;
  error.worker = body?.worker || null;
  return error;
}

export async function runQwenImageEdit(input, options = {}) {
  const files = Array.from(input?.sourceFiles || []).filter(Boolean);
  if (!files.length) throw new Error('At least one reference image is required.');
  if (options.onStatus) options.onStatus('uploading');
  const uploaded = await uploadSourceFiles(files);
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflowId: 'qwen-image-edit-2511',
      sourceKeys: uploaded.map((item) => item.key),
      sourceFilenames: uploaded.map((item) => item.filename),
      sourceContentTypes: uploaded.map((item) => item.contentType),
      sourceKey: uploaded[0]?.key,
      sourceFilename: uploaded[0]?.filename,
      prompt: input.prompt,
      negativePrompt: input.negativePrompt || '',
      resolution: input.resolution,
      seed: input.seed,
      steps: input.steps ?? 8,
      cfg: input.cfg ?? 1.0,
      megapixels: input.megapixels ?? 1.0,
    }),
  });
  if (response.status !== 202) throw await responseException(response, 'Could not submit Qwen generation');
  const payload = await response.json();
  if (!payload?.job?.id) throw new Error('Qwen generation submit did not return a job id.');
  if (options.onJob) options.onJob(payload.job);
  if (options.onWorkerStatus && payload.worker) options.onWorkerStatus(payload.worker);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(payload.job.id, options);
  return { job: payload.job, result };
}
