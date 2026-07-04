export function LogViewer({ lines = [] }) {
  if (!lines.length) return <div className="rounded-lg border border-dashed border-slate-800 bg-black/40 p-4 text-sm text-slate-400">No logs yet.</div>;
  return (
    <div className="max-h-[520px] overflow-auto rounded-lg border border-slate-800 bg-black p-3 font-mono text-xs">
      {lines.map((line, index) => {
        const raw = typeof line === "string" ? line : line?.line_text || JSON.stringify(line);
        const isError = /error|failed|traceback|exception/i.test(raw);
        const isWarn = /warn|retry|blocked|cancel/i.test(raw);
        return <div key={`${index}-${raw.slice(0, 16)}`} className={`border-b border-slate-900 py-1.5 ${isError ? "text-red-300" : isWarn ? "text-amber-200" : "text-slate-300"}`}>{raw}</div>;
      })}
    </div>
  );
}
