import { Button, Field, Panel, SelectInput } from "../primitives";
import { SelectedRunCard } from "./SelectedRunCard";

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
