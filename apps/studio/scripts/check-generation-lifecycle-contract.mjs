import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [client, app, workspace, controls] = await Promise.all([
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/VideoGenerationControls.jsx', root), 'utf8'),
]);

const requireText = (source, text, label) => {
  if (!source.includes(text)) throw new Error(`Missing lifecycle contract: ${label}`);
};

requireText(client, 'if (options.onJob) options.onJob(submitted.job);', 'submitted job callback');
requireText(client, "throw new DOMException('Generation cancelled', 'AbortError')", 'abortable generation polling');
requireText(app, "body: JSON.stringify({ id: activeJob.id, action: 'cancel' })", 'Create cancellation uses real job action');
requireText(app, "setSection('Jobs')", 'View Job navigates to Jobs');
requireText(workspace, 'onViewJob={onViewJob}', 'View Job callback reaches progress');
requireText(workspace, 'onCancelJob={onCancelJob}', 'Cancel callback reaches progress');
requireText(controls, 'Changes to settings now apply to your next generation.', 'running settings guidance');
requireText(controls, '> View Job</button>', 'View Job control');
requireText(controls, "'Cancelling…' : 'Cancel'", 'Cancel control');
requireText(controls, "cancelled: ['Generation cancelled'", 'explicit cancelled state');

console.log('Generation lifecycle contract passed.');
