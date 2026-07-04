import { Badge, DataCard, EmptyState, Field, Toolbar, formatDisplayValue, text } from "../primitives";

export function StateCard({ row, index }) {
  const name = row.character_name || row.entity_name || row.name || `State ${index + 1}`;
  const attributes = row.attributes || row.state || {};
  const latest = row.latest_state || row.state_at_latest || {};
  const metadata = row.agent_metadata || row.tool_runtime || {};
  const hasPayload = formatDisplayValue(attributes) || formatDisplayValue(latest) || formatDisplayValue(row.evidence);
  return (
    <DataCard>
      <Toolbar>
        <Badge>#{index + 1}</Badge>
        <Badge tone={hasPayload ? "green" : "amber"}>{hasPayload ? "state recorded" : "payload sparse"}</Badge>
      </Toolbar>
      <h3 className="mt-3 text-xl font-black text-white">{name}</h3>
      {hasPayload ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Field label="Stable attributes">{text(attributes)}</Field>
          <Field label="Latest state">{text(latest)}</Field>
          <Field label="Evidence">{text(row.evidence || row.notes)}</Field>
          <Field label="Agent metadata">{text(metadata)}</Field>
        </div>
      ) : (
        <EmptyState title="No stable character details recorded">A state entry exists for this character, but usable attributes were not saved yet.</EmptyState>
      )}
    </DataCard>
  );
}
