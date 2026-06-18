import { useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Panel, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";

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

  const canStart = validation?.can_start;
  return (
    <div className="space-y-5">
      <Panel title="Stage Books" subtitle="Upload one or more local book files into the database-backed staging area.">
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <input type="file" multiple accept=".epub,.pdf,.txt" onChange={(event) => setFiles(event.target.files)} className="rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100" />
          <Button onClick={upload} disabled={busy || !files.length} variant="primary">{busy ? "Uploading..." : "Upload files"}</Button>
        </div>
      </Panel>

      <Panel title="Import Plan" subtitle="Review order, titles, book indices, duplicates, and analysis depth before starting a database-native job.">
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Field label="Existing series">
            <select onChange={useExistingSeries} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm">
              <option value="">Create or keep custom series</option>
              {(series.value?.series || []).map((row) => <option key={row.series_id} value={row.series_id}>{row.title || row.series_id}</option>)}
            </select>
          </Field>
          <Field label="Series title">
            <input value={seriesTitle} onChange={(event) => { setSeriesTitle(event.target.value); resetPlanState(); }} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          </Field>
          <Field label="Series id">
            <input value={seriesId} onChange={(event) => { setSeriesId(event.target.value); resetPlanState(); }} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          </Field>
        </div>

        <div className="mb-4 grid gap-3 md:grid-cols-4">
          <Field label="Scene target words">
            <input type="number" min="200" max="2000" value={sceneTargetWords} onChange={(event) => { setSceneTargetWords(event.target.value); resetPlanState(); }} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          </Field>
          <Field label="Analysis model">
            <select value={analysisModel} onChange={(event) => { setAnalysisModel(event.target.value); resetPlanState(); }} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm">
              <option value="gpt_oss">gpt_oss</option>
              <option value="codex">codex</option>
              <option value="general_compute">general_compute</option>
            </select>
          </Field>
          <Field label="Provider mode">
            <select value={providerMode} onChange={(event) => { setProviderMode(event.target.value); resetPlanState(); }} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm">
              <option value="same_provider_rotating">same provider rotating</option>
              <option value="single_provider">single provider</option>
              <option value="cross_provider_fallback">cross-provider fallback</option>
            </select>
          </Field>
          <Field label="Pipeline depth">
            <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm">
              <input type="checkbox" checked={runAgents} onChange={(event) => { setRunAgents(event.target.checked); resetPlanState(); }} />
              Run DB agents
            </label>
          </Field>
        </div>

        {bookRows.length ? (
          <div className="space-y-3">
            {bookRows.map((row, index) => (
              <div key={row.source_id} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-black text-white">{row.source_name}</p>
                    <p className="mt-1 text-sm text-slate-500">{((row.size_bytes || 0) / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => moveRow(row.source_id, -1)} disabled={index === 0}>Move up</Button>
                    <Button onClick={() => moveRow(row.source_id, 1)} disabled={index === bookRows.length - 1}>Move down</Button>
                    <Button variant="danger" onClick={() => removeUpload(row.source_id)}>Remove</Button>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-[120px_1fr_160px]">
                  <Field label="Include">
                    <input type="checkbox" checked={row.selected} onChange={(event) => updateRow(row.source_id, { selected: event.target.checked })} />
                  </Field>
                  <Field label="Target title">
                    <input value={row.target_title} onChange={(event) => updateRow(row.source_id, { target_title: event.target.value })} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm" />
                  </Field>
                  <Field label="Book index">
                    <input type="number" min="1" value={row.book_index} onChange={(event) => updateRow(row.source_id, { book_index: event.target.value })} className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm" />
                  </Field>
                </div>
              </div>
            ))}

            <div className="flex flex-wrap gap-2">
              <Button onClick={createPlan}>Create and validate plan</Button>
              <Button onClick={start} disabled={!canStart} variant="primary">Start analysis job</Button>
            </div>

            {validation ? (
              <div className="rounded-2xl border border-slate-800 bg-black/25 p-4">
                <Badge tone={toneFor(validation.status)}>{validation.status}</Badge>
                <p className="mt-3 text-sm text-slate-300">{validation.summary}</p>
                {(validation.errors || []).map((item) => <p key={item} className="mt-2 text-sm text-red-200">{item}</p>)}
                {(validation.warnings || []).map((item) => <p key={item} className="mt-2 text-sm text-amber-200">{item}</p>)}
              </div>
            ) : null}
          </div>
        ) : <EmptyState title="No staged uploads">Upload ACOTAR EPUBs, then review their order before starting analysis.</EmptyState>}
      </Panel>
    </div>
  );
}
