import { Link } from "react-router-dom";
import { Badge, DataCard, EmptyState, Field, Panel, Toolbar, formatDisplayValue, text } from "./primitives";

export const ANALYSIS_SECTIONS = [
  ["scenes", "Scenes"],
  ["entities", "Entities"],
  ["events", "Events"],
  ["timeline", "Timeline"],
  ["states", "States"],
  ["world", "World State"],
  ["visuals", "Visuals"],
];

export function AnalysisSectionTabs({ bookRef, section, view }) {
  return (
    <Toolbar className="mb-4">
      {ANALYSIS_SECTIONS.map(([key, label]) => (
        <Link
          key={key}
          to={`/books/${encodeURIComponent(bookRef)}/analysis/${key}`}
          className={`rounded-lg border px-3 py-2 text-sm font-black transition ${section === key ? "border-cyan-300/60 bg-cyan-300/15 text-white" : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-white/20"}`}
        >
          {label} - {countFor(view, key)}
        </Link>
      ))}
    </Toolbar>
  );
}

export function AnalysisRowsPanel({ rows, section }) {
  return (
    <Panel title={`${rows.length} ${section}`} subtitle="Structured analysis results presented as reviewable cards.">
      {rows.length ? (
        <div className="space-y-3">
          {rows.map((row, index) => renderRow(section, row, index))}
        </div>
      ) : (
        <EmptyState title={`No ${section} entries`} />
      )}
    </Panel>
  );
}

export function countFor(view, key) {
  const counts = view?.counts || {};
  if (key === "scenes") return counts.resolved_scene_analyses || 0;
  if (key === "entities") return counts.entity_registry || 0;
  if (key === "events") return counts.event_ledger || 0;
  if (key === "timeline") return counts.timeline || 0;
  if (key === "states") return counts.stable_character_states || 0;
  if (key === "world") return counts.scene_world_state || 0;
  return counts.visual_inventory || 0;
}

export function searchableLabelFor(section, row) {
  if (!row || typeof row !== "object") return "";
  if (section === "entities" || section === "visuals") {
    return row.name || row.entity_name || row.canonical_name || "";
  }
  if (section === "events") {
    return row.title || row.event_title || row.summary || row.description || row.event_id || "";
  }
  if (section === "scenes" || section === "world") {
    return row.title || row.scene_title || row.scene_summary || row.summary || "";
  }
  if (section === "states") {
    return row.character_name || row.name || row.entity_name || "";
  }
  if (section === "timeline") {
    return row.title || row.summary || row.description || row.event || "";
  }
  return JSON.stringify(row);
}

function renderRow(section, row, index) {
  if (section === "entities" || section === "visuals") return <EntityCard key={`${row.name || row.entity_name || index}-${section}`} row={row} visual={section === "visuals"} />;
  if (section === "scenes" || section === "world") return <SceneCard key={`${row.chapter_index}-${row.scene_index}-${index}`} row={row} world={section === "world"} />;
  if (section === "events") return <EventCard key={row.event_id || index} row={row} />;
  if (section === "timeline") return <TimelineCard key={row.event_id || index} row={row} index={index} />;
  if (section === "states") return <StateCard key={row.character_name || row.entity_name || index} row={row} index={index} />;
  return <GenericCard key={index} row={row} index={index} />;
}

function GenericCard({ row, index }) {
  return (
    <DataCard>
      <Badge>#{index + 1}</Badge>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {Object.entries(row || {}).slice(0, 12).map(([key, value]) => <Field key={key} label={key}>{text(value)}</Field>)}
      </div>
    </DataCard>
  );
}

function EntityCard({ row, visual }) {
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

function SceneCard({ row, world }) {
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

function EventCard({ row }) {
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

function TimelineCard({ row, index }) {
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

function StateCard({ row, index }) {
  const name = row.character_name || row.entity_name || row.name || `State ${index + 1}`;
  const attributes = row.attributes || row.state || {};
  const latest = row.latest_state || row.state_at_latest || {};
  const metadata = row.agent_metadata || row.tool_runtime || {};
  const hasPayload = formatDisplayValue(attributes) || formatDisplayValue(latest) || formatDisplayValue(row.evidence);
  return (
    <DataCard>
      <Toolbar>
        <Badge>#{index + 1}</Badge>
        <Badge tone={hasPayload ? "green" : "amber"}>{hasPayload ? "state recorded" : "payload sparse"}</Badge>
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{name}</h3>
      {hasPayload ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Field label="Stable attributes">{text(attributes)}</Field>
          <Field label="Latest state">{text(latest)}</Field>
          <Field label="Evidence">{text(row.evidence || row.notes)}</Field>
          <Field label="Agent metadata">{text(metadata)}</Field>
        </div>
      ) : (
        <EmptyState title="No stable character details recorded">A state entry exists for this character, but usable attributes were not saved yet.</EmptyState>
      )}
    </DataCard>
  );
}

function CompactList({ title, rows }) {
  const visible = (rows || []).slice(0, 5);
  if (!visible.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-4">
      <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <div className="space-y-2">
        {visible.map((row, index) => (
          <div key={index} className="rounded-lg bg-black/25 p-3 text-sm leading-6 text-slate-200">{text(row)}</div>
        ))}
      </div>
      {rows.length > visible.length ? <p className="mt-3 text-xs text-slate-500">Showing {visible.length} of {rows.length} entries.</p> : null}
    </div>
  );
}
