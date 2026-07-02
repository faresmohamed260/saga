export function normalizeSeriesRows(seriesResponse) {
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

export function normalizeBookRows(responseBooks) {
  const rows = Array.isArray(responseBooks) ? responseBooks : [];
  return rows
    .map((row, index) => {
      if (typeof row === "string") {
        return {
          book_id: row,
          title: `Book ${index + 1}`,
          book_index: index + 1,
          chapter_count: 0,
          scene_count: 0,
        };
      }
      return {
        ...row,
        book_id: row?.book_id || row?.id || "",
        title: row?.title || row?.name || `Book ${row?.book_index || index + 1}`,
        book_index: Number(row?.book_index || index + 1),
        chapter_count: Number(row?.chapter_count || row?.chapters || 0),
        scene_count: Number(row?.scene_count || row?.scenes || 0),
      };
    })
    .filter((row) => row.book_id);
}

export function chapterLabel(chapter) {
  const bookIndex = chapter?.book_index || "?";
  const chapterIndex = chapter?.chapter_index || "?";
  return `Book ${bookIndex} / Chapter ${chapterIndex}`;
}

export function formatRunLabel(run) {
  const scope = String(run.scope_type || "book").toLowerCase() === "series" ? "series" : "book";
  return `${run.title || "Audiobook run"} / ${scope} / ${run.total_chapters || 0} chapters`;
}

export function filterSupersededRuns(runs) {
  const rows = Array.isArray(runs) ? runs : [];
  const grouped = new Map();

  for (const run of rows) {
    const key = [
      String(run?.series_id || ""),
      String(run?.book_id || ""),
      String(run?.scope_type || ""),
      String(run?.title || ""),
    ].join("::");
    const bucket = grouped.get(key) || [];
    bucket.push(run);
    grouped.set(key, bucket);
  }

  return Array.from(grouped.values())
    .flatMap((bucket) => {
      const sorted = [...bucket].sort((a, b) => String(b?.created_at || b?.updated_at || "").localeCompare(String(a?.created_at || a?.updated_at || "")));
      return sorted.slice(0, 1);
    })
    .sort((a, b) => String(b?.created_at || b?.updated_at || "").localeCompare(String(a?.created_at || a?.updated_at || "")));
}

export function runMatchesPlan(run, plan, selectedBook) {
  if (!run) return false;
  const runScope = String(run.scope_type || "book").toLowerCase();
  const runSeries = String(run.series_id || "");
  const runBookId = String(run.book_id || "");
  const planBookId = String(plan.bookRef || "").replace("db://book/", "");
  return runScope === String(plan.scope || "book").toLowerCase()
    && runSeries === String(plan.seriesId || "")
    && (runScope === "series" || runBookId === String(selectedBook?.book_id || planBookId || ""));
}

export function buildPlanPayload(plan) {
  return {
    scope: plan.scope,
    series_id: plan.seriesId,
    book_ref: plan.bookRef,
    tone: plan.tone,
    rewrite_provider: plan.rewriteProvider,
    rewrite_fallback_mode: plan.rewriteFallbackMode,
    voice: plan.voice,
    lang_code: plan.langCode,
    sample_rate: Number(plan.sampleRate || 24000),
    audio_format: plan.audioFormat,
    normalize_audio: plan.normalizeAudio,
    trim_silence: plan.trimSilence,
    sentence_pause_ms: Number(plan.sentencePauseMs || 0),
    store_transcript: true,
    store_audio: true,
  };
}
