import { Button, EmptyState, Panel } from "../primitives";
import { OperationCard } from "./OperationCard";

export function OperationsPanel({ jobs }) {
  return (
    <Panel
      title="Active Work"
      subtitle="Recent work with direct links into detailed progress."
      action={<Button asLink="/import/new" variant="primary">New import</Button>}
    >
      {jobs.length ? (
        <div className="grid gap-3">
          {jobs.slice(0, 6).map((job) => (
            <OperationCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <EmptyState title="No jobs recorded">Start with Import to stage books or use Decoder/Visual Assets for focused jobs.</EmptyState>
      )}
    </Panel>
  );
}
