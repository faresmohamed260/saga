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
expect(css.includes("content: 'Audio On';"), 'Desktop Audio On text is missing');
expect(css.includes("content: 'Audio Off';"), 'Desktop Audio Off text is missing');
expect(css.includes("content: 'Audio on · Generate with sound';"), 'Audio On explanatory tooltip copy is missing');
expect(css.includes("content: 'Audio off · Generate without sound';"), 'Audio Off explanatory tooltip copy is missing');
expect(css.includes("content: 'On';"), 'Compact mobile Audio On text is missing');
expect(css.includes("content: 'Off';"), 'Compact mobile Audio Off text is missing');
expect(/\.saga-audio-toggle:focus-visible\s*\{[\s\S]*?outline:\s*2px/.test(css), 'Audio control needs a 2px focus-visible outline');
expect(html.includes('/src/features/create/audio-control.css'), 'Audio control stylesheet is not loaded');
expect(pkg.scripts?.build?.includes('check-audio-control-contract.mjs'), 'Audio control contract is not part of the Studio build');
expect(pkg.scripts?.['visual:preview']?.includes('capture-audio-state-preview.mjs'), 'Audio state visual contract is not part of Studio Visual Preview');

console.log('Audio control contract passed: explicit On/Off text, explanatory tooltip copy, aria-pressed state, focus treatment, and compact mobile behavior are wired.');
