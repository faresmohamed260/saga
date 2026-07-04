import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { RuntimeProvider } from "../hooks/useRuntimeState";
import { OverviewPage } from "../features/overview/OverviewPage";
import { RunsPage } from "../features/runs/RunsPage";
import { LibraryPage } from "../features/library/LibraryPage";
import { AnalysisPage } from "../features/analysis/AnalysisPage";
import { ImportPage } from "../features/ingestion/ImportPage";
import { VisualAssetsPage } from "../features/visual-assets/VisualAssetsPage";
import { DecoderPage } from "../features/decoder/DecoderPage";
import { ProvidersPage } from "../features/providers/ProvidersPage";
import { DiagnosticsPage } from "../features/diagnostics/DiagnosticsPage";
import { AudiobookPage } from "../features/audiobook/AudiobookPage";

export default function App() {
  return (
    <RuntimeProvider>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="import/new" element={<ImportPage />} />
          <Route path="import/:planId/review" element={<ImportPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="runs/:jobId" element={<RunsPage />} />
          <Route path="books" element={<LibraryPage />} />
          <Route path="books/:bookId/analysis/:section?" element={<AnalysisPage />} />
          <Route path="assets" element={<VisualAssetsPage />} />
          <Route path="assets/entities/:entityId" element={<VisualAssetsPage />} />
          <Route path="audiobook" element={<AudiobookPage />} />
          <Route path="stories" element={<DecoderPage />} />
          <Route path="stories/new" element={<DecoderPage mode="new" />} />
          <Route path="stories/:storyId" element={<DecoderPage />} />
          <Route path="providers" element={<ProvidersPage />} />
          <Route path="diagnostics" element={<DiagnosticsPage />} />
        </Route>
      </Routes>
    </RuntimeProvider>
  );
}
