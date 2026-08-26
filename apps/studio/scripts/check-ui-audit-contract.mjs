import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [controls, presets, app, sidebar, models, workflowsView, settings, mediaCard, mediaActions, controller, client, workflows, gateway] = await Promise.all([
  readFile(new URL('src/create-controls.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('src/components/Sidebar.jsx', root), 'utf8'),
  readFile(new URL('src/features/catalog/ModelsView.jsx', root), 'utf8'),
  readFile(new URL('src/features/catalog/WorkflowsView.jsx', root), 'utf8'),
  readFile(new URL('src/features/settings/SettingsView.jsx', root), 'utf8'),
  readFile(new URL('src/components/MediaCard.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useMediaActions.js', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/flux2_klein_gateway.py', root), 'utf8'),
]);

function expect(condition, message) { if (!condition) throw new Error(message); }
expect(!controls.includes('<small>8 + 3</small>'), 'Advanced Steps must show 11 without internal stage arithmetic');
expect(controls.includes('createPortal('), 'Advanced custom selects must render through a viewport portal');
expect(controls.includes('saga-fancy-options-portal'), 'Advanced select portal surface is missing');
expect(/if \(mode === 'Image' \|\| mode === 'Edit'\)/.test(presets), 'Image setup and Edit must share the live FLUX advanced preset');
expect(controls.includes('aria-label="Negative prompt"'), 'Advanced must expose the backend negative-prompt parameter');
expect(controller.includes('negativePrompt, resolution:') && controller.includes('prompt: prompt.trim(), negativePrompt, resolution: videoResolution'), 'Negative prompt must reach both connected workflows');
expect(client.includes('negativePrompt') && client.includes('negativePrompt,'), 'Generation client must transport negative prompt');
expect(!controls.includes("isImageSetup ? 'Add image'"), 'Image setup must not use a wide Add image submit CTA');
// Image setup, Edit, and Video intentionally share this one circular reference-upload control.
const roundUploadMarkup = '<button type="button" className="saga-round-button" title="Upload reference images" aria-label="Upload reference images"';
expect(controls.includes(roundUploadMarkup) && !controls.includes(`{!isImageSetup && (\n              ${roundUploadMarkup}`), 'Image and Video must share the circular upload affordance');
expect(controls.includes('onDrop={handleReferenceDrop}') && controls.includes('Drop images to upload'), 'Create composer must support image drag-and-drop');
expect(!controls.includes('ref={settingsButtonRef}'), 'Prompt toolbar must not duplicate the global Advanced trigger');
expect(controls.includes('<span className="saga-submit-label">Generate</span>') && controls.includes('disabled={busy || !prompt.trim()}'), 'Generate must remain a separate prompt-gated action across Image/Edit/Video');
expect(app.includes('navigationOpen') && sidebar.includes('onBlurCapture') && sidebar.includes('handlePointerDown'), 'Sidebar must collapse from desktop/mobile and dismiss outside by pointer or keyboard focus');
expect(!controls.includes("mode === 'More'") && !sidebar.includes('Additional creation tools') && !sidebar.includes('label="Tools"'), 'Placeholder Tools mode must be removed');
expect(!models.includes('PLANNED') && !models.includes('SAGA Image'), 'Models page must contain only live production models');
expect(models.includes('Start image edit') && models.includes('Create video') && models.includes('onUseModel'), 'Models page must launch its live production paths');
expect(workflowsView.includes('Klein Multi-Reference Edit') && workflowsView.includes('LTX 2.5 Two-Stage Video'), 'Workflows page must list both live paths');
expect(workflowsView.includes('Start image edit') && workflowsView.includes('Create video') && workflowsView.includes('onUseWorkflow'), 'Workflows page must launch its live production paths');
expect(settings.includes('Output controls') && settings.includes('Aspect, resolution, duration, frame rate, and audio'), 'Settings must explain which output controls stay in Create');
expect(settings.includes('Advanced controls') && settings.includes('Seed, sampling, CFG, negative prompt'), 'Settings must explain which controls belong in Advanced');
expect(mediaCard.includes('Animate this') && mediaActions.includes('const animateThis = async (item)'), 'Generated images must expose the real image-to-video continuation path');
expect((gateway.match(/def _submit_state\(\):/g) || []).length === 1, 'FLUX gateway must not contain duplicate submit-state helpers');
const ltx = workflows.slice(workflows.indexOf("'ltx25-redgraft-video'"));
expect(!/defaults:\s*\{[\s\S]*?megapixels:\s*1\.0/.test(ltx.split('limits:')[0]), 'LTX workflow must not advertise an unused megapixels default');
expect(!app.includes('advanced={advanced}'), 'Dead Advanced state prop must be removed');
console.log('Studio UI audit contract passed: requested controls are fixed, connected backend parameters are exposed, and placeholder/dead surfaces are removed.');
expect(!controls.includes('aria-label="Active production model"'), 'Advanced must not duplicate MODEL/WORKFLOW detail cards below model selection');
expect(controls.includes('randomizeSeed') && controls.includes('Dice3DIcon'), 'Advanced seed must expose persistent/random per-generation mode');
