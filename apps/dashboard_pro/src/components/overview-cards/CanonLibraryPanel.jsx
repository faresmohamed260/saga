import { EmptyState, Panel } from "../primitives";
import { LibraryPreviewCard } from "./LibraryPreviewCard";

export function CanonLibraryPanel({ books }) {
  return (
    <Panel title="Canon Library" subtitle="Imported books ready for analysis, visual work, and story context.">
      {books.length ? (
        <div className="grid gap-3">
          {books.slice(0, 8).map((book) => (
            <LibraryPreviewCard key={book.path || book.book_id} book={book} />
          ))}
        </div>
      ) : (
        <EmptyState title="No books yet">Use Import to stage and validate source books.</EmptyState>
      )}
    </Panel>
  );
}
