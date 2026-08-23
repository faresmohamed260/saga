import React from 'react';
import { LoaderCircle, RefreshCcw, RotateCcw, X } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

function formatJobTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export default function JobsView({ jobs, filter, loading, error, actionBusyId, onFilterChange, onRefresh, onJobAction }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Execution" title="Jobs & queue" description="Live generation lifecycle. This page polls while open; completed media stays in History." action={<button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18}/> : <RefreshCcw size={18}/>} Refresh</button>} />
      <div className="history-toolbar"><div className="history-kind-tabs" role="group" aria-label="Job status filter">{[['active', 'Active'], ['queued', 'Queued'], ['running', 'Running'], ['failed', 'Failed'], ['completed', 'Completed'], ['all', 'Recent']].map(([value, label]) => <button key={value} className={filter === value ? 'selected' : ''} onClick={() => onFilterChange(value)}>{label}</button>)}</div></div>
      {error && <div className="history-state error">{error}</div>}
      {loading && jobs.length === 0 ? <div className="history-state"><LoaderCircle className="spin" size={22}/> Loading jobs…</div> : jobs.length === 0 ? <div className="history-state">No lifecycle jobs match this filter.</div> : <div style={{ display: 'grid', gap: 12 }}>{jobs.map((job) => {
        const cancelled = Boolean(job.metadata?.cancelled);
        const actionBusy = actionBusyId === job.id;
        return <article key={job.id} style={{ border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, background: 'rgba(255,255,255,.025)', padding: '16px 18px', display: 'grid', gap: 10 }}><div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}><div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}><span style={{ textTransform: 'uppercase', fontSize: 11, fontWeight: 700, letterSpacing: '.08em', padding: '5px 8px', borderRadius: 999, border: '1px solid rgba(255,255,255,.14)', opacity: job.status === 'failed' ? 1 : .8 }}>{cancelled ? 'cancelled' : job.status}</span><strong style={{ fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.prompt || 'Untitled job'}</strong></div><span style={{ fontSize: 12, color: '#7f8999' }}>{formatJobTime(job.created_at)}</span></div><div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, color: '#8f98a8' }}><span>{job.kind || 'image'} · {job.mode || 'generation'}</span><span>{job.model || 'Unknown model'}</span><span>{job.provider || 'provider n/a'}</span>{job.seed != null && <span>Seed {job.seed}</span>}{job.resolution && <span>{job.resolution}</span>}</div><div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 11, color: '#687284' }}><span>Queued {formatJobTime(job.created_at)}</span><span>Started {formatJobTime(job.started_at)}</span><span>Finished {formatJobTime(job.completed_at)}</span></div>{job.error_message && <div style={{ padding: '10px 12px', borderRadius: 9, background: 'rgba(120,20,35,.14)', border: '1px solid rgba(255,100,120,.25)', color: '#ffb4c0', fontSize: 12 }}>{job.error_message}</div>}<div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>{['queued', 'running'].includes(job.status) && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'cancel')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <X size={16}/>} Cancel</button>}{job.status === 'failed' && <button className="secondary-button" disabled={actionBusy} onClick={() => onJobAction(job, 'retry')}>{actionBusy ? <LoaderCircle className="spin" size={16}/> : <RotateCcw size={16}/>} Retry</button>}</div></article>;
      })}</div>}
    </section>
  );
}
