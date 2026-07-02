import { Badge, Button, DataCard, EmptyState, Field, Panel, SelectInput, TextArea, TextInput, Toolbar, toneFor } from "../../../components/ui/primitives";

export function DecoderControlsPanel({
  modes,
  payload,
  seriesRows,
  seriesBooks,
  providerRows,
  validation,
  modeRows,
  canStart,
  onPayloadChange,
  onValidate,
  onStart,
}) {
  return (
    <Panel title="Decoder Controls" subtitle="Validate a series-level generation plan before starting a story job.">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          {modes.map((mode) => (
            <Button
              key={mode}
              onClick={() => onPayloadChange({ ...payload, story_mode: mode })}
              variant={payload.story_mode === mode ? "primary" : "secondary"}
            >
              {mode.replaceAll("_", " ")}
            </Button>
          ))}
        </div>

        <Field label="Series">
          <SelectInput value={payload.series_id} onChange={(event) => onPayloadChange({ ...payload, series_id: event.target.value })}>
            {!seriesRows.length ? <option value="">No series available</option> : null}
            {seriesRows.map((row) => (
              <option key={row.series_id} value={row.series_id}>
                {(row.title || row.series_id) + (row.book_count ? ` (${row.book_count} books)` : "")}
              </option>
            ))}
          </SelectInput>
        </Field>

        {seriesBooks.length ? (
          <Field label="Series decoder scope">
            {`${seriesBooks.length} book${seriesBooks.length === 1 ? "" : "s"} available in this series. Decoder anchor is resolved automatically.`}
          </Field>
        ) : null}

        <Field label="Generation provider">
          <SelectInput value={payload.provider} onChange={(event) => onPayloadChange({ ...payload, provider: event.target.value })}>
            {!providerRows.length ? <option value="">No healthy providers available</option> : null}
            {providerRows.map((row) => (
              <option key={row.value} value={row.value}>
                {row.label}
              </option>
            ))}
          </SelectInput>
        </Field>

        <TextInput
          type="number"
          min="1"
          max="60"
          value={payload.chapter_count}
          onChange={(event) => onPayloadChange({ ...payload, chapter_count: Number(event.target.value) })}
        />

        <TextInput
          placeholder="Primary POV character"
          value={payload.primary_pov_character}
          onChange={(event) => onPayloadChange({ ...payload, primary_pov_character: event.target.value })}
        />

        <TextArea value={payload.user_prompt} onChange={(event) => onPayloadChange({ ...payload, user_prompt: event.target.value })} className="min-h-[180px]" />

        <Toolbar>
          <Button onClick={onValidate} disabled={!payload.series_id || !payload.provider}>
            Validate plan
          </Button>
          <Button onClick={onStart} disabled={!canStart} variant="primary">
            Start generation
          </Button>
        </Toolbar>

        {validation ? (
          <Field label={`Validation: ${validation.valid ? "ready" : "blocked"}`}>
            {[...(validation.errors || []), ...(validation.warnings || []), ...(modeRows.length ? [] : ["Decoder mode metadata unavailable."])]
              .join(" | ") || "Plan is ready."}
          </Field>
        ) : null}

        {!providerRows.length ? (
          <Field label="Provider health">No decoder providers are currently available. Refresh provider status before generating.</Field>
        ) : null}
      </div>
    </Panel>
  );
}

export function GeneratedStoriesPanel({ stories }) {
  return (
    <Panel title="Generated Stories" subtitle="Persisted stories and export links.">
      {stories.length ? (
        <div className="space-y-3">
          {stories.map((story) => (
            <GeneratedStoryCard key={story.id} story={story} />
          ))}
        </div>
      ) : (
        <EmptyState title="No generated stories" />
      )}
    </Panel>
  );
}

function GeneratedStoryCard({ story }) {
  return (
    <DataCard>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-black text-white">{story.title || story.id}</h3>
        <Badge tone={toneFor(story.status)}>{story.status || "unknown"}</Badge>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        {story.story_mode} / {story.primary_pov_character || "POV n/a"} / {story.series_id || story.series_title || "series n/a"}
      </p>
      <a
        className="mt-3 inline-flex rounded-xl border border-emerald-400/50 bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-400/20"
        href={`/runtime/export-generated-story-epub?story_id=${encodeURIComponent(story.id)}`}
      >
        Export EPUB
      </a>
    </DataCard>
  );
}
