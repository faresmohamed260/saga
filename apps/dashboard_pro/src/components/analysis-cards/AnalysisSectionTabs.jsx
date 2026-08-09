import { Link } from "react-router-dom";
import { Toolbar } from "../primitives";
import { ANALYSIS_SECTIONS } from "./constants";
import { countFor } from "./utils";

export function AnalysisSectionTabs({ bookRef, section, view }) {
  return (
    <Toolbar className="mb-4">
      {ANALYSIS_SECTIONS.map(([key, label]) => (
        <Link
          key={key}
          to={`/books/${encodeURIComponent(bookRef)}/analysis/${key}`}
          className={`rounded-lg border px-3 py-2 text-sm font-black transition ${section === key ? "border-cyan-300/60 bg-cyan-300/15 text-white" : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-white/20"}`}
        >
          {label} - {countFor(view, key)}
        </Link>
      ))}
    </Toolbar>
  );
}
