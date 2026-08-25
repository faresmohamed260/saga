import { readFile } from 'node:fs/promises';

const [controls, css, html, pkgRaw] = await Promise.all([
  readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/features/create/audio-control.css', import.meta.url), 'utf8'),
  readFile(new URL('../index.html', import.meta.url), 'utf8'),
  readFile(new URL('../package.json', import.meta.url), 'utf8'),
]);
const pkg = JSON.parse(pkgRaw);

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

expect(controls.includes('className={`saga-audio-toggle ${videoAudio ? \'active\' : \'\'}`}'), 'Audio control class contract changed');
expect(controls.includes('aria-pressed={videoAudio}'), 'Audio control must expose aria-pressed state');
expect(controls.includes("aria-label={videoAudio ? 'Disable audio' : 'Enable audio'}"), 'Audio control must preserve action-oriented accessible labels');
expect(controls.includes("title={videoAudio ? 'Audio enabled' : 'Audio disabled'}"), 'Audio control must preserve native state tooltip text');
expect(!css.includes('.saga-audio-toggle::after'), 'Audio control must not render a duplicate text button beside the circular control');
expect(/\.saga-audio-toggle:focus-visible\s*\{[\s\S]*?outline:\s*2px/.test(css), 'Audio control needs a 2px focus-visible outline');
expect(html.includes('/src/features/create/audio-control.css'), 'Audio control stylesheet is not loaded');
expect(pkg.scripts?.build?.includes('check-audio-control-contract.mjs'), 'Audio control contract is not part of the Studio build');
const visualPreview = pkg.scripts?.['visual:preview'] || '';
const visualCapture = pkg.scripts?.['visual:capture'] || '';
expect(
  visualPreview.includes('visual:capture') && visualCapture.includes('capture-audio-state-preview.mjs'),
  'Audio state visual contract is not part of Studio Visual Preview',
);

console.log('Audio control contract passed: one circular control, explanatory tooltip copy, aria-pressed state, and focus treatment are wired.');
