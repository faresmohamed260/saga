import { EmptyState, Field, Panel } from "../primitives";

export function PromptFilesPanel({ prompts }) {
  return (
    <Panel title="Prompt Library" subtitle="Available prompt and workflow files for this workspace.">
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
