import { useEffect, useState } from "react";
import { EditablePromptRegion } from "./EditablePromptRegion";
import { LockedPromptToken } from "./LockedPromptToken";

export function StructuredPromptEditor({ label, helper = "", compiledPrompt, segments, onChangeSegment, large = false }) {
  const [showCompiled, setShowCompiled] = useState(false);

  useEffect(() => {
    setShowCompiled(false);
  }, [label]);

  return (
    <div className={large ? "rounded-lg border border-white/10 bg-black/25 p-5" : "rounded-lg border border-white/10 bg-black/25 p-4"}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
        <button
          type="button"
          onClick={() => setShowCompiled((current) => !current)}
          className="text-[11px] font-medium text-cyan-300 transition hover:text-cyan-200"
        >
          {showCompiled ? "Hide compiled prompt" : "View compiled prompt"}
        </button>
      </div>
      {helper ? <p className="mb-3 text-[11px] leading-5 text-slate-500">{helper}</p> : null}
      {showCompiled ? (
        <div className="mb-3 rounded-lg border border-white/10 bg-slate-950/75 px-3 py-3">
          <p className="mb-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">Compiled prompt</p>
          <pre className="whitespace-pre-wrap break-words text-[12px] leading-[1.55] text-slate-300">{compiledPrompt || "No prompt compiled yet."}</pre>
        </div>
      ) : null}
      <div className="rounded-lg border border-white/10 bg-slate-950/80 transition focus-within:border-cyan-400/45 focus-within:ring-1 focus-within:ring-cyan-400/35">
        <div className="space-y-2 p-3">
          {segments.map((segment) => (
            segment.kind === "locked" ? (
              <LockedPromptToken key={segment.id} title={segment.title} value={segment.value} />
            ) : (
              <EditablePromptRegion
                key={segment.id}
                label={segment.title}
                value={segment.value}
                onChange={(value) => onChangeSegment(segment.id, value)}
                placeholder={segment.placeholder}
                large={large}
              />
            )
          ))}
        </div>
      </div>
    </div>
  );
}
