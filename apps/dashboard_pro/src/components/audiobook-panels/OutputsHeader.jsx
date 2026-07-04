import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Toolbar, toneFor } from "../primitives";

export function OutputsHeader({ selectedRun, playableChapters }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-slate-400">
        {playableChapters.length} downloadable file{playableChapters.length === 1 ? "" : "s"} ready
      </p>
      <Toolbar>
        <Badge tone={toneFor(selectedRun.status)}>{selectedRun.status || "unknown"}</Badge>
        {playableChapters.length ? (
          <a
            href={runtimeApi.audiobookRunBundleUrl(selectedRun.id)}
            download={`${selectedRun.title || "audiobook"}.wav`}
            className="rounded-lg border border-cyan-400/50 bg-cyan-400/10 px-4 py-2 text-sm font-bold text-cyan-100 transition hover:bg-cyan-400/20"
          >
            Download full audiobook
          </a>
        ) : null}
      </Toolbar>
    </div>
  );
}
