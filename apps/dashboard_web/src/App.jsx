import React, { useEffect, useMemo, useState } from "react";

const NAV = [
  { id: "command", label: "Command Center" },
  { id: "runs", label: "Runs" },
  { id: "library", label: "Library" },
  { id: "analysis", label: "Analysis" },
  { id: "assets", label: "Visual Assets" },
  { id: "stories", label: "Decoder" },
  { id: "providers", label: "Providers" },
  { id: "diagnostics", label: "Diagnostics" },
];

const ANALYSIS_SECTIONS = ["Entities", "Scenes", "Events", "Relationships", "Timeline", "States"];
const ASSET_GROUPS = ["Characters", "Locations", "Objects", "Creatures", "Other"];
const STORY_MODES = [
  { value: "pre_canon", label: "Pre canon" },
  { value: "mid_canon", label: "Mid canon" },
  { value: "post_canon", label: "Post canon" },
  { value: "alternate_universe", label: "Alternate universe" },
];

const DEFAULT_DECODER = {
  series_id: "",
  book_ref: "",
  story_mode: "post_canon",
  user_prompt: "",
  chapter_count: 20,
  primary_pov_character: "",
  continuity_anchor: "",
  divergence_anchor: "",
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.detail || response.statusText || `Request failed: ${path}`);
  }
  return payload;
}

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function num(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed.toLocaleString() : "0";
}

function clampText(value, fallback = "Not recorded") {
  if (value === null || value === undefined) return fallback;
  if (Array.isArray(value)) return value.filter(Boolean).join(", ") || fallback;
  if (typeof value === "object") {
    const entries = Object.entries(value)
      .filter(([, item]) => item !== null && item !== undefined && item !== "" && item !== "not_explicitly_stated_in_text")
      .map(([key, item]) => `${labelize(key)}: ${Array.isArray(item) ? item.join(", ") : String(item)}`);
    return entries.join(" | ") || fallback;
  }
  const text = String(value).trim();
  if (!text || text === "0" || text === "n/a" || text === "not_explicitly_stated_in_text") return fallback;
  return text;
}

function labelize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusTone(status) {
  const text = String(status || "").toLowerCase();
  if (["success", "completed", "complete", "healthy"].includes(text)) return "green";
  if (["running", "queued", "partial", "split_ready"].includes(text)) return "blue";
  if (["failed", "error", "invalid"].includes(text)) return "red";
  if (["warning", "stale", "unknown"].includes(text)) return "amber";
  return "slate";
}

function entityBucket(type) {
  const normalized = String(type || "other").toLowerCase();
  if (normalized.includes("character")) return "Characters";
  if (normalized.includes("location") || normalized.includes("place")) return "Locations";
  if (normalized.includes("object") || normalized.includes("artifact") || normalized.includes("weapon")) return "Objects";
  if (normalized.includes("creature") || normalized.includes("animal") || normalized.includes("nonhuman")) return "Creatures";
  return "Other";
}

function shortRef(value) {
  const text = String(value || "");
  if (!text) return "db://";
  if (text.length <= 88) return text;
  return `${text.slice(0, 42)}...${text.slice(-36)}`;
}

function progressOf(job) {
  const progress = job?.progress || {};
  const current = Number(progress.current ?? job?.current ?? 0);
  const total = Number(progress.total ?? job?.total ?? 0);
  if (!total) return { current: 0, total: 0, percent: 0 };
  return { current, total, percent: Math.max(0, Math.min(100, Math.round((current / total) * 100))) };
}

function Badge({ children, tone = "slate", className = "" }) {
  const tones = {
    slate: "border-slate-700 bg-slate-900/80 text-slate-300",
    blue: "border-sky-500/50 bg-sky-500/10 text-sky-200",
    green: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-500/50 bg-amber-500/10 text-amber-200",
    red: "border-red-500/50 bg-red-500/10 text-red-200",
  };
  return (
    <span className={classNames("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold", tones[tone], className)}>
      {children}
    </span>
  );
}

function Button({ children, variant = "secondary", className = "", ...props }) {
  const variants = {
    primary: "border-emerald-400/50 bg-emerald-500/15 text-emerald-100 hover:bg-emerald-500/25",
    secondary: "border-slate-700 bg-slate-950/70 text-slate-100 hover:border-sky-500/60 hover:bg-sky-500/10",
    danger: "border-red-500/50 bg-red-500/10 text-red-100 hover:bg-red-500/20",
  };
  return (
    <button
      className={classNames("rounded-xl border px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50", variants[variant], className)}
      {...props}
    >
      {children}
    </button>
  );
}

