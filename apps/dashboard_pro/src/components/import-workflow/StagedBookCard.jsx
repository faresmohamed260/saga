import { Button, DataCard, Field, TextInput, Toolbar } from "../primitives";

export function StagedBookCard({ row, index, total, onUpdateRow, onMoveRow, onRemoveUpload }) {
  return (
    <DataCard>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-black text-white">{row.source_name}</p>
          <p className="mt-1 text-sm text-slate-500">{((row.size_bytes || 0) / 1024 / 1024).toFixed(2)} MB</p>
        </div>
        <Toolbar>
          <Button onClick={() => onMoveRow(row.source_id, -1)} disabled={index === 0}>Move up</Button>
          <Button onClick={() => onMoveRow(row.source_id, 1)} disabled={index === total - 1}>Move down</Button>
          <Button variant="danger" onClick={() => onRemoveUpload(row.source_id)}>Remove</Button>
        </Toolbar>
      </div>
      <div className="grid gap-3 md:grid-cols-[120px_1fr_160px]">
        <Field label="Include">
          <input type="checkbox" checked={row.selected} onChange={(event) => onUpdateRow(row.source_id, { selected: event.target.checked })} />
        </Field>
        <Field label="Target title">
          <TextInput value={row.target_title} onChange={(event) => onUpdateRow(row.source_id, { target_title: event.target.value })} />
        </Field>
        <Field label="Book index">
          <TextInput type="number" min="1" value={row.book_index} onChange={(event) => onUpdateRow(row.source_id, { book_index: event.target.value })} />
        </Field>
      </div>
    </DataCard>
  );
}
