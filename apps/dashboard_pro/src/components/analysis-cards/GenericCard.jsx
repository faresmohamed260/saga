import { Badge, DataCard, Field, text } from "../primitives";

export function GenericCard({ row, index }) {
  return (
    <DataCard>
      <Badge>#{index + 1}</Badge>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {Object.entries(row || {}).slice(0, 12).map(([key, value]) => <Field key={key} label={key}>{text(value)}</Field>)}
      </div>
    </DataCard>
  );
}
