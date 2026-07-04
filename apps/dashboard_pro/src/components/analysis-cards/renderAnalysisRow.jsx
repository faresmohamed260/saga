import { EntityCard } from "./EntityCard";
import { EventCard } from "./EventCard";
import { GenericCard } from "./GenericCard";
import { SceneCard } from "./SceneCard";
import { StateCard } from "./StateCard";
import { TimelineCard } from "./TimelineCard";

export function renderAnalysisRow(section, row, index) {
  if (section === "entities" || section === "visuals") return <EntityCard key={`${row.name || row.entity_name || index}-${section}`} row={row} visual={section === "visuals"} />;
  if (section === "scenes" || section === "world") return <SceneCard key={`${row.chapter_index}-${row.scene_index}-${index}`} row={row} world={section === "world"} />;
  if (section === "events") return <EventCard key={row.event_id || index} row={row} />;
  if (section === "timeline") return <TimelineCard key={row.event_id || index} row={row} index={index} />;
  if (section === "states") return <StateCard key={row.character_name || row.entity_name || index} row={row} index={index} />;
  return <GenericCard key={index} row={row} index={index} />;
}
