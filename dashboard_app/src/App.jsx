import React, { useEffect, useMemo, useState } from "react";

const TABS = [
  "Overview",
  "Encode Runs",
  "New Encode Run",
  "Contract Viewer",
  "Visual World State",
  "Prompt Inspector",
  "Providers",
  "Reports",
];

const DEFAULT_FORM = {
  books: [],
  series_id: "acotar-full-booknlp-clean-live",
  series_title: "ACOTAR Full BookNLP Clean Live",
  book_index_base: 1,
  analysis_model: "gpt_oss",
  identity_model: "gpt_oss",
  analysis_provider_mode: "same_provider_rotating",
  identity_provider: "booknlp_clean",
  identity_strategy: "scene_inline",
  series_identity_json: "analysis_outputs\\identity_series\\acotar\\acotar_series_pipeline_identity.json",
  scene_failure_policy: "fail_fast",
  max_failed_scenes_absolute: 3,
  max_failed_scene_ratio: 0.1,
  min_nonempty_scene_ratio: 0.8,
  max_parallel_books: 1,
  max_chapters: 0,
  skip_ingest: false,
  no_progress: false,
  out: "analysis_outputs\\encoder_validation\\acotar_full_booknlp_clean_live.json",
};

async function runtimeJson(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.detail || response.statusText || "Runtime request failed");
  }
  return payload;
}

function Badge({ children, tone = "slate" }) {
  const tones = {
    slate: "border-slate-700 bg-slate-900 text-slate-300",
    blue: "border-sky-500/50 bg-sky-500/10 text-sky-200",
    green: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-500/50 bg-amber-500/10 text-amber-200",
    red: "border-red-500/50 bg-red-500/10 text-red-200",
  };
  return <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

function Panel({ title, subtitle, children, action }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-[#101216] p-4 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm leading-6 text-slate-400">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value, chip }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
        {chip}
      </div>
      <p className="mt-3 text-2xl font-black text-white">{value}</p>
    </div>
  );
}

function Input({ label, value, onChange, type = "text", className = "", ...props }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(type === "number" ? Number(event.target.value) : event.target.value)}
        className="w-full rounded-md border border-slate-800 bg-[#0b0c10] px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
        {...props}
      />
    </label>
  );
}

function Select({ label, value, onChange, options, className = "" }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-800 bg-[#0b0c10] px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Empty({ children }) {
  return <div className="rounded-lg border border-dashed border-slate-800 bg-[#0b0c10] p-4 text-sm text-slate-400">{children}</div>;
}

function LogTail({ lines }) {
  if (!lines?.length) return <Empty>No log output yet.</Empty>;
  return (
    <pre className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-black p-4 text-xs leading-5 text-emerald-100">
      {lines.join("\n")}
    </pre>
  );
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "completed" || value === "success") return "green";
  if (value === "failed" || value === "partial") return "red";
  if (value === "running" || value === "queued") return "blue";
  return "slate";
}

function contractRows(contract) {
  return [
    ["Run status", contract.run_status],
    ["Scenes", contract.scenes],
    ["Successful scenes", contract.successful_scenes ?? "n/a"],
    ["Failed scenes", contract.failed_scenes ?? "n/a"],
    ["Entity registry", contract.entity_registry],
    ["Timeline", contract.timeline],
    ["Event ledger", contract.event_ledger],
    ["Character profiles", contract.character_profiles],
    ["Stable character states", contract.stable_character_states],
    ["Story index docs", contract.story_index_docs],
    ["Identity provider", contract.identity_provider],
  ];
}

function StructuredContract({ payload }) {
  const outputs = payload?.outputs || {};
  const counts = payload?.counts || {};
  const visualRows = collectVisualPromptRows(outputs);
  const sections = [
    ["Scenes", outputs.resolved_scene_analyses || outputs.scene_analyses || [], (row) => row.scene_summary || row.summary || "Untitled scene"],
    ["Events", outputs.event_ledger || [], (row) => row.event || row.description || row.summary || "Event"],
    ["Entities", outputs.entity_registry || [], (row) => row.name || row.canonical_name || row.id || "Entity"],
    ["Timeline", outputs.timeline || [], (row) => row.event || row.description || row.summary || "Timeline item"],
    ["Profiles", outputs.character_profiles || [], (row) => row.name || row.display_name || row.character_id || "Character"],
    ["Relationships", outputs.relationship_profiles || [], (row) => `${row.source_character || "?"} ↔ ${row.target_character || "?"}`],
    ["States", outputs.stable_character_states || [], (row) => row.name || row.display_name || row.character_id || "State"],
    ["World State", outputs.scene_world_state || [], (row) => row.scene_summary || row.scene_id || "Scene world state"],
    ["Visuals", visualRows, (row) => row.entity_name || row.beat_title || row.prompt_type || "Visual prompt"],
  ];
  const [section, setSection] = useState(sections[0][0]);
  const active = sections.find((row) => row[0] === section) || sections[0];
  const rows = active[1].slice(0, 80);
  const sectionCounts = {
    Scenes: counts.resolved_scene_analyses,
    Events: counts.event_ledger,
    Entities: counts.entity_registry,
    Timeline: counts.timeline,
    Profiles: counts.character_profiles,
    Relationships: counts.relationship_profiles,
    States: counts.stable_character_states,
    "World State": counts.scene_world_state,
    Visuals: visualRows.length,
  };
  const content = section === "Entities"
    ? <EntityRegistryView rows={active[1]} totalCount={counts.entity_registry ?? active[1].length} />
    : section === "Profiles"
      ? <ProfilesView rows={active[1]} totalCount={counts.character_profiles ?? active[1].length} />
      : section === "Scenes"
        ? <ScenesView rows={active[1]} totalCount={counts.resolved_scene_analyses ?? active[1].length} />
        : section === "Events"
          ? <EventsView rows={active[1]} totalCount={counts.event_ledger ?? active[1].length} />
          : section === "Relationships"
            ? <RelationshipsView rows={active[1]} totalCount={counts.relationship_profiles ?? active[1].length} />
            : section === "World State"
              ? <SceneWorldStateView rows={active[1]} totalCount={counts.scene_world_state ?? active[1].length} />
            : section === "Visuals"
              ? <VisualPromptSetsView rows={active[1]} diagnostics={outputs.visual_prompt_diagnostics} />
              : null;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {sections.map(([name, values]) => (
          <button
            key={name}
            onClick={() => setSection(name)}
            className={`rounded-md border px-3 py-2 text-xs font-semibold ${
              section === name ? "border-sky-500 bg-sky-500/15 text-sky-100" : "border-slate-800 bg-[#0b0c10] text-slate-300"
            }`}
          >
            {name} · {sectionCounts[name] ?? values.length}
          </button>
        ))}
      </div>
      {content || (!rows.length ? (
        <Empty>No {section.toLowerCase()} found in this contract.</Empty>
      ) : (
        <div className="grid gap-3">
          {rows.map((row, index) => (
            <article key={`${section}-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{row.id || row.event_id || row.scene_id || `#${index + 1}`}</Badge>
                {row.chapter_index ? <Badge tone="blue">chapter {row.chapter_index}</Badge> : null}
                {row.scene_index ? <Badge tone="blue">scene {row.scene_index}</Badge> : null}
              </div>
              <h3 className="mt-3 font-bold text-slate-100">{active[2](row)}</h3>
              <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-300">
                {row.description || row.summary || row.state || row.evidence || row.notes || row.relationship_type || ""}
              </p>
            </article>
          ))}
        </div>
      ))}
    </div>
  );
}

