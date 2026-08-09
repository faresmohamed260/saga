import { runtimeApi } from "../../api/runtimeApi";
import { LatestJobDiagnosticsPanel } from "../../components/diagnostics-panels/LatestJobDiagnosticsPanel.jsx";
import { PromptFilesPanel } from "../../components/diagnostics-panels/PromptFilesPanel.jsx";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";

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
