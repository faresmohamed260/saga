import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { useAsync } from "../../hooks/useAsync";
import { DecoderControlsPanel, GeneratedStoriesPanel } from "./components/DecoderPanels";

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
      <DecoderControlsPanel
        modes={MODES}
        payload={payload}
        seriesRows={seriesRows}
        seriesBooks={seriesBooks}
        providerRows={providerRows}
        validation={validation}
        modeRows={modeRows}
        canStart={canStart}
        onPayloadChange={setPayload}
        onValidate={validate}
        onStart={start}
      />
      <GeneratedStoriesPanel stories={storyRows} />
    </div>
  );
}
