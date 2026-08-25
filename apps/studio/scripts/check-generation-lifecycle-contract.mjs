import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [client, controller, workspace, controls, app, recovery, libraryController, jobsView, galleryView, favoritesView] = await Promise.all([
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/VideoGenerationControls.jsx', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('server/job-recovery.js', root), 'utf8'),
  readFile(new URL('src/hooks/useLibraryController.js', root), 'utf8'),
  readFile(new URL('src/features/jobs/JobsView.jsx', root), 'utf8'),
  readFile(new URL('src/features/library/GalleryView.jsx', root), 'utf8'),
  readFile(new URL('src/features/library/FavoritesView.jsx', root), 'utf8'),
]);

const requireText = (source, text, label) => {
  if (!source.includes(text)) throw new Error(`Missing lifecycle contract: ${label}`);
};

const forbidText = (source, text, label) => {
  if (source.includes(text)) throw new Error(`Forbidden lifecycle contract: ${label}`);
};

requireText(client, 'if (options.onJob) options.onJob(submitted.job);', 'submitted job callback');
requireText(client, "throw new DOMException('Generation cancelled', 'AbortError')", 'abortable generation polling');
requireText(controller, "runJobAction(activeJob.id, 'cancel')", 'Create cancellation uses real job action');
requireText(controller, "setSection('Jobs')", 'View Job navigates to Jobs');
requireText(workspace, 'onViewJob={onViewJob}', 'View Job callback reaches progress');
requireText(workspace, 'onCancelJob={onCancelJob}', 'Cancel callback reaches progress');
requireText(controls, 'Changes to settings now apply to your next generation.', 'running settings guidance');
requireText(controls, '> View Job</button>', 'View Job control');
requireText(controls, "'Cancelling…' : 'Cancel'", 'Cancel control');
requireText(controls, "cancelled: ['Generation cancelled'", 'explicit cancelled state');

requireText(app, "window.setInterval(() => loadJobs({ silent: true, filter: jobsFilter }), 3000)", 'Jobs automatic polling');
requireText(recovery, 'persistVideoJobResult(', 'video recovery persistence');
requireText(recovery, 'result.posterBytes || null', 'recovered video poster persistence');
requireText(recovery, "outcome: 'completed'", 'recovered video completion state');
requireText(libraryController, 'const AUTO_REFRESH_MS = 5000;', 'library automatic refresh interval');
requireText(libraryController, 'window.setInterval(() => refresh(), AUTO_REFRESH_MS)', 'library automatic polling');
requireText(libraryController, "document.visibilityState === 'visible'", 'library refresh on visibility');
requireText(libraryController, "window.addEventListener('focus', onFocus)", 'library refresh on focus');
requireText(libraryController, 'preserveLoaded: !initial', 'Gallery automatic refresh preserves loaded pages');

for (const [source, label] of [[jobsView, 'Jobs'], [galleryView, 'Gallery'], [favoritesView, 'Favorites']]) {
  forbidText(source, 'RefreshCcw', `${label} manual refresh icon`);
  forbidText(source, 'onRefresh', `${label} manual refresh callback`);
  forbidText(source, '> Refresh</button>', `${label} manual refresh button`);
}

console.log('Generation lifecycle contract passed.');
