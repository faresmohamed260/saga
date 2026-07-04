import { Badge, DataCard, Field, toneFor } from "../primitives";

export function ProviderCard({ name, payload }) {
  const statuses = payload.statuses || payload.accounts || [];
  return (
    <DataCard as="section">
      <h3 className="text-xl font-black text-white">{name}</h3>
      <p className="mt-1 text-sm text-slate-500">{payload.config?.accounts?.length || payload.accounts?.length || 0} configured accounts</p>
      <div className="mt-4 space-y-3">
        {statuses.map((row) => (
          <Field key={row.label || row.account || row.provider_name || row.resolved_model} label={row.label || row.account || "account"}>
            <div className="flex flex-wrap gap-2">
              <Badge tone={toneFor(row.probe_status || row.status)}>{row.probe_status || row.status || "unknown"}</Badge>
              <Badge>{row.resolved_model || row.model || "model n/a"}</Badge>
            </div>
            <p className="mt-2 text-slate-400">{row.detail || "No detail recorded."}</p>
          </Field>
        ))}
      </div>
    </DataCard>
  );
}
