import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Panel, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";

export function ProvidersPage() {
  const statuses = useAsync(() => runtimeApi.providerStatuses(false), []);
  async function refresh() {
    await runtimeApi.providerStatuses(true);
    await statuses.reload();
  }
  const providers = statuses.value?.providers || {};
  return (
    <Panel title="Provider Health" subtitle="Live or last refreshed account status from the local provider registry." action={<Button onClick={refresh} variant="primary">Refresh provider health</Button>}>
      {Object.keys(providers).length ? <div className="grid gap-4 xl:grid-cols-3">{Object.entries(providers).map(([name, payload]) => (
        <section key={name} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
          <h3 className="text-xl font-black text-white">{name}</h3>
          <p className="mt-1 text-sm text-slate-500">{payload.config?.accounts?.length || 0} configured accounts</p>
          <div className="mt-4 space-y-3">
            {(payload.statuses || []).map((row) => (
              <Field key={row.label} label={row.label}>
                <div className="flex flex-wrap gap-2"><Badge tone={toneFor(row.probe_status)}>{row.probe_status || "unknown"}</Badge><Badge>{row.resolved_model || "model n/a"}</Badge></div>
                <p className="mt-2 text-slate-400">{row.detail || "No detail recorded."}</p>
              </Field>
            ))}
          </div>
        </section>
      ))}</div> : <EmptyState title="No providers configured" />}
    </Panel>
  );
}
