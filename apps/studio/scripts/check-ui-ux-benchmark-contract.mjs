import { readFile } from 'node:fs/promises';

const [app, gallery, card, modal, controls] = await Promise.all([
  readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/features/library/GalleryView.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaCard.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaModal.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8'),
]);

const checks = [
  [app.includes("useState('flux2-klein-image-edit')"), 'Image setup does not default to the live FLUX workflow'],
  [app.includes("useState('flux2-klein-9b')"), 'Image setup does not default to the live FLUX model'],
  [!gallery.includes('Reusable Elements are not available yet'), 'Disabled placeholder Elements tab remains'],
  [card.includes("item.kind !== 'video'"), 'Video cards still expose unsupported Edit actions'],
  [modal.includes('aria-modal="true"'), 'Media preview is not a real modal dialog'],
  [modal.includes("event.key === 'Escape'"), 'Media preview cannot close with Escape'],
  [controls.includes("Create from a reference"), 'Image setup copy does not explain the real task'],
];
const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error('UI/UX benchmark contract failed:', failures);
  process.exit(1);
}
console.log('UI/UX benchmark contract passed.');
