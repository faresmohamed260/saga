import { EmptyState, Panel } from "../primitives";
import { renderAnalysisRow } from "./renderAnalysisRow";

export function AnalysisRowsPanel({ rows, section }) {
  return (
    <Panel title={`${rows.length} ${section}`} subtitle="Structured analysis results presented as reviewable cards.">
      {rows.length ? (
        <div className="space-y-3">
          {rows.map((row, index) => renderAnalysisRow(section, row, index))}
        </div>
      ) : (
        <EmptyState title={`No ${section} entries`} />
      )}
    </Panel>
  );
}
