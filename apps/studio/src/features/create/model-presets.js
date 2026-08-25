// Keep these UI defaults aligned with apps/studio/api/_workflows.js and the deployed worker recipes.
// LTX `steps` is the fixed total across both stages (8 base + 3 refine), not an arbitrary sampler slider.
// The gateway/worker reject any other LTX step count so the UI cannot imply unsupported sampling behavior.
export const MODEL_ADVANCED_PRESETS = Object.freeze({
  'flux2-klein-9b': Object.freeze({
    modelId: 'flux2-klein-9b',
    modelLabel: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    workflowId: 'flux2-klein-image-edit',
    workflowLabel: 'Klein Multi-Reference Edit',
    seed: '42',
    steps: 4,
    cfg: 1.0,
    negativePrompt: '',
    stepsEditable: true,
    stepsDetail: '4 sampling iterations',
  }),
  'qwen-image-edit-2511': Object.freeze({
    modelId: 'qwen-image-edit-2511',
    modelLabel: 'Qwen Image Edit 2511 · Official BF16',
    workflowId: 'qwen-image-edit-2511',
    workflowLabel: 'Qwen Image Edit 2511',
    seed: '42',
    steps: 40,
    cfg: 4.0,
    negativePrompt: '',
    stepsEditable: true,
    stepsDetail: '40 official inference steps',
  }),
  'ltx25-redgraft': Object.freeze({
    modelId: 'ltx25-redgraft',
    modelLabel: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    workflowId: 'ltx25-redgraft-video',
    workflowLabel: 'LTX 2.5 two-stage video',
    seed: '42',
    steps: 11,
    cfg: 1.0,
    negativePrompt: '',
    stepsEditable: false,
    stepsDetail: '11 total · 8 base + 3 refine',
  }),
});

let activeImageModel = 'flux2-klein-9b';

export function setActiveImageModel(modelId) {
  if (MODEL_ADVANCED_PRESETS[modelId] && modelId !== 'ltx25-redgraft') activeImageModel = modelId;
  return activeImageModel;
}

export function activeImageModelId() {
  return activeImageModel;
}

export function advancedPresetForMode(mode) {
  if (mode === 'Image' || mode === 'Edit') return MODEL_ADVANCED_PRESETS[activeImageModel] || MODEL_ADVANCED_PRESETS['flux2-klein-9b'];
  if (mode === 'Video') return MODEL_ADVANCED_PRESETS['ltx25-redgraft'];
  return null;
}
