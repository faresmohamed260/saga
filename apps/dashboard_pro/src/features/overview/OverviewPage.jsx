import { CanonLibraryPanel } from "../../components/overview-cards/CanonLibraryPanel.jsx";
import { OperationsPanel } from "../../components/overview-cards/OperationsPanel.jsx";
import { Metric, toneFor } from "../../components/primitives/index.js";
import { useRuntimeState } from "../../hooks/useRuntimeState";

export function OverviewPage() {
  const { state } = useRuntimeState();
  const artifacts = state?.artifacts || {};
  const database = artifacts.database || {};
  const jobs = state?.jobs || [];
  const books = artifacts.books || [];
  const latestJob = jobs[0];
  const storyCount = Number(database.generated_stories || 0);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Books" value={books.length} detail="library" tone="green" />
        <Metric label="Jobs" value={jobs.length} detail={latestJob?.status || "idle"} tone={toneFor(latestJob?.status)} />
        <Metric label="Stories" value={storyCount} detail="generated" tone="blue" />
        <Metric label="Prompts" value={state?.prompts?.length || 0} detail="available" tone="slate" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <OperationsPanel jobs={jobs} />
        <CanonLibraryPanel books={books} />
      </div>
    </div>
  );
}
