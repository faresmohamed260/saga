import { Badge, DataCard, StatusBanner, toneFor } from "../primitives";

export function ValidationSummary({ validation }) {
  if (!validation) return null;
  return (
    <DataCard className="bg-black/20">
      <Badge tone={toneFor(validation.status)}>{validation.status}</Badge>
      <p className="mt-3 text-sm text-slate-300">{validation.summary}</p>
      {(validation.errors || []).map((item) => <StatusBanner key={item} tone="red" message={item} />)}
      {(validation.warnings || []).map((item) => <StatusBanner key={item} tone="amber" message={item} />)}
    </DataCard>
  );
}
