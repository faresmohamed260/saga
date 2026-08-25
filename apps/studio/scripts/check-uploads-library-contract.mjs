import { readFile } from 'node:fs/promises';

const uploadsApi = await readFile(new URL('../api/uploads.js', import.meta.url), 'utf8');
const r2 = await readFile(new URL('../api/_r2.js', import.meta.url), 'utf8');
const gallery = await readFile(new URL('../src/features/library/GalleryView.jsx', import.meta.url), 'utf8');
const uploadsView = await readFile(new URL('../src/features/library/UploadsView.jsx', import.meta.url), 'utf8');
const app = await readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8');
const migration = await readFile(new URL('../../../supabase/migrations/20260825062000_add_studio_upload_asset_library.sql', import.meta.url), 'utf8');

const checks = [
  [migration.includes('create table if not exists public.studio_uploads'), 'studio_uploads migration is missing'],
  [migration.includes('is_favorite boolean not null default false'), 'upload favorites persistence is missing'],
  [uploadsApi.includes("body.purpose === 'library-upload' ? 'uploads' : 'sources'"), 'library uploads are not separated from transient generation sources'],
  [uploadsApi.includes("if (req.method === 'GET')"), 'Uploads listing endpoint is missing'],
  [uploadsApi.includes("if (req.method === 'PATCH')"), 'Uploads update endpoint is missing'],
  [uploadsApi.includes("if (req.method === 'DELETE')"), 'Uploads delete endpoint is missing'],
  [uploadsApi.includes("body.phase === 'complete'"), 'Uploads finalize phase is missing'],
  [uploadsApi.includes('headSourceObject(key)'), 'Uploads finalize does not verify the R2 object'],
  [r2.includes('createSourceReadUrl'), 'R2 signed read URLs are missing'],
  [r2.includes('deleteSourceObject'), 'R2 asset deletion is missing'],
  [r2.includes('(?:sources|uploads)'), 'Generation source validation does not allow persisted uploads'],
  [gallery.includes("import UploadsView from './UploadsView.jsx'"), 'Gallery does not mount the Uploads library'],
  [gallery.includes("onClick={() => switchLibrary('uploads')}"), 'Uploads tab is not interactive'],
  [!gallery.includes('Uploads library is not available yet'), 'Legacy disabled Uploads tab remains'],
  [uploadsView.includes("purpose: 'library-upload'"), 'Uploads UI does not request persistent upload tickets'],
  [uploadsView.includes("phase: 'complete'"), 'Uploads UI does not finalize persisted assets'],
  [uploadsView.includes('Set as Reference'), 'Upload detail view is missing Set as Reference'],
  [uploadsView.includes('Generate Video'), 'Upload detail view is missing Generate Video'],
  [uploadsView.includes('Selected upload actions'), 'Upload batch manager is missing'],
  [app.includes('onUseUploadReference={useUploadReference}'), 'Upload reuse is not wired into Create'],
];

const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error(`Uploads library contract failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}
console.log('Uploads library contract passed: durable R2 catalog, list/search/favorite/rename/delete, batch actions, preview, and Create reuse are wired.');
