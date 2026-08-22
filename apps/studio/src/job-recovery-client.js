const RECOVERY_INTERVAL_MS = 10_000;
let recoveryInFlight = false;

async function recoverActiveJobs() {
  if (recoveryInFlight || document.visibilityState === 'hidden') return;
  recoveryInFlight = true;
  try {
    await fetch('/api/jobs/recover', {
      method: 'POST',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
  } catch {
    // Recovery is best-effort. The Jobs page and next visibility/open event retry it.
  } finally {
    recoveryInFlight = false;
  }
}

recoverActiveJobs();
const timer = window.setInterval(recoverActiveJobs, RECOVERY_INTERVAL_MS);
window.addEventListener('focus', recoverActiveJobs);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') recoverActiveJobs();
});
window.addEventListener('beforeunload', () => window.clearInterval(timer), { once: true });
