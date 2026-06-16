import React, { useEffect, useMemo, useState } from "react";

const TABS = [
  "Overview",
  "Encode Runs",
  "New Encode Run",
  "Analysis",
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
  series_identity_json: "db://identity-series/acotar-full-booknlp-clean-live",
  scene_failure_policy: "fail_fast",
  max_failed_scenes_absolute: 3,
  max_failed_scene_ratio: 0.1,
  min_nonempty_scene_ratio: 0.8,
  max_parallel_books: 1,
  max_chapters: 0,
  skip_ingest: false,
  no_progress: true,
  out: "analysis_outputs\\encoder_validation\\acotar_full_booknlp_clean_live.json",
  generate_identity_bundles: false,
  generate_visuals: false,
  identity_output_root: "",
  export_contracts: false,
  quality_preset: "balanced",
  force_full_text_scenes: true,
  visual_strictness: "strict",
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
        {options.map((option) => {
          const normalized = typeof option === "string" ? { value: option, label: option } : option;
          return (
          <option key={normalized.value} value={normalized.value}>
            {normalized.label}
          </option>
          );
        })}
      </select>
    </label>
  );
}

function Empty({ children }) {
  return <div className="rounded-lg border border-dashed border-slate-800 bg-[#0b0c10] p-4 text-sm text-slate-400">{children}</div>;
}

