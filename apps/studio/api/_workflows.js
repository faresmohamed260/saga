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
  'ltx25-redgraft-video': {
    id: 'ltx25-redgraft-video',
    kind: 'video',
    mode: 'video',
    model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    provider: 'modal-ltx25-redgraft',
    requiresSourceImage: false,
    supportsMultipleReferences: false,
    automaticOutputSize: false,
    outputMimeType: 'video/mp4',
    defaults: {
      negativePrompt: '',
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
      resolutions: ['480p', '720p', '1080p', '2K'],
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
