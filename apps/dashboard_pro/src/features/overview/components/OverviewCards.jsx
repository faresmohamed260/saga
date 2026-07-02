import { Link } from "react-router-dom";
import { Badge, Button, DataCard, EmptyState, Panel, Toolbar, shortRef, toneFor } from "../../../components/ui/primitives";

export function OperationsPanel({ jobs }) {
  return (
    <Panel
      title="Current Operations"
      subtitle="Latest persisted dashboard jobs, with direct links into the run monitor."
      action={<Button asLink="/import/new" variant="primary">New import</Button>}
    >
      {jobs.length ? (
        <div className="grid gap-3">
          {jobs.slice(0, 6).map((job) => (
            <OperationCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <EmptyState title="No jobs recorded">Start with Import to stage books or use Decoder/Visual Assets for focused jobs.</EmptyState>
      )}
    </Panel>
  );
}

function OperationCard({ job }) {
  return (
    <DataCard as={Link} to={`/runs/${encodeURIComponent(job.id)}`} interactive className="block">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-black text-white" title={job.id}>{job.id}</p>
          <p className="mt-1 text-sm text-slate-400">{job.type || job.job_type || "job"} - {job.progress?.label || "no active progress"}</p>
        </div>
        <Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge>
      </div>
    </DataCard>
  );
}

export function CanonLibraryPanel({ books }) {
  return (
    <Panel title="Canon Library" subtitle="Database-backed books available for inspection and decoder context.">
      {books.length ? (
        <div className="grid gap-3">
          {books.slice(0, 8).map((book) => (
            <LibraryPreviewCard key={book.path || book.book_id} book={book} />
          ))}
        </div>
      ) : (
        <EmptyState title="No books in the database yet">Use the Import workflow to stage and validate source books.</EmptyState>
      )}
    </Panel>
  );
}

function LibraryPreviewCard({ book }) {
  const bookRef = book.path || `db://book/${book.book_id}`;
  return (
    <DataCard as={Link} to={`/books/${encodeURIComponent(bookRef)}/analysis/entities`} interactive className="block">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-black text-white">{book.name || book.title}</p>
          <p className="mt-1 text-sm text-slate-500">{shortRef(bookRef)}</p>
        </div>
        <Badge tone="blue">{book.series_id || "series n/a"}</Badge>
      </div>
      <Toolbar className="mt-4">
        <Badge>{book.scenes || 0} scenes</Badge>
        <Badge>{book.entity_registry || 0} entities</Badge>
      </Toolbar>
    </DataCard>
  );
}
