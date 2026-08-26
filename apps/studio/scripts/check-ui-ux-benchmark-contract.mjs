import { readFile } from 'node:fs/promises';

const [app, gallery, card, modal, controls, workflowRegistry, generationController] = await Promise.all([
  readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/features/library/GalleryView.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaCard.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaModal.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../api/_workflows.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/hooks/useGenerationController.js', import.meta.url), 'utf8'),
]);

const checks = [
  [workflowRegistry.includes("'flux2-klein-image-edit'") && workflowRegistry.includes("'flux2-klein-9b'"), 'Live FLUX edit workflow/model is missing from the production workflow registry'],
  [generationController.includes("mode") && generationController.includes("generate"), 'Generation controller is not mode-driven'],
  [!app.includes('setWorkflowId') && !app.includes('setModelId'), 'Dead workflow/model React state returned to App'],
  [!gallery.includes('Reusable Elements are not available yet'), 'Disabled placeholder Elements tab remains'],
  [card.includes("item.kind !== 'video'"), 'Video cards still expose unsupported Edit actions'],
  [modal.includes('aria-modal="true"'), 'Media preview is not a real modal dialog'],
  [modal.includes("event.key === 'Escape'"), 'Media preview cannot close with Escape'],
  [controls.includes('Create an image') && controls.includes('References are optional'), 'Image setup copy does not explain text generation with optional references'],
];
const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error('UI/UX benchmark contract failed:', failures);
  process.exit(1);
}
console.log('UI/UX benchmark contract passed.');
