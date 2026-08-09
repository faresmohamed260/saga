import { Button, Field, Panel, SelectInput, TextInput, Toolbar } from "../primitives";

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
