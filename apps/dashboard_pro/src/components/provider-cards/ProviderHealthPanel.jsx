import { Button, EmptyState, Panel } from "../primitives";
import { ProviderCard } from "./ProviderCard";
import { normalizeProviderEntries } from "./providerUtils";

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
