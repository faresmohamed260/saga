export function Field({ label, children }) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <div className="text-sm leading-6 text-slate-100">{children}</div>
    </div>
  );
}
