export function computeProgressPercent({ current, total, details, stage, status }) {
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

export function computeCounterLabel({ current, total, details, stage, status }) {
  const normalizedStatus = String(status || "").toLowerCase();
  const normalizedStage = String(stage || "").toLowerCase();
  const normalizedPhase = String(details.phase || "").toLowerCase();
  const chapterTotal = Number(details.chapter_count || total || 0);
  const chapterNumber = Number(details.chapter_number || 0);
  const totalScenes = Number(details.total_scenes || 0);
  const sceneNumber = Number(details.scene_number || 0);

  if (chapterTotal > 0 && chapterNumber > 0 && totalScenes > 0 && sceneNumber > 0) {
    return `${chapterNumber}/${chapterTotal} - ${sceneNumber}/${totalScenes}`;
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
