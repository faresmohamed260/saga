import { useState } from "react";
import { text } from "../primitives";
import { segmentLineCount } from "../../features/visual-assets/promptTemplates";

export function LockedPromptToken({ title, value }) {
  const lines = String(value || "").split("\n").filter(Boolean);
  const isLong = lines.length > 6;
  const [expanded, setExpanded] = useState(false);
  const preview = isLong && !expanded ? `${lines.slice(0, 2).join(" ")}` : value;

  return (
    <div className="rounded-md bg-slate-900/40 px-3 py-2 text-slate-300">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-[10px] text-slate-500">
          <span aria-hidden="true" className="inline-flex h-3.5 w-3.5 items-center justify-center text-slate-500">
            <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
              <path d="M5.5 7V5.75a2.5 2.5 0 1 1 5 0V7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              <rect x="3.5" y="7" width="9" height="6" rx="1.6" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </span>
          <span className="truncate font-medium uppercase tracking-[0.14em]">{title || "Locked template"}</span>
          <span className="whitespace-nowrap">{segmentLineCount(value)} lines</span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="shrink-0 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500 transition hover:text-slate-300"
        >
          {expanded ? "Hide" : "Preview"}
        </button>
      </div>
      {expanded ? (
        <div className="mt-2 border-l-2 border-slate-700/60 pl-3">
          <p className="whitespace-pre-wrap break-words text-[12.5px] leading-[1.55] text-slate-300">{text(value, "No locked template.")}</p>
        </div>
      ) : isLong ? null : (
        <div className="mt-1.5 border-l-2 border-slate-700/60 pl-3">
          <p className="truncate text-[12px] leading-[1.55] text-slate-400">{preview}</p>
        </div>
      )}
    </div>
  );
}
