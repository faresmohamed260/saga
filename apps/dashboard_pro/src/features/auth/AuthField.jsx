export function AuthField({ label, error = "", className = "", ...props }) {
  const describedBy = error ? `${props.id}-error` : undefined;
  return (
    <label className={`block ${className}`}>
      <span className="text-sm font-bold text-slate-200">{label}</span>
      <input
        {...props}
        aria-describedby={describedBy}
        aria-invalid={Boolean(error)}
        className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/72 px-4 py-3.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 hover:border-white/18 focus:border-cyan-300/55 focus:bg-slate-950/88 focus:ring-2 focus:ring-cyan-300/12"
      />
      {error ? <span id={describedBy} className="mt-2 block text-xs font-bold text-rose-200">{error}</span> : null}
    </label>
  );
}
