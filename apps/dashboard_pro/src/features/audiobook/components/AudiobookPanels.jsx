import { runtimeApi } from "../../../api/runtimeApi";
import { Badge, Button, DataCard, EmptyState, Field, Panel, SearchBox, SelectInput, StatusBanner, TextInput, Toolbar, toneFor } from "../../../components/ui/primitives";
import { chapterLabel, formatRunLabel } from "../audiobookUtils";

export function AudiobookNotice({ notice }) {
  if (!notice?.text) return null;
  return <StatusBanner tone={notice.tone} message={notice.text} />;
}

export function AudiobookControlsPanel({
  plan,
  seriesRows,
  seriesBooks,
  selectedSeries,
  canStage,
  stageSubmitting,
  queueSubmitting,
  onPlanChange,
  onStagePlan,
  onQueuePlan,
}) {
  return (
    <Panel
      title="Audiobook Controls"
      subtitle="Select a series, scope it to one book or a full series, then stage or run audiobook production."
    >
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <Button onClick={() => onPlanChange((current) => ({ ...current, scope: "book" }))} variant={plan.scope === "book" ? "primary" : "secondary"}>
            Single book
          </Button>
          <Button onClick={() => onPlanChange((current) => ({ ...current, scope: "series" }))} variant={plan.scope === "series" ? "primary" : "secondary"}>
            Entire series
          </Button>
        </div>

        <Field label="Series">
          <SelectInput value={plan.seriesId} onChange={(event) => onPlanChange((current) => ({ ...current, seriesId: event.target.value, bookRef: "" }))}>
            {!seriesRows.length ? <option value="">No series available</option> : null}
            {seriesRows.map((row) => (
              <option key={row.series_id} value={row.series_id}>
                {(row.title || row.series_id) + (row.book_count ? ` (${row.book_count} books)` : "")}
              </option>
            ))}
          </SelectInput>
        </Field>

        {plan.scope === "book" ? (
          <Field label="Book">
            <SelectInput value={plan.bookRef} onChange={(event) => onPlanChange((current) => ({ ...current, bookRef: event.target.value }))}>
              {!seriesBooks.length ? <option value="">No books available</option> : null}
              {seriesBooks.map((book) => (
                <option key={book.book_id} value={`db://book/${book.book_id}`}>
                  {book.title}
                </option>
              ))}
            </SelectInput>
          </Field>
        ) : (
          <Field label="Series scope">
            {seriesBooks.length
              ? `${seriesBooks.length} books from ${selectedSeries?.title || plan.seriesId} will be narrated in library order.`
              : "No books are currently available for the selected series."}
          </Field>
        )}

        <Field label="Narration tone">
          <SelectInput value={plan.tone} onChange={(event) => onPlanChange((current) => ({ ...current, tone: event.target.value }))}>
            <option value="classic">classic</option>
            <option value="dramatic">dramatic</option>
            <option value="epic">epic</option>
          </SelectInput>
        </Field>

        <Field label="Rewrite provider">
          <SelectInput value={plan.rewriteProvider} onChange={(event) => onPlanChange((current) => ({ ...current, rewriteProvider: event.target.value }))}>
            <option value="ollama">ollama</option>
            <option value="general_compute">general_compute</option>
            <option value="codex">codex</option>
            <option value="mistral">mistral</option>
            <option value="gemini">gemini</option>
          </SelectInput>
        </Field>

        <Field label="Rewrite fallback">
          <SelectInput value={plan.rewriteFallbackMode} onChange={(event) => onPlanChange((current) => ({ ...current, rewriteFallbackMode: event.target.value }))}>
            <option value="strict_rewrite">require rewrite success</option>
            <option value="fallback_to_source">fallback to source text on rewrite failure</option>
          </SelectInput>
        </Field>

        <Field label="Voice profile">
          <SelectInput value={plan.voice} onChange={(event) => onPlanChange((current) => ({ ...current, voice: event.target.value }))}>
            <option value="af_bella">af_bella</option>
            <option value="af_sarah">af_sarah</option>
            <option value="am_adam">am_adam</option>
            <option value="bf_emma">bf_emma</option>
          </SelectInput>
        </Field>

        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Sample Rate">
            <TextInput type="number" min="8000" step="1000" value={plan.sampleRate} onChange={(event) => onPlanChange((current) => ({ ...current, sampleRate: event.target.value }))} />
          </Field>
          <Field label="Audio Format">
            <SelectInput value={plan.audioFormat} onChange={(event) => onPlanChange((current) => ({ ...current, audioFormat: event.target.value }))}>
              <option value="wav">wav</option>
              <option value="flac">flac</option>
            </SelectInput>
          </Field>
        </div>

        <Field label="Normalization">
          <SelectInput value={plan.normalizeAudio ? "on" : "off"} onChange={(event) => onPlanChange((current) => ({ ...current, normalizeAudio: event.target.value === "on" }))}>
            <option value="on">normalize audio</option>
            <option value="off">keep original levels</option>
          </SelectInput>
        </Field>

        <Field label="Silence Trim">
          <SelectInput value={plan.trimSilence ? "on" : "off"} onChange={(event) => onPlanChange((current) => ({ ...current, trimSilence: event.target.value === "on" }))}>
            <option value="off">keep natural pauses</option>
            <option value="on">trim silence</option>
          </SelectInput>
        </Field>

        <Field label="Sentence Pause (ms)">
          <TextInput type="number" min="0" step="50" value={plan.sentencePauseMs} onChange={(event) => onPlanChange((current) => ({ ...current, sentencePauseMs: event.target.value }))} />
        </Field>

        <Field label="Storage">
          Transcript rows and audio paths are always stored for audiobook runs.
        </Field>

        <Toolbar>
          <Button onClick={onStagePlan} disabled={!canStage || stageSubmitting}>
            {stageSubmitting ? "Staging..." : "Stage outputs"}
          </Button>
          <Button variant="primary" onClick={onQueuePlan} disabled={!canStage || queueSubmitting}>
            {queueSubmitting ? "Queueing..." : "Queue audiobook pipeline"}
          </Button>
        </Toolbar>
      </div>
    </Panel>
  );
}

