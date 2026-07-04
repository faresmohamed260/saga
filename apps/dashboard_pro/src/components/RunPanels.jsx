import { Link } from "react-router-dom";
import { LogViewer, Progress } from "./Progress";
import { Badge, Button, DataCard, EmptyState, Field, Panel, shortRef, toneFor } from "./primitives";

export function RunsListPanel({ jobs }) {
  return (
    <Panel title="Runs" subtitle="Recent work items and queued jobs.">
      {jobs.length ? (
        <div className="space-y-3">
          {jobs.map((job) => (
            <RunListItem key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <EmptyState title="No runs found" />
      )}
    </Panel>
  );
}

function RunListItem({ job }) {
  return (
    <DataCard as={Link} to={`/runs/${encodeURIComponent(job.id)}`} interactive className="block overflow-hidden">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-black text-white" title={job.id}>{job.id}</p>
          <p className="mt-1 truncate text-sm text-slate-500" title={job.command || job.type || ""}>{shortRef(job.command || job.type || "")}</p>
        </div>
        <div className="max-w-[120px] shrink-0">
          <Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge>
        </div>
      </div>
    </DataCard>
  );
}

export function RunDetailsPanel({ job, progress, logs, failureSummary, canRetry, canCancel, onControl }) {
  return (
    <Panel
      title={job?.id || "Select a run"}
      subtitle={job ? `${job.type || job.job_type || "job"} - ${job.status || "unknown"}` : "Choose a run from the left."}
      action={job ? (
        <div className="flex flex-wrap gap-2">
          {canRetry ? <Button onClick={() => onControl("retry")}>Retry</Button> : null}
          {canCancel ? <Button variant="danger" onClick={() => onControl("cancel")}>Cancel</Button> : null}
        </div>
      ) : null}
    >
      {job ? (
        <div className="space-y-4">
          <Progress job={{ ...job, progress }} />
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="Status"><Badge tone={toneFor(job.status)}>{job.status}</Badge></Field>
            <Field label="Phase">{progress.phase || progress.stage || progress.status || "n/a"}</Field>
            <Field label="PID">{job.pid || "n/a"}</Field>
            <Field label="Return code">{job.return_code ?? "n/a"}</Field>
          </div>
          {failureSummary ? <FailureSummary summary={failureSummary} /> : null}
          <Panel title="Run log" subtitle="Most recent job logs. Errors are highlighted for review.">
            <LogViewer lines={logs} />
          </Panel>
        </div>
      ) : (
        <EmptyState title="No run selected" />
      )}
    </Panel>
  );
}

function FailureSummary({ summary }) {
  return (
    <div className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100">
      <p className="font-black text-amber-50">Failure summary</p>
      <p className="mt-2">{summary.reason}</p>
      {summary.exception && summary.exception !== summary.reason ? <p className="mt-2 text-amber-200/80">{summary.exception}</p> : null}
      <p className="mt-2 text-xs uppercase tracking-[0.18em] text-amber-200/70">{summary.traceback}</p>
    </div>
  );
}
