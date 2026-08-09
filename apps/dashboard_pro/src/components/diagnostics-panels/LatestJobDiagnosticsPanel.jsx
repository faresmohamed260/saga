import { EmptyState, Panel } from "../primitives";

export function LatestJobDiagnosticsPanel({ selected, details }) {
  return (
    <Panel title="Latest Run Details" subtitle={selected?.id || "No job selected"}>
      {details.value ? (
        <pre className="max-h-[650px] overflow-auto rounded-lg border border-white/10 bg-black/50 p-4 text-xs leading-6 text-slate-200">{(details.value.log_tail || []).join("\n")}</pre>
      ) : (
        <EmptyState title="No diagnostics available" />
      )}
    </Panel>
  );
}
