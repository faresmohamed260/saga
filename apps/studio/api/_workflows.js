const workflowRegistry = {
  'flux2-klein-image-edit': {
    id: 'flux2-klein-image-edit',
    kind: 'image',
    mode: 'edit',
    model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    provider: 'modal-flux2-klein',
    requiresSourceImage: true,
    supportsMultipleReferences: true,
    automaticOutputSize: true,
    outputMimeType: 'image/png',
    defaults: {
      negativePrompt: '',
      seed: 42,
      steps: 4,
      cfg: 1.0,
      megapixels: 1.0,
    },
    limits: {
      maxSourceBytes: 25 * 1024 * 1024,
      minMegapixels: 0.25,
      maxMegapixels: 4.0,
    },
  },
  'ltx23-video': {
    id: 'ltx23-video',
    kind: 'video',
    mode: 'video',
    model: 'LTX-Video 2.3 · 22B Distilled',
    provider: 'modal-ltx23',
    requiresSourceImage: false,
    supportsMultipleReferences: false,
    automaticOutputSize: false,
    outputMimeType: 'video/mp4',
    defaults: {
      negativePrompt: 'pc game, console game, video game, cartoon, childish, ugly, watermark, subtitles, text overlay',
      seed: 42,
      steps: 8,
      cfg: 1.0,
      megapixels: 1.0,
      resolution: '480p',
      durationSeconds: 5,
      audioEnabled: true,
    },
    limits: {
      maxSourceBytes: 25 * 1024 * 1024,
      minMegapixels: 0.25,
      maxMegapixels: 4.0,
      minDurationSeconds: 5,
      maxDurationSeconds: 30,
      resolutions: ['480p', '720p', '1080p', '2K', '4K'],
    },
  },
};

export function getWorkflow(workflowId) {
  return workflowRegistry[String(workflowId || '')] || null;
}

export function listWorkflows() {
  return Object.values(workflowRegistry).map((workflow) => ({
    id: workflow.id,
    kind: workflow.kind,
    mode: workflow.mode,
    model: workflow.model,
    provider: workflow.provider,
    requiresSourceImage: workflow.requiresSourceImage,
    supportsMultipleReferences: Boolean(workflow.supportsMultipleReferences),
    automaticOutputSize: Boolean(workflow.automaticOutputSize),
    outputMimeType: workflow.outputMimeType,
    capabilities: workflow.kind === 'video' ? {
      resolutions: workflow.limits.resolutions,
      minDurationSeconds: workflow.limits.minDurationSeconds,
      maxDurationSeconds: workflow.limits.maxDurationSeconds,
      audio: true,
      imageToVideo: true,
    } : undefined,
  }));
}
