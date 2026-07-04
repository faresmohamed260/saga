export function FailureSummary({ summary }) {
  return (
    <div className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100">
      <p className="font-black text-amber-50">Failure summary</p>
      <p className="mt-2">{summary.reason}</p>
      {summary.exception && summary.exception !== summary.reason ? <p className="mt-2 text-amber-200/80">{summary.exception}</p> : null}
      <p className="mt-2 text-xs uppercase tracking-[0.18em] text-amber-200/70">{summary.traceback}</p>
    </div>
  );
}
