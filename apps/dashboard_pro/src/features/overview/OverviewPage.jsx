import { Link } from "react-router-dom";
import { Badge, Button, EmptyState, Metric, Panel, toneFor } from "../../components/ui/primitives";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function OverviewPage() {
  const { state } = useRuntimeState();
  const artifacts = state?.artifacts || {};
  const database = artifacts.database || {};
  const jobs = state?.jobs || [];
  const books = artifacts.books || [];
  const latestJob = jobs[0];
  const storyCount = Number(database.generated_stories || 0);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Books" value={books.length} detail="database" tone="green" />
        <Metric label="Jobs" value={jobs.length} detail={latestJob?.status || "idle"} tone={toneFor(latestJob?.status)} />
        <Metric label="Stories" value={storyCount} detail="generated" tone="blue" />
        <Metric label="Prompts" value={state?.prompts?.length || 0} detail="inspectable" tone="slate" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <Panel
          title="Current Operations"
          subtitle="Latest persisted dashboard jobs, with direct links into the run monitor."
          action={<Button asLink="/import/new" variant="primary">New import</Button>}
        >
          {jobs.length ? (
            <div className="space-y-3">
              {jobs.slice(0, 6).map((job) => (
                <Link key={job.id} to={`/runs/${encodeURIComponent(job.id)}`} className="block rounded-2xl border border-slate-800 bg-slate-900/45 p-4 transition hover:border-sky-500/60">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-black text-white">{job.id}</p>
                      <p className="mt-1 text-sm text-slate-400">{job.type || job.job_type || "job"} - {job.progress?.label || "no active progress"}</p>
                    </div>
                    <Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="No jobs recorded">Start with Import to stage books or use Decoder/Visual Assets for focused jobs.</EmptyState>
          )}
        </Panel>

        <Panel title="Canon Library" subtitle="Database-backed books available for inspection and decoder context.">
          {books.length ? (
            <div className="space-y-3">
              {books.slice(0, 8).map((book) => (
                <Link key={book.path || book.book_id} to={`/books/${encodeURIComponent(book.path || `db://book/${book.book_id}`)}/analysis/entities`} className="block rounded-2xl bg-black/25 p-4 hover:bg-sky-500/10">
                  <p className="font-black text-white">{book.name || book.title}</p>
                  <p className="mt-1 text-sm text-slate-500">{book.series_id || "series n/a"} - {book.scenes || 0} scenes - {book.entity_registry || 0} entities</p>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="No books in the database yet">Use the Import workflow to stage and validate source books.</EmptyState>
          )}
        </Panel>
      </div>
    </div>
  );
}
