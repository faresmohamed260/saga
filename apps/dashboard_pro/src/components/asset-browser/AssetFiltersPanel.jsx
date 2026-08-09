import { Button, Panel, SearchBox } from "../primitives";
import { ENTITY_FILTERS } from "./constants";

export function AssetFiltersPanel({ selectedSeriesId, entityType, onEntityTypeChange, query, onQueryChange }) {
  return (
    <Panel
      title={selectedSeriesId ? `Assets for ${selectedSeriesId}` : "Asset inventory"}
      subtitle="The grid loads paged thumbnails only. Full prompts and original images open on demand."
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {ENTITY_FILTERS.map((item) => (
          <Button
            key={item}
            onClick={() => onEntityTypeChange(item)}
            variant={entityType === item ? "primary" : "secondary"}
          >
            {item}
          </Button>
        ))}
      </div>
      <SearchBox value={query} onChange={onQueryChange} placeholder="Search entity name..." />
    </Panel>
  );
}
