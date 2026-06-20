import { Badge, toneFor } from "../ui/primitives";

export function Progress({ job }) {
  const progress = job?.progress || {};
  const current = Number(progress.current || 0);
  const total = Number(progress.total || 0);
  const details = progress.details || {};
  const percent = computeProgressPercent({
    current,
    total,
    details,
    stage: progress.stage,
    status: job?.status || progress.status || "unknown",
  });
  const status = job?.status || progress.status || "unknown";
  const counterLabel = computeCounterLabel({
    current,
    total,
    details,
    stage: progress.stage,
    status,
  });
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#10141d] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-white">{progress.label || job?.status_reason || job?.type || "No active step"}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{progress.stage || job?.type || "job"}</p>
        </div>
        <div className="flex gap-2">
          <Badge tone={toneFor(status)}>{status}</Badge>
          <Badge tone="blue">{counterLabel}</Badge>
        </div>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-black/50">
        <div className="h-full rounded-full bg-sky-400 transition-all" style={{ width: `${percent || (String(status).includes("running") ? 8 : 0)}%` }} />
      </div>
    </div>
  );
}

function computeProgressPercent({ current, total, details, stage, status }) {
  const normalizedStatus = String(status || "").toLowerCase();
  const normalizedStage = String(stage || "").toLowerCase();
  const normalizedPhase = String(details.phase || "").toLowerCase();
  const chapterTotal = Number(details.chapter_count || total || 0);
  const chapterNumber = Number(details.chapter_number || 0);
  const totalScenes = Number(details.total_scenes || 0);
  const sceneNumber = Number(details.scene_number || 0);
  const event = String(details.event || "").toLowerCase();

  if (chapterTotal > 0 && chapterNumber > 0 && totalScenes > 0 && sceneNumber > 0) {
    const completedChapters = Math.max(0, chapterNumber - 1);
    const completedScenesInChapter = Math.max(
      0,
      Math.min(
        totalScenes,
        event === "scene_completed" ? sceneNumber : sceneNumber - 1,
      ),
    );
    const chapterProgress = completedScenesInChapter / totalScenes;
    return Math.max(0, Math.min(100, Math.round(((completedChapters + chapterProgress) / chapterTotal) * 100)));
  }

  if (chapterTotal > 0 && chapterNumber > 0 && event === "chapter_completed") {
    return Math.max(0, Math.min(100, Math.round((chapterNumber / chapterTotal) * 100)));
  }

  if (chapterTotal > 0 && chapterNumber > 0 && normalizedPhase === "transcript") {
    const transcriptCompleted = normalizedStage === "transcript_completed" ? chapterNumber : chapterNumber - 1;
    return Math.max(0, Math.min(100, Math.round((Math.max(0, transcriptCompleted) / chapterTotal) * 50)));
  }

  if (chapterTotal > 0 && normalizedPhase === "tts") {
    const safeTotal = Math.max(1, chapterTotal);
    const completedAudio = Math.max(0, Math.min(safeTotal, current));
    const inFlightOffset = chapterNumber > completedAudio ? 0.5 : 0;
    return Math.max(
      50,
      Math.min(100, Math.round(50 + (((completedAudio + inFlightOffset) / safeTotal) * 50))),
    );
  }

  if (total > 0) {
    return Math.max(0, Math.min(100, Math.round((current / total) * 100)));
  }

  return normalizedStatus.includes("completed") ? 100 : 0;
}

function computeCounterLabel({ current, total, details, stage, status }) {
  const normalizedStatus = String(status || "").toLowerCase();
  const normalizedStage = String(stage || "").toLowerCase();
  const normalizedPhase = String(details.phase || "").toLowerCase();
  const chapterTotal = Number(details.chapter_count || total || 0);
  const chapterNumber = Number(details.chapter_number || 0);
  const totalScenes = Number(details.total_scenes || 0);
  const sceneNumber = Number(details.scene_number || 0);

  if (chapterTotal > 0 && chapterNumber > 0 && totalScenes > 0 && sceneNumber > 0) {
    return `${chapterNumber}/${chapterTotal} · ${sceneNumber}/${totalScenes}`;
  }
  if (chapterTotal > 0 && chapterNumber > 0 && normalizedPhase === "transcript") {
    const transcriptCompleted = normalizedStage === "transcript_completed" ? chapterNumber : Math.max(0, chapterNumber - 1);
    return `${transcriptCompleted}/${chapterTotal} transcripts`;
  }
  if (chapterTotal > 0 && normalizedPhase === "tts") {
    return `${Math.max(0, current)}/${chapterTotal} audio`;
  }
  if (chapterTotal > 0) {
    const safeCurrent = normalizedStatus.includes("completed") ? chapterTotal : current;
    return `${safeCurrent}/${chapterTotal}`;
  }
  return "indeterminate";
}

export function LogViewer({ lines = [] }) {
  if (!lines.length) return <div className="rounded-2xl border border-dashed border-slate-800 bg-black/40 p-4 text-sm text-slate-400">No logs yet.</div>;
  return (
    <div className="max-h-[520px] overflow-auto rounded-2xl border border-slate-800 bg-black p-3 font-mono text-xs">
      {lines.map((line, index) => {
        const raw = typeof line === "string" ? line : line?.line_text || JSON.stringify(line);
        const isError = /error|failed|traceback|exception/i.test(raw);
        const isWarn = /warn|retry|blocked|cancel/i.test(raw);
        return <div key={`${index}-${raw.slice(0, 16)}`} className={`border-b border-slate-900 py-1.5 ${isError ? "text-red-300" : isWarn ? "text-amber-200" : "text-slate-300"}`}>{raw}</div>;
      })}
    </div>
  );
}
