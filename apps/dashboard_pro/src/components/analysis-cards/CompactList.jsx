import { text } from "../primitives";

export function CompactList({ title, rows }) {
  const visible = (rows || []).slice(0, 5);
  if (!visible.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-4">
      <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <div className="space-y-2">
        {visible.map((row, index) => (
          <div key={index} className="rounded-lg bg-black/25 p-3 text-sm leading-6 text-slate-200">{text(row)}</div>
        ))}
      </div>
      {rows.length > visible.length ? <p className="mt-3 text-xs text-slate-500">Showing {visible.length} of {rows.length} entries.</p> : null}
    </div>
  );
}
