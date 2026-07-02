import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Metric, Panel, SearchBox, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { buildPlanPayload, chapterLabel, filterSupersededRuns, formatRunLabel, normalizeBookRows, normalizeSeriesRows, runMatchesPlan } from "./audiobookUtils";

export function AudiobookPage() {
  const { state } = useRuntimeState();
  const series = useAsync(() => runtimeApi.series(), []);
  const [seriesBooks, setSeriesBooks] = useState([]);
  const [notice, setNotice] = useState(null);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [browserSeriesId, setBrowserSeriesId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [expandedChapterIds, setExpandedChapterIds] = useState([]);
  const [runLoading, setRunLoading] = useState(false);
  const [stageSubmitting, setStageSubmitting] = useState(false);
  const [queueSubmitting, setQueueSubmitting] = useState(false);
  const [outputQuery, setOutputQuery] = useState("");
  const [outputBookFilter, setOutputBookFilter] = useState("all");
  const [plan, setPlan] = useState({
    scope: "book",
    seriesId: "",
    bookRef: "",
    tone: "classic",
    rewriteProvider: "ollama",
    rewriteFallbackMode: "strict_rewrite",
    voice: "af_bella",
    langCode: "a",
    sampleRate: 24000,
    audioFormat: "wav",
    normalizeAudio: true,
    trimSilence: false,
    sentencePauseMs: 0,
  });

  const seriesRows = useMemo(() => normalizeSeriesRows(series.value), [series.value]);
  const runs = useAsync(() => runtimeApi.audiobookRuns(browserSeriesId ? { series_id: browserSeriesId } : {}), [browserSeriesId]);
  const visibleRuns = useMemo(() => filterSupersededRuns(runs.value?.runs || []), [runs.value]);
  const fallbackLibraryBooks = useMemo(
    () => normalizeBookRows((state?.artifacts?.books || []).filter((book) => String(book?.series_id || "") === String(plan.seriesId || ""))),
    [plan.seriesId, state?.artifacts?.books],
  );

  useEffect(() => {
    if (!seriesRows.length || plan.seriesId) return;
    setPlan((current) => ({ ...current, seriesId: seriesRows[0].series_id }));
  }, [plan.seriesId, seriesRows]);

  useEffect(() => {
    if (!seriesRows.length || browserSeriesId) return;
    setBrowserSeriesId(seriesRows[0].series_id);
  }, [browserSeriesId, seriesRows]);

  useEffect(() => {
    let cancelled = false;

    async function loadSeriesBooks() {
      if (!plan.seriesId) {
        setSeriesBooks([]);
        setPlan((current) => ({ ...current, bookRef: "" }));
        return;
      }

      try {
        const response = await runtimeApi.seriesBooks(plan.seriesId);
        if (cancelled) return;
        const rows = normalizeBookRows(response?.books || response);
        const resolvedRows = rows.length ? rows : fallbackLibraryBooks;
        setSeriesBooks(resolvedRows);
        const hasSelectedBook = resolvedRows.some((book) => `db://book/${book.book_id}` === plan.bookRef);
        const nextBookRef = hasSelectedBook ? plan.bookRef : (resolvedRows[0]?.book_id ? `db://book/${resolvedRows[0].book_id}` : "");
        setPlan((current) => ({ ...current, bookRef: nextBookRef }));
        if (!rows.length && fallbackLibraryBooks.length) {
          setNotice({ tone: "amber", text: "Loaded book choices from the runtime library fallback because the direct series-books response came back empty." });
        } else {
          setNotice(null);
        }
      } catch (exc) {
        if (cancelled) return;
        const resolvedRows = fallbackLibraryBooks;
        setSeriesBooks(resolvedRows);
        const nextBookRef = resolvedRows[0]?.book_id ? `db://book/${resolvedRows[0].book_id}` : "";
        setPlan((current) => ({ ...current, bookRef: nextBookRef }));
        setNotice(resolvedRows.length ? null : { tone: "red", text: exc.message || String(exc) });
      }
    }

    loadSeriesBooks();
    return () => {
      cancelled = true;
    };
  }, [plan.seriesId, fallbackLibraryBooks]);

  useEffect(() => {
    const nextRuns = visibleRuns;
    if (!nextRuns.length) {
      setSelectedRunId("");
      setSelectedRun(null);
      return;
    }
    if (!selectedRunId || !nextRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(nextRuns[0].id);
    }
  }, [visibleRuns, selectedRunId]);

  useEffect(() => {
    let cancelled = false;

    async function loadRun() {
      if (!selectedRunId) {
        setSelectedRun(null);
        return;
      }
      setRunLoading(true);
      try {
        const payload = await runtimeApi.audiobookRun(selectedRunId);
        if (!cancelled) {
          setSelectedRun(payload);
          setNotice((current) => (current?.tone === "red" ? null : current));
        }
      } finally {
        if (!cancelled) setRunLoading(false);
      }
    }

    loadRun();
    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  useEffect(() => {
      const timer = window.setInterval(() => {
      runs.reload();
      if (selectedRunId) {
        runtimeApi.audiobookRun(selectedRunId).then(setSelectedRun).catch(() => {});
      }
    }, 8000);
    return () => window.clearInterval(timer);
  }, [runs, selectedRunId]);

  const selectedSeries = seriesRows.find((row) => row.series_id === plan.seriesId) || null;
  const selectedBrowserSeries = seriesRows.find((row) => row.series_id === browserSeriesId) || null;
  const selectedBooks = useMemo(() => {
    if (plan.scope === "series") return seriesBooks;
    return seriesBooks.filter((book) => `db://book/${book.book_id}` === plan.bookRef);
  }, [plan.bookRef, plan.scope, seriesBooks]);
  const selectedBook = selectedBooks[0] || null;
  const existingOutputs = visibleRuns.length;
  const selectedRunChapters = Array.isArray(selectedRun?.chapters) ? selectedRun.chapters : [];
  useEffect(() => {
    setExpandedChapterIds((current) => current.filter((chapterId) => selectedRunChapters.some((chapter) => chapter.chapter_id === chapterId)));
  }, [selectedRunChapters]);
  const playableChapters = useMemo(
    () => selectedRunChapters.filter((chapter) => String(chapter?.audio_status || "").toLowerCase() === "completed"),
    [selectedRunChapters],
  );
  const sortedPlayableChapters = useMemo(
    () => [...playableChapters].sort((left, right) => {
      const leftBook = Number(left?.book_index || 0);
      const rightBook = Number(right?.book_index || 0);
      if (leftBook !== rightBook) return leftBook - rightBook;
      return Number(left?.chapter_index || 0) - Number(right?.chapter_index || 0);
    }),
    [playableChapters],
  );
  const availableBookFilters = useMemo(
    () => [...new Set(sortedPlayableChapters.map((chapter) => String(chapter?.book_index || "")).filter(Boolean))],
    [sortedPlayableChapters],
  );
  const filteredPlayableChapters = useMemo(() => {
    const query = outputQuery.trim().toLowerCase();
    return sortedPlayableChapters.filter((chapter) => {
      const matchesBook = outputBookFilter === "all" || String(chapter?.book_index || "") === outputBookFilter;
      const haystack = [
        String(chapter?.chapter_title || ""),
        chapterLabel(chapter),
        String(chapter?.book_index || ""),
        String(chapter?.chapter_index || ""),
      ].join(" ").toLowerCase();
      const matchesQuery = !query || haystack.includes(query);
      return matchesBook && matchesQuery;
    });
  }, [outputBookFilter, outputQuery, sortedPlayableChapters]);
  const canStage = !!plan.seriesId && !!selectedBooks.length;

  async function stagePlan() {
    if (!canStage || stageSubmitting) return;
    setStageSubmitting(true);
    try {
      const response = await runtimeApi.stageAudiobookRun(buildPlanPayload(plan));
      const createdRun = response?.run || null;
      await runs.reload();
      setSelectedRunId(createdRun?.id || "");
      setSelectedRun(createdRun);
      setNotice({
        tone: "green",
        text:
        plan.scope === "series"
          ? `Persisted a staged audiobook run for the full ${selectedSeries?.title || plan.seriesId} series.`
          : `Persisted a staged audiobook run for ${selectedBook?.title || "the selected book"}.`,
      });
    } catch (exc) {
      setNotice({ tone: "red", text: exc.message || String(exc) });
    } finally {
      setStageSubmitting(false);
    }
  }

  async function queuePlan() {
    if (!canStage || queueSubmitting) return;
    setQueueSubmitting(true);
    try {
      const shouldStartSelected = runMatchesPlan(selectedRun, plan, selectedBook)
        && ["staged", "failed", "cancelled", "partial"].includes(String(selectedRun?.status || "").toLowerCase());
      const response = shouldStartSelected
        ? await runtimeApi.startAudiobookRun(selectedRun.id)
        : await runtimeApi.startAudiobookJob(buildPlanPayload(plan));
      const run = response?.run || null;
      const job = response?.job || null;
      await runs.reload();
      if (run?.id) {
        setSelectedRunId(run.id);
        setSelectedRun(run);
      }
      setNotice({
        tone: "green",
        text:
        job?.id
          ? `Queued audiobook pipeline as job ${job.id}. Open Runs to monitor live progress and logs.`
          : "Queued audiobook pipeline.",
      });
    } catch (exc) {
      setNotice({ tone: "red", text: exc.message || String(exc) });
    } finally {
      setQueueSubmitting(false);
    }
  }

  function toggleChapter(chapterId) {
    setExpandedChapterIds((current) => (
      current.includes(chapterId)
        ? current.filter((item) => item !== chapterId)
        : [...current, chapterId]
    ));
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Series" value={seriesRows.length} detail="indexed" tone="blue" />
        <Metric label="Books In Scope" value={selectedBooks.length} detail={plan.scope === "series" ? "full series" : "single book"} tone="green" />
        <Metric label="Stored Runs" value={existingOutputs} detail="persistent" tone="amber" />
      </div>

      {notice?.text ? (
        <div className={`rounded-2xl border p-4 text-sm ${notice.tone === "red" ? "border-red-500/40 bg-red-500/10 text-red-100" : notice.tone === "amber" ? "border-amber-500/40 bg-amber-500/10 text-amber-100" : "border-emerald-500/40 bg-emerald-500/10 text-emerald-100"}`}>
          {notice.text}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[520px_1fr]">
        <Panel
          title="Audiobook Controls"
          subtitle="Select a series, scope it to one book or a full series, then stage or run the audiobook pipeline directly from the database."
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={() => setPlan((current) => ({ ...current, scope: "book" }))} variant={plan.scope === "book" ? "primary" : "secondary"}>
                Single book
              </Button>
              <Button onClick={() => setPlan((current) => ({ ...current, scope: "series" }))} variant={plan.scope === "series" ? "primary" : "secondary"}>
                Entire series
              </Button>
            </div>

            <Field label="Series">
              <select
                value={plan.seriesId}
                onChange={(event) => setPlan((current) => ({ ...current, seriesId: event.target.value, bookRef: "" }))}
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

            {plan.scope === "book" ? (
              <Field label="Book">
                <select
                  value={plan.bookRef}
                  onChange={(event) => setPlan((current) => ({ ...current, bookRef: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
                >
                  {!seriesBooks.length ? <option value="">No books available</option> : null}
                  {seriesBooks.map((book) => (
                    <option key={book.book_id} value={`db://book/${book.book_id}`}>
                      {book.title}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <Field label="Series scope">
                {seriesBooks.length
                  ? `${seriesBooks.length} books from ${selectedSeries?.title || plan.seriesId} will be narrated in database order.`
                  : "No books are currently available for the selected series."}
              </Field>
            )}

            <Field label="Narration tone">
              <select
                value={plan.tone}
                onChange={(event) => setPlan((current) => ({ ...current, tone: event.target.value }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="classic">classic</option>
                <option value="dramatic">dramatic</option>
                <option value="epic">epic</option>
              </select>
            </Field>

            <Field label="Rewrite provider">
              <select
                value={plan.rewriteProvider}
                onChange={(event) => setPlan((current) => ({ ...current, rewriteProvider: event.target.value }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="ollama">ollama</option>
                <option value="general_compute">general_compute</option>
                <option value="codex">codex</option>
                <option value="mistral">mistral</option>
                <option value="gemini">gemini</option>
              </select>
            </Field>

            <Field label="Rewrite fallback">
              <select
                value={plan.rewriteFallbackMode}
                onChange={(event) => setPlan((current) => ({ ...current, rewriteFallbackMode: event.target.value }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="strict_rewrite">require rewrite success</option>
                <option value="fallback_to_source">fallback to source text on rewrite failure</option>
              </select>
            </Field>

            <Field label="Voice profile">
              <select
                value={plan.voice}
                onChange={(event) => setPlan((current) => ({ ...current, voice: event.target.value }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="af_bella">af_bella</option>
                <option value="af_sarah">af_sarah</option>
                <option value="am_adam">am_adam</option>
                <option value="bf_emma">bf_emma</option>
              </select>
            </Field>

            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Sample Rate">
                <input
                  type="number"
                  min="8000"
                  step="1000"
                  value={plan.sampleRate}
                  onChange={(event) => setPlan((current) => ({ ...current, sampleRate: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
                />
              </Field>
              <Field label="Audio Format">
                <select
                  value={plan.audioFormat}
                  onChange={(event) => setPlan((current) => ({ ...current, audioFormat: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
                >
                  <option value="wav">wav</option>
                  <option value="flac">flac</option>
                </select>
              </Field>
            </div>

            <Field label="Normalization">
              <select
                value={plan.normalizeAudio ? "on" : "off"}
                onChange={(event) => setPlan((current) => ({ ...current, normalizeAudio: event.target.value === "on" }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="on">normalize audio</option>
                <option value="off">leave raw levels</option>
              </select>
            </Field>

            <Field label="Silence Trim">
              <select
                value={plan.trimSilence ? "on" : "off"}
                onChange={(event) => setPlan((current) => ({ ...current, trimSilence: event.target.value === "on" }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
              >
                <option value="off">keep natural pauses</option>
                <option value="on">trim silence</option>
              </select>
            </Field>

            <Field label="Sentence Pause (ms)">
              <input
                type="number"
                min="0"
                step="50"
                value={plan.sentencePauseMs}
                onChange={(event) => setPlan((current) => ({ ...current, sentencePauseMs: event.target.value }))}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
              />
            </Field>

            <Field label="Storage">
              Transcript rows and audio paths are always stored for audiobook runs.
            </Field>

            <div className="flex gap-2">
              <Button onClick={stagePlan} disabled={!canStage || stageSubmitting}>
                {stageSubmitting ? "Staging..." : "Stage outputs"}
              </Button>
              <Button variant="primary" onClick={queuePlan} disabled={!canStage || queueSubmitting}>
                {queueSubmitting ? "Queueing..." : "Queue audiobook pipeline"}
              </Button>
            </div>
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel title="Audiobook Library" subtitle="Browse stored audiobook runs and playable outputs without touching the control panel.">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{selectedBrowserSeries?.title || "Select a series"}</p>
                  <p className="text-sm text-slate-400">{existingOutputs} stored run{existingOutputs === 1 ? "" : "s"} available</p>
                </div>
                <Button variant="secondary" onClick={() => setLibraryOpen((current) => !current)}>
                  {libraryOpen ? "Collapse library" : "Expand library"}
                </Button>
              </div>

              {libraryOpen ? (
                <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Library series">
                      <select
                        value={browserSeriesId}
                        onChange={(event) => setBrowserSeriesId(event.target.value)}
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

                    <Field label="Stored run">
                      <select
                        value={selectedRunId}
                        onChange={(event) => setSelectedRunId(event.target.value)}
                        className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm"
                      >
                        {!visibleRuns.length ? <option value="">No stored runs available</option> : null}
                        {visibleRuns.map((run) => (
                          <option key={run.id} value={run.id}>
                            {`${run.title || "Audiobook run"} - ${run.status || "unknown"}`}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>

                  {selectedRun ? (
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-black text-white">{selectedRun.title || "Audiobook run"}</p>
                          <p className="mt-1 text-sm text-slate-400">{formatRunLabel(selectedRun)}</p>
                        </div>
                        <Badge tone={toneFor(selectedRun.status)}>{selectedRun.status || "unknown"}</Badge>
                      </div>
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        <Field label="Voice">{selectedRun.voice || "Not set"}</Field>
                        <Field label="Audio format">{selectedRun.audio_format || "wav"}</Field>
                        <Field label="Updated">{selectedRun.updated_at || "n/a"}</Field>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </Panel>

          <Panel title="Outputs" subtitle="Playable audio files for the selected stored run.">
            {selectedRun ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-slate-400">
                    {playableChapters.length} downloadable file{playableChapters.length === 1 ? "" : "s"} ready
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={toneFor(selectedRun.status)}>{selectedRun.status || "unknown"}</Badge>
                    {playableChapters.length ? (
                      <a
                        href={runtimeApi.audiobookRunBundleUrl(selectedRun.id)}
                        download={`${selectedRun.title || "audiobook"}.wav`}
                        className="rounded-xl border border-sky-400/50 bg-sky-500/15 px-4 py-2 text-sm font-bold text-sky-100 transition hover:bg-sky-500/25"
                      >
                        Download full audiobook
                      </a>
                    ) : null}
                  </div>
                </div>

                {playableChapters.length ? (
                  <div className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
                      <SearchBox value={outputQuery} onChange={setOutputQuery} placeholder="Filter by chapter title, book, or chapter number" />
                      <select
                        value={outputBookFilter}
                        onChange={(event) => setOutputBookFilter(event.target.value)}
                        className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
                      >
                        <option value="all">All books</option>
                        {availableBookFilters.map((bookIndex) => (
                          <option key={bookIndex} value={bookIndex}>
                            {`Book ${bookIndex}`}
                          </option>
                        ))}
                      </select>
                    </div>
                    {filteredPlayableChapters.map((chapter) => {
                      const audioUrl = runtimeApi.audiobookChapterAudioUrl(selectedRun.id, chapter.chapter_id);
                      const filename = `${selectedRun.title || "audiobook"}-book-${chapter.book_index || "x"}-chapter-${chapter.chapter_index || "x"}.${selectedRun.audio_format || "wav"}`;
                      const isExpanded = expandedChapterIds.includes(chapter.chapter_id);
                      return (
                        <div key={chapter.chapter_id} className="rounded-2xl border border-slate-800 bg-[#0b1117] p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="font-black text-white">{chapter.chapter_title || `Chapter ${chapter.chapter_index || "?"}`}</p>
                              <p className="mt-1 text-sm text-slate-400">{chapterLabel(chapter)}</p>
                            </div>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => toggleChapter(chapter.chapter_id)}
                                className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-bold text-slate-100 transition hover:border-sky-500/50"
                              >
                                {isExpanded ? "Collapse" : "Expand"}
                              </button>
                              <a
                                href={audioUrl}
                                download={filename}
                                className="rounded-xl border border-emerald-400/50 bg-emerald-500/15 px-4 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-500/25"
                              >
                                Download
                              </a>
                            </div>
                          </div>
                          {isExpanded ? (
                            <audio className="mt-4 w-full" controls preload="none" src={audioUrl} />
                          ) : null}
                        </div>
                      );
                    })}
                    {!filteredPlayableChapters.length ? (
                      <EmptyState title="No matching outputs">
                        Adjust the search or book filter to find a specific playable chapter.
                      </EmptyState>
                    ) : null}
                  </div>
                ) : (
                  <EmptyState title="No playable audio yet">
                    This run does not have completed audio files available for playback or download yet.
                  </EmptyState>
                )}
              </div>
            ) : runLoading ? (
              <EmptyState title="Loading run">Fetching the selected audiobook run from the database.</EmptyState>
            ) : (
              <EmptyState title="No staged outputs">
                Select a stored run or stage a new audiobook scope to access playable audio files.
              </EmptyState>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

