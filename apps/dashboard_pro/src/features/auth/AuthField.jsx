export function AuthField({ label, error = "", className = "", ...props }) {
  const describedBy = error ? `${props.id}-error` : undefined;
  return (
    <label className={`block ${className}`}>
      <span className="text-[13px] font-bold text-slate-200">{label}</span>
      <input
        {...props}
        aria-describedby={describedBy}
        aria-invalid={Boolean(error)}
        className="mt-2 h-11 w-full appearance-none rounded-lg border border-white/10 bg-slate-950/[0.78] px-3.5 text-sm text-slate-100 shadow-inner shadow-black/15 outline-none transition placeholder:text-slate-600 hover:border-white/20 focus:border-cyan-300/55 focus:bg-slate-950/[0.9] focus:ring-2 focus:ring-cyan-300/12"
      />
      {error ? <span id={describedBy} className="mt-2 block text-xs font-bold text-rose-200">{error}</span> : null}
    </label>
  );
}
