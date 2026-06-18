import { NavLink, Outlet } from "react-router-dom";
import { Badge, Button } from "../ui/primitives";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { ErrorBoundary } from "../feedback/ErrorBoundary";

const NAV = [
  ["/overview", "Overview"],
  ["/import/new", "Import"],
  ["/runs", "Runs"],
  ["/books", "Library"],
  ["/assets", "Visual Assets"],
  ["/stories", "Decoder"],
  ["/providers", "Providers"],
  ["/diagnostics", "Diagnostics"],
];

export function AppShell() {
  const { state, loading, error, reload } = useRuntimeState();
  const jobs = state?.jobs || [];
  const active = jobs.find((job) => ["running", "queued", "starting", "validating", "staging"].includes(String(job.status || "").toLowerCase()));
  const latestCompleted = jobs.find((job) => ["completed", "success"].includes(String(job.status || "").toLowerCase()));
  const latest = active || latestCompleted || jobs[0];
  const latestLabel = loading ? "loading" : active ? active.status : latestCompleted ? "idle" : latest?.status || "idle";
  const latestDetail = active ? active.type || active.id : latestCompleted ? `last complete: ${latestCompleted.type || latestCompleted.id}` : "no active job";
  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto max-w-[1800px] px-5 py-5">
        <header className="overflow-hidden rounded-[2rem] border border-slate-800 bg-[linear-gradient(135deg,rgba(15,23,42,.95),rgba(2,6,23,.85)),radial-gradient(circle_at_80%_20%,rgba(14,165,233,.22),transparent_32%)] p-7">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <div className="mb-4 flex flex-wrap gap-2">
                <Badge tone="blue">Database-backed</Badge>
                <Badge tone="green">Production dashboard</Badge>
                <Badge>No mock controls</Badge>
              </div>
              <h1 className="text-4xl font-black tracking-tight text-white">S.A.G.A. Operations Console</h1>
              <p className="mt-3 max-w-4xl text-base leading-7 text-slate-300">
                Import books, monitor analysis jobs, inspect canon data, manage visual assets, and generate stories from real backend workflows.
              </p>
              <p className="mt-3 text-sm text-slate-500">{state?.workspace?.root || "Loading project root..."}</p>
            </div>
            <div className="min-w-[240px] rounded-3xl border border-emerald-500/40 bg-emerald-500/10 p-5 text-right">
              <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-200">Latest activity</p>
              <p className="mt-2 text-2xl font-black text-white">{latestLabel}</p>
              <p className="mt-2 text-xs leading-5 text-emerald-100/80">{latestDetail}</p>
              <Button className="mt-4" onClick={reload}>Refresh</Button>
            </div>
          </div>
        </header>
        {error ? <div className="mt-4 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-100">{error}</div> : null}
        <nav className="sticky top-0 z-20 mt-5 flex flex-wrap gap-2 border-b border-slate-900 bg-[#081013]/90 py-3 backdrop-blur-xl">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => `rounded-2xl border px-4 py-2 text-sm font-black transition ${isActive ? "border-sky-400 bg-sky-500/15 text-white" : "border-slate-800 bg-slate-950/70 text-slate-300 hover:border-slate-600"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="mt-5">
          <ErrorBoundary>
            <Outlet context={{ state, reload }} />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
