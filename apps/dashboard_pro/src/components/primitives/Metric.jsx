import { Badge } from "./Badge";
import { Surface } from "./Surface";
import { cx, formatNumber } from "./helpers";

export function Metric({ label, value, detail = "live", tone = "slate" }) {
  return (
    <Surface className="relative overflow-hidden p-4">
      <div className={cx("absolute inset-x-0 top-0 h-1", tone === "green" ? "bg-emerald-300/70" : tone === "blue" ? "bg-cyan-300/70" : tone === "amber" ? "bg-amber-300/70" : tone === "red" ? "bg-rose-300/70" : "bg-white/15")} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
        <Badge tone={tone}>{detail}</Badge>
      </div>
      <p className="mt-3 text-3xl font-black text-white tabular-nums">{formatNumber(value)}</p>
    </Surface>
  );
}
