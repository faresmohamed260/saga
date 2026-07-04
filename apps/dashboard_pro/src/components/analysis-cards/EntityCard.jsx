import { Badge, DataCard, Field, Toolbar, text } from "../primitives";
import { CompactList } from "./CompactList";

export function EntityCard({ row, visual }) {
  const name = row.name || row.entity_name || "Unnamed entity";
  const baselineFields = row.initial_physical_description?.baseline_visual_fields || {};
  const persistentTraits = row.first_appearance_profile?.persistent_traits || row.persistent_traits || {};
  const typedAttributes = row.typed_attributes || {};
  const latestWorldState = row.latest_world_state || {};
  const qualityFlags = row.analysis_quality_flags || [];
  const description = row.initial_physical_description?.description || row.initial_physical_description;
  const firstAppearance = row.first_appearance_profile?.baseline_description || row.first_appearance_profile;

  return (
    <DataCard>
      <Toolbar>
        <Badge tone="blue">{row.entity_type || "entity"}</Badge>
        <Badge>{row.mention_count || 0} mentions</Badge>
        <Badge>first: c{row.first_seen?.chapter_index || "?"} s{row.first_seen?.scene_index || "?"}</Badge>
        {row.render_status ? <Badge tone={row.render_status === "rendered" ? "green" : "amber"}>{row.render_status}</Badge> : null}
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{name}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-300">{text(row.entity_context || row.baseline_source_evidence)}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Field label="Initial physical description">{text(description)}</Field>
        <Field label="First appearance">{text(firstAppearance)}</Field>
        <Field label="Baseline visual fields">{text(baselineFields)}</Field>
        <Field label="Persistent traits">{text(persistentTraits)}</Field>
        <Field label="Typed attributes">{text(typedAttributes)}</Field>
        <Field label="Latest state">{text(latestWorldState)}</Field>
      </div>
      {qualityFlags.length ? <Toolbar className="mt-3">{qualityFlags.map((flag, index) => <Badge key={`${index}-${text(flag)}`} tone="amber">{text(flag)}</Badge>)}</Toolbar> : null}
      <CompactList title="Visual change log" rows={row.visual_change_log} />
      {visual ? (
        <div className="mt-4 space-y-3">
          <Field label="Prompt">{text(row.baseline_prompt || row.baseline_visual_prompt)}</Field>
          <Field label="Negative prompt">{text(row.negative_prompt)}</Field>
          {row.generated_image_path ? <img src={`/runtime/file?path=${encodeURIComponent(row.generated_image_path)}`} alt={name} className="max-h-[520px] rounded-lg border border-white/10 object-contain" /> : <Field label="Image">No image version recorded.</Field>}
        </div>
      ) : null}
    </DataCard>
  );
}
