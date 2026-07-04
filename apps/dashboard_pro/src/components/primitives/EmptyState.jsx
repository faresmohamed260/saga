export function EmptyState({ title = "Nothing here yet", children }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.03] p-6 text-sm text-slate-400">
      <p className="font-bold text-slate-200">{title}</p>
      {children ? <div className="mt-2 leading-6">{children}</div> : null}
    </div>
  );
}
