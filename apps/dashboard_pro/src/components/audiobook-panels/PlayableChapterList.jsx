import { EmptyState, SearchBox, SelectInput } from "../primitives";
import { ChapterOutputCard } from "./ChapterOutputCard";

export function PlayableChapterList({
  selectedRun,
  outputQuery,
  onOutputQueryChange,
  outputBookFilter,
  onOutputBookFilterChange,
  availableBookFilters,
  chapters,
  expandedChapterIds,
  onToggleChapter,
}) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
        <SearchBox value={outputQuery} onChange={onOutputQueryChange} placeholder="Filter by chapter title, book, or chapter number" />
        <SelectInput value={outputBookFilter} onChange={(event) => onOutputBookFilterChange(event.target.value)}>
          <option value="all">All books</option>
          {availableBookFilters.map((bookIndex) => (
            <option key={bookIndex} value={bookIndex}>
              {`Book ${bookIndex}`}
            </option>
          ))}
        </SelectInput>
      </div>
      {chapters.map((chapter) => (
        <ChapterOutputCard
          key={chapter.chapter_id}
          selectedRun={selectedRun}
          chapter={chapter}
          expanded={expandedChapterIds.includes(chapter.chapter_id)}
          onToggle={() => onToggleChapter(chapter.chapter_id)}
        />
      ))}
      {!chapters.length ? (
        <EmptyState title="No matching outputs">
          Adjust the search or book filter to find a specific playable chapter.
        </EmptyState>
      ) : null}
    </div>
  );
}
