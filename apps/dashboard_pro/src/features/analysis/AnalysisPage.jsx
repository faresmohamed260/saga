import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { runtimeApi } from "../../api/runtimeApi";
import { AnalysisRowsPanel } from "../../components/analysis-cards/AnalysisRowsPanel.jsx";
import { AnalysisSectionTabs } from "../../components/analysis-cards/AnalysisSectionTabs.jsx";
import { searchableLabelFor } from "../../components/analysis-cards/utils.js";
import { EmptyState, Panel, SearchBox } from "../../components/primitives/index.js";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function AnalysisPage() {
  const params = useParams();
  const { state } = useRuntimeState();
  const defaultBook = state?.artifacts?.books?.[0]?.path;
  const bookRef = params.bookId ? decodeURIComponent(params.bookId) : defaultBook;
  const section = params.section || "entities";
  const analysis = useAsync(() => bookRef ? runtimeApi.bookAnalysis(bookRef, { section, limit: 250 }) : Promise.resolve(null), [bookRef, section]);
  const [query, setQuery] = useState("");

  const view = analysis.value;
  const outputs = view?.outputs || {};
  const rows = useMemo(() => {
    const raw = section === "scenes" ? outputs.resolved_scene_analyses
      : section === "entities" ? outputs.entity_registry
      : section === "events" ? outputs.event_ledger
      : section === "timeline" ? outputs.timeline
      : section === "states" ? outputs.stable_character_states
      : section === "world" ? outputs.scene_world_state
      : outputs.visual_inventory;
    const q = query.trim().toLowerCase();
    if (!q) return raw || [];
    return (raw || []).filter((row) => searchableLabelFor(section, row).toLowerCase().includes(q));
  }, [outputs, section, query]);

  if (!bookRef) return <EmptyState title="No books found">Import or seed a book first.</EmptyState>;
  if (analysis.loading) return <EmptyState title="Loading analysis" />;
  if (analysis.error) return <EmptyState title="Analysis failed to load">{analysis.error}</EmptyState>;

  return (
    <div className="space-y-5">
      <Panel title={view?.summary?.name || "Book analysis"} subtitle={view?.path || bookRef}>
        <AnalysisSectionTabs bookRef={bookRef} section={section} view={view} />
        <SearchBox value={query} onChange={setQuery} placeholder={`Search ${section}...`} />
      </Panel>

      <AnalysisRowsPanel rows={rows} section={section} />
    </div>
  );
}
