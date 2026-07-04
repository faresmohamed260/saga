import { EmptyState, Panel } from "../primitives";
import { OutputsHeader } from "./OutputsHeader";
import { PlayableChapterList } from "./PlayableChapterList";

export function AudiobookOutputsPanel({
  selectedRun,
  runLoading,
  playableChapters,
  outputQuery,
  onOutputQueryChange,
  outputBookFilter,
  onOutputBookFilterChange,
  availableBookFilters,
  filteredPlayableChapters,
  expandedChapterIds,
  onToggleChapter,
}) {
  return (
    <Panel title="Outputs" subtitle="Playable audio files for the selected stored run.">
      {selectedRun ? (
        <div className="space-y-4">
          <OutputsHeader selectedRun={selectedRun} playableChapters={playableChapters} />
          {playableChapters.length ? (
            <PlayableChapterList
              selectedRun={selectedRun}
              outputQuery={outputQuery}
              onOutputQueryChange={onOutputQueryChange}
              outputBookFilter={outputBookFilter}
              onOutputBookFilterChange={onOutputBookFilterChange}
              availableBookFilters={availableBookFilters}
              chapters={filteredPlayableChapters}
              expandedChapterIds={expandedChapterIds}
              onToggleChapter={onToggleChapter}
            />
          ) : (
            <EmptyState title="No playable audio yet">
              This run does not have completed audio files available for playback or download yet.
            </EmptyState>
          )}
        </div>
      ) : runLoading ? (
        <EmptyState title="Loading run">Fetching the selected audiobook run.</EmptyState>
      ) : (
        <EmptyState title="No staged outputs">
          Select a stored run or stage a new audiobook scope to access playable audio files.
        </EmptyState>
      )}
    </Panel>
  );
}