function Panel({ title, subtitle, children, action, className = "" }) {
  return (
    <section className={classNames("rounded-3xl border border-slate-800 bg-slate-950/70 p-5 shadow-2xl shadow-black/20", className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-black text-white">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value, detail, tone = "slate" }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0d1017] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">{label}</p>
        <Badge tone={tone}>{detail || "live"}</Badge>
      </div>
      <p className="mt-3 text-3xl font-black text-white">{value}</p>
    </div>
  );
}

function Empty({ title = "Nothing here yet", children }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
      <p className="font-bold text-slate-200">{title}</p>
      {children ? <div className="mt-2 leading-6">{children}</div> : null}
    </div>
  );
}

function SearchBox({ value, onChange, placeholder = "Search..." }) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-sky-500"
    />
  );
}

function Field({ label, children }) {
  return (
    <div className="rounded-2xl bg-black/25 p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <div className="text-sm leading-6 text-slate-100">{children}</div>
    </div>
  );
}

function Progress({ job }) {
  const progress = progressOf(job);
  const status = String(job?.status || "unknown");
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#10141d] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-white">{job?.message || job?.current_step || job?.type || "No active step"}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{status}</p>
        </div>
        <div className="flex gap-2">
          <Badge tone={statusTone(status)}>{status}</Badge>
          <Badge tone="blue">{progress.total ? `${progress.current}/${progress.total}` : "no counter"}</Badge>
        </div>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-black/50">
        <div className="h-full rounded-full bg-sky-400 transition-all" style={{ width: `${progress.percent || (status === "running" ? 8 : 0)}%` }} />
      </div>
    </div>
  );
}

function LogTail({ lines }) {
  const rows = asArray(lines).slice(-80);
  if (!rows.length) return <Empty title="No log lines">Logs will appear here when the runtime records them.</Empty>;
  return (
    <div className="max-h-[460px] overflow-auto rounded-2xl border border-slate-800 bg-black p-3 font-mono text-xs">
      {rows.map((line, index) => {
        const text = typeof line === "string" ? line : JSON.stringify(line);
        const isError = /error|failed|traceback|exception/i.test(text);
        const isWarn = /warn|retry|stale/i.test(text);
        return (
          <div key={`${index}-${text.slice(0, 20)}`} className={classNames("border-b border-slate-900 py-1.5", isError ? "text-red-300" : isWarn ? "text-amber-200" : "text-slate-300")}>
            {text}
          </div>
        );
      })}
    </div>
  );
}

function useFiltered(items, query, fields) {
  return useMemo(() => {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => fields.some((field) => String(item?.[field] || "").toLowerCase().includes(q)));
  }, [items, query, fields]);
}