export function AudiobookLibraryPanel({
  selectedBrowserSeries,
  existingOutputs,
  libraryOpen,
  onToggleLibrary,
  seriesRows,
  browserSeriesId,
  onBrowserSeriesChange,
  selectedRunId,
  onSelectedRunChange,
  visibleRuns,
  selectedRun,
}) {
  return (
    <Panel title="Audiobook Library" subtitle="Browse stored audiobook runs and playable outputs without touching the control panel.">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-100">{selectedBrowserSeries?.title || "Select a series"}</p>
            <p className="text-sm text-slate-400">{existingOutputs} stored run{existingOutputs === 1 ? "" : "s"} available</p>
          </div>
          <Button variant="secondary" onClick={onToggleLibrary}>
            {libraryOpen ? "Collapse library" : "Expand library"}
          </Button>
        </div>

        {libraryOpen ? (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Library series">
                <SelectInput value={browserSeriesId} onChange={(event) => onBrowserSeriesChange(event.target.value)}>
                  {!seriesRows.length ? <option value="">No series available</option> : null}
                  {seriesRows.map((row) => (
                    <option key={row.series_id} value={row.series_id}>
                      {(row.title || row.series_id) + (row.book_count ? ` (${row.book_count} books)` : "")}
                    </option>
                  ))}
                </SelectInput>
              </Field>

              <Field label="Stored run">
                <SelectInput value={selectedRunId} onChange={(event) => onSelectedRunChange(event.target.value)}>
                  {!visibleRuns.length ? <option value="">No stored runs available</option> : null}
                  {visibleRuns.map((run) => (
                    <option key={run.id} value={run.id}>
                      {`${run.title || "Audiobook run"} - ${run.status || "unknown"}`}
                    </option>
                  ))}
                </SelectInput>
              </Field>
            </div>

            {selectedRun ? <SelectedRunCard run={selectedRun} /> : null}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function SelectedRunCard({ run }) {
  return (
    <DataCard>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-black text-white">{run.title || "Audiobook run"}</p>
          <p className="mt-1 text-sm text-slate-400">{formatRunLabel(run)}</p>
        </div>
        <Badge tone={toneFor(run.status)}>{run.status || "unknown"}</Badge>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <Field label="Voice">{run.voice || "Not set"}</Field>
        <Field label="Audio format">{run.audio_format || "wav"}</Field>
        <Field label="Updated">{run.updated_at || "n/a"}</Field>
      </div>
    </DataCard>
  );
}

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

function OutputsHeader({ selectedRun, playableChapters }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-slate-400">
        {playableChapters.length} downloadable file{playableChapters.length === 1 ? "" : "s"} ready
      </p>
      <Toolbar>
        <Badge tone={toneFor(selectedRun.status)}>{selectedRun.status || "unknown"}</Badge>
        {playableChapters.length ? (
          <a
            href={runtimeApi.audiobookRunBundleUrl(selectedRun.id)}
            download={`${selectedRun.title || "audiobook"}.wav`}
            className="rounded-lg border border-cyan-400/50 bg-cyan-400/10 px-4 py-2 text-sm font-bold text-cyan-100 transition hover:bg-cyan-400/20"
          >
            Download full audiobook
          </a>
        ) : null}
      </Toolbar>
    </div>
  );
}

function PlayableChapterList({
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

function ChapterOutputCard({ selectedRun, chapter, expanded, onToggle }) {
  const audioUrl = runtimeApi.audiobookChapterAudioUrl(selectedRun.id, chapter.chapter_id);
  const filename = `${selectedRun.title || "audiobook"}-book-${chapter.book_index || "x"}-chapter-${chapter.chapter_index || "x"}.${selectedRun.audio_format || "wav"}`;
  return (
    <DataCard className="bg-[#0b1117]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-black text-white">{chapter.chapter_title || `Chapter ${chapter.chapter_index || "?"}`}</p>
          <p className="mt-1 text-sm text-slate-400">{chapterLabel(chapter)}</p>
        </div>
        <Toolbar>
          <Button type="button" onClick={onToggle}>
            {expanded ? "Collapse" : "Expand"}
          </Button>
          <a
            href={audioUrl}
            download={filename}
            className="rounded-lg border border-emerald-400/50 bg-emerald-400/10 px-4 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-400/20"
          >
            Download
          </a>
        </Toolbar>
      </div>
      {expanded ? <audio className="mt-4 w-full" controls preload="none" src={audioUrl} /> : null}
    </DataCard>
  );
}
