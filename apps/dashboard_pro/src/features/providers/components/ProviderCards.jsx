import { Badge, Button, DataCard, EmptyState, Field, Panel, toneFor } from "../../../components/ui/primitives";

export function ProviderHealthPanel({ providers, onRefresh }) {
  const providerEntries = normalizeProviderEntries(providers);
  return (
    <Panel title="Provider Health" subtitle="Live or last refreshed account status from the local provider registry." action={<Button onClick={onRefresh} variant="primary">Refresh provider health</Button>}>
      {providerEntries.length ? (
        <div className="grid gap-4 xl:grid-cols-3">
          {providerEntries.map(([name, payload]) => (
            <ProviderCard key={name} name={name} payload={payload} />
          ))}
        </div>
      ) : (
        <EmptyState title="No providers configured" />
      )}
    </Panel>
  );
}

function ProviderCard({ name, payload }) {
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

function normalizeProviderEntries(providers) {
  if (Array.isArray(providers)) {
    return providers.map((payload) => [payload.provider_name || payload.name || "provider", payload]);
  }
  return Object.entries(providers || {});
}
