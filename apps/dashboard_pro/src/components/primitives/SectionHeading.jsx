export function SectionHeading({ title, subtitle, className = "" }) {
  return (
    <div className={className}>
      <h2 className="text-lg font-black text-white">{title}</h2>
      {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p> : null}
    </div>
  );
}