function App() {
  const [page, setPage] = useState("command");
  const [state, setState] = useState(null);
  const [stories, setStories] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedBook, setSelectedBook] = useState("");
  const [bookView, setBookView] = useState(null);
  const [bookLoading, setBookLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [analysisSection, setAnalysisSection] = useState("Entities");
  const [assetGroup, setAssetGroup] = useState("Characters");
  const [decoder, setDecoder] = useState(DEFAULT_DECODER);
  const [jobFocus, setJobFocus] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  async function refresh({ silent = false } = {}) {
    if (!silent) setLoading(true);
    try {
      const [runtime, storyPayload] = await Promise.all([api("/runtime/state"), api("/runtime/generated-stories").catch(() => ({ stories: [] }))]);
      setState(runtime);
      setStories(asArray(storyPayload.stories));
      setError("");
    } catch (exc) {
      setError(exc.message || String(exc));
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadBook(path) {
    if (!path) return;
    setBookLoading(true);
    try {
      const payload = await api(`/runtime/contract-view?path=${encodeURIComponent(path)}&limit=500`);
      setBookView(payload);
      setError("");
    } catch (exc) {
      setError(exc.message || String(exc));
      setBookView(null);
    } finally {
      setBookLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const books = asArray(state?.artifacts?.contracts);
  const runs = asArray(state?.artifacts?.runs);
  const jobs = asArray(state?.jobs);
  const latestJob = jobs[0] || null;
  const hasRunningJob = jobs.some((job) => ["running", "queued"].includes(String(job?.status || "").toLowerCase()));

  useEffect(() => {
    if (!selectedBook && books.length) setSelectedBook(books[0].path || books[0].contract_path || books[0].id || "");
  }, [books, selectedBook]);

  useEffect(() => {
    if (selectedBook) loadBook(selectedBook);
  }, [selectedBook]);

  useEffect(() => {
    if (!hasRunningJob) return undefined;
    const timer = window.setInterval(() => refresh({ silent: true }), 5000);
    return () => window.clearInterval(timer);
  }, [hasRunningJob]);

  useEffect(() => {
    if (!jobFocus && latestJob?.id) setJobFocus(latestJob.id);
  }, [latestJob, jobFocus]);

  const selectedJob = jobs.find((job) => job.id === jobFocus) || latestJob;
  const outputs = bookView?.outputs || {};
  const counts = state?.artifacts?.counts || {};
  const db = state?.artifacts?.database || {};
  const entities = asArray(outputs.entity_registry);
  const scenes = asArray(outputs.resolved_scene_analyses);
  const events = asArray(outputs.event_ledger);
  const timeline = asArray(outputs.timeline);
  const relationships = asArray(outputs.relationships || outputs.relationship_profiles);
  const states = asArray(outputs.stable_character_states);
  const visualInventory = asArray(outputs.visual_inventory);
  const prompts = asArray(state?.prompts);
  const providers = state?.providers || {};
  const providerStatuses = state?.provider_statuses || {};

  async function startStory() {
    const payload = {
      ...decoder,
      book_ref: decoder.book_ref || selectedBook,
      series_id: decoder.series_id || bookView?.summary?.series_id || books[0]?.series_id || "",
    };
    setActionMessage("");
    const job = await api("/runtime/start-decoder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setActionMessage(`Decoder job queued: ${job.id}`);
    await refresh({ silent: true });
    setPage("runs");
  }

  async function renderSelectedBookVisuals() {
    if (!selectedBook) return;
    const job = await api("/runtime/start-character-render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contract_path: selectedBook, overwrite: false, limit: 0 }),
    });
    setActionMessage(`Visual render queued: ${job.id}`);
    await refresh({ silent: true });
    setPage("runs");
  }

  async function renderSeriesVisuals(seriesId) {
    if (!seriesId) return;
    const job = await api("/runtime/start-series-character-render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ series_id: seriesId, overwrite: false, limit: 0 }),
    });
    setActionMessage(`Series visual render queued: ${job.id}`);
    await refresh({ silent: true });
    setPage("runs");
  }

  async function refreshProviderHealth() {
    const payload = await api("/runtime/providers/status?refresh=1");
    setState((previous) => ({ ...previous, provider_statuses: payload.providers }));
    setActionMessage("Provider health refreshed.");
  }

  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto max-w-[1800px] px-5 py-5">
        <Hero state={state} latestJob={latestJob} loading={loading} onRefresh={() => refresh()} />
        {error ? <div className="mt-4 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-100">{error}</div> : null}
        {actionMessage ? <div className="mt-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-100">{actionMessage}</div> : null}

        <nav className="sticky top-0 z-20 mt-5 flex flex-wrap gap-2 border-b border-slate-900 bg-[#081013]/90 py-3 backdrop-blur-xl">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={classNames(
                "rounded-2xl border px-4 py-2 text-sm font-black transition",
                page === item.id ? "border-sky-400 bg-sky-500/15 text-white" : "border-slate-800 bg-slate-950/70 text-slate-300 hover:border-slate-600",
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <main className="mt-5">
          {page === "command" ? (
            <CommandCenter state={state} runs={runs} books={books} latestJob={latestJob} stories={stories} onSelectBook={(path) => { setSelectedBook(path); setPage("analysis"); }} onSelectJob={(id) => { setJobFocus(id); setPage("runs"); }} />
          ) : null}
          {page === "runs" ? <RunsPage runs={runs} jobs={jobs} selectedJob={selectedJob} setJobFocus={setJobFocus} /> : null}
          {page === "library" ? <LibraryPage books={books} identities={asArray(state?.artifacts?.identity_db)} uploads={asArray(state?.uploads)} query={query} setQuery={setQuery} onSelectBook={(path) => { setSelectedBook(path); setPage("analysis"); }} /> : null}
          {page === "analysis" ? (
            <AnalysisPage books={books} selectedBook={selectedBook} setSelectedBook={setSelectedBook} bookView={bookView} loading={bookLoading} section={analysisSection} setSection={setAnalysisSection} query={query} setQuery={setQuery} entities={entities} scenes={scenes} events={events} relationships={relationships} timeline={timeline} states={states} />
          ) : null}
          {page === "assets" ? (
            <AssetsPage bookView={bookView} books={books} selectedBook={selectedBook} setSelectedBook={setSelectedBook} visualInventory={visualInventory} group={assetGroup} setGroup={setAssetGroup} query={query} setQuery={setQuery} onRenderBook={renderSelectedBookVisuals} onRenderSeries={renderSeriesVisuals} />
          ) : null}
          {page === "stories" ? <StoriesPage stories={stories} books={books} selectedBook={selectedBook} decoder={decoder} setDecoder={setDecoder} onStartStory={startStory} /> : null}
          {page === "providers" ? <ProvidersPage providers={providers} statuses={providerStatuses} onRefresh={refreshProviderHealth} /> : null}
          {page === "diagnostics" ? <DiagnosticsPage prompts={prompts} reports={asArray(state?.artifacts?.reports)} selectedJob={selectedJob} runtime={state} /> : null}
        </main>
      </div>
    </div>
  );
}

function Hero({ state, latestJob, loading, onRefresh }) {
  const status = latestJob?.status || state?.latest_activity?.status || "idle";
  return (
    <header className="overflow-hidden rounded-[2rem] border border-slate-800 bg-[linear-gradient(135deg,rgba(15,23,42,.95),rgba(2,6,23,.85)),radial-gradient(circle_at_80%_20%,rgba(14,165,233,.22),transparent_32%)] p-7">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="blue">Database-backed</Badge>
            <Badge tone="green">Local runtime</Badge>
            <Badge tone="slate">No mock data</Badge>
          </div>
          <h1 className="text-4xl font-black tracking-tight text-white">S.A.G.A. Operations Console</h1>
          <p className="mt-3 max-w-4xl text-base leading-7 text-slate-300">
            Operate ingestion, inspect book analysis, manage visual assets, review generated stories, and diagnose provider health from one professional control surface.
          </p>
          <p className="mt-3 text-sm text-slate-500">{state?.workspace?.root || "Loading project root..."}</p>
        </div>
        <div className="min-w-[220px] rounded-3xl border border-emerald-500/40 bg-emerald-500/10 p-5 text-right">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-200">Latest activity</p>
          <p className="mt-2 text-2xl font-black text-white">{loading ? "loading" : status}</p>
          <Button className="mt-4" onClick={onRefresh}>Refresh</Button>
        </div>
      </div>
    </header>
  );
}

function CommandCenter({ state, runs, books, latestJob, stories, onSelectBook, onSelectJob }) {
  const counts = state?.artifacts?.counts || {};
  const db = state?.artifacts?.database || {};
  const attention = [
    latestJob && ["failed", "error"].includes(String(latestJob.status || "").toLowerCase()) ? `Latest job failed: ${latestJob.id}` : "",
    !books.length ? "No database-backed books discovered." : "",
    Number(db.visual_prompts || 0) && !Number(db.generated_images || 0) ? "Visual prompts exist but no generated images were found." : "",
  ].filter(Boolean);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Books" value={num(db.books || counts.contracts)} detail="database" tone="blue" />
        <Metric label="Scenes" value={num(db.scenes || counts.total_scenes)} detail="stored" tone="blue" />
        <Metric label="Entities" value={num(db.entities)} detail="registry" tone="green" />
        <Metric label="Visuals" value={num(db.generated_images)} detail="images" tone="amber" />
        <Metric label="Stories" value={num(stories.length || db.generated_stories)} detail="decoder" tone="green" />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <Panel title="Recommended next actions" subtitle="A short, honest queue based on the data currently visible to the dashboard.">
          {attention.length ? attention.map((item) => <div key={item} className="mb-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{item}</div>) : <Empty title="No urgent issues">The current database summaries do not show an obvious blocker.</Empty>}
        </Panel>
        <Panel title="Active work" subtitle="Latest job progress and status.">
          {latestJob ? (
            <div className="space-y-3">
              <Progress job={latestJob} />
              <Button onClick={() => onSelectJob(latestJob.id)}>Open run details</Button>
            </div>
          ) : <Empty title="No job in focus">Start a run or decoder task to see live progress here.</Empty>}
        </Panel>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Recent books" subtitle="Database-backed books ready for inspection.">
          <List>
            {books.slice(0, 6).map((book) => (
              <button key={book.path || book.name} onClick={() => onSelectBook(book.path)} className="w-full rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-sky-500/50">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-black text-white">{book.name || book.title || "Untitled book"}</p>
                    <p className="mt-1 text-xs text-slate-500">{shortRef(book.path)}</p>
                  </div>
                  <Badge tone={statusTone(book.run_status)}>{book.run_status || "ready"}</Badge>
                </div>
                <div className="mt-3 grid grid-cols-4 gap-2 text-xs">
                  <Mini label="Scenes" value={book.scenes} />
                  <Mini label="Entities" value={book.entity_registry || book.entities} />
                  <Mini label="Events" value={book.event_ledger || book.events} />
                  <Mini label="Images" value={book.generated_images || 0} />
                </div>
              </button>
            ))}
          </List>
        </Panel>
        <Panel title="Recent runs" subtitle="Newest pipeline runs and jobs.">
          <List>
            {runs.slice(0, 6).map((run) => (
              <button key={run.path || run.id} onClick={() => onSelectJob(run.id)} className="w-full rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-sky-500/50">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-black text-white">{run.series_id || run.name || run.id || "Run"}</p>
                    <p className="mt-1 text-xs text-slate-500">{shortRef(run.path)}</p>
                  </div>
                  <Badge tone={statusTone(run.status || run.run_status)}>{run.status || run.run_status || "unknown"}</Badge>
                </div>
              </button>
            ))}
          </List>
        </Panel>
      </div>
    </div>
  );
}

function RunsPage({ runs, jobs, selectedJob, setJobFocus }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
      <Panel title="Runs and jobs" subtitle="Pipeline runs discovered from the database plus live dashboard jobs.">
        <List>
          {[...jobs, ...runs].map((run, index) => (
            <button key={run.id || run.path || index} onClick={() => setJobFocus(run.id)} className="w-full rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-sky-500/50">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-black text-white">{run.id || run.series_id || run.name || "Run"}</p>
                  <p className="mt-1 text-xs text-slate-500">{shortRef(run.path || run.command)}</p>
                </div>
                <Badge tone={statusTone(run.status || run.run_status)}>{run.status || run.run_status || "unknown"}</Badge>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-2">
                <Mini label="Books" value={run.books} />
                <Mini label="Contracts" value={run.contracts} />
                <Mini label="Scenes" value={run.total_scenes || run.scenes} />
                <Mini label="Failed" value={run.failed_books || run.failed} />
              </div>
            </button>
          ))}
        </List>
      </Panel>
      <Panel title={selectedJob?.id || "No selected run"} subtitle={selectedJob?.type || selectedJob?.series_id || "Select a job to inspect progress and logs."}>
        {selectedJob ? (
          <div className="space-y-4">
            <Progress job={selectedJob} />
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Command">{clampText(selectedJob.command)}</Field>
              <Field label="Created">{clampText(selectedJob.created_at)}</Field>
              <Field label="Finished">{clampText(selectedJob.finished_at)}</Field>
            </div>
            <LogTail lines={selectedJob.log_tail || selectedJob.logs || selectedJob.events} />
          </div>
        ) : <Empty title="No run selected">Choose a run from the left column.</Empty>}
      </Panel>
    </div>
  );
}

function LibraryPage({ books, identities, uploads, query, setQuery, onSelectBook }) {
  const filteredBooks = useFiltered(books, query, ["name", "path", "series_id"]);
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <Panel title="Book library" subtitle="Database-backed books and their analysis readiness." action={<SearchBox value={query} onChange={setQuery} placeholder="Search books..." />}>
        <List>
          {filteredBooks.map((book) => (
            <button key={book.path || book.name} onClick={() => onSelectBook(book.path)} className="w-full rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-left hover:border-sky-500/50">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-black text-white">{book.name || "Untitled book"}</p>
                  <p className="mt-1 text-xs text-slate-500">{shortRef(book.path)}</p>
                </div>
                <Badge tone={statusTone(book.run_status)}>{book.run_status || "ready"}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
                <Mini label="Scenes" value={book.scenes} />
                <Mini label="Events" value={book.event_ledger || book.events} />
                <Mini label="Entities" value={book.entity_registry || book.entities} />
                <Mini label="Prompts" value={book.visual_prompts} />
                <Mini label="Images" value={book.generated_images} />
              </div>
            </button>
          ))}
        </List>
      </Panel>
      <div className="space-y-5">
        <Panel title="Identity bundles" subtitle="BookNLP-clean identity memory stored for series/book analysis.">
          <List>
            {identities.slice(0, 8).map((identity) => (
              <div key={identity.series_id || identity.source_path} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
                <p className="font-black text-white">{identity.series_id || "Identity bundle"}</p>
                <p className="mt-1 text-xs text-slate-500">{identity.provider || "booknlp_clean"}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Mini label="Characters" value={identity.character_count} />
                  <Mini label="Aliases" value={identity.alias_count} />
                </div>
              </div>
            ))}
          </List>
        </Panel>
        <Panel title="Uploads" subtitle="Books uploaded through the local dashboard runtime.">
          <List>
            {uploads.slice(0, 6).map((upload) => (
              <div key={upload.id || upload.path} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
                <p className="font-black text-white">{upload.original_name || upload.name}</p>
                <p className="mt-1 text-xs text-slate-500">{shortRef(upload.stored_path || upload.path)}</p>
              </div>
            ))}
          </List>
        </Panel>
      </div>
    </div>
  );
}

function AnalysisPage({ books, selectedBook, setSelectedBook, bookView, loading, section, setSection, query, setQuery, entities, scenes, events, relationships, timeline, states }) {
  const filteredEntities = useFiltered(entities, query, ["name", "entity_type", "entity_context"]);
  const filteredEvents = useFiltered(events, query, ["title", "summary", "event_text", "location", "event_type"]);
  const filteredScenes = useFiltered(scenes, query, ["scene_title", "scene_summary", "full_text"]);
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <Panel title="Analyses" subtitle="Choose a database-backed book.">
        <List>
          {books.map((book) => (
            <button key={book.path || book.name} onClick={() => setSelectedBook(book.path)} className={classNames("w-full rounded-2xl border p-4 text-left", selectedBook === book.path ? "border-sky-400 bg-sky-500/10" : "border-slate-800 bg-slate-900/40 hover:border-sky-500/50")}>
              <p className="font-black text-white">{book.name || "Untitled book"}</p>
              <p className="mt-1 text-xs text-slate-500">{shortRef(book.path)}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Mini label="Scenes" value={book.scenes} />
                <Mini label="Entities" value={book.entity_registry || book.entities} />
              </div>
            </button>
          ))}
        </List>
      </Panel>
      <Panel
        title={bookView?.summary?.name || "Analysis workspace"}
        subtitle={selectedBook ? shortRef(selectedBook) : "Select a book to inspect database-backed analysis."}
        action={selectedBook ? <a className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-bold text-emerald-100" href={`/runtime/export-book-json?path=${encodeURIComponent(selectedBook)}`}>Download JSON</a> : null}
      >
        {loading ? <Empty title="Loading analysis">Reading the selected book from the runtime.</Empty> : null}
        {!loading && !bookView ? <Empty title="No analysis selected">Choose a book from the left column.</Empty> : null}
        {bookView ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {ANALYSIS_SECTIONS.map((item) => (
                <button key={item} onClick={() => setSection(item)} className={classNames("rounded-xl border px-3 py-2 text-sm font-bold", section === item ? "border-sky-400 bg-sky-500/15 text-white" : "border-slate-800 bg-slate-950 text-slate-300")}>
                  {item}
                </button>
              ))}
            </div>
            <SearchBox value={query} onChange={setQuery} placeholder={`Search ${section.toLowerCase()}...`} />
            {section === "Entities" ? <EntitySection entities={filteredEntities} /> : null}
            {section === "Scenes" ? <SceneSection scenes={filteredScenes} /> : null}
            {section === "Events" ? <EventSection events={filteredEvents} /> : null}
            {section === "Relationships" ? <RelationshipSection relationships={relationships} /> : null}
            {section === "Timeline" ? <TimelineSection timeline={timeline} /> : null}
            {section === "States" ? <StateSection states={states} /> : null}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

function EntitySection({ entities }) {
  const grouped = useMemo(() => {
    const result = Object.fromEntries(ASSET_GROUPS.map((group) => [group, []]));
    entities.forEach((entity) => result[entityBucket(entity.entity_type)].push(entity));
    return result;
  }, [entities]);
  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-5">
        {ASSET_GROUPS.map((group) => <Metric key={group} label={group} value={num(grouped[group]?.length)} detail="entities" />)}
      </div>
      {ASSET_GROUPS.map((group) => grouped[group]?.length ? (
        <div key={group}>
          <h3 className="mb-3 text-sm font-black uppercase tracking-[0.2em] text-slate-500">{group}</h3>
          <CardGrid>
            {grouped[group].map((entity, index) => <EntityCard key={`${entity.name}-${index}`} entity={entity} />)}
          </CardGrid>
        </div>
      ) : null)}
    </div>
  );
}

function EntityCard({ entity }) {
  const baseline = entity.first_appearance_profile?.baseline_description || entity.initial_physical_description?.description || entity.entity_context;
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="mb-3 flex flex-wrap gap-2">
        <Badge tone="blue">{entity.entity_type || "entity"}</Badge>
        <Badge>{num(entity.mention_count)} mentions</Badge>
      </div>
      <h3 className="text-lg font-black text-white">{entity.name || "Unnamed entity"}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-300">{clampText(baseline)}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Field label="Persistent traits">{clampText(entity.persistent_traits || entity.typed_attributes)}</Field>
        <Field label="Visual prompt">{clampText(entity.baseline_visual_prompt, "No prompt generated")}</Field>
      </div>
    </article>
  );
}

function SceneSection({ scenes }) {
  if (!scenes.length) return <Empty title="No scenes">Scenes are not available for this book.</Empty>;
  return (
    <List>
      {scenes.map((scene, index) => (
        <article key={scene.scene_id || index} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge>chapter {scene.chapter_index || "?"}</Badge>
            <Badge>scene {scene.scene_index || index + 1}</Badge>
          </div>
          <h3 className="text-lg font-black text-white">{scene.scene_title || scene.title || scene.scene_summary || "Untitled scene"}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">{clampText(scene.scene_summary)}</p>
          <details className="mt-4">
            <summary className="cursor-pointer text-sm font-bold text-sky-200">Read stored scene text</summary>
            <p className="mt-3 whitespace-pre-wrap rounded-2xl bg-black/25 p-4 text-sm leading-7 text-slate-200">{clampText(scene.full_text || scene.text || scene.scene_text)}</p>
          </details>
        </article>
      ))}
    </List>
  );
}

function EventSection({ events }) {
  if (!events.length) return <Empty title="No events">The event agent has not produced events for this book.</Empty>;
  return (
    <List>
      {events.map((event, index) => (
        <article key={event.id || event.event_id || index} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge>chapter {event.chapter_index || "?"}</Badge>
            <Badge>scene {event.scene_index || "?"}</Badge>
            <Badge tone="blue">{event.event_type || event.type || "event"}</Badge>
          </div>
          <h3 className="text-lg font-black text-white">{event.title || event.summary || event.event_text || "Untitled event"}</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Field label="Participants">{clampText(event.participants || event.characters_involved)}</Field>
            <Field label="Location">{clampText(event.location || event.locations_involved)}</Field>
            <Field label="Reason">{clampText(event.reason || event.cause)}</Field>
            <Field label="Outcome">{clampText(event.outcome || event.consequence)}</Field>
          </div>
        </article>
      ))}
    </List>
  );
}

function RelationshipSection({ relationships }) {
  if (!relationships.length) return <Empty title="No relationships">Relationship rows are not available for this book yet.</Empty>;
  return <CardGrid>{relationships.map((item, index) => <EntityCard key={index} entity={{ name: item.name || item.pair || item.source, entity_type: item.relationship_type || "relationship", entity_context: item.summary || item.description || item.evidence }} />)}</CardGrid>;
}

function TimelineSection({ timeline }) {
  if (!timeline.length) return <Empty title="No timeline">Timeline rows are not available for this book yet.</Empty>;
  return (
    <List>
      {timeline.map((row, index) => (
        <article key={row.id || index} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
          <Badge>#{row.row_index || index + 1}</Badge>
          <h3 className="mt-3 text-lg font-black text-white">{row.title || row.summary || "Timeline event"}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">{clampText(row.description || row.event_text || row.summary)}</p>
        </article>
      ))}
    </List>
  );
}

function StateSection({ states }) {
  if (!states.length) return <Empty title="No stable states">Stable character states are not available for this book yet.</Empty>;
  return <CardGrid>{states.map((state, index) => <EntityCard key={index} entity={{ name: state.character_name || state.name, entity_type: "state", entity_context: state.summary || state.state_summary, persistent_traits: state }} />)}</CardGrid>;
}

function AssetsPage({ bookView, books, selectedBook, setSelectedBook, visualInventory, group, setGroup, query, setQuery, onRenderBook, onRenderSeries }) {
  const currentSeries = bookView?.summary?.series_id || books.find((book) => book.path === selectedBook)?.series_id || "";
  const filtered = useFiltered(visualInventory, query, ["name", "entity_type", "baseline_prompt", "baseline_visual_prompt"]);
  const grouped = useMemo(() => {
    const result = Object.fromEntries(ASSET_GROUPS.map((item) => [item, []]));
    filtered.forEach((item) => result[entityBucket(item.entity_type)].push(item));
    return result;
  }, [filtered]);
  return (
    <div className="space-y-5">
      <Panel
        title="Visual asset command deck"
        subtitle="One visual prompt per entity, plus generated image paths when rendering has completed."
        action={<div className="flex flex-wrap gap-2"><Button onClick={onRenderBook} variant="primary" disabled={!selectedBook}>Render selected book</Button><Button onClick={() => renderSeriesGuard(currentSeries, onRenderSeries)} disabled={!currentSeries}>Render series</Button></div>}
      >
        <div className="grid gap-3 md:grid-cols-[320px_1fr]">
          <select value={selectedBook} onChange={(event) => setSelectedBook(event.target.value)} className="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100">
            {books.map((book) => <option key={book.path} value={book.path}>{book.name || book.path}</option>)}
          </select>
          <SearchBox value={query} onChange={setQuery} placeholder="Search visual prompts and entities..." />
        </div>
      </Panel>
      <Panel title="Visual inventory" subtitle="Grouped to match the entity registry so the mapping is easy to verify.">
        <div className="mb-4 flex flex-wrap gap-2">
          {ASSET_GROUPS.map((item) => (
            <button key={item} onClick={() => setGroup(item)} className={classNames("rounded-xl border px-3 py-2 text-sm font-bold", group === item ? "border-sky-400 bg-sky-500/15 text-white" : "border-slate-800 bg-slate-950 text-slate-300")}>
              {item} - {num(grouped[item]?.length)}
            </button>
          ))}
        </div>
        <CardGrid>
          {asArray(grouped[group]).map((item, index) => <VisualCard key={`${item.name}-${index}`} item={item} />)}
        </CardGrid>
        {!grouped[group]?.length ? <Empty title="No visuals in this group">Generate prompts or select a different book/group.</Empty> : null}
      </Panel>
    </div>
  );
}

function renderSeriesGuard(seriesId, onRenderSeries) {
  if (seriesId) onRenderSeries(seriesId);
}

function VisualCard({ item }) {
  const imagePath = item.generated_image_path || item.generated_image?.path || item.image_path;
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="mb-3 flex flex-wrap gap-2">
        <Badge tone="blue">{item.entity_type || "entity"}</Badge>
        {imagePath ? <Badge tone="green">image ready</Badge> : <Badge tone="amber">prompt only</Badge>}
      </div>
      <h3 className="text-lg font-black text-white">{item.name || "Unnamed entity"}</h3>
      {imagePath ? <img alt={item.name || "generated visual"} src={`/runtime/file?path=${encodeURIComponent(imagePath)}`} className="mt-4 max-h-96 w-full rounded-2xl border border-slate-800 object-contain bg-black" /> : null}
      <Field label="Positive prompt">{clampText(item.baseline_prompt || item.baseline_visual_prompt)}</Field>
    </article>
  );
}

function StoriesPage({ stories, books, selectedBook, decoder, setDecoder, onStartStory }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[460px_1fr]">
      <Panel title="Generate story" subtitle="Create database-backed decoder jobs with explicit mode, length, POV, and continuity controls.">
        <div className="space-y-3">
          <select value={decoder.book_ref || selectedBook} onChange={(event) => setDecoder((value) => ({ ...value, book_ref: event.target.value }))} className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100">
            <option value="">Choose source book/context</option>
            {books.map((book) => <option key={book.path} value={book.path}>{book.name || book.path}</option>)}
          </select>
          <select value={decoder.story_mode} onChange={(event) => setDecoder((value) => ({ ...value, story_mode: event.target.value }))} className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100">
            {STORY_MODES.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
          </select>
          <input type="number" min="1" max="80" value={decoder.chapter_count} onChange={(event) => setDecoder((value) => ({ ...value, chapter_count: Number(event.target.value) }))} className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100" />
          <input value={decoder.primary_pov_character} onChange={(event) => setDecoder((value) => ({ ...value, primary_pov_character: event.target.value }))} placeholder="Primary POV character" className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100" />
          <textarea value={decoder.user_prompt} onChange={(event) => setDecoder((value) => ({ ...value, user_prompt: event.target.value }))} placeholder="Story request, premise, constraints, tone..." className="min-h-40 w-full rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-100" />
          <Button onClick={onStartStory} variant="primary">Start decoder job</Button>
        </div>
      </Panel>
      <Panel title="Generated stories" subtitle="Stored decoder outputs with EPUB export.">
        <List>
          {stories.map((story) => (
            <article key={story.id} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-black text-white">{story.title || "Untitled story"}</p>
                  <p className="mt-1 text-sm text-slate-400">{story.story_mode || story.mode} - {num(story.chapter_count || asArray(story.chapters).length)} chapters</p>
                </div>
                <a className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-bold text-emerald-100" href={`/runtime/export-generated-story-epub?story_id=${encodeURIComponent(story.id)}`}>Export EPUB</a>
              </div>
            </article>
          ))}
        </List>
      </Panel>
    </div>
  );
}

function ProvidersPage({ providers, statuses, onRefresh }) {
  const names = ["ollama", "general_compute", "codex"];
  return (
    <Panel title="Provider operations" subtitle="Configured provider accounts and latest stored health checks. Secrets stay masked in the UI." action={<Button onClick={onRefresh} variant="primary">Refresh provider health</Button>}>
      <div className="grid gap-4 xl:grid-cols-3">
        {names.map((name) => {
          const config = providers[name] || statuses[name]?.config || {};
          const statusRows = statuses[name]?.statuses || statuses[name] || [];
          return (
            <div key={name} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
              <h3 className="text-lg font-black text-white">{labelize(name)}</h3>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Mini label="Accounts" value={asArray(config.accounts).length} />
                <Mini label="Status rows" value={asArray(statusRows).length} />
              </div>
              <List className="mt-4">
                {asArray(config.accounts).map((account, index) => (
                  <div key={account.label || index} className="rounded-xl bg-black/25 p-3">
                    <p className="font-bold text-white">{account.label || `account ${index + 1}`}</p>
                    <p className="text-xs text-slate-500">{account.email || account.base_url || "local/session account"}</p>
                  </div>
                ))}
              </List>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function DiagnosticsPage({ prompts, reports, selectedJob, runtime }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
      <Panel title="Prompt inspector" subtitle="Source prompt files discovered by the runtime. This is intentionally a diagnostics view.">
        <List>
          {prompts.map((prompt) => (
            <details key={prompt.path} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
              <summary className="cursor-pointer font-black text-white">{prompt.name || prompt.path}</summary>
              <p className="mt-1 text-xs text-slate-500">{prompt.path} - {num(prompt.line_count)} lines</p>
              <pre className="mt-4 max-h-80 overflow-auto rounded-2xl bg-black p-4 text-xs text-slate-300">{prompt.content}</pre>
            </details>
          ))}
        </List>
      </Panel>
      <div className="space-y-5">
        <Panel title="Selected job logs" subtitle="Raw log tail for debugging failures.">
          <LogTail lines={selectedJob?.log_tail || selectedJob?.logs || []} />
        </Panel>
        <Panel title="Runtime snapshot" subtitle="High-level runtime metadata, not a primary data browser.">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Loaded at">{clampText(runtime?.loaded_at)}</Field>
            <Field label="Reports">{num(reports.length)}</Field>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function List({ children, className = "" }) {
  const items = React.Children.toArray(children).filter(Boolean);
  if (!items.length) return <Empty />;
  return <div className={classNames("space-y-3", className)}>{items}</div>;
}

function CardGrid({ children }) {
  const items = React.Children.toArray(children).filter(Boolean);
  if (!items.length) return <Empty />;
  return <div className="grid gap-4 xl:grid-cols-2">{items}</div>;
}

function Mini({ label, value }) {
  return (
    <div className="rounded-xl bg-black/30 p-3">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-black text-white">{value === undefined || value === null || value === "" ? "0" : num(value)}</p>
    </div>
  );
}

export default App;
