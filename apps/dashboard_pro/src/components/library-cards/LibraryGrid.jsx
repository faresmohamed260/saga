import { EmptyState, Panel } from "../primitives";
import { BookCard } from "./BookCard";

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
