import { Link } from "react-router-dom";
import { Badge, DataCard, Toolbar, shortRef } from "../primitives";

export function LibraryPreviewCard({ book }) {
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
