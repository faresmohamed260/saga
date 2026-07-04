import { Outlet, useLocation } from "react-router-dom";
import { StatusBanner } from "./primitives";
import { useRuntimeState } from "../hooks/useRuntimeState";
import { ErrorBoundary } from "./ErrorBoundary";
import { NAV_ITEMS } from "./navConfig";
import { ShellHeader, ShellNav } from "./ShellHeader";

export function AppShell() {
  const location = useLocation();
  const { state, loading, error, reload } = useRuntimeState();
  const routeKey = `${location.pathname}${location.search}`;
  const jobs = state?.jobs || [];
  const active = jobs.find((job) => ["running", "queued", "starting", "validating", "staging"].includes(String(job.status || "").toLowerCase()));
  const latestCompleted = jobs.find((job) => ["completed", "success"].includes(String(job.status || "").toLowerCase()));
  const latest = active || latestCompleted || jobs[0];
  const latestLabel = loading ? "loading" : active ? active.status : latestCompleted ? "idle" : latest?.status || "idle";
  const latestDetail = active ? active.type || active.id : latestCompleted ? `last complete: ${latestCompleted.type || latestCompleted.id}` : "no active job";
  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto max-w-[1800px] px-4 py-4 md:px-5 md:py-5">
        <ShellHeader state={state} loading={loading} latestLabel={latestLabel} latestDetail={latestDetail} onRefresh={reload} />
        {error ? <div className="mt-4"><StatusBanner tone="red" message={error} /></div> : null}
        <ShellNav items={NAV_ITEMS} />
        <main className="mt-5">
          <ErrorBoundary key={routeKey}>
            <Outlet context={{ state, reload }} />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
