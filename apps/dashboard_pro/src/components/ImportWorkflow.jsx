import { Badge, Button, DataCard, EmptyState, Field, Panel, SelectInput, StatusBanner, TextInput, Toolbar, toneFor } from "./primitives";

export function StageBooksPanel({ busy, files, onFilesChange, onUpload }) {
  return (
    <Panel title="Stage Books" subtitle="Upload one or more local book files into the staging area.">
      <div className="grid gap-4 md:grid-cols-[1fr_auto]">
        <input type="file" multiple accept=".epub,.pdf,.txt" onChange={onFilesChange} className="w-full rounded-lg border border-white/10 bg-slate-950/70 p-3 text-sm text-slate-100" />
        <Button onClick={onUpload} disabled={busy || !files.length} variant="primary">{busy ? "Uploading..." : "Upload files"}</Button>
      </div>
    </Panel>
  );
}

export function ImportPlanPanel({
  seriesRows,
  bookRows,
  seriesTitle,
  seriesId,
  runAgents,
  sceneTargetWords,
  analysisModel,
  providerMode,
  validation,
  onExistingSeries,
  onSeriesTitleChange,
  onSeriesIdChange,
  onRunAgentsChange,
  onSceneTargetWordsChange,
  onAnalysisModelChange,
  onProviderModeChange,
  onUpdateRow,
  onMoveRow,
  onRemoveUpload,
  onCreatePlan,
  onStart,
}) {
  const canStart = validation?.can_start;
  return (
    <Panel title="Import Plan" subtitle="Review order, titles, book indices, duplicates, and analysis depth before starting analysis.">
      <ImportPlanSettings
        seriesRows={seriesRows}
        seriesTitle={seriesTitle}
        seriesId={seriesId}
        runAgents={runAgents}
        sceneTargetWords={sceneTargetWords}
        analysisModel={analysisModel}
        providerMode={providerMode}
        onExistingSeries={onExistingSeries}
        onSeriesTitleChange={onSeriesTitleChange}
        onSeriesIdChange={onSeriesIdChange}
        onRunAgentsChange={onRunAgentsChange}
        onSceneTargetWordsChange={onSceneTargetWordsChange}
        onAnalysisModelChange={onAnalysisModelChange}
        onProviderModeChange={onProviderModeChange}
      />

      {bookRows.length ? (
        <div className="space-y-3">
          <StagedBookList rows={bookRows} onUpdateRow={onUpdateRow} onMoveRow={onMoveRow} onRemoveUpload={onRemoveUpload} />
          <Toolbar>
            <Button onClick={onCreatePlan}>Create and validate plan</Button>
            <Button onClick={onStart} disabled={!canStart} variant="primary">Start analysis job</Button>
          </Toolbar>
          <ValidationSummary validation={validation} />
        </div>
      ) : (
        <EmptyState title="No staged uploads">Upload EPUB, PDF, or TXT files, then review their order before starting analysis.</EmptyState>
      )}
    </Panel>
  );
}

function ImportPlanSettings({
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

function StagedBookList({ rows, onUpdateRow, onMoveRow, onRemoveUpload }) {
  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <StagedBookCard
          key={row.source_id}
          row={row}
          index={index}
          total={rows.length}
          onUpdateRow={onUpdateRow}
          onMoveRow={onMoveRow}
          onRemoveUpload={onRemoveUpload}
        />
      ))}
    </div>
  );
}

function StagedBookCard({ row, index, total, onUpdateRow, onMoveRow, onRemoveUpload }) {
  return (
    <DataCard>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-black text-white">{row.source_name}</p>
          <p className="mt-1 text-sm text-slate-500">{((row.size_bytes || 0) / 1024 / 1024).toFixed(2)} MB</p>
        </div>
        <Toolbar>
          <Button onClick={() => onMoveRow(row.source_id, -1)} disabled={index === 0}>Move up</Button>
          <Button onClick={() => onMoveRow(row.source_id, 1)} disabled={index === total - 1}>Move down</Button>
          <Button variant="danger" onClick={() => onRemoveUpload(row.source_id)}>Remove</Button>
        </Toolbar>
      </div>
      <div className="grid gap-3 md:grid-cols-[120px_1fr_160px]">
        <Field label="Include">
          <input type="checkbox" checked={row.selected} onChange={(event) => onUpdateRow(row.source_id, { selected: event.target.checked })} />
        </Field>
        <Field label="Target title">
          <TextInput value={row.target_title} onChange={(event) => onUpdateRow(row.source_id, { target_title: event.target.value })} />
        </Field>
        <Field label="Book index">
          <TextInput type="number" min="1" value={row.book_index} onChange={(event) => onUpdateRow(row.source_id, { book_index: event.target.value })} />
        </Field>
      </div>
    </DataCard>
  );
}

function ValidationSummary({ validation }) {
  if (!validation) return null;
  return (
    <DataCard className="bg-black/20">
      <Badge tone={toneFor(validation.status)}>{validation.status}</Badge>
      <p className="mt-3 text-sm text-slate-300">{validation.summary}</p>
      {(validation.errors || []).map((item) => <StatusBanner key={item} tone="red" message={item} />)}
      {(validation.warnings || []).map((item) => <StatusBanner key={item} tone="amber" message={item} />)}
    </DataCard>
  );
}
