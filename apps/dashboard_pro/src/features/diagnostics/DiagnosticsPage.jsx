import { runtimeApi } from "../../api/runtimeApi";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { LatestJobDiagnosticsPanel, PromptFilesPanel } from "../../components/DiagnosticsPanels";

export function DiagnosticsPage() {
  const { state } = useRuntimeState();
  const jobs = state?.jobs || [];
  const selected = jobs[0];
  const details = useAsync(() => selected?.id ? runtimeApi.job(selected.id) : Promise.resolve(null), [selected?.id]);
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
      <PromptFilesPanel prompts={state?.prompts || []} />
      <LatestJobDiagnosticsPanel selected={selected} details={details} />
    </div>
  );
}
