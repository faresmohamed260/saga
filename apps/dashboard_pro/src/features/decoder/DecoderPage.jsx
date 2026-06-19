import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Panel, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";

const MODES = ["pre_canon", "mid_canon", "post_canon", "alternate_universe"];

function normalizeSeriesRows(seriesResponse) {
  return (seriesResponse?.series || [])
    .map((row) => {
      if (typeof row === "string") {
        return {
          series_id: row,
          title: row,
          book_count: 0,
        };
      }
      return {
        series_id: row?.series_id || row?.id || "",
        title: row?.title || row?.series_id || row?.id || "Unnamed series",
        book_count: Number(row?.book_count || 0),
      };
    })
    .filter((row) => row.series_id);
}

export function DecoderPage() {
  const stories = useAsync(() => runtimeApi.stories(), []);
  const options = useAsync(() => runtimeApi.decoderOptions(), []);
  const series = useAsync(() => runtimeApi.series(), []);
  const [seriesBooks, setSeriesBooks] = useState([]);
  const [payload, setPayload] = useState({
    story_mode: "post_canon",
    series_id: "",
    book_ref: "",
    provider: "",
    chapter_count: 20,
    user_prompt: "Write a canon-aware long-form story using the selected mode.",
    primary_pov_character: "",
  });
  const [validation, setValidation] = useState(null);

  const seriesRows = useMemo(() => normalizeSeriesRows(series.value), [series.value]);
  const providerRows = useMemo(() => options.value?.providers || [], [options.value]);

  useEffect(() => {
    const firstSeries = seriesRows[0]?.series_id || "";
    if (firstSeries && !payload.series_id) {
      setPayload((current) => ({ ...current, series_id: firstSeries }));
    }
  }, [payload.series_id, seriesRows]);

  useEffect(() => {
    let cancelled = false;

    async function loadSeriesBooks() {
      if (!payload.series_id) {
        setSeriesBooks([]);
        setPayload((current) => ({ ...current, book_ref: "" }));
        return;
      }
      const response = await runtimeApi.seriesBooks(payload.series_id);
      if (cancelled) return;
      const rows = response?.books || [];
      setSeriesBooks(rows);
      const ordered = [...rows].sort((left, right) => Number(left.book_index || 0) - Number(right.book_index || 0));
      const latest = ordered[ordered.length - 1];
      const bookRef = latest?.book_id ? `db://book/${latest.book_id}` : "";
      setPayload((current) => (current.book_ref === bookRef ? current : { ...current, book_ref: bookRef }));
    }

    loadSeriesBooks();
    return () => {
      cancelled = true;
    };
  }, [payload.series_id]);

  useEffect(() => {
    const defaultProvider = options.value?.defaults?.provider || "";
    const availableProviders = providerRows.map((row) => row.value);
    if (!availableProviders.length) {
      if (payload.provider) {
        setPayload((current) => ({ ...current, provider: "" }));
      }
      return;
    }
    if (!payload.provider || !availableProviders.includes(payload.provider)) {
      setPayload((current) => ({ ...current, provider: defaultProvider || availableProviders[0] }));
    }
  }, [options.value, payload.provider, providerRows]);

  async function validate() {
    setValidation(await runtimeApi.validateDecoderPlan(payload));
  }

  async function start() {
    const job = await runtimeApi.startDecoder(payload);
    window.location.href = `/runs/${encodeURIComponent(job.id)}`;
  }

  const storyRows = stories.value?.stories || [];
  const modeRows = options.value?.modes || [];
  const canStart = !!validation?.valid && !!payload.series_id && !!payload.provider;

  return (
    <div className="grid gap-5 xl:grid-cols-[520px_1fr]">
      <Panel title="Decoder Controls" subtitle="Validate a series-level generation plan before starting a story job.">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {MODES.map((mode) => (
              <Button
                key={mode}
                onClick={() => setPayload({ ...payload, story_mode: mode })}
                variant={payload.story_mode === mode ? "primary" : "secondary"}
              >
                {mode.replaceAll("_", " ")}
              </Button>
            ))}
          </div>

          <Field label="Series">
            <select
              value={payload.series_id}
              onChange={(event) => setPayload({ ...payload, series_id: event.target.value })}
              className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
            >
              {!seriesRows.length ? <option value="">No series available</option> : null}
              {seriesRows.map((row) => (
                <option key={row.series_id} value={row.series_id}>
                  {(row.title || row.series_id) + (row.book_count ? ` (${row.book_count} books)` : "")}
                </option>
              ))}
            </select>
          </Field>

          {seriesBooks.length ? (
            <Field label="Series decoder scope">
              {`${seriesBooks.length} book${seriesBooks.length === 1 ? "" : "s"} available in this series. Decoder anchor is resolved automatically.`}
            </Field>
          ) : null}

          <Field label="Generation provider">
            <select
              value={payload.provider}
              onChange={(event) => setPayload({ ...payload, provider: event.target.value })}
              className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
            >
              {!providerRows.length ? <option value="">No healthy providers available</option> : null}
              {providerRows.map((row) => (
                <option key={row.value} value={row.value}>
                  {row.label}
                </option>
              ))}
            </select>
          </Field>

          <input
            type="number"
            min="1"
            max="60"
            value={payload.chapter_count}
            onChange={(event) => setPayload({ ...payload, chapter_count: Number(event.target.value) })}
            className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
          />

          <input
            placeholder="Primary POV character"
            value={payload.primary_pov_character}
            onChange={(event) => setPayload({ ...payload, primary_pov_character: event.target.value })}
            className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
          />

          <textarea
            value={payload.user_prompt}
            onChange={(event) => setPayload({ ...payload, user_prompt: event.target.value })}
            className="min-h-[180px] w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
          />

          <div className="flex gap-2">
            <Button onClick={validate} disabled={!payload.series_id || !payload.provider}>
              Validate plan
            </Button>
            <Button onClick={start} disabled={!canStart} variant="primary">
              Start generation
            </Button>
          </div>

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

      <Panel title="Generated Stories" subtitle="Persisted stories and export links.">
        {storyRows.length ? (
          <div className="space-y-3">
            {storyRows.map((story) => (
              <article key={story.id} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-black text-white">{story.title || story.id}</h3>
                  <Badge tone={toneFor(story.status)}>{story.status || "unknown"}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  {story.story_mode} · {story.primary_pov_character || "POV n/a"} · {story.series_id || story.series_title || "series n/a"}
                </p>
                <a
                  className="mt-3 inline-block rounded-xl border border-emerald-500/50 px-3 py-2 text-sm font-bold text-emerald-100"
                  href={`/runtime/export-generated-story-epub?story_id=${encodeURIComponent(story.id)}`}
                >
                  Export EPUB
                </a>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No generated stories" />
        )}
      </Panel>
    </div>
  );
}
