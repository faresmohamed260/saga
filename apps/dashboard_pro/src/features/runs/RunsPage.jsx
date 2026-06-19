import { useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { runtimeApi } from "../../api/runtimeApi";
import { LogViewer, Progress } from "../../components/feedback/Progress";
import { Badge, Button, EmptyState, Field, Panel, shortRef, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function RunsPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { state, reload } = useRuntimeState();
  const jobs = useMemo(() => sortJobs(state?.jobs || []), [state?.jobs]);
  const selected = useMemo(() => {
    const direct = jobs.find((job) => job.id === jobId);
    if (direct) {
      const retryJob = jobs.find(
        (job) =>
          String(job?.artifacts?.retry_of || "") === String(direct.id || "") &&
          isActiveJob(job),
      );
      return retryJob || direct;
    }
    return jobs.find(isActiveJob) || jobs.find(isCompletedJob) || jobs[0];
  }, [jobs, jobId]);
  const details = useAsync(() => selected?.id ? runtimeApi.job(selected.id) : Promise.resolve(null), [selected?.id]);

  useEffect(() => {
    if (selected?.id && selected.id !== jobId) {
      navigate(`/runs/${encodeURIComponent(selected.id)}`, { replace: true });
    }
  }, [selected?.id, jobId, navigate]);

  useEffect(() => {
    if (!selected || !["running", "queued", "starting"].includes(String(selected.status || "").toLowerCase())) return;
    const timer = setInterval(() => {
      reload();
      details.reload();
    }, 3000);
    return () => clearInterval(timer);
  }, [selected?.id, selected?.status]);

  useEffect(() => {
    if (!selected?.id || !details.value || details.value.id !== selected.id) return;
    const selectedStatus = String(selected.status || "").toLowerCase();
    const detailStatus = String(details.value.status || "").toLowerCase();
    if (selectedStatus && selectedStatus !== detailStatus && !isActiveJob(selected)) {
      details.reload();
    }
  }, [selected?.id, selected?.status, details.value?.id, details.value?.status]);

  async function control(action) {
    if (!selected?.id) return;
    try {
      const result = await runtimeApi.jobControl(selected.id, action);
      await reload();
      if (action === "retry" && result?.id) {
        navigate(`/runs/${encodeURIComponent(result.id)}`);
        return;
      }
      await details.reload();
    } catch (error) {
      alert(error.message);
    }
  }

  const job = useMemo(() => mergeJobSnapshot(selected, details.value), [selected, details.value]);
  const progress = normalizedProgress(job);
  const logs = job?.log_tail || [];
  const failureSummary = summarizeFailure(job, logs);
  const status = String(job?.status || "").toLowerCase();
  const type = String(job?.type || job?.job_type || "");
  const canCancel = ["queued", "running", "starting", "staging", "validated", "blocked"].includes(status);
  const canRetry = ["failed", "cancelled"].includes(status) && type === "db-native-analysis";

  return (
    <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
      <Panel title="Runs" subtitle="One card per persisted dashboard job.">
        {jobs.length ? (
          <div className="space-y-3">
            {jobs.map((job) => (
              <Link key={job.id} to={`/runs/${encodeURIComponent(job.id)}`} className="block overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/45 p-4 hover:border-sky-500/60">
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-black text-white" title={job.id}>{job.id}</p>
                    <p className="mt-1 truncate text-sm text-slate-500" title={job.command || job.type || ""}>{shortRef(job.command || job.type || "")}</p>
                  </div>
                  <div className="max-w-[120px] shrink-0"><Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge></div>
                </div>
              </Link>
            ))}
          </div>
        ) : <EmptyState title="No runs found" />}
      </Panel>

      <Panel
        title={job?.id || "Select a run"}
        subtitle={job ? `${job.type || job.job_type || "job"} - ${job.status || "unknown"}` : "Choose a run from the left."}
        action={job ? (
          <div className="flex flex-wrap gap-2">
            {canRetry ? <Button onClick={() => control("retry")}>Retry</Button> : null}
            {canCancel ? <Button variant="danger" onClick={() => control("cancel")}>Cancel</Button> : null}
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
            <Panel title="Structured log tail" subtitle="Most recent persisted job logs. Errors are highlighted; full tracebacks stay scrollable for debugging.">
              <LogViewer lines={logs} />
            </Panel>
          </div>
        ) : <EmptyState title="No run selected" />}
      </Panel>
    </div>
  );
}

function mergeJobSnapshot(selected, detail) {
  if (!detail) return selected;
  if (!selected) return detail;
  if (selected.id !== detail.id) return detail;
  return {
    ...detail,
    ...selected,
    log_tail: detail.log_tail || selected.log_tail || [],
    request: detail.request || selected.request || {},
    artifacts: {
      ...(detail.artifacts || {}),
      ...(selected.artifacts || {}),
    },
    progress: {
      ...(detail.progress || {}),
      ...(selected.progress || {}),
    },
  };
}

function isActiveJob(job) {
  return ["running", "queued", "starting", "validating", "staging"].includes(String(job?.status || "").toLowerCase());
}

function isCompletedJob(job) {
  return ["completed", "success"].includes(String(job?.status || "").toLowerCase());
}

function sortJobs(jobs) {
  const score = (job) => {
    if (isActiveJob(job)) return 0;
    if (isCompletedJob(job)) return 1;
    if (String(job?.status || "").toLowerCase() === "failed") return 2;
    return 3;
  };
  return [...jobs].sort((a, b) => {
    const statusDelta = score(a) - score(b);
    if (statusDelta) return statusDelta;
    return String(b.started_at || b.finished_at || "").localeCompare(String(a.started_at || a.finished_at || ""));
  });
}

function normalizedProgress(job) {
  const progress = job?.progress || {};
  const status = String(job?.status || progress.status || "").toLowerCase();
  if (status === "failed") {
    return {
      ...progress,
      current: progress.current || 0,
      total: progress.total || 1,
      label: job?.status_reason || job?.error || progress.label || "Job failed",
      phase: progress.phase || progress.stage || "failed",
      status: "failed",
    };
  }
  if (["completed", "success"].includes(status)) {
    return {
      ...progress,
      current: progress.current || progress.total || 1,
      total: progress.total || progress.current || 1,
      label: progress.label || "Job completed",
      phase: progress.phase || progress.stage || "complete",
      status: "completed",
    };
  }
  return {
    ...progress,
    current: progress.current || 0,
    total: progress.total || 0,
    label: progress.label || job?.status_reason || job?.type || "Waiting for progress",
    status: job?.status || progress.status || "unknown",
  };
}

function summarizeFailure(job, logs) {
  const status = String(job?.status || "").toLowerCase();
  const terminalFailureStatuses = new Set(["failed", "cancelled", "blocked", "blocked_rate_limit", "paused"]);
  if (!terminalFailureStatuses.has(status)) return null;
  const lines = (logs || []).map((line) => typeof line === "string" ? line : line?.line_text || JSON.stringify(line));
  const tracebackStart = lines.findIndex((line) => /Traceback/i.test(line));
  const exceptionLine = [...lines].reverse().find((line) => /(Error|Exception|ImportError|KeyboardInterrupt|failed with exit code)/i.test(line));
  return {
    reason: job?.status_reason || job?.error || exceptionLine || "Job failed.",
    exception: exceptionLine || "",
    traceback: tracebackStart >= 0 ? `${lines.length - tracebackStart} traceback line(s) recorded` : "No traceback recorded",
  };
}

function FailureSummary({ summary }) {
  return (
    <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100">
      <p className="font-black text-amber-50">Failure summary</p>
      <p className="mt-2">{summary.reason}</p>
      {summary.exception && summary.exception !== summary.reason ? <p className="mt-2 text-amber-200/80">{summary.exception}</p> : null}
      <p className="mt-2 text-xs uppercase tracking-[0.18em] text-amber-200/70">{summary.traceback}</p>
    </div>
  );
}
