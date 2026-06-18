import { Link } from "react-router-dom";
import { EmptyState, Metric, Panel, shortRef } from "../../components/ui/primitives";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function LibraryPage() {
  const { state } = useRuntimeState();
  const books = state?.artifacts?.books || [];
  const series = Array.from(new Set(books.map((book) => book.series_id).filter(Boolean)));
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Books" value={books.length} detail="database" tone="green" />
        <Metric label="Series" value={series.length} detail="indexed" tone="blue" />
        <Metric label="Scenes" value={books.reduce((sum, book) => sum + Number(book.scenes || 0), 0)} detail="stored" tone="slate" />
      </div>
      <Panel title="Library" subtitle="Books available in SQLite. Open one to inspect structured analysis.">
        {books.length ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {books.map((book) => (
              <Link key={book.path || book.book_id} to={`/books/${encodeURIComponent(book.path || `db://book/${book.book_id}`)}/analysis/scenes`} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 hover:border-sky-500/60">
                <p className="font-black text-white">{book.name || book.title}</p>
                <p className="mt-2 text-sm text-slate-500">{shortRef(book.path || `db://book/${book.book_id}`)}</p>
                <div className="mt-4 grid grid-cols-4 gap-2 text-sm">
                  <span>{book.scenes || 0} scenes</span>
                  <span>{book.event_ledger || 0} events</span>
                  <span>{book.entity_registry || 0} entities</span>
                  <span>{book.run_status || "status n/a"}</span>
                </div>
              </Link>
            ))}
          </div>
        ) : <EmptyState title="No books found" />}
      </Panel>
    </div>
  );
}
