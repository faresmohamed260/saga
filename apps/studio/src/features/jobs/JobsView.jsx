import React, { useEffect, useState } from 'react';
import { CheckCircle2, LoaderCircle, RotateCcw, X, XCircle } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const JOB_PAGE_SIZE = 10;

const STATUS_COPY = {
  uploading: ['Uploading reference', 'Preparing the source image for generation.'],
  submitting: ['Submitting generation', 'Sending the request to the assigned model ecosystem.'],
  queued: ['Waiting for worker', 'The request is queued for an available ecosystem worker.'],
  sleeping: ['Worker sleeping', 'Compute is scaled to zero and will start on demand.'],
  waking: ['Starting worker', 'The assigned worker is waking from zero compute.'],
  loading: ['Loading model', 'Cached model assets are loading into GPU memory.'],
  ready: ['Worker ready', 'The model ecosystem is ready to begin generation.'],
  generating: ['Generating', 'The assigned model ecosystem is producing the requested media.'],
  running: ['Generating', 'The assigned model ecosystem is producing the requested media.'],
  finalizing: ['Finalizing result', 'Generation is complete and the result is being prepared for Gallery.'],
  credit_exhausted: ['Switching worker', 'The assigned worker reached its credit limit. A standby worker will be used when available.'],
  unavailable: ['Worker unavailable', 'The assigned worker is unavailable. A standby worker will be used when available.'],
  completed: ['Generation ready', 'The completed result has been saved to Gallery.'],
  cancelled: ['Generation cancelled', 'The running provider job was stopped by request.'],
  failed: ['Generation failed', 'The request did not complete. See the message below for details.'],
};

function formatJobTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function formatElapsed(value) {
  if (!value) return '';
  const started = new Date(value).getTime();
  if (!Number.isFinite(started)) return '';
  const elapsed = Math.max(0, Math.floor((Date.now() - started) / 1000));
  if (elapsed < 60) return `${elapsed}s elapsed`;
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return `${minutes}m ${seconds}s elapsed`;
}

