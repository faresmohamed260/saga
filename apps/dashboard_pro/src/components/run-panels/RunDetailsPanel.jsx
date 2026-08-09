import { LogViewer, Progress } from "../Progress";
import { Badge, Button, EmptyState, Field, Panel, toneFor } from "../primitives";
import { FailureSummary } from "./FailureSummary";

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
