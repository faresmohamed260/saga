import { Button, Panel } from "../primitives";

export function StageBooksPanel({ busy, files, onFilesChange, onUpload }) {
  return (
    <Panel title="Stage Books" subtitle="Upload one or more local book files into the staging area.">
      <div className="grid gap-4 md:grid-cols-[1fr_auto]">
        <input type="file" multiple accept=".epub,.pdf,.txt" onChange={onFilesChange} className="w-full rounded-lg border border-white/10 bg-slate-950/70 p-3 text-sm text-slate-100" />
        <Button onClick={onUpload} disabled={busy || !files.length} variant="primary">{busy ? "Uploading..." : "Upload files"}</Button>
      </div>
    </Panel>
  );
}
