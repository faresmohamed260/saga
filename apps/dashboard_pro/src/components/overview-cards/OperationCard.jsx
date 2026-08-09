import { Link } from "react-router-dom";
import { Badge, DataCard, toneFor } from "../primitives";

export function OperationCard({ job }) {
  return (
    <DataCard as={Link} to={`/runs/${encodeURIComponent(job.id)}`} interactive className="block">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-black text-white" title={job.id}>{job.id}</p>
          <p className="mt-1 text-sm text-slate-400">{job.type || job.job_type || "job"} - {job.progress?.label || "waiting for progress"}</p>
        </div>
        <Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge>
      </div>
    </DataCard>
  );
}
