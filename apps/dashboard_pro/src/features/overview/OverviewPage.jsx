import { Metric, toneFor } from "../../components/ui/primitives";
import { useRuntimeState } from "../../hooks/useRuntimeState";
import { CanonLibraryPanel, OperationsPanel } from "./components/OverviewCards";

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
        <Metric label="Books" value={books.length} detail="database" tone="green" />
        <Metric label="Jobs" value={jobs.length} detail={latestJob?.status || "idle"} tone={toneFor(latestJob?.status)} />
        <Metric label="Stories" value={storyCount} detail="generated" tone="blue" />
        <Metric label="Prompts" value={state?.prompts?.length || 0} detail="inspectable" tone="slate" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <OperationsPanel jobs={jobs} />
        <CanonLibraryPanel books={books} />
      </div>
    </div>
  );
}
