import { Link } from "react-router-dom";
import { Badge, DataCard, shortRef, toneFor } from "../primitives";

export function RunListItem({ job }) {
  return (
    <DataCard as={Link} to={`/runs/${encodeURIComponent(job.id)}`} interactive className="block overflow-hidden">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-black text-white" title={job.id}>{job.id}</p>
          <p className="mt-1 truncate text-sm text-slate-500" title={job.command || job.type || ""}>{shortRef(job.command || job.type || "")}</p>
        </div>
        <div className="max-w-[120px] shrink-0">
          <Badge tone={toneFor(job.status)}>{job.status || "unknown"}</Badge>
        </div>
      </div>
    </DataCard>
  );
}
