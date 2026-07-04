import { Badge, DataCard, Field, Toolbar, text } from "../primitives";

export function TimelineCard({ row, index }) {
  return (
    <DataCard>
      <Toolbar>
        <Badge>#{index + 1}</Badge>
        <Badge>chapter {row.chapter_index || "?"}</Badge>
        <Badge>scene {row.scene_index || "?"}</Badge>
        <Badge tone="blue">{row.type || row.event_type || "event"}</Badge>
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{row.summary || row.title || row.description || "Timeline beat"}</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Field label="Characters">{text(row.characters || row.participants)}</Field>
        <Field label="Entities involved">{text(row.entities_involved)}</Field>
        <Field label="Reason">{text(row.reason)}</Field>
        <Field label="Outcome">{text(row.outcome)}</Field>
      </div>
    </DataCard>
  );
}
