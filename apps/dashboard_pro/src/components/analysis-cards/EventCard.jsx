import { Badge, DataCard, Field, Toolbar, text } from "../primitives";

export function EventCard({ row }) {
  return (
    <DataCard>
      <Toolbar>
        <Badge>{row.event_id || "event"}</Badge>
        <Badge tone="blue">{row.type || row.event_type || "type n/a"}</Badge>
        <Badge>c{row.chapter_index || "?"} s{row.scene_index || "?"}</Badge>
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{row.title || row.description || "Untitled event"}</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Field label="Participants">{text(row.participants || row.characters)}</Field>
        <Field label="Entities involved">{text(row.entities_involved)}</Field>
        <Field label="Location">{text(row.location || row.event_location)}</Field>
        <Field label="Reason">{text(row.reason)}</Field>
        <Field label="Outcome">{text(row.outcome)}</Field>
        <Field label="Summary">{text(row.description || row.summary)}</Field>
      </div>
    </DataCard>
  );
}
