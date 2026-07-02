import { EmptyState, Field, Panel } from "../../../components/ui/primitives";

export function PromptFilesPanel({ prompts }) {
  return (
    <Panel title="Prompt Files" subtitle="Runtime-visible prompt and agent files.">
      {prompts.length ? (
        <div className="space-y-3">
          {prompts.map((prompt) => <Field key={prompt.path} label={prompt.path}>{prompt.size_bytes || 0} bytes</Field>)}
        </div>
      ) : (
        <EmptyState title="No prompt files discovered" />
      )}
    </Panel>
  );
}

export function LatestJobDiagnosticsPanel({ selected, details }) {
  return (
    <Panel title="Latest Job Diagnostics" subtitle={selected?.id || "No job selected"}>
      {details.value ? (
        <pre className="max-h-[650px] overflow-auto rounded-2xl border border-white/10 bg-black/50 p-4 text-xs leading-6 text-slate-200">{(details.value.log_tail || []).join("\n")}</pre>
      ) : (
        <EmptyState title="No diagnostics available" />
      )}
    </Panel>
  );
}