function collectVisualPromptRows(outputs) {
  const sets = outputs?.visual_prompt_sets || {};
  const rows = [];
  const labels = {
    initial_characters: "Initial character",
    character_changes: "Character change",
    objects_creatures: "Object / creature",
    locations: "Location",
    scene_compositions: "Scene composition",
  };
  Object.entries(labels).forEach(([key, label]) => {
    (sets[key] || []).forEach((row) => rows.push({ ...row, visual_bucket: key, visual_bucket_label: label }));
  });
  if (rows.length) return rows;
  const scenes = outputs?.resolved_scene_analyses || outputs?.scene_analyses || [];
  scenes.forEach((scene) => {
    const visual = scene.visual_analysis || {};
    (visual.scene_compositions || []).forEach((row) => rows.push({
      ...row,
      visual_bucket: "scene_compositions",
      visual_bucket_label: "Scene composition",
      positive_prompt: row.scene_prompt,
      book_index: scene.book_index,
      chapter_index: scene.chapter_index,
      scene_index: scene.scene_index,
    }));
  });
  return rows;
}

function VisualPromptSetsView({ rows, diagnostics }) {
  const groups = useMemo(() => {
    const next = {};
    rows.forEach((row) => {
      const label = row.visual_bucket_label || row.prompt_type || "Visual prompt";
      next[label] = next[label] || [];
      next[label].push(row);
    });
    return next;
  }, [rows]);
  const groupNames = Object.keys(groups);
  const [activeGroup, setActiveGroup] = useState(groupNames[0] || "Initial character");
  const activeRows = groups[activeGroup] || [];
  if (!rows.length) return <Empty>No native visual prompt sets found in this contract.</Empty>;
  return (
    <div>
      <div className="mb-4 rounded-lg border border-slate-800 bg-[#15171c] p-4 text-sm leading-6 text-slate-300">
        <p><strong className="text-slate-100">Visuals</strong> are contract-native outputs from the visual state analyzer: first-look character prompts, image-edit changes, object/creature prompts, location prompts, and scene composition prompts.</p>
        <p className="mt-2">These are extracted during analysis with scene provenance, instead of being guessed later from registry summaries.</p>
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {groupNames.map((name) => (
          <button
            key={name}
            onClick={() => setActiveGroup(name)}
            className={`rounded-md border px-3 py-2 text-xs font-semibold ${
              activeGroup === name ? "border-sky-500 bg-sky-500/15 text-sky-100" : "border-slate-800 bg-[#0b0c10] text-slate-300"
            }`}
          >
            {name} آ· {groups[name].length}
          </button>
        ))}
        <Badge>{rows.length} total</Badge>
      </div>
      <div className="grid gap-3">
        {activeRows.slice(0, 120).map((row, index) => (
          <article key={`${activeGroup}-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone="blue">{row.prompt_type || row.visual_bucket_label}</Badge>
              <Badge>{row.confidence || "confidence n/a"}</Badge>
              <Badge>book {row.book_index ?? "?"}, chapter {row.chapter_index ?? "?"}, scene {row.scene_index ?? "?"}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{row.entity_name || row.details?.beat_title || row.prompt_type || "Visual prompt"}</h3>
            {row.positive_prompt ? (
              <div className="mt-3 rounded-md bg-[#0b0c10] p-3 text-sm leading-6 text-slate-200">
                <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Positive prompt</p>
                <p>{row.positive_prompt}</p>
              </div>
            ) : null}
            {row.image_edit_prompt ? (
              <div className="mt-3 rounded-md bg-[#0b0c10] p-3 text-sm leading-6 text-slate-200">
                <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Image edit prompt</p>
                <p>{row.image_edit_prompt}</p>
              </div>
            ) : null}
            {row.source_evidence ? <p className="mt-3 text-sm leading-6 text-slate-400">Evidence: {row.source_evidence}</p> : null}
          </article>
        ))}
      </div>
      {diagnostics?.missing_visual_evidence?.length ? (
        <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          Missing visual evidence flagged: {diagnostics.missing_visual_evidence.slice(0, 20).join(", ")}
        </div>
      ) : null}
    </div>
  );
}

function ScenesView({ rows, totalCount }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2"><Badge>{totalCount} scenes</Badge><Badge tone="blue">full scene text included when stored in contract</Badge></div>
      <div className="grid gap-3">
        {rows.slice(0, 80).map((scene, index) => (
          <article key={`scene-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>#{index + 1}</Badge>
              <Badge tone="blue">chapter {scene.chapter_index ?? "?"}</Badge>
              <Badge tone="blue">scene {scene.scene_index ?? "?"}</Badge>
              {scene.final_status ? <Badge tone={scene.final_status === "success" ? "green" : "amber"}>{scene.final_status}</Badge> : null}
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{scene.scene_summary || "Untitled scene"}</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Mini label="Entities" value={(scene.entities_present || []).length} />
              <Mini label="State changes" value={(scene.state_changes || []).length} />
              <Mini label="Relationship changes" value={(scene.relationship_changes || []).length} />
            </div>
            <p className="mt-3 whitespace-pre-wrap rounded-md bg-[#0b0c10] p-4 text-sm leading-7 text-slate-300">{scene.text || "Full scene text was not present in this contract."}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

function EventsView({ rows, totalCount }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2"><Badge>{totalCount} events</Badge></div>
      <div className="grid gap-3">
        {rows.slice(0, 120).map((event, index) => (
          <article key={`event-${event.ledger_event_id || index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{event.ledger_event_id || event.event_id || `#${index + 1}`}</Badge>
              <Badge tone="blue">chapter {event.chapter_index ?? "?"}</Badge>
              <Badge tone="blue">scene {event.scene_index ?? "?"}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{event.title || event.summary || "Untitled event"}</h3>
            {event.summary ? <p className="mt-2 text-sm leading-6 text-slate-300">{event.summary}</p> : null}
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Mini label="Participants" value={(event.participants || event.characters || []).join(", ") || "n/a"} />
              <Mini label="Entities involved" value={(event.entities_involved || []).join(", ") || "n/a"} />
              <Mini label="Location" value={typeof event.location === "string" ? event.location : event.location?.name || "n/a"} />
              <Mini label="Type" value={event.type || "n/a"} />
              <Mini label="Reason" value={event.reason || "n/a"} />
              <Mini label="Outcome" value={event.outcome || "n/a"} />
            </div>
            <EvidenceList title="Consequences" rows={event.direct_consequences} render={(row) => <span>{String(row)}</span>} />
            <EvidenceList title="Preconditions" rows={event.preconditions} render={(row) => <span>{String(row)}</span>} />
          </article>
        ))}
      </div>
    </div>
  );
}

function RelationshipsView({ rows, totalCount }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2"><Badge>{totalCount} relationships</Badge></div>
      <div className="grid gap-3">
        {rows.slice(0, 120).map((relationship, index) => (
          <article key={relationship.relationship_id || index} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{relationship.relationship_type || "relationship"}</Badge>
              <Badge tone="blue">trust {relationship.trust_level || "unknown"}</Badge>
              <Badge tone="blue">conflict {relationship.conflict_level || "unknown"}</Badge>
              <Badge tone="blue">romance {relationship.romantic_signal || "unknown"}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{relationship.source_character || "?"} ↔ {relationship.target_character || "?"}</h3>
            {relationship.baseline_dynamic ? <p className="mt-2 text-sm leading-6 text-slate-300">{relationship.baseline_dynamic}</p> : null}
            <EvidenceList title="Change log" rows={relationship.change_log} render={(row) => <span>{row.change || row.evidence || JSON.stringify(row)}</span>} />
            <EvidenceList title="Shared history" rows={relationship.shared_history} render={(row) => <span>{String(row)}</span>} />
          </article>
        ))}
      </div>
    </div>
  );
}

function classifyEntityType(entity) {
  const raw = String(entity.entity_type || entity.type || "").toLowerCase();
  if (raw.includes("character") || raw.includes("person")) return "Characters";
  if (raw.includes("location") || raw.includes("place") || raw.includes("setting")) return "Locations";
  if (raw.includes("object") || raw.includes("artifact") || raw.includes("weapon") || raw.includes("item")) return "Objects";
  if (raw.includes("creature") || raw.includes("monster") || raw.includes("animal")) return "Creatures";
  return "Other";
}

function formatProvenance(value) {
  if (!value || typeof value !== "object") return "n/a";
  const book = value.book_index ?? "?";
  const chapter = value.chapter_index ?? "?";
  const scene = value.scene_index ?? "?";
  return `book ${book}, chapter ${chapter}, scene ${scene}`;
}

function EvidenceList({ title, rows, render }) {
  const values = Array.isArray(rows) ? rows.filter(Boolean).slice(0, 4) : [];
  if (!values.length) return null;
  return (
    <div className="mt-3">
      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</p>
      <div className="space-y-2">
        {values.map((row, index) => (
          <div key={index} className="rounded-md bg-[#0b0c10] p-3 text-sm leading-6 text-slate-300">
            {render(row)}
          </div>
        ))}
      </div>
    </div>
  );
}

function EntityRegistryView({ rows, totalCount }) {
  const groups = useMemo(() => {
    const next = { Characters: [], Locations: [], Objects: [], Creatures: [], Other: [] };
    rows.forEach((row) => next[classifyEntityType(row)].push(row));
    for (const key of Object.keys(next)) {
      next[key].sort((a, b) => Number(b.mention_count || 0) - Number(a.mention_count || 0) || String(a.name || "").localeCompare(String(b.name || "")));
    }
    return next;
  }, [rows]);
  const visibleTabs = Object.keys(groups).filter((key) => groups[key].length);
  const [activeGroup, setActiveGroup] = useState(visibleTabs[0] || "Characters");
  const activeRows = groups[activeGroup] || [];
  return (
    <div>
      <div className="mb-4 rounded-lg border border-slate-800 bg-[#15171c] p-4 text-sm leading-6 text-slate-300">
        <p><strong className="text-slate-100">Entities</strong> are the broad registry of things the encoder tracked: characters, places, objects/artifacts, creatures, and other named world items.</p>
        <p className="mt-2"><strong className="text-slate-100">Profiles</strong> are character-only synthesized memory: aliases, core description, traits, and important history. So a character can appear in both tabs, but locations/objects only belong in Entities.</p>
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {visibleTabs.map((group) => (
          <button
            key={group}
            onClick={() => setActiveGroup(group)}
            className={`rounded-md border px-3 py-2 text-xs font-semibold ${
              activeGroup === group ? "border-sky-500 bg-sky-500/15 text-sky-100" : "border-slate-800 bg-[#0b0c10] text-slate-300"
            }`}
          >
            {group} · {groups[group].length}
          </button>
        ))}
        <Badge>{totalCount} total</Badge>
      </div>
      <div className="grid gap-3">
        {activeRows.slice(0, 120).map((entity, index) => (
          <article key={`${activeGroup}-${entity.name}-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="blue">{entity.entity_type || activeGroup.slice(0, -1).toLowerCase()}</Badge>
              <Badge>{entity.mention_count ?? 0} mentions</Badge>
              <Badge>first seen: {formatProvenance(entity.first_seen)}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{entity.name || entity.canonical_name || entity.id || "Unnamed entity"}</h3>
            {entity.entity_context ? <p className="mt-2 text-sm leading-6 text-slate-300">{entity.entity_context}</p> : null}
            {entity.initial_physical_description ? (
              <div className="mt-3 rounded-md border border-sky-500/30 bg-sky-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-sky-200">Initial physical description · {entity.initial_physical_description.status}</p>
                <p className="mt-1">{entity.initial_physical_description.description || entity.initial_physical_description.reason || "Not captured."}</p>
              </div>
            ) : null}
            {entity.first_appearance_profile ? (
              <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-emerald-200">First appearance profile · {entity.first_appearance_profile.status || "n/a"}</p>
                <p className="mt-1">{entity.first_appearance_profile.baseline_description || "No first-appearance baseline recorded."}</p>
                <TypedAttributeGrid attributes={entity.first_appearance_profile.typed_attributes} />
              </div>
            ) : null}
            <TypedAttributeGrid attributes={entity.typed_attributes} />
            {entity.latest_world_state && Object.keys(entity.latest_world_state).length ? (
              <div className="mt-3 rounded-md border border-violet-500/30 bg-violet-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-violet-200">Latest world state</p>
                {entity.latest_world_state.baseline_description ? <p className="mt-1">{entity.latest_world_state.baseline_description}</p> : null}
                <TypedAttributeGrid attributes={entity.latest_world_state.typed_attributes} />
                {entity.latest_world_state.source_evidence?.length ? <p className="mt-2 text-xs text-violet-100">Evidence: {entity.latest_world_state.source_evidence.join(" | ")}</p> : null}
              </div>
            ) : null}
            {(entity.analysis_quality_flags || []).length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {entity.analysis_quality_flags.map((flag) => <Badge key={flag} tone="amber">{flag}</Badge>)}
              </div>
            ) : null}
            <EvidenceList
              title="Descriptions"
              rows={entity.descriptions}
              render={(row) => (
                <>
                  <span>{row.description || row.summary || String(row)}</span>
                  {row.description_type ? <span className="ml-2 text-xs text-slate-500">({row.description_type}, {formatProvenance(row)})</span> : null}
                </>
              )}
            />
            <EvidenceList
              title="State changes"
              rows={entity.state_changes}
              render={(row) => (
                <>
                  <span>{row.attribute || "state"}: {row.previous_state || "?"} → {row.new_state || "?"}</span>
                  {row.evidence ? <span className="block text-slate-400">{row.evidence}</span> : null}
                  <span className="text-xs text-slate-500">{formatProvenance(row)}</span>
                </>
              )}
            />
            <EvidenceList title="Event links" rows={entity.event_links} render={(row) => <span>{row.description || row.outcome || row.reason || JSON.stringify(row)}</span>} />
            <EvidenceList title="Visual change log" rows={entity.visual_change_log} render={(row) => <span>{row.description || row.evidence || JSON.stringify(row)}</span>} />
          </article>
        ))}
      </div>
    </div>
  );
}

function ProfilesView({ rows, totalCount }) {
  return (
    <div>
      <div className="mb-4 rounded-lg border border-slate-800 bg-[#15171c] p-4 text-sm leading-6 text-slate-300">
        <p><strong className="text-slate-100">Profiles</strong> are synthesized character memory, not the full entity registry. They are meant for retrieval/generation: who the character is, aliases, traits, and important history.</p>
        <p className="mt-2"><strong className="text-slate-100">Entities</strong> are broader and more mechanical: every tracked character/location/object/creature with provenance, descriptions, mentions, and state changes.</p>
      </div>
      <div className="mb-3 flex flex-wrap gap-2"><Badge>{totalCount} character profiles</Badge></div>
      <div className="grid gap-3">
        {rows.slice(0, 120).map((profile, index) => (
          <article key={`${profile.character_id || profile.canonical_name}-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{profile.character_id || `#${index + 1}`}</Badge>
              {(profile.aliases || []).slice(0, 4).map((alias) => <Badge key={alias} tone="blue">{alias}</Badge>)}
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{profile.canonical_name || profile.display_name || profile.name || "Unnamed character"}</h3>
            {profile.core_description ? <p className="mt-2 text-sm leading-6 text-slate-300">{profile.core_description}</p> : null}
            <EvidenceList title="Traits" rows={profile.traits} render={(row) => <span>{typeof row === "string" ? row : row.description || JSON.stringify(row)}</span>} />
            {profile.visual_profile ? (
              <div className="mt-3 rounded-md border border-sky-500/30 bg-sky-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-sky-200">Visual profile</p>
                {profile.visual_profile.first_appearance?.baseline_description ? <p className="mt-1">{profile.visual_profile.first_appearance.baseline_description}</p> : null}
                <TypedAttributeGrid attributes={{
                  appearance: profile.visual_profile.appearance || [],
                  outfit: profile.visual_profile.outfit || [],
                  condition: profile.visual_profile.condition || [],
                  body_language: profile.visual_profile.body_language || [],
                }} />
              </div>
            ) : null}
            {profile.world_state_profile ? (
              <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-emerald-200">World-state profile</p>
                <TypedAttributeGrid attributes={{
                  possessions: profile.world_state_profile.possessions || [],
                  abilities: profile.world_state_profile.abilities || [],
                  titles_or_roles: profile.world_state_profile.titles_or_roles || [],
                  affiliations: profile.world_state_profile.affiliations || [],
                }} />
              </div>
            ) : null}
            <EvidenceList title="Important history" rows={profile.important_history} render={(row) => <span>{row.summary || row.description || String(row)}</span>} />
            <EvidenceList title="Relationship refs" rows={profile.relationship_refs} render={(row) => <span>{row.source_entity} → {row.target_entity}: {row.relationship || row.change || "relationship"}</span>} />
            <EvidenceList title="State history" rows={profile.state_history} render={(row) => <span>{row.attribute || "state"}: {row.new_state || row.description || JSON.stringify(row)}</span>} />
          </article>
        ))}
      </div>
    </div>
  );
}

function TypedAttributeGrid({ attributes }) {
  const entries = Object.entries(attributes || {}).filter(([, values]) => Array.isArray(values) && values.length);
  if (!entries.length) return null;
  return (
    <div className="mt-3 grid gap-3 md:grid-cols-2">
      {entries.map(([key, values]) => (
        <div key={key} className="rounded-md bg-[#0b0c10] p-3">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">{key.replaceAll("_", " ")}</p>
          <p className="mt-2 text-sm leading-6 text-slate-200">{values.join(", ")}</p>
        </div>
      ))}
    </div>
  );
}

function SceneWorldStateView({ rows, totalCount }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2"><Badge>{totalCount} scene state packets</Badge></div>
      <div className="grid gap-3">
        {rows.slice(0, 80).map((row, index) => {
          const worldEntities = row.entity_world_state?.entities || [];
          const visual = row.visual_analysis || {};
          return (
            <article key={row.scene_id || index} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
              <div className="flex flex-wrap gap-2">
                <Badge>{row.scene_id || `#${index + 1}`}</Badge>
                <Badge tone="blue">chapter {row.chapter_index ?? "?"}</Badge>
                <Badge tone="blue">scene {row.scene_index ?? "?"}</Badge>
                <Badge>{worldEntities.length} typed entities</Badge>
              </div>
              <h3 className="mt-3 text-lg font-black text-slate-100">{row.scene_summary || "Scene world state"}</h3>
              {row.location?.name ? <p className="mt-2 text-sm leading-6 text-slate-300">Location: {row.location.name}{row.location.description ? ` — ${row.location.description}` : ""}</p> : null}
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <Mini label="Characters" value={(visual.characters || []).length} />
                <Mini label="Objects" value={(visual.objects || []).length} />
                <Mini label="Locations" value={(visual.locations || []).length} />
                <Mini label="Visual beats" value={(visual.scene_compositions || []).length} />
              </div>
              <EvidenceList
                title="Typed world-state entities"
                rows={worldEntities}
                render={(entity) => (
                  <div>
                    <p className="font-semibold text-slate-100">{entity.entity_name} <span className="text-slate-500">({entity.entity_type})</span></p>
                    {entity.baseline_description ? <p className="mt-1">{entity.baseline_description}</p> : null}
                    <TypedAttributeGrid attributes={entity.typed_attributes} />
                  </div>
                )}
              />
              <EvidenceList
                title="Scene relationship changes"
                rows={row.relationship_changes}
                render={(change) => <span>{change.source_entity} → {change.target_entity}: {change.relationship || change.change || "relationship"}{change.evidence ? ` — ${change.evidence}` : ""}</span>}
              />
              <EvidenceList
                title="Scene state changes"
                rows={row.state_changes}
                render={(change) => <span>{change.entity_name}: {change.attribute || "state"} → {change.new_state || "?"}{change.evidence ? ` — ${change.evidence}` : ""}</span>}
              />
            </article>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("Overview");
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [newBookPath, setNewBookPath] = useState("");
  const [selectedContractPath, setSelectedContractPath] = useState("");
  const [selectedContractPayload, setSelectedContractPayload] = useState(null);
  const [contractLoading, setContractLoading] = useState(false);
  const [selectedPromptPath, setSelectedPromptPath] = useState("");
  const [promptSearch, setPromptSearch] = useState("");
  const [ollamaProviderDraft, setOllamaProviderDraft] = useState({ active_index: 0, accounts: [] });
  const [codexProviderDraft, setCodexProviderDraft] = useState({ active_index: 0, accounts: [] });

  async function refresh() {
    try {
      const next = await runtimeJson("/runtime/state");
      setState(next);
      setError("");
      if (!form.books.length) setForm((current) => ({ ...current, books: next.defaults.books }));
      setOllamaProviderDraft({
        active_index: next.providers.ollama.active_index || 0,
        accounts: (next.providers.ollama.accounts || []).map((account) => ({
          label: account.label,
          email: account.email || "",
          password: "",
          api_key: "",
          has_password: account.has_password,
          has_api_key: account.has_api_key,
        })),
      });
      setCodexProviderDraft({
        active_index: next.providers.codex?.active_index || 0,
        accounts: (next.providers.codex?.accounts || []).map((account) => ({
          label: account.label,
          api_key: "",
          has_api_key: account.has_api_key,
        })),
      });
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedContractPath) return;
    setContractLoading(true);
    setSelectedContractPayload(null);
    runtimeJson(`/runtime/contract-view?path=${encodeURIComponent(selectedContractPath)}&limit=200`)
      .then((payload) => setSelectedContractPayload(payload))
      .catch((err) => setError(err.message))
      .finally(() => setContractLoading(false));
  }, [selectedContractPath]);

  const artifacts = state?.artifacts || { counts: {}, contracts: [], runs: [], reports: [], visual_states: [], identities: [] };
  const latestJob = state?.jobs?.[0];
  const selectedPrompt = useMemo(
    () => (state?.prompts || []).find((prompt) => prompt.path === selectedPromptPath) || (state?.prompts || [])[0],
    [state, selectedPromptPath],
  );
  const filteredPrompts = useMemo(() => {
    const query = promptSearch.toLowerCase();
    return (state?.prompts || []).filter((prompt) => !query || `${prompt.path}\n${prompt.content}`.toLowerCase().includes(query));
  }, [state, promptSearch]);

  function updateForm(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function addBook(path) {
    const clean = String(path || "").trim();
    if (!clean) return;
    setForm((current) => ({ ...current, books: [...current.books, clean] }));
    setNewBookPath("");
  }

  function moveBook(index, direction) {
    setForm((current) => {
      const books = [...current.books];
      const next = index + direction;
      if (next < 0 || next >= books.length) return current;
      [books[index], books[next]] = [books[next], books[index]];
      return { ...current, books };
    });
  }

  async function uploadBook(file) {
    if (!file) return;
    const payload = new FormData();
    payload.append("file", file);
    const result = await runtimeJson("/runtime/upload-book", { method: "POST", body: payload });
    addBook(result.path);
  }

  async function startEncode() {
    setBusy(true);
    try {
      await runtimeJson("/runtime/start-encode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setActiveTab("Encode Runs");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveProviders() {
    setBusy(true);
    try {
      await runtimeJson("/runtime/providers/ollama", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ollamaProviderDraft),
      });
      await runtimeJson("/runtime/providers/codex", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(codexProviderDraft),
      });
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-5 text-slate-100">
      <header className="mb-5 rounded-lg border border-slate-800 bg-[#0b0c10] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="blue">Web local runtime</Badge>
              <Badge tone="green">Python-owned project root</Badge>
              <Badge>no workspace picker</Badge>
              <Badge>direct saga_tools runs</Badge>
            </div>
            <h1 className="text-3xl font-black tracking-tight">S.A.G.A. Local Operations Dashboard</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
              Create encoder runs, inspect contracts, review visual-world state, browse prompts, and manage local Ollama plus Codex provider accounts from one project-owned web console.
            </p>
            <p className="mt-2 text-xs text-slate-500">{state?.workspace?.root || "Starting local runtime..."}</p>
          </div>
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-right">
            <p className="text-xs font-bold uppercase tracking-wide text-emerald-300">Latest job</p>
            <p className="mt-1 text-xl font-black text-white">{latestJob?.status || "none"}</p>
          </div>
        </div>
      </header>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>
      ) : null}

      <nav className="mb-5 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-lg border px-4 py-2 text-sm font-bold transition ${
              activeTab === tab ? "border-sky-500 bg-sky-500/15 text-sky-100" : "border-slate-800 bg-[#0b0c10] text-slate-300 hover:border-slate-600"
            }`}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main>
        {activeTab === "Overview" && (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-5">
              <Metric label="Encode runs" value={artifacts.counts.runs || 0} />
              <Metric label="Contracts" value={artifacts.counts.contracts || 0} />
              <Metric label="Total scenes" value={artifacts.counts.total_scenes || 0} />
              <Metric label="Identities" value={artifacts.counts.identities || 0} />
              <Metric label="Visual outputs" value={artifacts.counts.visual_states || 0} />
            </div>
            <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
              <Panel title="Latest encode runs" subtitle="Auto-discovered from analysis_outputs/encode_runs.">
                <RunList runs={artifacts.runs.slice(0, 5)} />
              </Panel>
              <Panel title="Latest contracts" subtitle="Structured contract counts, not raw JSON.">
                <ContractList contracts={artifacts.contracts.slice(0, 6)} onSelect={(path) => { setSelectedContractPath(path); setActiveTab("Contract Viewer"); }} />
              </Panel>
            </div>
          </div>
        )}

        {activeTab === "Encode Runs" && (
          <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Runs" subtitle="One card per local encode run.">
              <RunList runs={artifacts.runs} />
            </Panel>
            <Panel title={latestJob?.id || "Live job log"} subtitle={latestJob ? latestJob.command : "No dashboard-launched job yet."}>
              {latestJob ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={statusTone(latestJob.status)}>{latestJob.status}</Badge>
                    {latestJob.pid ? <Badge>pid {latestJob.pid}</Badge> : null}
                    {latestJob.return_code !== undefined ? <Badge>exit {latestJob.return_code}</Badge> : null}
                  </div>
                  <LogTail lines={latestJob.log_tail} />
                </div>
              ) : (
                <Empty>Create an encode run from the dashboard to see live progress here.</Empty>
              )}
            </Panel>
          </div>
        )}

        {activeTab === "New Encode Run" && (
          <div className="grid gap-4 xl:grid-cols-[1fr,24rem]">
            <Panel title="Create encode run" subtitle="Upload or add books, order them, choose models, and launch saga_tools.py directly.">
              <div className="mb-4 grid gap-3 md:grid-cols-2">
                <Input label="Series ID" value={form.series_id} onChange={(value) => updateForm("series_id", value)} />
                <Input label="Series title" value={form.series_title} onChange={(value) => updateForm("series_title", value)} />
                <Select label="Analysis model" value={form.analysis_model} onChange={(value) => updateForm("analysis_model", value)} options={state?.defaults?.models || ["gpt_oss"]} />
                <Select label="Identity model" value={form.identity_model} onChange={(value) => updateForm("identity_model", value)} options={state?.defaults?.models || ["gpt_oss"]} />
                <Select label="Provider mode" value={form.analysis_provider_mode} onChange={(value) => updateForm("analysis_provider_mode", value)} options={state?.defaults?.provider_modes || ["same_provider_rotating"]} />
                <Select label="Identity provider" value={form.identity_provider} onChange={(value) => updateForm("identity_provider", value)} options={["booknlp_clean"]} />
                <Input className="md:col-span-2" label="Series identity JSON" value={form.series_identity_json} onChange={(value) => updateForm("series_identity_json", value)} />
                <Input className="md:col-span-2" label="Run summary output" value={form.out} onChange={(value) => updateForm("out", value)} />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <Input label="Max failed scenes" type="number" value={form.max_failed_scenes_absolute} onChange={(value) => updateForm("max_failed_scenes_absolute", value)} />
                <Input label="Failed scene ratio" type="number" step="0.01" value={form.max_failed_scene_ratio} onChange={(value) => updateForm("max_failed_scene_ratio", value)} />
                <Input label="Min nonempty ratio" type="number" step="0.01" value={form.min_nonempty_scene_ratio} onChange={(value) => updateForm("min_nonempty_scene_ratio", value)} />
                <Input label="Max chapters (0 = full)" type="number" value={form.max_chapters} onChange={(value) => updateForm("max_chapters", value)} />
              </div>
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-300">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.skip_ingest} onChange={(event) => updateForm("skip_ingest", event.target.checked)} /> Skip Neo4j ingest</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.no_progress} onChange={(event) => updateForm("no_progress", event.target.checked)} /> Quiet terminal progress</label>
              </div>
              <div className="mt-5">
                <h3 className="mb-2 text-sm font-bold text-slate-100">Books in order</h3>
                <div className="space-y-2">
                  {form.books.map((book, index) => (
                    <div key={`${book}-${index}`} className="flex items-center gap-2 rounded-lg border border-slate-800 bg-[#15171c] p-3">
                      <span className="w-8 text-sm font-bold text-slate-500">{index + 1}</span>
                      <span className="min-w-0 flex-1 break-words text-sm text-slate-200">{book}</span>
                      <button className="rounded-md border border-slate-700 px-2 py-1 text-xs" onClick={() => moveBook(index, -1)}>Up</button>
                      <button className="rounded-md border border-slate-700 px-2 py-1 text-xs" onClick={() => moveBook(index, 1)}>Down</button>
                      <button className="rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-200" onClick={() => updateForm("books", form.books.filter((_, i) => i !== index))}>Remove</button>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-[1fr,auto]">
                  <input value={newBookPath} onChange={(event) => setNewBookPath(event.target.value)} placeholder="Paste local book path..." className="rounded-md border border-slate-800 bg-[#0b0c10] px-3 py-2 text-sm text-slate-100" />
                  <button className="rounded-md border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-bold text-sky-100" onClick={() => addBook(newBookPath)}>Add path</button>
                </div>
                <label className="mt-3 inline-flex cursor-pointer rounded-md border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-bold text-emerald-100">
                  Upload EPUB/PDF
                  <input type="file" accept=".epub,.pdf" className="hidden" onChange={(event) => uploadBook(event.target.files?.[0])} />
                </label>
              </div>
              <button disabled={busy || !form.books.length} onClick={startEncode} className="mt-5 rounded-lg border border-emerald-500/50 bg-emerald-500/15 px-5 py-3 text-sm font-black text-emerald-100 disabled:opacity-50">
                {busy ? "Starting..." : "Start encode run"}
              </button>
            </Panel>
            <Panel title="Command behavior" subtitle="Dashboard launches the same CLI you would run manually.">
              <ul className="space-y-3 text-sm leading-6 text-slate-300">
                <li><Badge tone="green">same provider rotation</Badge> stays inside the Ollama/gpt-oss model path.</li>
                <li><Badge tone="amber">fail fast</Badge> prevents fake-empty contracts from provider failures.</li>
                <li><Badge tone="blue">BookNLP clean</Badge> uses the series identity map per book.</li>
                <li><Badge tone="green">Neo4j ingest</Badge> is enabled by default; use Skip Neo4j ingest only for contract-only smokes.</li>
              </ul>
            </Panel>
          </div>
        )}

        {activeTab === "Contract Viewer" && (
          <div className="grid gap-4 xl:grid-cols-[24rem,1fr]">
            <Panel title="Contracts" subtitle="Select a contract; details are rendered as sections.">
              <ContractList contracts={artifacts.contracts} selected={selectedContractPath} onSelect={setSelectedContractPath} />
            </Panel>
            <Panel title={selectedContractPath ? selectedContractPath.split(/[\\/]/).pop() : "Contract details"} subtitle={selectedContractPath || "No contract selected."}>
              {contractLoading ? <Empty>Loading structured contract sections...</Empty> : selectedContractPayload ? <StructuredContract payload={selectedContractPayload} /> : <Empty>Select a contract to inspect scenes, events, entities, timelines, profiles, and states.</Empty>}
            </Panel>
          </div>
        )}

        {activeTab === "Visual World State" && (
          <div className="space-y-4">
            <Panel title="Contract-native scene world state" subtitle="Structured scene-by-scene typed world state from the selected contract.">
              {selectedContractPayload?.outputs?.scene_world_state?.length ? (
                <SceneWorldStateView rows={selectedContractPayload.outputs.scene_world_state} totalCount={selectedContractPayload.counts?.scene_world_state ?? selectedContractPayload.outputs.scene_world_state.length} />
              ) : (
                <Empty>Select a contract with the new analysis fields to inspect typed world-state cards here.</Empty>
              )}
            </Panel>
            <Panel title="Visual world-state artifacts" subtitle="Actual visual/entity/location state files from analysis_outputs/visual_state.">
              {!artifacts.visual_states.length ? <Empty>No visual world-state artifacts found yet.</Empty> : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {artifacts.visual_states.map((item) => (
                    <article key={item.path} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
                      <Badge tone="blue">{item.type}</Badge>
                      <h3 className="mt-3 break-words font-bold text-slate-100">{item.name}</h3>
                      <p className="mt-2 break-words text-xs leading-5 text-slate-500">{item.path}</p>
                    </article>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        )}

        {activeTab === "Prompt Inspector" && (
          <div className="grid gap-4 xl:grid-cols-[24rem,1fr]">
            <Panel title="Prompt-bearing files" subtitle="System/user prompt sources used by analyzers and decoders.">
              <input value={promptSearch} onChange={(event) => setPromptSearch(event.target.value)} placeholder="Search prompts..." className="mb-3 w-full rounded-md border border-slate-800 bg-[#0b0c10] px-3 py-2 text-sm text-slate-100" />
              <div className="space-y-2">
                {filteredPrompts.map((prompt) => (
                  <button key={prompt.path} onClick={() => setSelectedPromptPath(prompt.path)} className={`w-full rounded-lg border p-3 text-left ${selectedPrompt?.path === prompt.path ? "border-sky-500 bg-sky-500/10" : "border-slate-800 bg-[#15171c]"}`}>
                    <p className="font-bold text-slate-100">{prompt.name}</p>
                    <p className="mt-1 break-words text-xs text-slate-500">{prompt.path}</p>
                    <p className="mt-2 text-xs text-slate-400">{prompt.line_count} lines</p>
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title={selectedPrompt?.path || "Prompt preview"} subtitle="Search hits first, full source below for exact inspection.">
              {selectedPrompt ? (
                <div className="space-y-4">
                  <div className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
                    <h3 className="mb-2 text-sm font-bold text-slate-100">Prompt-related lines</h3>
                    <ul className="space-y-2 text-sm leading-6 text-slate-300">
                      {selectedPrompt.prompt_hits.map((line, index) => <li key={index}>{line}</li>)}
                    </ul>
                  </div>
                  <pre className="max-h-[34rem] overflow-auto rounded-lg border border-slate-800 bg-black p-4 text-xs leading-5 text-slate-300">{selectedPrompt.content}</pre>
                </div>
              ) : <Empty>No prompt file selected.</Empty>}
            </Panel>
          </div>
        )}

        {activeTab === "Providers" && (
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Ollama provider accounts" subtitle="Local-only rotator config from deploy/ollama/accounts.local.json. Existing secrets are masked; leave secret fields blank to keep them.">
              <div className="space-y-3">
                {ollamaProviderDraft.accounts.map((account, index) => (
                  <div key={`${account.label}-${index}`} className="grid gap-3 rounded-lg border border-slate-800 bg-[#15171c] p-4 md:grid-cols-5">
                    <Input label="Label" value={account.label} onChange={(value) => setOllamaProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, label: value } : row) }))} />
                    <Input label="Email" value={account.email} onChange={(value) => setOllamaProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, email: value } : row) }))} />
                    <Input label={account.has_password ? "Password (configured)" : "Password"} type="password" value={account.password} onChange={(value) => setOllamaProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, password: value } : row) }))} />
                    <Input label={account.has_api_key ? "API key (configured)" : "API key"} type="password" value={account.api_key} onChange={(value) => setOllamaProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, api_key: value } : row) }))} />
                    <div className="flex items-end gap-2">
                      <label className="flex items-center gap-2 pb-2 text-sm text-slate-300">
                        <input type="radio" checked={ollamaProviderDraft.active_index === index} onChange={() => setOllamaProviderDraft((current) => ({ ...current, active_index: index }))} />
                        active
                      </label>
                      <button className="mb-1 rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-200" onClick={() => setOllamaProviderDraft((current) => ({ ...current, accounts: current.accounts.filter((_, i) => i !== index) }))}>Remove</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button className="rounded-md border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-bold text-sky-100" onClick={() => setOllamaProviderDraft((current) => ({ ...current, accounts: [...current.accounts, { label: `account-${current.accounts.length + 1}`, email: "", password: "", api_key: "" }] }))}>Add Ollama account</button>
              </div>
            </Panel>
            <Panel title="Codex provider accounts" subtitle="Local OpenAI/Codex keys from deploy/openai/accounts.local.json. Existing keys stay masked unless you replace them.">
              <div className="space-y-3">
                {codexProviderDraft.accounts.map((account, index) => (
                  <div key={`${account.label}-${index}`} className="grid gap-3 rounded-lg border border-slate-800 bg-[#15171c] p-4 md:grid-cols-3">
                    <Input label="Label" value={account.label} onChange={(value) => setCodexProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, label: value } : row) }))} />
                    <Input label={account.has_api_key ? "API key (configured)" : "API key"} type="password" value={account.api_key} onChange={(value) => setCodexProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, api_key: value } : row) }))} />
                    <div className="flex items-end gap-2">
                      <label className="flex items-center gap-2 pb-2 text-sm text-slate-300">
                        <input type="radio" checked={codexProviderDraft.active_index === index} onChange={() => setCodexProviderDraft((current) => ({ ...current, active_index: index }))} />
                        active
                      </label>
                      <button className="mb-1 rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-200" onClick={() => setCodexProviderDraft((current) => ({ ...current, accounts: current.accounts.filter((_, i) => i !== index) }))}>Remove</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button className="rounded-md border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-bold text-sky-100" onClick={() => setCodexProviderDraft((current) => ({ ...current, accounts: [...current.accounts, { label: `codex-${current.accounts.length + 1}`, api_key: "" }] }))}>Add Codex key</button>
                <button disabled={busy} className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-bold text-emerald-100 disabled:opacity-50" onClick={saveProviders}>{busy ? "Saving..." : "Save provider config"}</button>
              </div>
            </Panel>
          </div>
        )}

        {activeTab === "Reports" && (
          <Panel title="Reports" subtitle="Markdown reports discovered under analysis_outputs.">
            {!artifacts.reports.length ? <Empty>No reports found.</Empty> : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {artifacts.reports.map((report) => (
                  <article key={report.path} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
                    <h3 className="break-words font-bold text-slate-100">{report.name}</h3>
                    <p className="mt-2 break-words text-xs leading-5 text-slate-500">{report.path}</p>
                    <Badge>{report.category}</Badge>
                  </article>
                ))}
              </div>
            )}
          </Panel>
        )}
      </main>
    </div>
  );
}

function RunList({ runs }) {
  if (!runs?.length) return <Empty>No encode runs found.</Empty>;
  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <article key={run.path} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="break-words font-bold text-slate-100">{run.series_id}</h3>
              <p className="mt-1 break-words text-xs text-slate-500">{run.path}</p>
            </div>
            <Badge tone={statusTone(run.status)}>{run.status}</Badge>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-4">
            <Mini label="Books" value={run.books} />
            <Mini label="Contracts" value={run.contracts} />
            <Mini label="Scenes" value={run.total_scenes} />
            <Mini label="Failed" value={run.failed_books} />
          </div>
          <div className="mt-3 space-y-2">
            {(run.book_rows || []).map((book) => (
              <div key={book.path} className="flex items-center justify-between gap-3 rounded-md bg-[#0b0c10] px-3 py-2 text-sm">
                <span className="min-w-0 break-words">{book.name}</span>
                <Badge tone={statusTone(book.run_status)}>{book.scenes} scenes</Badge>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function ContractList({ contracts, selected, onSelect }) {
  if (!contracts?.length) return <Empty>No contracts found.</Empty>;
  return (
    <div className="space-y-2">
      {contracts.map((contract) => (
        <button key={contract.path} onClick={() => onSelect(contract.path)} className={`w-full rounded-lg border p-3 text-left ${selected === contract.path ? "border-sky-500 bg-sky-500/10" : "border-slate-800 bg-[#15171c]"}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 break-words font-bold text-slate-100">{contract.name}</p>
            <Badge tone={statusTone(contract.run_status)}>{contract.run_status}</Badge>
          </div>
          <p className="mt-2 break-words text-xs leading-5 text-slate-500">{contract.path}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {contractRows(contract).slice(1, 5).map(([label, value]) => <Mini key={label} label={label} value={value} />)}
          </div>
        </button>
      ))}
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="rounded-md bg-[#0b0c10] px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-black text-white">{value ?? "n/a"}</p>
    </div>
  );
}
