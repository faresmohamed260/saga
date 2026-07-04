import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Metric } from "../../components/primitives";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { buildPlanPayload, chapterLabel, filterSupersededRuns, normalizeBookRows, normalizeSeriesRows, runMatchesPlan } from "./audiobookUtils";
import { AudiobookControlsPanel, AudiobookLibraryPanel, AudiobookNotice, AudiobookOutputsPanel } from "../../components/AudiobookPanels";

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
  }, [runs.reload, selectedRunId]);

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

      <AudiobookNotice notice={notice} />

      <div className="grid gap-5 xl:grid-cols-[520px_1fr]">
        <AudiobookControlsPanel
          plan={plan}
          seriesRows={seriesRows}
          seriesBooks={seriesBooks}
          selectedSeries={selectedSeries}
          canStage={canStage}
          stageSubmitting={stageSubmitting}
          queueSubmitting={queueSubmitting}
          onPlanChange={setPlan}
          onStagePlan={stagePlan}
          onQueuePlan={queuePlan}
        />

        <div className="space-y-5">
          <AudiobookLibraryPanel
            selectedBrowserSeries={selectedBrowserSeries}
            existingOutputs={existingOutputs}
            libraryOpen={libraryOpen}
            onToggleLibrary={() => setLibraryOpen((current) => !current)}
            seriesRows={seriesRows}
            browserSeriesId={browserSeriesId}
            onBrowserSeriesChange={setBrowserSeriesId}
            selectedRunId={selectedRunId}
            onSelectedRunChange={setSelectedRunId}
            visibleRuns={visibleRuns}
            selectedRun={selectedRun}
          />
          <AudiobookOutputsPanel
            selectedRun={selectedRun}
            runLoading={runLoading}
            playableChapters={playableChapters}
            outputQuery={outputQuery}
            onOutputQueryChange={setOutputQuery}
            outputBookFilter={outputBookFilter}
            onOutputBookFilterChange={setOutputBookFilter}
            availableBookFilters={availableBookFilters}
            filteredPlayableChapters={filteredPlayableChapters}
            expandedChapterIds={expandedChapterIds}
            onToggleChapter={toggleChapter}
          />
        </div>
      </div>
    </div>
  );
}

