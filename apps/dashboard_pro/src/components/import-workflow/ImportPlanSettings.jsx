import { Field, SelectInput, TextInput } from "../primitives";

export function ImportPlanSettings({
  seriesRows,
  seriesTitle,
  seriesId,
  runAgents,
  sceneTargetWords,
  analysisModel,
  providerMode,
  onExistingSeries,
  onSeriesTitleChange,
  onSeriesIdChange,
  onRunAgentsChange,
  onSceneTargetWordsChange,
  onAnalysisModelChange,
  onProviderModeChange,
}) {
  return (
    <>
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Field label="Existing series">
          <SelectInput onChange={onExistingSeries}>
            <option value="">Create or keep custom series</option>
            {seriesRows.map((row) => <option key={row.series_id} value={row.series_id}>{row.title || row.series_id}</option>)}
          </SelectInput>
        </Field>
        <Field label="Series title">
          <TextInput value={seriesTitle} onChange={onSeriesTitleChange} />
        </Field>
        <Field label="Series id">
          <TextInput value={seriesId} onChange={onSeriesIdChange} />
        </Field>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <Field label="Scene target words">
          <TextInput type="number" min="200" max="2000" value={sceneTargetWords} onChange={onSceneTargetWordsChange} />
        </Field>
        <Field label="Analysis model">
          <SelectInput value={analysisModel} onChange={onAnalysisModelChange}>
            <option value="gpt_oss">gpt_oss</option>
            <option value="codex">codex</option>
            <option value="general_compute">general_compute</option>
          </SelectInput>
        </Field>
        <Field label="Provider mode">
          <SelectInput value={providerMode} onChange={onProviderModeChange}>
            <option value="same_provider_rotating">same provider rotating</option>
            <option value="single_provider">single provider</option>
            <option value="cross_provider_fallback">cross-provider fallback</option>
          </SelectInput>
        </Field>
        <Field label="Pipeline depth">
          <label className="flex items-center gap-3 rounded-lg border border-white/10 bg-slate-950/70 p-3 text-sm">
            <input type="checkbox" checked={runAgents} onChange={onRunAgentsChange} />
            Run full analysis pipeline
          </label>
        </Field>
      </div>
    </>
  );
}
