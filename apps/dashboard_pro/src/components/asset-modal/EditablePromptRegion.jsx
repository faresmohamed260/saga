export function EditablePromptRegion({ label, value, onChange, placeholder = "", large = false }) {
  return (
    <div className="rounded-md bg-slate-950/55 px-3 py-2.5">
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={[
          "w-full resize-none overflow-y-auto rounded-md border border-white/10 bg-slate-900/85 px-3 py-2.5 text-[12.5px] leading-[1.55] text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400/55 focus:ring-1 focus:ring-cyan-400/35",
          large ? "h-64" : "h-36",
        ].join(" ")}
      />
    </div>
  );
}
