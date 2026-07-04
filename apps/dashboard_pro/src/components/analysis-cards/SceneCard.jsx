import { Badge, DataCard, Field, Toolbar, text } from "../primitives";

export function SceneCard({ row, world }) {
  return (
    <DataCard>
      <Toolbar>
        <Badge>chapter {row.chapter_index}</Badge>
        <Badge>scene {row.scene_index}</Badge>
        <Badge>{row.final_status || "stored"}</Badge>
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{row.title || row.scene_summary || "Untitled scene"}</h3>
      <p className="mt-2 text-sm text-slate-300">{row.scene_summary || row.summary}</p>
      {world ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Field label="Location">{text(row.location)}</Field>
          <Field label="Visual analysis">{text(row.visual_analysis)}</Field>
          <Field label="Entity world state">{text(row.entity_world_state)}</Field>
          <Field label="State changes">{text(row.state_changes)}</Field>
          <Field label="Relationship changes">{text(row.relationship_changes)}</Field>
        </div>
      ) : (
        <div className="mt-4 whitespace-pre-wrap rounded-lg border border-white/5 bg-black/25 p-4 text-sm leading-7 text-slate-100">{row.text || "No scene text stored."}</div>
      )}
    </DataCard>
  );
}
