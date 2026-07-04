import { Badge, DataCard, Field, toneFor } from "../primitives";
import { formatRunLabel } from "../../features/audiobook/audiobookUtils";

export function SelectedRunCard({ run }) {
  return (
    <DataCard>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-black text-white">{run.title || "Audiobook run"}</p>
          <p className="mt-1 text-sm text-slate-400">{formatRunLabel(run)}</p>
        </div>
        <Badge tone={toneFor(run.status)}>{run.status || "unknown"}</Badge>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <Field label="Voice">{run.voice || "Not set"}</Field>
        <Field label="Audio format">{run.audio_format || "wav"}</Field>
        <Field label="Updated">{run.updated_at || "n/a"}</Field>
      </div>
    </DataCard>
  );
}
