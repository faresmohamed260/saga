import { Badge, toneFor } from "../ui/primitives";

export function Progress({ job }) {
  const progress = job?.progress || {};
  const current = Number(progress.current || 0);
  const total = Number(progress.total || 0);
  const percent = total ? Math.max(0, Math.min(100, Math.round((current / total) * 100))) : 0;
  const status = job?.status || progress.status || "unknown";
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#10141d] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-white">{progress.label || job?.status_reason || job?.type || "No active step"}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{progress.stage || job?.type || "job"}</p>
        </div>
        <div className="flex gap-2">
          <Badge tone={toneFor(status)}>{status}</Badge>
          <Badge tone="blue">{total ? `${current}/${total}` : "indeterminate"}</Badge>
        </div>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-black/50">
        <div className="h-full rounded-full bg-sky-400 transition-all" style={{ width: `${percent || (String(status).includes("running") ? 8 : 0)}%` }} />
      </div>
    </div>
  );
}

export function LogViewer({ lines = [] }) {
  if (!lines.length) return <div className="rounded-2xl border border-dashed border-slate-800 bg-black/40 p-4 text-sm text-slate-400">No logs yet.</div>;
  return (
    <div className="max-h-[520px] overflow-auto rounded-2xl border border-slate-800 bg-black p-3 font-mono text-xs">
      {lines.map((line, index) => {
        const raw = typeof line === "string" ? line : line?.line_text || JSON.stringify(line);
        const isError = /error|failed|traceback|exception/i.test(raw);
        const isWarn = /warn|retry|blocked|cancel/i.test(raw);
        return <div key={`${index}-${raw.slice(0, 16)}`} className={`border-b border-slate-900 py-1.5 ${isError ? "text-red-300" : isWarn ? "text-amber-200" : "text-slate-300"}`}>{raw}</div>;
      })}
    </div>
  );
}
