import { EmptyState, Panel } from "../primitives";
import { RunListItem } from "./RunListItem";

export function RunsListPanel({ jobs }) {
  return (
    <Panel title="Runs" subtitle="Recent work items and queued jobs.">
      {jobs.length ? (
        <div className="space-y-3">
          {jobs.map((job) => (
            <RunListItem key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <EmptyState title="No runs found" />
      )}
    </Panel>
  );
}
