import { EmptyState, Panel } from "../primitives";
import { SeriesCard } from "./SeriesCard";

export function AssetSeriesPanel({ seriesCards, selectedSeriesId, onSelectSeries }) {
  return (
    <Panel
      title="Visual Asset Browser"
      subtitle="Browse by series first, then load lightweight thumbnail pages instead of the full asset library at once."
    >
      {seriesCards.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {seriesCards.map((item) => (
            <SeriesCard key={item.seriesId} item={item} selected={item.seriesId === selectedSeriesId} onSelect={() => onSelectSeries(item.seriesId)} />
          ))}
        </div>
      ) : (
        <EmptyState title="No series with visual assets found">Run visual generation first, then the browser will group assets by series.</EmptyState>
      )}
    </Panel>
  );
}
