import { Badge, toneFor } from "../primitives";
import { computeCounterLabel, computeProgressPercent } from "./progressUtils";

export function Progress({ job }) {
  const progress = job?.progress || {};
  const current = Number(progress.current || 0);
  const total = Number(progress.total || 0);
  const details = progress.details || {};
  const percent = computeProgressPercent({
    current,
    total,
    details,
    stage: progress.stage,
    status: job?.status || progress.status || "unknown",
  });
  const status = job?.status || progress.status || "unknown";
  const counterLabel = computeCounterLabel({
    current,
    total,
    details,
    stage: progress.stage,
    status,
  });
  return (
    <div className="rounded-lg border border-slate-800 bg-[#10141d] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-white">{progress.label || job?.status_reason || job?.type || "No active step"}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{progress.stage || job?.type || "job"}</p>
        </div>
        <div className="flex gap-2">
          <Badge tone={toneFor(status)}>{status}</Badge>
          <Badge tone="blue">{counterLabel}</Badge>
        </div>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-black/50">
        <div className="h-full rounded-full bg-sky-400 transition-all" style={{ width: `${percent || (String(status).includes("running") ? 8 : 0)}%` }} />
      </div>
    </div>
  );
}
