import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [presets, controls, wrapper, app, library, controller, client, workflows, providers, gateway, runtime, audioCss] = await Promise.all([
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/create-controls.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useLibraryController.js', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('api/_providers.js', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/ltx23_gateway.py', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/ltx23_app.py', root), 'utf8'),
  readFile(new URL('src/features/create/audio-control.css', root), 'utf8'),
]);

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

expect(/'flux2-klein-9b'[\s\S]*?steps:\s*4[\s\S]*?cfg:\s*1\.0/.test(presets), 'FLUX preset must be 4 steps / CFG 1.0');
expect(/'ltx25-redgraft'[\s\S]*?steps:\s*11[\s\S]*?cfg:\s*1\.0/.test(presets), 'LTX preset must be 11 total steps / CFG 1.0');
expect(controls.includes('data-ltx-fixed-steps="11"'), 'LTX fixed 11-step recipe must be explicit in Advanced');
expect(!controls.includes('<small>8 + 3</small>'), 'LTX Steps value must not show internal stage arithmetic beside 11');
expect(controls.includes('ariaLabel="Video aspect"'), 'Video aspect must live in Advanced');
expect(controls.includes('label="Video frame rate"'), 'Video frame rate must live in Advanced');
expect(controls.includes('aria-label={label}'), 'Advanced custom-select triggers must expose their accessible labels');
expect(!controls.includes('{isVideo && videoToolbarSlot}'), 'Video aspect/FPS must not remain in the prompt toolbar');
expect(!wrapper.includes('<VideoOutputControls'), 'Wrapper must not inject duplicate inline video output controls');
expect(controller.includes('seed: effectiveSeed, steps, cfg'), 'Video controller must forward steps and CFG');
expect(client.includes('steps = 11') && client.includes('cfg = 1.0'), 'Video client defaults must mirror LTX preset');
expect(/frameRate,[\s\S]*?seed,[\s\S]*?steps,[\s\S]*?cfg/.test(client), 'Video request body must include steps and CFG');
expect(/'ltx25-redgraft-video'[\s\S]*?steps:\s*11,[\s\S]*?cfg:\s*1\.0/.test(workflows), 'Backend LTX defaults must be 11 / 1.0');
expect(providers.includes("form.append('steps', String(input.steps))") && providers.includes("form.append('cfg', String(input.cfg))"), 'Provider must forward LTX sampling values');
expect(gateway.includes('steps: int = Form(11)') && gateway.includes('cfg: float = Form(1.0)'), 'LTX gateway must accept sampling values');
expect(runtime.includes('DEFAULT_TOTAL_STEPS = 11') && runtime.includes('LOW_STAGE_STEPS = 8') && runtime.includes('HIGH_STAGE_STEPS = 3'), 'LTX runtime must describe the fixed 8+3 recipe');
expect(runtime.match(/"cfg": float\(cfg\)/g)?.length === 2, 'LTX CFG must drive both stage guiders');
expect(runtime.includes('"separate_distill_lora": False'), 'LTX health contract must state that no separate distill LoRA is loaded');
expect(!app.includes('const samples = ['), 'Create must not ship stock face/scene placeholders');
expect(app.includes('favoriteItems.filter'), 'Create output wall must draw from Favorites');
expect(app.includes("setCreateMode('Edit')"), 'Uploading a reference must apply the FLUX preset when entering Edit');
expect(library.includes("['Create', 'Gallery', 'Favorites', 'Collections']"), 'Favorites must refresh while Create is visible');
expect(/item\.kind === 'video'[\s\S]*?setSteps\(11\)[\s\S]*?setCfg\(1\)/.test(await readFile(new URL('src/hooks/useMediaActions.js', root), 'utf8')), 'Reusing a video must restore the LTX production sampling preset');
expect(!audioCss.includes('.saga-audio-toggle::after'), 'Audio must render only the circular button');

expect(!app.includes('setWorkflowId') && !app.includes('setModelId') && !controls.includes('saved.workflowId') && !controls.includes('saved.modelId'), 'Dead workflow/model presentation state must stay removed from Create');
expect(!app.includes('setOutputs') && !controls.includes('saved.outputs'), 'Dead output-count presentation state must stay removed from Create');
expect(controls.includes('aria-label=\"Recent work\"') && controls.includes('Current-session results appear first'), 'Create results must explain session-first Recent work semantics');
console.log('Create Advanced contract passed: production presets, live LTX CFG transport, fixed 11-step recipe, dead presentation plumbing removed, and Recent work is explicit.');
