import { Button, EmptyState, Panel, Toolbar } from "../primitives";
import { ImportPlanSettings } from "./ImportPlanSettings";
import { StagedBookList } from "./StagedBookList";
import { ValidationSummary } from "./ValidationSummary";

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
