import { Metric } from "../../components/ui/primitives";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { LibraryGrid } from "./components/LibraryCards";

export function LibraryPage() {
  const { state } = useRuntimeState();
  const books = state?.artifacts?.books || [];
  const series = Array.from(new Set(books.map((book) => book.series_id).filter(Boolean)));
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Books" value={books.length} detail="library" tone="green" />
        <Metric label="Series" value={series.length} detail="indexed" tone="blue" />
        <Metric label="Scenes" value={books.reduce((sum, book) => sum + Number(book.scenes || 0), 0)} detail="mapped" tone="slate" />
      </div>
      <LibraryGrid books={books} />
    </div>
  );
}