function LogTail({ lines }) {
  if (!lines?.length) return <Empty>No log output yet.</Empty>;
  const rows = lines.map((line, index) => {
    const text = String(line || "");
    const dashboardMatch = text.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC) \| (.*)$/);
    const runtimeMatch = text.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \| ([A-Z]+) \| (.*)$/);
    const stageMatch = text.match(/^\[([a-z_]+)\]\s+(.*)$/i);
    if (!dashboardMatch && !runtimeMatch) {
      const stage = stageMatch ? stageMatch[1] : "";
      const message = stageMatch ? stageMatch[2] : text;
      return { key: index, timestamp: "", level: stage ? stage.toUpperCase() : "", message, tone: "text-slate-300" };
    }
    const timestamp = dashboardMatch ? dashboardMatch[1] : runtimeMatch[1];
    const level = runtimeMatch ? runtimeMatch[2] : "";
    const message = dashboardMatch ? dashboardMatch[2] : runtimeMatch[3];
    let tone = "text-slate-300";
    if (level === "ERROR" || message.includes("Runtime failed") || message.includes("failed with exit code")) tone = "text-red-300";
    else if (level === "WARNING") tone = "text-amber-200";
    else if (message.includes("Building") || message.includes("Generating") || message.includes("queueing") || message.includes("launching")) tone = "text-sky-300";
    else if (message.includes("ready") || message.includes("completed") || message.includes("rendered") || message.includes("success")) tone = "text-emerald-300";
    else if (message.startsWith("$ ")) tone = "text-amber-200";
    return { key: index, timestamp, level, message, tone };
  });
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-black p-3">
      <div className="space-y-2 text-xs leading-5">
        {rows.map((row) => (
          <div key={row.key} className="grid grid-cols-[11rem,5rem,1fr] gap-3 border-b border-slate-900/70 pb-2 last:border-b-0">
            <div className="font-mono text-slate-500">{row.timestamp || "runtime"}</div>
            <div className="font-mono text-slate-500">{row.level || "INFO"}</div>
            <div className={`font-mono whitespace-pre-wrap break-words ${row.tone}`}>{row.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds || 0)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

function displayValue(value, fallback = "n/a") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string" && !value.trim()) return fallback;
  return value;
}

function sceneHeading(scene) {
  return scene?.title || scene?.scene_summary || scene?.summary || "Untitled scene";
}

function eventHeading(event) {
  return event?.title || event?.summary || event?.description || "Untitled event";
}

function formatVisualChangeEntry(row) {
  if (!row || typeof row !== "object") return "";
  if (row.description) return row.description;
  const fields = [
    ["Outfit", row.scene_outfit],
    ["Accessories", row.scene_accessories],
    ["Footwear", row.scene_footwear],
    ["Condition", row.visible_condition],
    ["Injuries", row.injuries],
    ["Marks", row.dirt_blood_markings],
    ["Body language", row.body_language],
    ["Expression", row.expression],
    ["Carried items", row.carried_items],
    ["Temporary effects", row.temporary_effects],
  ].filter(([, value]) => isMeaningfulValue(value));
  if (!fields.length) return "";
  return fields.map(([label, value]) => `${label}: ${value}`).join("; ");
}

function JobProgress({ progress, activity }) {
  if (!progress) return null;
  const current = Number(progress.current || 0);
  const total = Number(progress.total || 0);
  const percent = total ? Math.min(100, Math.round((current / total) * 100)) : 0;
  const startedAt = activity?.started_at || activity?.started_at_utc;
  const finishedAt = activity?.finished_at || activity?.finished_at_utc;
  const liveElapsedSeconds = firstDefined(
    progress.details?.elapsed_seconds,
    progress.details?.book_elapsed_seconds,
    startedAt ? ((finishedAt ? new Date(finishedAt) : new Date()).getTime() - new Date(startedAt).getTime()) / 1000 : null,
  );
  return (
    <div className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-slate-100">Live progress</p>
        <div className="flex flex-wrap gap-2">
          {progress.stage ? <Badge tone="amber">{progress.stage}</Badge> : null}
          {total ? <Badge tone="blue">{current} / {total}</Badge> : null}
        </div>
      </div>
      {total ? (
        <div className="h-3 overflow-hidden rounded-full bg-[#0b0c10]">
          <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${percent}%` }} />
        </div>
      ) : null}
      <p className="mt-2 text-sm text-slate-300">{progress.label || "Working..."}</p>
      <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{progress.status || "running"}</p>
      {progress.details?.status_reason ? (
        <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100">
          {progress.details.status_reason}
        </div>
      ) : null}
      {progress.details?.series_identity_json ? (
        <p className="mt-2 break-words text-xs text-slate-500">identity: {progress.details.series_identity_json}</p>
      ) : null}
      {progress.details?.contract_path ? (
        <p className="mt-2 break-words text-xs text-slate-500">contract: {progress.details.contract_path}</p>
      ) : null}
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {progress.details?.book_title ? <Mini label="Book" value={progress.details.book_title} /> : null}
        {progress.details?.book_position !== undefined ? <Mini label="Book progress" value={`${progress.details.book_position}/${progress.details.book_total || "?"}`} /> : null}
        {progress.details?.book_phase ? <Mini label="Phase" value={progress.details.book_phase} /> : null}
        {progress.details?.substage ? <Mini label="Substage" value={progress.details.substage} /> : null}
        {liveElapsedSeconds !== null && liveElapsedSeconds !== undefined ? <Mini label="Elapsed" value={formatDuration(liveElapsedSeconds)} /> : null}
        {progress.details?.status_update_age_seconds !== undefined && progress.details?.status_update_age_seconds !== null
          ? <Mini label="Last update age" value={formatDuration(progress.details.status_update_age_seconds)} />
          : null}
        {progress.details?.analysis_model ? <Mini label="Analysis model" value={progress.details.analysis_model} /> : null}
        {progress.details?.identity_model ? <Mini label="Identity model" value={progress.details.identity_model} /> : null}
        {progress.details?.completed_books !== undefined ? <Mini label="Completed books" value={`${progress.details.completed_books}/${progress.details.total_books || "?"}`} /> : null}
        {progress.details?.failed_books !== undefined ? <Mini label="Failed books" value={progress.details.failed_books} /> : null}
        {progress.details?.character_count !== undefined ? <Mini label="Identity characters" value={progress.details.character_count} /> : null}
        {progress.details?.alias_count !== undefined ? <Mini label="Identity aliases" value={progress.details.alias_count} /> : null}
        {progress.details?.reference_entity_count !== undefined ? <Mini label="Reference entities" value={progress.details.reference_entity_count} /> : null}
        {progress.details?.book_count !== undefined ? <Mini label="Identity books" value={progress.details.book_count} /> : null}
        {progress.details?.current_entity ? <Mini label="Current render" value={progress.details.current_entity} /> : null}
        {progress.details?.render_status ? <Mini label="Render status" value={progress.details.render_status} /> : null}
        {progress.details?.render_current !== undefined ? <Mini label="Render progress" value={`${progress.details.render_current}/${progress.details.render_total || "?"}`} /> : null}
      </div>
    </div>
  );
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "completed" || value === "success" || value === "ok") return "green";
  if (value === "failed" || value === "partial") return "red";
  if (value === "blocked_rate_limit" || value === "superseded" || value === "forbidden" || value === "session_insufficient_scope") return "amber";
  if (value === "running" || value === "queued" || value === "refreshing") return "blue";
  return "slate";
}

function statusLabel(status) {
  const value = String(status || "").toLowerCase();
  if (value === "blocked_rate_limit") return "blocked";
  if (value === "superseded") return "superseded";
  if (value === "completed") return "completed";
  if (value === "success") return "success";
  if (value === "failed") return "failed";
  if (value === "running") return "running";
  if (value === "queued") return "queued";
  if (value === "partial") return "partial";
  if (value === "ok") return "ok";
  if (value === "forbidden") return "forbidden";
  if (value === "session_insufficient_scope") return "session scope";
  if (value === "unconfigured") return "unconfigured";
  return value || "unknown";
}

function isHelperRunPath(path) {
  return String(path || "").replace(/\\/g, "/").toLowerCase().includes("/resume_checkpoints");
}

function contractRows(contract) {
  const scenes = typeof contract.scenes === "number" ? contract.scenes : null;
  const failedScenes = typeof contract.failed_scenes === "number"
    ? contract.failed_scenes
    : (String(contract.run_status || "").toLowerCase() === "success" && scenes !== null ? 0 : null);
  const explicitSuccessfulScenes = typeof contract.successful_scenes === "number" ? contract.successful_scenes : null;
  const successfulScenes = explicitSuccessfulScenes !== null
    ? ((explicitSuccessfulScenes === 0 && scenes !== null && failedScenes === 0) ? scenes : explicitSuccessfulScenes)
    : (scenes !== null && failedScenes !== null ? Math.max(0, scenes - failedScenes) : null);
  return [
    ["Run status", contract.run_status],
    ["Scenes", contract.scenes],
    ["Successful scenes", displayValue(successfulScenes)],
    ["Failed scenes", displayValue(failedScenes)],
    ["Entity registry", contract.entity_registry],
    ["Timeline", contract.timeline],
    ["Event ledger", contract.event_ledger],
    ["Character profiles", contract.character_profiles],
    ["Stable character states", contract.stable_character_states],
    ["Story index docs", contract.story_index_docs],
    ["Identity provider", contract.identity_provider],
  ];
}

function contractDownloadHref(contractPath) {
  if (!contractPath) return "#";
  return `/runtime/export-book-json?path=${encodeURIComponent(contractPath)}`;
}

function contractDownloadName(contractPath, fallback = "contract.json") {
  const name = String(contractPath || "").split(/[\\/]/).pop();
  return name || fallback;
}

function StructuredContract({ payload, contractPath, onRenderCharacterSheets }) {
  const outputs = payload?.outputs || {};
  const counts = payload?.counts || {};
  const visualRows = (outputs.visual_inventory && outputs.visual_inventory.length)
    ? outputs.visual_inventory
    : buildVisualInventoryFallback(outputs);
  const sections = [
    ["Entities", outputs.entity_registry || [], (row) => row.name || row.canonical_name || row.id || "Entity"],
    ["Events", outputs.event_ledger || [], (row) => row.event || row.description || row.summary || "Event"],
    ["Scenes", outputs.resolved_scene_analyses || outputs.scene_analyses || [], (row) => row.scene_summary || row.summary || "Untitled scene"],
    ["Relationships", outputs.relationship_profiles || [], (row) => `${row.source_character || "?"} ↔ ${row.target_character || "?"}`],
    ["States", outputs.stable_character_states || [], (row) => row.name || row.display_name || row.character_id || "State"],
    ["World State", outputs.scene_world_state || [], (row) => row.scene_summary || row.scene_id || "Scene world state"],
    ["Visuals", visualRows, (row) => row.entity_name || row.beat_title || row.prompt_type || "Visual prompt"],
    ["Timeline", outputs.timeline || [], (row) => row.event || row.description || row.summary || "Timeline item"],
  ];
  const [section, setSection] = useState(sections[0][0]);
  const active = sections.find((row) => row[0] === section) || sections[0];
  const rows = active[1].slice(0, 80);
  const sectionCounts = {
    Scenes: counts.resolved_scene_analyses,
    Events: counts.event_ledger,
    Entities: counts.entity_registry,
    Timeline: counts.timeline,
    Relationships: counts.relationship_profiles,
    States: counts.stable_character_states,
    "World State": counts.scene_world_state,
    Visuals: firstDefined(counts.visual_inventory, visualRows.length),
  };
  const content = section === "Entities"
    ? <EntityRegistryView rows={active[1]} totalCount={firstDefined(counts.entity_registry, active[1].length)} />
    : section === "Scenes"
        ? <ScenesView rows={active[1]} totalCount={firstDefined(counts.resolved_scene_analyses, active[1].length)} />
        : section === "Events"
          ? <EventsView rows={active[1]} totalCount={firstDefined(counts.event_ledger, active[1].length)} />
          : section === "Relationships"
            ? <RelationshipsView rows={active[1]} totalCount={firstDefined(counts.relationship_profiles, active[1].length)} />
            : section === "World State"
              ? <SceneWorldStateView rows={active[1]} totalCount={firstDefined(counts.scene_world_state, active[1].length)} />
              : section === "Visuals"
                ? <VisualInventoryView rows={active[1]} diagnostics={outputs.visual_prompt_diagnostics} contractPath={contractPath} renderSummary={payload?.render_summary} onRenderCharacterSheets={onRenderCharacterSheets} />
              : null;
  return (
    <div>
      {contractPath ? (
        <div className="mb-3 flex flex-wrap gap-2">
          <a
            href={contractDownloadHref(contractPath)}
            download={contractDownloadName(contractPath)}
            className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-xs font-bold text-emerald-100"
          >
            Download JSON
          </a>
        </div>
      ) : null}
      <div className="mb-3 flex flex-wrap gap-2">
        {sections.map(([name, values]) => (
          <button
            key={name}
            onClick={() => setSection(name)}
            className={`rounded-md border px-3 py-2 text-xs font-semibold ${
              section === name ? "border-sky-500 bg-sky-500/15 text-sky-100" : "border-slate-800 bg-[#0b0c10] text-slate-300"
            }`}
          >
            {name} · {displayValue(sectionCounts[name], values.length)}
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

function buildVisualInventoryFallback(outputs) {
  const entities = outputs?.entity_registry || [];
  const sets = outputs?.visual_prompt_sets || {};
  const baselineMap = new Map();

  function setBaseline(rows = []) {
    rows.forEach((row) => {
      const name = String(row?.entity_name || "").trim();
      const entityType = String(row?.entity_type || "").trim().toLowerCase();
      if (!name || !entityType) return;
      baselineMap.set(`${entityType}::${name.toLowerCase()}`, row);
    });
  }

  setBaseline(sets.initial_characters || []);
  setBaseline(sets.objects_creatures || []);
  setBaseline(sets.locations || []);

  return entities.map((entity) => {
    const name = String(entity?.name || entity?.canonical_name || "").trim();
    const entityType = String(entity?.entity_type || entity?.type || "").trim().toLowerCase();
    const baseline = baselineMap.get(`${entityType}::${name.toLowerCase()}`) || {};
    return {
      name,
      entity_type: entityType,
      mention_count: firstDefined(entity?.mention_count, 0),
      first_seen: entity?.first_seen || {},
      entity_context: entity?.entity_context || "",
      initial_physical_description: entity?.initial_physical_description || {},
      first_appearance_profile: entity?.first_appearance_profile || {},
      typed_attributes: entity?.typed_attributes || {},
      analysis_quality_flags: entity?.analysis_quality_flags || [],
      baseline_prompt: baseline?.positive_prompt || "",
      baseline_prompt_type: baseline?.prompt_type || "",
      baseline_source_evidence: baseline?.source_evidence || "",
      baseline_confidence: baseline?.confidence || "",
      baseline_details: baseline?.details || {},
      change_prompts: [],
      scene_prompts: [],
      generated_image_path: baseline?.generated_image_path || "",
      negative_prompt: baseline?.negative_prompt || "",
      render_status: baseline?.render_status || "",
    };
  }).filter((row) => row.name);
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

function VisualPromptSetsView({ rows, diagnostics, contractPath, renderSummary, onRenderCharacterSheets }) {
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
        {contractPath ? (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => onRenderCharacterSheets?.(contractPath)}
              className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-xs font-bold text-emerald-100"
            >
              Generate character-sheet images
            </button>
            {renderSummary?.render_count ? <Badge tone="green">{renderSummary.render_count} renders indexed</Badge> : null}
          </div>
        ) : null}
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
              <Badge>book {displayValue(row.book_index, "?")}, chapter {displayValue(row.chapter_index, "?")}, scene {displayValue(row.scene_index, "?")}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{row.entity_name || row.details?.beat_title || row.prompt_type || "Visual prompt"}</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Mini
                label={
                  row.visual_bucket === "initial_characters" || row.visual_bucket === "character_changes"
                    ? "Character"
                    : row.visual_bucket === "locations"
                      ? "Location"
                      : row.visual_bucket === "objects_creatures"
                        ? "Entity"
                        : "Scene beat"
                }
                value={row.entity_name || row.details?.beat_title || "n/a"}
              />
              <Mini
                label="Prompt mode"
                value={
                  row.visual_bucket === "initial_characters"
                    ? "baseline character sheet"
                    : row.visual_bucket === "character_changes"
                      ? "character edit/update"
                      : row.visual_bucket === "locations"
                        ? "location concept"
                        : row.visual_bucket === "objects_creatures"
                          ? "object or creature concept"
                          : "scene composition"
                }
              />
            </div>
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
            {row.generated_image_path ? (
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-800 bg-[#0b0c10] p-3">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Generated image</p>
                <img
                  src={`/runtime/file?path=${encodeURIComponent(row.generated_image_path)}`}
                  alt={row.entity_name || "Generated visual"}
                  className="w-full rounded-md border border-slate-800 object-cover"
                  loading="lazy"
                />
                <p className="mt-2 text-xs text-slate-500">{row.generated_image_path}</p>
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

function VisualInventoryView({ rows, diagnostics, contractPath, renderSummary, onRenderCharacterSheets }) {
  const groups = useMemo(() => {
    const next = { Characters: [], Locations: [], Objects: [], Creatures: [], Other: [] };
    rows.forEach((row) => next[classifyEntityType(row)].push(row));
    for (const key of Object.keys(next)) {
      next[key].sort((a, b) => Number(b.mention_count || 0) - Number(a.mention_count || 0) || String(a.name || "").localeCompare(String(b.name || "")));
    }
    return next;
  }, [rows]);
  const groupNames = Object.keys(groups).filter((key) => groups[key].length);
  const [activeGroup, setActiveGroup] = useState(groupNames[0] || "Characters");
  const activeRows = groups[activeGroup] || [];
  if (!rows.length) return <Empty>No visual inventory found in this contract.</Empty>;
  return (
    <div>
      <div className="mb-4 rounded-lg border border-slate-800 bg-[#15171c] p-4 text-sm leading-6 text-slate-300">
        <p><strong className="text-slate-100">Visual state</strong> mirrors the canonical entity registry one-to-one.</p>
        <p className="mt-2">You should see the same entries and sections as the <strong className="text-slate-100">Entities</strong> tab, with prompts and generated images attached to those exact entities.</p>
        {contractPath ? (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => onRenderCharacterSheets?.(contractPath)}
              className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-xs font-bold text-emerald-100"
            >
              Generate character-sheet images
            </button>
            {renderSummary?.render_count ? <Badge tone="green">{renderSummary.render_count} renders indexed</Badge> : null}
          </div>
        ) : null}
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
            {name} · {groups[name].length}
          </button>
        ))}
        <Badge>{rows.length} total</Badge>
      </div>
      <div className="grid gap-3">
        {activeRows.slice(0, 120).map((row, index) => (
          <article key={`${activeGroup}-${index}`} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone="blue">{row.entity_type || activeGroup.slice(0, -1).toLowerCase()}</Badge>
              <Badge>{displayValue(row.mention_count, 0)} mentions</Badge>
              <Badge>first seen: {formatProvenance(row.first_seen)}</Badge>
              {row.render_status ? <Badge tone="green">{row.render_status}</Badge> : null}
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{row.name || "Unnamed entity"}</h3>
            {row.entity_context ? <p className="mt-2 text-sm leading-6 text-slate-300">{row.entity_context}</p> : null}
            {row.initial_physical_description?.description ? (
              <div className="mt-3 rounded-md border border-sky-500/30 bg-sky-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-sky-200">Initial physical description</p>
                <p className="mt-1">{row.initial_physical_description.description}</p>
              </div>
            ) : null}
            {row.first_appearance_profile?.baseline_description ? (
              <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-emerald-200">First appearance profile</p>
                <p className="mt-1">{row.first_appearance_profile.baseline_description}</p>
                <TypedAttributeGrid attributes={row.first_appearance_profile.typed_attributes} />
              </div>
            ) : null}
            <TypedAttributeGrid attributes={row.typed_attributes} />
            {row.baseline_prompt ? (
              <div className="mt-3 rounded-md bg-[#0b0c10] p-3 text-sm leading-6 text-slate-200">
                <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Baseline prompt</p>
                <p>{row.baseline_prompt}</p>
              </div>
            ) : null}
            {row.negative_prompt ? (
              <div className="mt-3 rounded-md bg-[#0b0c10] p-3 text-sm leading-6 text-slate-200">
                <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Negative prompt</p>
                <p>{row.negative_prompt}</p>
              </div>
            ) : null}
            {row.generated_image_path ? (
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-800 bg-[#0b0c10] p-3">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Generated image</p>
                <img
                  src={`/runtime/file?path=${encodeURIComponent(row.generated_image_path)}`}
                  alt={row.name || "Generated visual"}
                  className="w-full rounded-md border border-slate-800 object-cover"
                  loading="lazy"
                />
                <p className="mt-2 text-xs text-slate-500">{row.generated_image_path}</p>
              </div>
            ) : null}
            <EvidenceList
              title="Change prompts"
              rows={row.change_prompts}
              render={(change) => (
                <div>
                  <p>{change.prompt || "n/a"}</p>
                  <p className="mt-1 text-xs text-slate-500">{change.prompt_type || "change"} · {formatProvenance(change)}</p>
                  {change.source_evidence ? <p className="mt-1 text-xs text-slate-400">Evidence: {change.source_evidence}</p> : null}
                </div>
              )}
            />
            <EvidenceList
              title="Scene prompts"
              rows={row.scene_prompts}
              render={(scenePrompt) => (
                <div>
                  <p className="font-semibold text-slate-100">{scenePrompt.beat_title || "Scene prompt"}</p>
                  <p className="mt-1">{scenePrompt.prompt || "n/a"}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatProvenance(scenePrompt)}</p>
                  {scenePrompt.source_evidence ? <p className="mt-1 text-xs text-slate-400">Evidence: {scenePrompt.source_evidence}</p> : null}
                </div>
              )}
            />
            {row.baseline_source_evidence ? <p className="mt-3 text-sm leading-6 text-slate-400">Baseline evidence: {row.baseline_source_evidence}</p> : null}
            {(row.analysis_quality_flags || []).length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {row.analysis_quality_flags.map((flag) => <Badge key={flag} tone="amber">{flag}</Badge>)}
              </div>
            ) : null}
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
              <Badge tone="blue">chapter {displayValue(scene.chapter_index, "?")}</Badge>
              <Badge tone="blue">scene {displayValue(scene.scene_index, "?")}</Badge>
              {scene.final_status && String(scene.final_status).toLowerCase() !== "pending_analysis" ? <Badge tone={scene.final_status === "success" ? "green" : "amber"}>{scene.final_status}</Badge> : null}
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{sceneHeading(scene)}</h3>
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
              <Badge tone="blue">chapter {displayValue(event.chapter_index, "?")}</Badge>
              <Badge tone="blue">scene {displayValue(event.scene_index, "?")}</Badge>
            </div>
            <h3 className="mt-3 text-lg font-black text-slate-100">{eventHeading(event)}</h3>
            {(event.summary || event.description) ? <p className="mt-2 text-sm leading-6 text-slate-300">{event.summary || event.description}</p> : null}
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Mini label="Participants" value={(event.participants || event.characters || []).join(", ") || "n/a"} />
              <Mini label="Entities involved" value={(event.entities_involved || []).join(", ") || "n/a"} />
              <Mini label="Location" value={typeof event.location === "string" ? event.location : event.location?.name || event.event_location || "n/a"} />
              <Mini label="Type" value={event.type || event.event_type || "n/a"} />
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
  const book = displayValue(value.book_index, "?");
  const chapter = displayValue(value.chapter_index, "?");
  const scene = displayValue(value.scene_index, "?");
  return `book ${book}, chapter ${chapter}, scene ${scene}`;
}

function isMeaningfulValue(value) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) return false;
  if (["not_explicitly_stated_in_text", "n/a", "none", "null", "unknown"].includes(text)) return false;
  return !text.includes("not explicitly stated")
    && !text.includes("not explicitly described")
    && !text.includes("commonly depicted")
    && !text.includes("presumed")
    && !text.includes("unspecified");
}

function summarizeStructuredTraits(record) {
  if (!record || typeof record !== "object") return "";
  const candidates = [record.baseline_visual_fields, record.persistent_traits];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") continue;
    const parts = Object.values(candidate)
      .map((value) => String(value || "").trim())
      .filter((value) => isMeaningfulValue(value));
    if (parts.length) return parts.slice(0, 6).join(", ");
  }
  return "";
}

function hasTypedAttributes(attributes) {
  return Object.values(attributes || {}).some((values) => Array.isArray(values) && values.length);
}

function hasRenderableSummary(record) {
  if (!record || typeof record !== "object") return false;
  return Boolean(
    [record.description, record.baseline_description, record.reason].some((value) => isMeaningfulValue(value))
      || summarizeStructuredTraits(record)
      || hasTypedAttributes(record.typed_attributes)
  );
}

function readableStatus(value) {
  const text = String(value || "").trim();
  return isMeaningfulValue(text) ? text : "";
}

function renderEntitySummary(record, fallback = "") {
  if (!record || typeof record !== "object") return fallback;
  if (isMeaningfulValue(record.description)) return record.description;
  if (isMeaningfulValue(record.baseline_description)) return record.baseline_description;
  const traits = summarizeStructuredTraits(record);
  if (traits) return traits;
  if (isMeaningfulValue(record.reason)) return record.reason;
  return fallback;
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
        <p><strong className="text-slate-100">Entities</strong> are the broad registry of things the analysis tracked: characters, places, objects/artifacts, creatures, and other named world items.</p>
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
            {group} | {groups[group].length}
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
            {hasRenderableSummary(entity.initial_physical_description) ? (
              <div className="mt-3 rounded-md border border-sky-500/30 bg-sky-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-sky-200">Initial physical description{readableStatus(entity.initial_physical_description.status) ? ` | ${readableStatus(entity.initial_physical_description.status)}` : ""}</p>
                <p className="mt-1">{renderEntitySummary(entity.initial_physical_description, "Not captured.")}</p>
              </div>
            ) : null}
            {hasRenderableSummary(entity.first_appearance_profile) ? (
              <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm leading-6 text-slate-200">
                <p className="text-xs font-bold uppercase tracking-wide text-emerald-200">First appearance profile{readableStatus(entity.first_appearance_profile.status) ? ` | ${readableStatus(entity.first_appearance_profile.status)}` : ""}</p>
                <p className="mt-1">{renderEntitySummary(entity.first_appearance_profile, "No first-appearance baseline recorded.")}</p>
                <TypedAttributeGrid attributes={entity.first_appearance_profile.typed_attributes} />
              </div>
            ) : null}
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
            <EvidenceList title="Visual change log" rows={entity.visual_change_log} render={(row) => <span>{formatVisualChangeEntry(row) || row.evidence || ""}</span>} />
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
                <Badge tone="blue">chapter {displayValue(row.chapter_index, "?")}</Badge>
                <Badge tone="blue">scene {displayValue(row.scene_index, "?")}</Badge>
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
  const [generalComputeProviderDraft, setGeneralComputeProviderDraft] = useState({ active_index: 0, accounts: [] });
  const [codexProviderDraft, setCodexProviderDraft] = useState({ active_index: 0, accounts: [] });

  async function refresh() {
    try {
      const next = await runtimeJson("/runtime/state");
      setState(next);
      setError("");
      setForm((current) => ({
        ...current,
        books: current.books.length ? current.books : next.defaults.books,
        series_identity_json: current.series_identity_json || next.defaults.series_identity_json,
      }));
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
          auth_mode: account.auth_mode || "",
          api_key: "",
          account_id: account.account_id || "",
          has_api_key: account.has_api_key,
        })),
      });
      setGeneralComputeProviderDraft({
        active_index: next.providers.general_compute?.active_index || 0,
        accounts: (next.providers.general_compute?.accounts || []).map((account) => ({
          label: account.label,
          api_key: "",
          has_api_key: account.has_api_key,
        })),
      });
    } catch (err) {
      setError(err.message);
    }
  }

  const artifacts = state?.artifacts || { counts: {}, contracts: [], runs: [], reports: [], visual_states: [], identities: [] };
  const visibleRuns = useMemo(
    () => (artifacts.runs || []).filter((run) => !isHelperRunPath(run.path)),
    [artifacts.runs],
  );
  const latestJob = state?.jobs?.[0] || null;
  const providerStatuses = state?.provider_statuses || {};
  const activeJob = useMemo(
    () => (state?.jobs || []).find((job) => ["queued", "running"].includes(String(job.status || "").toLowerCase())) || null,
    [state?.jobs],
  );
  const latestRunActivity = useMemo(
    () => visibleRuns.find((run) => ["running", "queued"].includes(String(run.status || "").toLowerCase())) || null,
    [visibleRuns],
  );
  const liveActivity = activeJob || latestRunActivity || latestJob;
  const selectedPrompt = useMemo(
    () => (state?.prompts || []).find((prompt) => prompt.path === selectedPromptPath) || (state?.prompts || [])[0],
    [state, selectedPromptPath],
  );
  const filteredPrompts = useMemo(() => {
    const query = promptSearch.toLowerCase();
    return (state?.prompts || []).filter((prompt) => !query || `${prompt.path}\n${prompt.content}`.toLowerCase().includes(query));
  }, [state, promptSearch]);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const isActive = ["queued", "running"].includes(String(liveActivity?.status || "").toLowerCase());
    const timer = setInterval(refresh, isActive ? 2000 : 10000);
    return () => clearInterval(timer);
  }, [liveActivity?.id, liveActivity?.run_id, liveActivity?.status]);

  useEffect(() => {
    if (selectedContractPath) return;
    const firstPath = artifacts.contracts?.[0]?.path;
    if (firstPath) {
      setSelectedContractPath(firstPath);
    }
  }, [artifacts.contracts, selectedContractPath]);

  useEffect(() => {
    if (!selectedContractPath) return;
    setContractLoading(true);
    setSelectedContractPayload(null);
    runtimeJson(`/runtime/contract-view?path=${encodeURIComponent(selectedContractPath)}&limit=200`)
      .then((payload) => setSelectedContractPayload(payload))
      .catch((err) => setError(err.message))
      .finally(() => setContractLoading(false));
  }, [selectedContractPath]);

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
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function startCharacterRender(contractPath) {
    if (!contractPath) return;
    setBusy(true);
    try {
      await runtimeJson("/runtime/start-character-render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract_path: contractPath, overwrite: true }),
      });
      await refresh();
      setActiveTab("Encode Runs");
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
      await runtimeJson("/runtime/providers/general-compute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(generalComputeProviderDraft),
      });
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function refreshProviderStatuses() {
    setBusy(true);
    try {
      await runtimeJson("/runtime/providers/status?refresh=true");
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
              Create encoder runs, inspect contracts, review visual-world state, browse prompts, and manage local provider accounts plus live provider health from one project-owned web console.
            </p>
            <p className="mt-2 text-xs text-slate-500">{state?.workspace?.root || "Starting local runtime..."}</p>
          </div>
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-right">
            <p className="text-xs font-bold uppercase tracking-wide text-emerald-300">Latest activity</p>
            <p className="mt-1 text-xl font-black text-white">{statusLabel(liveActivity?.status || "none")}</p>
            {liveActivity?.status_reason ? <p className="mt-1 max-w-56 text-xs leading-5 text-slate-300">{liveActivity.status_reason}</p> : null}
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
              <Metric label="Encode runs" value={visibleRuns.length || 0} />
              <Metric label="Analyses" value={artifacts.counts.contracts || 0} />
              <Metric label="Total scenes" value={artifacts.counts.total_scenes || 0} />
              <Metric label="Identities" value={artifacts.database?.identity_series || artifacts.counts.identity_db || 0} />
              <Metric label="Visual outputs" value={artifacts.database?.generated_images || 0} />
            </div>
            <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
              <Panel title="Latest encode runs" subtitle="Tracked from the SQLite control room and pipeline runtime state.">
                <RunList runs={visibleRuns.slice(0, 5)} />
              </Panel>
              <Panel title="Latest analyses" subtitle="Structured database-backed book analyses.">
                <ContractList contracts={artifacts.contracts.slice(0, 6)} onSelect={(path) => { setSelectedContractPath(path); setActiveTab("Analysis"); }} />
              </Panel>
            </div>
            <Panel title="Identity bundles (SQLite indexed)" subtitle="BookNLP-clean identity bundles are now indexed into the canonical SQLite store for dashboard inspection and later DB-native retrieval wiring.">
              {!artifacts.identity_db?.length ? <Empty>No indexed identity bundles yet.</Empty> : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {artifacts.identity_db.map((item) => (
                    <article key={item.series_id} className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
                      <div className="flex flex-wrap gap-2">
                        <Badge tone="green">{item.provider}</Badge>
                        <Badge>{item.book_count} books</Badge>
                      </div>
                      <h3 className="mt-3 font-bold text-slate-100">{item.series_id}</h3>
                      <p className="mt-2 break-words text-xs leading-5 text-slate-500">{item.source_path}</p>
                      <div className="mt-3 grid gap-2 md:grid-cols-2">
                        <Mini label="Characters" value={item.character_count} />
                        <Mini label="Aliases" value={item.alias_count} />
                        <Mini label="References" value={item.reference_entity_count} />
                        <Mini label="Narrators" value={item.narrator_count} />
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        )}

        {activeTab === "Encode Runs" && (
          <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Runs" subtitle="One card per local encode run.">
              <RunList runs={visibleRuns} />
            </Panel>
            <Panel title={liveActivity?.id || liveActivity?.series_id || "Live run log"} subtitle={liveActivity ? (liveActivity.command || liveActivity.path) : "No dashboard-launched or active filesystem run yet."}>
              {liveActivity ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={statusTone(liveActivity.status)}>{statusLabel(liveActivity.status)}</Badge>
                    {liveActivity.pid ? <Badge>pid {liveActivity.pid}</Badge> : null}
                    {liveActivity.return_code !== undefined ? <Badge>exit {liveActivity.return_code}</Badge> : null}
                    {!latestJob && liveActivity.run_id ? <Badge tone="blue">filesystem run</Badge> : null}
                  </div>
                  {liveActivity.status_reason ? (
                    <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm leading-6 text-amber-100">
                      {liveActivity.status_reason}
                    </div>
                  ) : null}
                  <JobProgress progress={liveActivity.progress} activity={liveActivity} />
                  <LogTail lines={liveActivity.log_tail} />
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
                <Select label="Quality preset" value={form.quality_preset} onChange={(value) => updateForm("quality_preset", value)} options={state?.defaults?.quality_presets || ["balanced"]} />
                <Select label="Visual strictness" value={form.visual_strictness} onChange={(value) => updateForm("visual_strictness", value)} options={state?.defaults?.visual_strictness_modes || ["strict"]} />
                <Input className="md:col-span-2" label="Series identity JSON" value={form.series_identity_json} onChange={(value) => updateForm("series_identity_json", value)} />
                <Input className="md:col-span-2" label="Identity output root (optional)" value={form.identity_output_root} onChange={(value) => updateForm("identity_output_root", value)} placeholder="analysis_outputs\\identity_series\\your_series" />
                <Input className="md:col-span-2" label="Run summary output" value={form.out} onChange={(value) => updateForm("out", value)} />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <Input label="Max failed scenes" type="number" value={form.max_failed_scenes_absolute} onChange={(value) => updateForm("max_failed_scenes_absolute", value)} />
                <Input label="Failed scene ratio" type="number" step="0.01" value={form.max_failed_scene_ratio} onChange={(value) => updateForm("max_failed_scene_ratio", value)} />
                <Input label="Min nonempty ratio" type="number" step="0.01" value={form.min_nonempty_scene_ratio} onChange={(value) => updateForm("min_nonempty_scene_ratio", value)} />
                <Input label="Max chapters (0 = full)" type="number" value={form.max_chapters} onChange={(value) => updateForm("max_chapters", value)} />
              </div>
              <div className="mt-4 rounded-lg border border-slate-800 bg-[#15171c] p-4">
                <h3 className="text-sm font-bold text-slate-100">Quality controls</h3>
                <p className="mt-1 text-sm leading-6 text-slate-400">These controls are dashboard planning and observability settings. They do not change the locked encoder logic unless they map to an existing saga_tools option already supported by the pipeline.</p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <Mini label="Preset intent" value={
                    form.quality_preset === "fast_debug" ? "small smoke / lower cost"
                    : form.quality_preset === "high_quality" ? "more conservative run review"
                    : form.quality_preset === "max_quality" ? "slowest / strictest monitoring"
                    : "balanced default"
                  } />
                  <Mini label="Visual extraction mode" value={form.visual_strictness} />
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-300">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.generate_identity_bundles} onChange={(event) => updateForm("generate_identity_bundles", event.target.checked)} /> Generate BookNLP identity bundles first</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.generate_visuals} onChange={(event) => updateForm("generate_visuals", event.target.checked)} /> Generate visuals after encode</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.skip_ingest} onChange={(event) => updateForm("skip_ingest", event.target.checked)} /> Skip Neo4j ingest</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.no_progress} onChange={(event) => updateForm("no_progress", event.target.checked)} /> Quiet terminal progress</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.export_contracts} onChange={(event) => updateForm("export_contracts", event.target.checked)} /> Export compatibility contract JSONs</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.force_full_text_scenes} onChange={(event) => updateForm("force_full_text_scenes", event.target.checked)} /> Prefer full scene text in viewer when available</label>
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
            <div className="space-y-4">
              <Panel title="Run plan" subtitle="The dashboard can stage identity bundles, encode, and visual generation in one local job.">
                <ul className="space-y-3 text-sm leading-6 text-slate-300">
                  <li><Badge tone="green">same provider rotation</Badge> stays inside the Ollama/gpt-oss model path.</li>
                  <li><Badge tone="amber">fail fast</Badge> prevents fake-empty contracts from provider failures.</li>
                  <li><Badge tone="blue">Generate BookNLP identity bundles first</Badge> rebuilds per-book identity JSONs and refreshes the series map before encode.</li>
                  <li><Badge tone="green">Generate visuals after encode</Badge> renders character sheets from contract-native prompts once contracts are healthy.</li>
                  <li><Badge tone="blue">SQLite canonical storage</Badge> keeps the operational dataset in the DB even if you choose not to export compatibility contracts.</li>
                </ul>
              </Panel>
              <Panel title={liveActivity?.id || liveActivity?.series_id || "Live run status"} subtitle={liveActivity ? (liveActivity.command || liveActivity.path) : "No dashboard-launched or active filesystem run yet."}>
                {liveActivity ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={statusTone(liveActivity.status)}>{statusLabel(liveActivity.status)}</Badge>
                      {liveActivity.pid ? <Badge>pid {liveActivity.pid}</Badge> : null}
                      {liveActivity.return_code !== undefined ? <Badge>exit {liveActivity.return_code}</Badge> : null}
                      {!latestJob && liveActivity.run_id ? <Badge tone="blue">filesystem run</Badge> : null}
                    </div>
                    {liveActivity.status_reason ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm leading-6 text-amber-100">
                        {liveActivity.status_reason}
                      </div>
                    ) : null}
                    <JobProgress progress={liveActivity.progress} activity={liveActivity} />
                    <LogTail lines={liveActivity.log_tail} />
                  </div>
                ) : (
                  <Empty>Launch a run here to watch identity bundles, encode, and visuals update live.</Empty>
                )}
              </Panel>
            </div>
          </div>
        )}

        {activeTab === "Analysis" && (
          <div className="grid gap-4 xl:grid-cols-[24rem,1fr]">
            <Panel title="Analyses" subtitle="Select a database-backed book analysis; details are rendered as sections.">
              <ContractList contracts={artifacts.contracts} selected={selectedContractPath} onSelect={setSelectedContractPath} />
            </Panel>
            <Panel title={selectedContractPath ? selectedContractPath.split(/[\\/]/).pop() : "Analysis details"} subtitle={selectedContractPath || "No analysis selected."}>
              {contractLoading ? <Empty>Loading structured analysis sections...</Empty> : selectedContractPayload ? <StructuredContract payload={selectedContractPayload} contractPath={selectedContractPath} onRenderCharacterSheets={startCharacterRender} /> : <Empty>Select an analysis to inspect scenes, events, entities, states, world-state, and visuals.</Empty>}
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
          <div className="space-y-4">
            <Panel
              title="Provider health"
              subtitle="Live probe status is refreshed on demand and cached in SQLite. Budget numbers are shown only where the provider or local rotator exposes reliable signals."
              action={<button disabled={busy} className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-bold text-emerald-100 disabled:opacity-50" onClick={refreshProviderStatuses}>{busy ? "Refreshing..." : "Refresh provider status"}</button>}
            >
              <div className="grid gap-4 xl:grid-cols-3">
                <ProviderStatusPanel providerName="Ollama" statuses={providerStatuses.ollama || []} />
                <ProviderStatusPanel providerName="General Compute" statuses={providerStatuses.general_compute || []} />
                <ProviderStatusPanel providerName="Codex" statuses={providerStatuses.codex || []} />
              </div>
            </Panel>
            <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Ollama provider accounts" subtitle="Canonical config is stored in SQLite and mirrored to deploy/ollama/accounts.local.json for the runtime rotator. Existing secrets are masked; leave secret fields blank to keep them.">
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
            <Panel title="General Compute provider accounts" subtitle="Canonical config is stored in SQLite and mirrored to deploy/general_compute/accounts.local.json. Local budget tracking exposes remaining requests/tokens from the configured limits.">
              <div className="space-y-3">
                {generalComputeProviderDraft.accounts.map((account, index) => (
                  <div key={`${account.label}-${index}`} className="grid gap-3 rounded-lg border border-slate-800 bg-[#15171c] p-4 md:grid-cols-3">
                    <Input label="Label" value={account.label} onChange={(value) => setGeneralComputeProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, label: value } : row) }))} />
                    <Input label={account.has_api_key ? "API key (configured)" : "API key"} type="password" value={account.api_key} onChange={(value) => setGeneralComputeProviderDraft((current) => ({ ...current, accounts: current.accounts.map((row, i) => i === index ? { ...row, api_key: value } : row) }))} />
                    <div className="flex items-end gap-2">
                      <label className="flex items-center gap-2 pb-2 text-sm text-slate-300">
                        <input type="radio" checked={generalComputeProviderDraft.active_index === index} onChange={() => setGeneralComputeProviderDraft((current) => ({ ...current, active_index: index }))} />
                        active
                      </label>
                      <button className="mb-1 rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-200" onClick={() => setGeneralComputeProviderDraft((current) => ({ ...current, accounts: current.accounts.filter((_, i) => i !== index) }))}>Remove</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button className="rounded-md border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-bold text-sky-100" onClick={() => setGeneralComputeProviderDraft((current) => ({ ...current, accounts: [...current.accounts, { label: `gc-${current.accounts.length + 1}`, api_key: "" }] }))}>Add GC key</button>
              </div>
            </Panel>
            <Panel title="Codex provider accounts" subtitle="Canonical config is stored in SQLite and mirrored to deploy/openai/accounts.local.json for API-key usage. Codex desktop session access is probed separately and shown in provider health.">
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
              {run.status_reason ? <p className="mt-2 text-xs leading-5 text-amber-200">{run.status_reason}</p> : null}
            </div>
            <Badge tone={statusTone(run.status)}>{statusLabel(run.status)}</Badge>
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
                <span className="min-w-0 break-words">{book.name || book.title || book.path || "Book"}</span>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone(book.run_status || book.status)}>{statusLabel(book.run_status || book.status || "unknown")}</Badge>
                  <Badge tone="blue">{displayValue(firstDefined(book.scenes, book.scenes_processed, book.total_scenes), 0)} scenes</Badge>
                </div>
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
        <article
          key={contract.path}
          onClick={() => onSelect(contract.path)}
          className={`w-full cursor-pointer rounded-lg border p-3 text-left ${selected === contract.path ? "border-sky-500 bg-sky-500/10" : "border-slate-800 bg-[#15171c]"}`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 break-words font-bold text-slate-100">{contract.name}</p>
            <Badge tone={statusTone(contract.run_status)}>{contract.run_status}</Badge>
          </div>
          <p className="mt-2 break-words text-xs leading-5 text-slate-500">{contract.path}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {contractRows(contract).slice(1, 5).map(([label, value]) => <Mini key={label} label={label} value={value} />)}
          </div>
          {String(contract.run_status || "").toLowerCase() === "success" ? (
            <div className="mt-3 flex justify-end">
              <a
                href={contractDownloadHref(contract.path)}
                download={contractDownloadName(contract.path)}
                onClick={(event) => event.stopPropagation()}
                className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-xs font-bold text-emerald-100"
              >
                Export JSON
              </a>
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="rounded-md bg-[#0b0c10] px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-black text-white">{displayValue(value)}</p>
    </div>
  );
}

function ProviderStatusPanel({ providerName, statuses }) {
  const rows = Array.isArray(statuses) ? statuses : [];
  return (
    <div className="rounded-lg border border-slate-800 bg-[#15171c] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="font-bold text-slate-100">{providerName}</h3>
        <Badge tone="blue">{rows.length} accounts</Badge>
      </div>
      {!rows.length ? <Empty>No provider status snapshots yet.</Empty> : (
        <div className="space-y-3">
          {rows.map((row) => (
            <div key={`${row.provider_name}-${row.label}`} className="rounded-md border border-slate-800 bg-[#0b0c10] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-100">{row.label}</p>
                <Badge tone={statusTone(row.probe_status)}>{statusLabel(row.probe_status)}</Badge>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <Mini label="Transport" value={row.transport || "n/a"} />
                <Mini label="Model" value={row.resolved_model || "n/a"} />
                <Mini label="Quota source" value={row.quota_source || "n/a"} />
                <Mini label="Refreshed" value={row.last_checked_at_utc ? new Date(row.last_checked_at_utc).toLocaleString() : "n/a"} />
                <Mini label="Req/min left" value={displayValue(row.remaining_requests_minute, "unknown")} />
                <Mini label="Input tok/min left" value={displayValue(row.remaining_input_tokens_minute, "unknown")} />
                <Mini label="Output tok/min left" value={displayValue(row.remaining_output_tokens_minute, "unknown")} />
                <Mini label="Req/day left" value={displayValue(row.remaining_requests_day, "unknown")} />
                <Mini label="Tokens/day left" value={displayValue(row.remaining_tokens_day, "unknown")} />
                <Mini label="Credits left" value={row.credits_remaining || "unknown"} />
              </div>
              {row.detail ? <p className="mt-3 text-xs leading-5 text-slate-400">{row.detail}</p> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
