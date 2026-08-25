import {
  createGenerationJob,
  transitionGenerationJob,
  updateGenerationWorkerAssignment,
} from './_generation-jobs.js';
import { submitWorkflow } from './_providers.js';
import { readSourceObject, isSourceKey } from './_r2.js';
import { getWorkflow, listWorkflows } from './_workflows.js';

export const config = { maxDuration: 60 };

function decodeHeader(value) {
  const raw = String(value || '');
  if (!raw) return '';
  try { return decodeURIComponent(raw); } catch { return raw; }
}

function parseNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseBoolean(value, fallback) {
  if (typeof value === 'boolean') return value;
  const text = String(value ?? '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(text)) return true;
  if (['0', 'false', 'no', 'off'].includes(text)) return false;
  return fallback;
}

function stringArray(value, maxLength = 300) {
  return Array.isArray(value)
    ? value.map((item) => String(item || '').trim().slice(0, maxLength)).filter(Boolean)
    : [];
}

async function readBody(req, limit) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > limit) {
      const error = new Error('Source image is too large for this workflow');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (req.method === 'GET') return res.status(200).json({ workflows: listWorkflows() });

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  let job = null;
  try {
    const requestContentType = String(req.headers['content-type'] || 'application/octet-stream').split(';')[0].trim().toLowerCase();
    const jsonMode = requestContentType === 'application/json';
    const body = jsonMode && typeof req.body === 'object' && req.body ? req.body : {};
    const workflowId = jsonMode ? String(body.workflowId || '').trim() : String(req.headers['x-saga-workflow'] || '').trim();
    const workflow = getWorkflow(workflowId);
    if (!workflow) return res.status(404).json({ error: 'Unknown generation workflow' });

    const prompt = jsonMode ? String(body.prompt || '').trim().slice(0, 2000) : decodeHeader(req.headers['x-saga-prompt']).trim().slice(0, 2000);
    const negativePrompt = jsonMode ? String(body.negativePrompt || '').trim().slice(0, 2000) : decodeHeader(req.headers['x-saga-negative-prompt']).trim().slice(0, 2000);
    const requestedResolution = jsonMode ? body.resolution : decodeHeader(req.headers['x-saga-resolution']);
    const resolution = String(requestedResolution || workflow.defaults.resolution || '').trim().slice(0, 96);
    const seed = Number.parseInt(String(jsonMode ? body.seed ?? workflow.defaults.seed : req.headers['x-saga-seed'] || workflow.defaults.seed), 10);
    const steps = parseNumber(jsonMode ? body.steps : req.headers['x-saga-steps'], workflow.defaults.steps);
    const cfg = parseNumber(jsonMode ? body.cfg : req.headers['x-saga-cfg'], workflow.defaults.cfg);
    const megapixels = parseNumber(jsonMode ? body.megapixels : req.headers['x-saga-megapixels'], workflow.defaults.megapixels);
    const durationSeconds = parseNumber(
      jsonMode ? body.durationSeconds : req.headers['x-saga-duration-seconds'],
      workflow.defaults.durationSeconds,
    );
    const audioEnabled = parseBoolean(
      jsonMode ? body.audioEnabled : req.headers['x-saga-audio-enabled'],
      workflow.defaults.audioEnabled,
    );
    const aspectRatio = String(
      jsonMode ? body.aspectRatio ?? workflow.defaults.aspectRatio : decodeHeader(req.headers['x-saga-aspect-ratio']) || workflow.defaults.aspectRatio || '16:9',
    ).trim().slice(0, 32);
    const frameRate = parseNumber(
      jsonMode ? body.frameRate : req.headers['x-saga-frame-rate'],
      workflow.defaults.frameRate || 24,
    );

    if (!prompt) return res.status(400).json({ error: 'Prompt is required' });

    let sources = [];
    let sourceKeys = [];
    let sourceFilenames = [];
    let sourceContentTypes = [];

    if (jsonMode) {
      sourceKeys = stringArray(body.sourceKeys);
      if (!sourceKeys.length && body.sourceKey) sourceKeys = [String(body.sourceKey || '').trim()];
      if (workflow.requiresSourceImage && (!sourceKeys.length || sourceKeys.some((key) => !isSourceKey(key)))) {
        return res.status(400).json({ error: 'At least one valid source reference is required' });
      }
      if (!workflow.supportsMultipleReferences && sourceKeys.length > 1) return res.status(400).json({ error: 'This workflow accepts only one source image' });

      sourceFilenames = stringArray(body.sourceFilenames, 240);
      if (!sourceFilenames.length && body.sourceFilename) sourceFilenames = [String(body.sourceFilename || '').trim().slice(0, 240)];
      sourceContentTypes = stringArray(body.sourceContentTypes, 120);

      for (let index = 0; index < sourceKeys.length; index += 1) {
        const source = await readSourceObject(sourceKeys[index], workflow.limits.maxSourceBytes);
        if (!String(source.contentType || '').startsWith('image/')) return res.status(415).json({ error: `Reference Image ${index + 1} is not an image` });
        sources.push({
          bytes: source.bytes,
          contentType: source.contentType,
          filename: sourceFilenames[index] || `input-${index + 1}.png`,
          key: sourceKeys[index],
        });
      }
    } else {
      if (workflow.requiresSourceImage && !requestContentType.startsWith('image/')) {
        return res.status(415).json({ error: 'This workflow requires an image source' });
      }
      const sourceBytes = await readBody(req, workflow.limits.maxSourceBytes);
      if (sourceBytes.length) {
        sources = [{
          bytes: sourceBytes,
          contentType: requestContentType,
          filename: decodeHeader(req.headers['x-saga-source-filename']).trim().slice(0, 240) || 'input.png',
          key: '',
        }];
      }
    }

    if (workflow.requiresSourceImage && !sources.length) return res.status(400).json({ error: 'Source image is empty' });

    const primary = sources[0] || { bytes: Buffer.alloc(0), contentType: '', filename: '', key: '' };
    const normalizedPrompt = sources.length > 1
      ? `Reference images are numbered in upload order from Image 1 through Image ${sources.length}. Image 1 is the primary canvas that determines output shape.\n\n${prompt}`
      : prompt;
    const inputTransport = sourceKeys.length ? 'r2' : sources.length ? 'inline' : 'none';

    job = await createGenerationJob({
      kind: workflow.kind,
      mode: workflow.mode,
      model: workflow.model,
      prompt,
      negativePrompt,
      resolution,
      seed,
      workflowId: workflow.id,
      provider: workflow.provider,
      metadata: {
        inputTransport,
        ecosystem: workflow.ecosystem || null,
        sourceR2Key: sourceKeys[0] || null,
        sourceR2Keys: sourceKeys,
        sourceContentType: primary.contentType || null,
        sourceContentTypes: sources.map((source) => source.contentType || null),
        sourceFilename: primary.filename || null,
        sourceFilenames: sources.map((source) => source.filename),
        referenceCount: sources.length,
        primaryReferenceIndex: sources.length ? 0 : null,
        automaticOutputSize: Boolean(workflow.automaticOutputSize),
        execution: {
          steps,
          cfg,
          megapixels,
          ...(workflow.kind === 'video' ? { durationSeconds, audioEnabled, resolution, aspectRatio, frameRate } : {}),
        },
      },
    });
    await transitionGenerationJob(job.id, 'running');

    const submitted = await submitWorkflow(workflow, {
      sources,
      sourceBytes: primary.bytes,
      sourceContentType: primary.contentType,
      sourceFilename: primary.filename,
      prompt: normalizedPrompt,
      negativePrompt,
      resolution,
      seed,
      steps,
      cfg,
      megapixels,
      durationSeconds,
      audioEnabled,
      aspectRatio,
      frameRate,
    });
    const submissionFailures = Array.isArray(submitted.worker?.failedWorkers) ? submitted.worker.failedWorkers : [];
    const submittedAt = new Date().toISOString();
    const updatedJob = await updateGenerationWorkerAssignment(job.id, submitted.providerJobId, {
      assignedWorkerId: submitted.worker?.workerId || null,
      workerRuntime: submitted.worker ? { ...submitted.worker, updatedAt: submittedAt } : null,
      workerFailoverHistory: submissionFailures.map((failure) => ({
        fromWorkerId: failure.workerId || null,
        reason: failure.kind || 'unavailable',
        errorCode: failure.code || null,
        at: submittedAt,
      })),
    });

    return res.status(202).json({
      job: updatedJob,
      status: 'running',
      workflow: workflow.id,
      provider: workflow.provider,
      ecosystem: workflow.ecosystem || null,
      worker: submitted.worker || null,
      inputTransport,
      referenceCount: sources.length,
    });
  } catch (error) {
    if (job?.id) {
      try {
        await transitionGenerationJob(job.id, 'failed', { errorMessage: error?.message || 'Generation submit failed' });
      } catch (transitionError) {
        console.error('Could not mark generation job failed', transitionError);
      }
    }
    console.error('Generation orchestration submit failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Generation submit failed', errorCode: error?.errorCode || null, workerState: error?.workerState || null });
  }
}
