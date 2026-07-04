import { Badge } from "../primitives";

export function SeriesCard({ item, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "rounded-lg border p-4 text-left transition",
        selected
          ? "border-cyan-300/60 bg-cyan-300/10 shadow-lg shadow-cyan-950/30"
          : "border-white/10 bg-slate-950/45 hover:border-cyan-300/40 hover:bg-cyan-300/5",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-slate-500">{item.seriesId}</p>
          <h3 className="mt-2 text-xl font-black text-white">{item.seriesTitle}</h3>
        </div>
        <Badge tone={selected ? "blue" : "slate"}>{item.assetCount} assets</Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Badge tone="green">{item.renderedCount} rendered</Badge>
        <Badge>{Math.max(item.assetCount - item.renderedCount, 0)} pending</Badge>
      </div>
    </button>
  );
}
