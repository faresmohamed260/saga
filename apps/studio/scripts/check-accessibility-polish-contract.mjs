import { readFile } from 'node:fs/promises';

const [tokens, gallery, galleryView, polish, app] = await Promise.all([
  readFile(new URL('../src/design-tokens.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/gallery-controls.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/features/library/GalleryView.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/studio-polish.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8'),
]);

function requireSource(source, needle, label) {
  if (!source.includes(needle)) throw new Error(`Accessibility polish contract missing: ${label}`);
}

requireSource(tokens, '--saga-text-2xs: 10px;', '10px minimum dense utility type');
requireSource(tokens, '--saga-text-xs: 11px;', 'raised extra-small type');
requireSource(tokens, '--saga-text-sm: 12px;', 'raised small type');
requireSource(tokens, '--saga-color-text-muted: #a9b0bd;', 'stronger muted text contrast');
requireSource(tokens, '--saga-color-text-subtle: #8993a3;', 'stronger subtle text contrast');
requireSource(tokens, '--saga-focus-shadow:', 'supplemental focus halo');
requireSource(polish, '.app-shell button:focus-visible', 'consistent keyboard focus rule');
requireSource(polish, 'box-shadow: var(--saga-focus-shadow);', 'focus halo usage');
requireSource(galleryView, 'ariaLabel="Type"', 'media filter accessible naming');
requireSource(galleryView, 'aria-pressed={managing}', 'Manage state semantics');
requireSource(gallery, 'font-weight:700;', 'non-color selected-state emphasis');
requireSource(gallery, 'box-shadow:inset 0 -2px 0 var(--saga-color-accent-soft)', 'selected-state shape cue');
requireSource(app, "setSection('Create'); setSettingsOpen(true)", 'global generation-settings action routes to Create before opening Advanced');

console.log('Typography, contrast, focus, and non-color state accessibility contract passed.');
