import { readFile } from 'node:fs/promises';

const [controls, css, tokens, visual] = await Promise.all([
  readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/create-workspace-v2.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/design-tokens.css', import.meta.url), 'utf8'),
  readFile(new URL('./capture-ui-preview.mjs', import.meta.url), 'utf8'),
]);

function requireSource(source, needle, label) {
  if (!source.includes(needle)) throw new Error(`Generate primary-action contract missing: ${label}`);
}

requireSource(controls, 'className="saga-round-button"', 'shared circular reference-upload action');
requireSource(controls, 'onDrop={handleReferenceDrop}', 'composer file-drop handler');
requireSource(controls, 'Drop images to upload', 'drag-over upload affordance');
requireSource(controls, '<span className="saga-submit-label">{isEdit ? \'Edit\' : \'Generate\'}</span>', 'connected generation verb markup');
requireSource(css, 'min-width:112px;height:38px', 'promoted desktop dimensions');
requireSource(css, 'display:inline-flex;align-items:center;justify-content:center;gap:8px', 'desktop label/icon layout');
requireSource(css, '.workspace .saga-submit:focus-visible{outline:var(--saga-focus-ring);outline-offset:2px}', 'tokenized strong focus-visible treatment');
requireSource(tokens, '--saga-focus-ring: 2px solid var(--saga-color-accent-soft);', 'shared focus-ring token');
requireSource(css, '.workspace .saga-submit-label{display:none}', 'compact mobile label collapse');
requireSource(css, 'width:36px;height:36px;min-width:36px;flex-basis:36px', 'compact mobile submit geometry');
requireSource(visual, "Image setup circular upload action is missing", 'desktop circular-upload assertion');
requireSource(visual, "Mobile circular upload action does not provide a 44px touch target", 'mobile circular-upload assertion');
requireSource(visual, "Edit mode primary action does not expose its principal Edit verb", 'Edit-mode Playwright assertion');

console.log('Generate primary-action contract passed.');
