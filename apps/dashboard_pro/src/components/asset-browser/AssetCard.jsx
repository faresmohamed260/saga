import { Badge, EmptyState, toneFor } from "../primitives";
import { assetImageUrl } from "./assetImageUrl";
import { STANDARD_ASSET_RATIO_CLASS } from "./constants";

export function AssetCard({ entity, selected, onToggleSelect, onOpen }) {
  const thumbnailRef = entity.generated_thumbnail || entity.generated_thumbnail_artifact
    || entity.generated_image || entity.generated_image_artifact;
  const hasImage = !!assetImageUrl(thumbnailRef);

  return (
    <div
      className={[
        "overflow-hidden rounded-lg border bg-slate-950/55 text-left shadow-lg shadow-black/10 transition",
        selected
          ? "border-emerald-300/55 shadow-emerald-950/20"
          : "border-white/10 hover:border-cyan-300/50 hover:bg-cyan-300/5",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <label className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-emerald-400 focus:ring-emerald-400"
          />
          Select
        </label>
        <Badge tone={selected ? "green" : toneFor(entity.render_status)}>{selected ? "selected" : (entity.render_status || "not rendered")}</Badge>
      </div>

      <button type="button" onClick={onOpen} className="block w-full text-left">
        <div className={`${STANDARD_ASSET_RATIO_CLASS} border-b border-white/10 bg-black/40`}>
          {hasImage ? (
            <img
              src={assetImageUrl(thumbnailRef)}
              alt={entity.name}
              loading="lazy"
              decoding="async"
              className="h-full w-full bg-[#050816] object-contain"
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6">
              <EmptyState title="No image">Render pending</EmptyState>
            </div>
          )}
        </div>

        <div className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-black text-white">{entity.name}</h3>
              <p className="mt-1 text-sm text-slate-400">{entity.book_title || entity.series_title || entity.series_id || entity.book_id}</p>
            </div>
            <Badge tone={toneFor(entity.render_status)}>{entity.render_status || "not rendered"}</Badge>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone="blue">{entity.entity_type}</Badge>
            <Badge>{entity.prompt_count || 0} prompts</Badge>
            <Badge tone={entity.image_count ? "green" : "amber"}>{entity.image_count || 0} images</Badge>
          </div>
        </div>
      </button>
    </div>
  );
}
