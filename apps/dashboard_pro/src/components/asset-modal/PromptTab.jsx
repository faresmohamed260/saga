export function PromptTab({ active, dirty, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition",
        active ? "border-cyan-400/60 bg-cyan-400/12 text-white" : "border-white/10 bg-slate-950/55 text-slate-300 hover:border-cyan-400/35",
      ].join(" ")}
    >
      <span>{children}</span>
      {dirty ? <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-amber-200">Edited</span> : null}
    </button>
  );
}
