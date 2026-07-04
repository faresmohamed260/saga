import { Link } from "react-router-dom";
import { Badge, DataCard, EmptyState, Panel, Toolbar, shortRef, toneFor } from "./primitives";

export function LibraryGrid({ books }) {
  return (
    <Panel title="Library" subtitle="Imported books ready for structured analysis.">
      {books.length ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {books.map((book) => (
            <BookCard key={book.path || book.book_id} book={book} />
          ))}
        </div>
      ) : (
        <EmptyState title="No books yet" />
      )}
    </Panel>
  );
}

function BookCard({ book }) {
  const bookRef = book.path || `db://book/${book.book_id}`;
  return (
    <DataCard as={Link} to={`/books/${encodeURIComponent(bookRef)}/analysis/scenes`} interactive className="block">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-lg font-black text-white">{book.name || book.title}</p>
          <p className="mt-2 truncate text-sm text-slate-500" title={bookRef}>{shortRef(bookRef)}</p>
        </div>
        <Badge tone={toneFor(book.run_status)}>{book.run_status || "status n/a"}</Badge>
      </div>
      <Toolbar className="mt-4">
        <Badge tone="blue">{book.scenes || 0} scenes</Badge>
        <Badge>{book.event_ledger || 0} events</Badge>
        <Badge tone="green">{book.entity_registry || 0} entities</Badge>
        <Badge>{book.series_id || "series n/a"}</Badge>
      </Toolbar>
    </DataCard>
  );
}
