import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { useAsync } from "../../hooks/useAsync";
import { ImportPlanPanel, StageBooksPanel } from "../../components/ImportWorkflow";

export function ImportPage() {
  const uploads = useAsync(() => runtimeApi.uploads(), []);
  const series = useAsync(() => runtimeApi.series(), []);
  const [files, setFiles] = useState([]);
  const [bookRows, setBookRows] = useState([]);
  const [plan, setPlan] = useState(null);
  const [validation, setValidation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [seriesTitle, setSeriesTitle] = useState("ACOTAR Dashboard QA");
  const [seriesId, setSeriesId] = useState("acotar-dashboard-qa");
  const [runAgents, setRunAgents] = useState(true);
  const [sceneTargetWords, setSceneTargetWords] = useState(700);
  const [analysisModel, setAnalysisModel] = useState("gpt_oss");
  const [providerMode, setProviderMode] = useState("same_provider_rotating");

  const staged = uploads.value?.uploads || [];
  const stagedKey = useMemo(() => staged.map((source) => source.id).join("|"), [staged]);

  useEffect(() => {
    setBookRows((current) => {
      const currentById = new Map(current.map((row) => [row.source_id, row]));
      return staged.map((source, index) => {
        const existing = currentById.get(source.id);
        return {
          source_id: source.id,
          source_name: source.original_name,
          size_bytes: source.size_bytes,
          target_title: existing?.target_title || source.original_name,
          book_index: existing?.book_index || index + 1,
          selected: existing?.selected ?? true,
        };
      });
    });
  }, [stagedKey]);

  function resetPlanState() {
    setPlan(null);
    setValidation(null);
  }

  async function upload() {
    if (!files.length) return;
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    setBusy(true);
    try {
      await runtimeApi.uploadBatch(form);
      await uploads.reload();
      resetPlanState();
    } finally {
      setBusy(false);
    }
  }

  function updateRow(sourceId, patch) {
    setBookRows((rows) => rows.map((row) => row.source_id === sourceId ? { ...row, ...patch } : row));
    resetPlanState();
  }

  function moveRow(sourceId, direction) {
    setBookRows((rows) => {
      const index = rows.findIndex((row) => row.source_id === sourceId);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= rows.length) return rows;
      const copy = [...rows];
      const [row] = copy.splice(index, 1);
      copy.splice(nextIndex, 0, row);
      return copy.map((item, itemIndex) => ({ ...item, book_index: itemIndex + 1 }));
    });
    resetPlanState();
  }

  async function removeUpload(sourceId) {
    await runtimeApi.removeUpload(sourceId);
    await uploads.reload();
    setBookRows((rows) => rows.filter((row) => row.source_id !== sourceId));
    resetPlanState();
  }

  function useExistingSeries(event) {
    const selected = (series.value?.series || []).find((row) => row.series_id === event.target.value);
    if (!selected) return;
    setSeriesId(selected.series_id);
    setSeriesTitle(selected.title || selected.series_id);
    resetPlanState();
  }

  async function createPlan() {
    const rows = bookRows.map((row, index) => ({
      source_id: row.source_id,
      target_title: row.target_title,
      book_index: Number(row.book_index) || index + 1,
      selected: Boolean(row.selected),
    }));
    const created = await runtimeApi.createImportPlan({
      series_id: seriesId,
      series_title: seriesTitle,
      books: rows,
      shared_config: {
        run_agents: runAgents,
        scene_target_words: Number(sceneTargetWords) || 700,
        analysis_model: analysisModel,
        analysis_provider_mode: providerMode,
      },
    });
    setPlan(created);
    const checked = await runtimeApi.validateImportPlan(created.id);
    setValidation(checked.validation);
  }

  async function start() {
    if (!plan?.id) return;
    const job = await runtimeApi.startImportPlan(plan.id);
    window.location.href = `/runs/${encodeURIComponent(job.id)}`;
  }

  return (
    <div className="space-y-5">
      <StageBooksPanel busy={busy} files={files} onFilesChange={(event) => setFiles(event.target.files)} onUpload={upload} />
      <ImportPlanPanel
        seriesRows={series.value?.series || []}
        bookRows={bookRows}
        seriesTitle={seriesTitle}
        seriesId={seriesId}
        runAgents={runAgents}
        sceneTargetWords={sceneTargetWords}
        analysisModel={analysisModel}
        providerMode={providerMode}
        validation={validation}
        onExistingSeries={useExistingSeries}
        onSeriesTitleChange={(event) => { setSeriesTitle(event.target.value); resetPlanState(); }}
        onSeriesIdChange={(event) => { setSeriesId(event.target.value); resetPlanState(); }}
        onRunAgentsChange={(event) => { setRunAgents(event.target.checked); resetPlanState(); }}
        onSceneTargetWordsChange={(event) => { setSceneTargetWords(event.target.value); resetPlanState(); }}
        onAnalysisModelChange={(event) => { setAnalysisModel(event.target.value); resetPlanState(); }}
        onProviderModeChange={(event) => { setProviderMode(event.target.value); resetPlanState(); }}
        onUpdateRow={updateRow}
        onMoveRow={moveRow}
        onRemoveUpload={removeUpload}
        onCreatePlan={createPlan}
        onStart={start}
      />
    </div>
  );
}
