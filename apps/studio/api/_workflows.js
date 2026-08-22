const workflowRegistry = {
  'flux2-klein-image-edit': {
    id: 'flux2-klein-image-edit',
    kind: 'image',
    mode: 'edit',
    model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    provider: 'modal-flux2-klein',
    requiresSourceImage: true,
    outputMimeType: 'image/png',
    defaults: {
      negativePrompt: '',
      seed: 42,
      steps: 4,
      cfg: 1.0,
      megapixels: 1.0,
    },
    limits: {
      maxSourceBytes: 6 * 1024 * 1024,
      minMegapixels: 0.25,
      maxMegapixels: 4.0,
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
    outputMimeType: workflow.outputMimeType,
  }));
}
