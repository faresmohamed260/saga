import { runtimeApi } from "../../api/runtimeApi";
import { EmptyState, Field, Panel } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function DiagnosticsPage() {
  const { state } = useRuntimeState();
  const jobs = state?.jobs || [];
  const selected = jobs[0];
  const details = useAsync(() => selected?.id ? runtimeApi.job(selected.id) : Promise.resolve(null), [selected?.id]);
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
      <Panel title="Prompt Files" subtitle="Runtime-visible prompt and agent files.">
        {state?.prompts?.length ? <div className="space-y-3">{state.prompts.map((prompt) => <Field key={prompt.path} label={prompt.path}>{prompt.size_bytes || 0} bytes</Field>)}</div> : <EmptyState title="No prompt files discovered" />}
      </Panel>
      <Panel title="Latest Job Diagnostics" subtitle={selected?.id || "No job selected"}>
        {details.value ? <pre className="max-h-[650px] overflow-auto rounded-2xl bg-black p-4 text-xs leading-6">{(details.value.log_tail || []).join("\n")}</pre> : <EmptyState title="No diagnostics available" />}
      </Panel>
    </div>
  );
}
