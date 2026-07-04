import { StagedBookCard } from "./StagedBookCard";

export function StagedBookList({ rows, onUpdateRow, onMoveRow, onRemoveUpload }) {
  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <StagedBookCard
          key={row.source_id}
          row={row}
          index={index}
          total={rows.length}
          onUpdateRow={onUpdateRow}
          onMoveRow={onMoveRow}
          onRemoveUpload={onRemoveUpload}
        />
      ))}
    </div>
  );
}