function objectValue(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function runtimePresentation(job) {
  const metadata = objectValue(job.metadata);
  const runtime = objectValue(metadata.workerRuntime);
  const cancelled = Boolean(metadata.cancelled);
  const state = cancelled
    ? 'cancelled'
    : ['completed', 'failed'].includes(job.status)
      ? job.status
      : runtime.state || job.status || 'queued';
  const [baseTitle, baseDetail] = STATUS_COPY[state] || STATUS_COPY.running;
  const failedWorkers = Array.isArray(runtime.failedWorkers) ? runtime.failedWorkers : [];
  const failoverReason = runtime.failoverReason
    || failedWorkers.find((failure) => failure?.kind === 'credit_exhausted')?.kind
    || failedWorkers.find((failure) => failure?.kind === 'unavailable')?.kind
    || '';
  const workerName = runtime.displayName || runtime.workerId || metadata.assignedWorkerId || '';
  let title = state === 'generating' || state === 'running' ? `Generating ${job.kind || 'media'}` : baseTitle;
  let detail = workerName ? `${baseDetail} · ${workerName}` : baseDetail;

  if (!['completed', 'failed', 'cancelled'].includes(state) && failoverReason === 'credit_exhausted') {
    title = 'Switching worker';
    detail = `The previous worker reached its credit limit. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  } else if (!['completed', 'failed', 'cancelled'].includes(state) && failoverReason === 'unavailable') {
    title = 'Switching worker';
    detail = `The previous worker became unavailable. ${workerName ? `Starting ${workerName}.` : 'Starting a standby worker.'}`;
  }

  return {
    state,
    title,
    detail,
    terminal: ['completed', 'failed', 'cancelled'].includes(state),
  };
}

export default function JobsView({ jobs, filter, loading, error, actionBusyId, onFilterChange, onJobAction }) {
  const [visibleCount, setVisibleCount] = useState(JOB_PAGE_SIZE);
  useEffect(() => setVisibleCount(JOB_PAGE_SIZE), [filter]);
  const visibleJobs = jobs.slice(0, visibleCount);

  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Execution" title="Jobs & queue" description="Live generation lifecycle. Jobs update automatically while this page is open; completed media moves to Gallery." />
      <div className="gallery-toolbar" style={{ justifyContent: 'flex-start' }}>
        <div className="gallery-kind-tabs" role="group" aria-label="Job status filter">
          {[['active', 'Active'], ['queued', 'Queued'], ['running', 'Running'], ['failed', 'Failed'], ['completed', 'Completed'], ['all', 'Recent']].map(([value, label]) => (
            <button key={value} className={filter === value ? 'selected' : ''} aria-pressed={filter === value} onClick={() => onFilterChange(value)}>{label}</button>
          ))}
        </div>
      </div>
      {error && <div className="history-state error">{error}</div>}
      {loading && jobs.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading jobs…</div> : jobs.length === 0 ? <div className="history-state">No lifecycle jobs match this filter.</div> : <><div className="jobs-list">{visibleJobs.map((job) => {
        const cancelled = Boolean(job.metadata?.cancelled);
        const actionBusy = actionBusyId === job.id;
        const runtime = runtimePresentation(job);
        return <article className="job-card" key={job.id} style={{ border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, background: 'rgba(255,255,255,.025)', padding: '16px 18px', display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}>
              <span style={{ textTransform: 'uppercase', fontSize: 11, fontWeight: 700, letterSpacing: '.08em', padding: '5px 8px', borderRadius: 999, border: '1px solid rgba(255,255,255,.14)', opacity: job.status === 'failed' ? 1 : .8 }}>{cancelled ? 'cancelled' : job.status}</span>
              <strong style={{ fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.prompt || 'Untitled job'}</strong>
            </div>
            <span style={{ fontSize: 12, color: '#7f8999' }}>{formatJobTime(job.created_at)}</span>
          </div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, color: '#8f98a8' }}>
            <span>{job.kind || 'image'} · {job.mode || 'generation'}</span><span>{job.model || 'Unknown model'}</span>{job.seed != null && <span>Seed {job.seed}</span>}{job.resolution && <span>{job.resolution}</span>}
          </div>
          <div className={`saga-generation-progress is-${runtime.state}`} style={{ margin: 0 }} role="status" aria-live="polite">
            <div className="saga-generation-progress-icon">
              {runtime.state === 'completed' ? <CheckCircle2 size={17}/> : runtime.state === 'failed' || runtime.state === 'cancelled' ? <XCircle size={17}/> : <LoaderCircle className="spin" size={17}/>}
            </div>
            <div className="saga-generation-progress-copy">
              <div><strong>{runtime.title}</strong>{!runtime.terminal && <span>{formatElapsed(job.started_at)}</span>}</div>
              <small>{runtime.detail}</small>
              <div className={`saga-generation-progress-track ${runtime.terminal ? 'terminal' : 'indeterminate'}`} aria-hidden="true"><span /></div>
            </div>
          </div>
          <details style={{ fontSize: 11, color: '#687284' }}>
            <summary style={{ cursor: 'pointer', width: 'fit-content' }}>Technical details</summary>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', paddingTop: 8 }}>
              <span>Provider {job.provider || 'n/a'}</span><span>Queued {formatJobTime(job.created_at)}</span><span>Started {formatJobTime(job.started_at)}</span><span>Finished {formatJobTime(job.completed_at)}</span>
            </div>
          </details>
          {job.error_message && <div style={{ padding: '10px 12px', borderRadius: 9, background: 'rgba(120,20,35,.14)', border: '1px solid rgba(255,100,120,.25)', color: '#ffb4c0', fontSize: 12 }}>{job.error_message}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>{['queued', 'running'].includes(job.status) && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'cancel')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <X size={16}/>} Cancel</button>}{job.status === 'failed' && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'retry')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <RotateCcw size={16}/>} Retry</button>}</div>
        </article>;
      })}</div>
      {visibleCount < jobs.length && <div className="jobs-list-more"><button type="button" className="secondary-button" onClick={() => setVisibleCount((current) => Math.min(current + JOB_PAGE_SIZE, jobs.length))}>Show more jobs</button><span>Showing {visibleJobs.length} of {jobs.length}</span></div>}
      </>}
    </section>
  );
}
