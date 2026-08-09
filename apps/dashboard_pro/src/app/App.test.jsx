import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import { AudiobookControlsPanel } from "../components/audiobook-panels/AudiobookControlsPanel.jsx";

const apiMock = vi.hoisted(() => ({
  state: vi.fn(async () => ({
    workspace: { root: "test-root" },
    artifacts: { books: [], generated_stories: [] },
    jobs: [{ id: "job-1", status: "completed", type: "db-native-analysis", progress: { label: "done" } }],
    prompts: [{ path: "saga/agents/db_event_agent.py", size_bytes: 100, snippet: "prompt schema" }],
  })),
  jobs: vi.fn(async () => ({ jobs: [{ id: "job-1", status: "completed", type: "db-native-analysis", progress: { label: "done" } }] })),
  job: vi.fn(async () => ({ id: "job-1", status: "completed", progress: { label: "done" }, log_tail: ["job finished"] })),
  jobLogs: vi.fn(async () => ({ lines: ["job finished"] })),
  series: vi.fn(async () => ({ series: [{ series_id: "series-1", title: "Series One", book_count: 1 }] })),
  seriesBooks: vi.fn(async () => ({ books: [{ book_id: "book-1", title: "Book One", run_status: "success", chapter_count: 3, scene_count: 5 }] })),
  audiobookRuns: vi.fn(async () => ({ runs: [{ id: "audio-run-1", title: "Book One audiobook", scope_type: "book", total_chapters: 3, voice: "af_bella", audio_format: "wav", status: "staged", updated_at: "2026-06-20T00:00:00Z" }] })),
  audiobookRun: vi.fn(async () => ({
    id: "audio-run-1",
    title: "Book One audiobook",
    scope_type: "book",
    total_books: 1,
    total_chapters: 3,
    transcript_storage_mode: "database",
    audio_storage_mode: "artifact",
    voice: "af_bella",
    audio_format: "wav",
    status: "staged",
    metadata: { rewrite_provider: "ollama", rewrite_fallback_mode: "strict_rewrite" },
    chapters: [
      { id: "audio-chapter-1", chapter_id: "chapter-1", book_id: "book-1", book_index: 1, chapter_index: 1, chapter_title: "Chapter 1", transcript_status: "staged", audio_status: "staged", transcript_text: "Chapter one transcript preview.", audio_artifact: { bucket_name: "audio-outputs", object_path: "series/series-1/audio/runs/audio-run-1/chapters/chapter-1/chapter-1.wav" } },
    ],
  })),
  stageAudiobookRun: vi.fn(async () => ({ run: { id: "audio-run-2", title: "Staged audiobook", scope_type: "book", total_books: 1, total_chapters: 3, transcript_storage_mode: "database", audio_storage_mode: "artifact", voice: "af_bella", audio_format: "wav", status: "staged", chapters: [] } })),
  startAudiobookJob: vi.fn(async () => ({
    run: { id: "audio-run-3", title: "Queued audiobook", scope_type: "book", total_books: 1, total_chapters: 3, transcript_storage_mode: "database", audio_storage_mode: "artifact", voice: "af_bella", audio_format: "wav", status: "queued", job_id: "audiobook-job-1", chapters: [] },
    job: { id: "audiobook-job-1", status: "queued" },
  })),
  startAudiobookRun: vi.fn(async () => ({
    run: { id: "audio-run-1", title: "Book One audiobook", scope_type: "book", total_books: 1, total_chapters: 3, transcript_storage_mode: "database", audio_storage_mode: "artifact", voice: "af_bella", audio_format: "wav", status: "queued", job_id: "audiobook-job-2", chapters: [] },
    job: { id: "audiobook-job-2", status: "queued" },
  })),
  audiobookChapterAudioUrl: vi.fn((runId, chapterId) => `/runtime/audiobook/runs/${runId}/chapters/${chapterId}/audio`),
  bookAnalysis: vi.fn(async () => ({
    book: { id: "book-1", title: "Book One" },
    sections: {
      scenes: [{ id: "scene-1", title: "Opening", text: "Full scene text" }],
      entities: [{ id: "entity-1", canonical_name: "Hero", entity_type: "character" }],
      events: [{ id: "event-1", description: "Hero finds a key", event_type: "discovery" }],
    },
    counts: { scenes: 1, entities: 1, events: 1 },
  })),
  uploads: vi.fn(async () => ({ uploads: [{ id: "source-1", original_name: "book.txt", size_bytes: 1000 }] })),
  uploadBatch: vi.fn(async () => ({ uploaded: [] })),
  createImportPlan: vi.fn(async () => ({ id: "plan-1", status: "staging" })),
  validateImportPlan: vi.fn(async () => ({ validation: { status: "ready", can_start: true, summary: "ready", errors: [], warnings: [] } })),
  startImportPlan: vi.fn(async () => ({ id: "analysis-1", status: "queued" })),
  decoderOptions: vi.fn(async () => ({
    modes: ["pre_canon", "mid_canon", "post_canon", "alternate_universe"],
    defaults: { provider: "ollama" },
    series: [{ series_id: "series-1", title: "Series One", book_count: 1 }],
    providers: [{ value: "ollama", label: "Ollama" }],
  })),
  validateDecoderPlan: vi.fn(async () => ({ valid: true, warnings: [], errors: [], plan: { series_id: "series-1" } })),
  stories: vi.fn(async () => ({ stories: [{ id: "story-1", title: "Story One", status: "completed", story_mode: "post_canon", series_id: "series-1" }] })),
  assetSeriesSummary: vi.fn(async () => ({ series: [{ series_id: "series-1", series_title: "Series One", asset_count: 1, rendered_count: 1 }] })),
  assets: vi.fn(async () => ({ total: 1, entities: [{ id: "entity-1", name: "Hero", entity_type: "character", series_id: "series-1", series_title: "Series One", book_title: "Book One", image_count: 1, prompt_count: 1, render_status: "completed", generated_image_artifact: { bucket_name: "generated-images", object_path: "series/series-1/assets/entity-1/render.png" } }] })),
  asset: vi.fn(async () => ({ entity: { id: "entity-1", name: "Hero", entity_type: "character", baseline_visual_prompt: "photo prompt", series_id: "series-1", series_title: "Series One", book_title: "Book One" }, prompts: [], images: [] })),
  savePromptVersion: vi.fn(async () => ({ prompt_id: "prompt-1" })),
  renderEntity: vi.fn(async () => ({ id: "render-1", status: "queued" })),
  renderBatch: vi.fn(async () => ({ id: "render-batch-1", status: "queued" })),
  providerStatuses: vi.fn(async () => ({ providers: [{ provider_name: "ollama", accounts: [], status: "ok" }] })),
}));

vi.mock("../api/runtimeApi", () => ({
  runtimeApi: apiMock,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("renders the production studio shell", async () => {
  window.history.pushState({}, "", "/overview");
  render(<BrowserRouter><App /></BrowserRouter>);
  expect(await screen.findByText("Story Production Studio")).toBeInTheDocument();
  expect(screen.getByText("S.A.G.A.")).toBeInTheDocument();
  expect(screen.getByText("Import")).toBeInTheDocument();
  expect(screen.getByText("Audiobook")).toBeInTheDocument();
});

test("renders the audiobook controls component", () => {
  render(
    <AudiobookControlsPanel
      plan={{
        scope: "book",
        seriesId: "series-1",
        bookRef: "db://book/book-1",
        tone: "classic",
        rewriteProvider: "ollama",
        rewriteFallbackMode: "strict_rewrite",
        voice: "af_bella",
        sampleRate: 24000,
        audioFormat: "wav",
        normalizeAudio: true,
        trimSilence: false,
        sentencePauseMs: 0,
      }}
      seriesRows={[{ series_id: "series-1", title: "Series One", book_count: 1 }]}
      seriesBooks={[{ book_id: "book-1", title: "Book One" }]}
      selectedSeries={{ series_id: "series-1", title: "Series One" }}
      canStage
      stageSubmitting={false}
      queueSubmitting={false}
      onPlanChange={vi.fn()}
      onStagePlan={vi.fn()}
      onQueuePlan={vi.fn()}
    />,
  );

  expect(screen.getByText("Audiobook Controls")).toBeInTheDocument();
  expect(screen.getByText("Single book")).toBeInTheDocument();
  expect(screen.getByText("Entire series")).toBeInTheDocument();
  expect(screen.getByText("Stage outputs")).toBeInTheDocument();
  expect(screen.getByText("Queue audiobook pipeline")).not.toBeDisabled();
});

test("switches away from audiobook without keeping stale content mounted", async () => {
  window.history.pushState({}, "", "/overview");
  render(<BrowserRouter><App /></BrowserRouter>);

  fireEvent.click(await screen.findByRole("link", { name: "Audiobook" }));
  expect(await screen.findByRole("heading", { name: "Audiobook Controls" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Library" }));

  expect(await screen.findByRole("heading", { name: "Library" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Audiobook Controls" })).not.toBeInTheDocument();
});

test("renders import workflow controls backed by upload and plan APIs", async () => {
  window.history.pushState({}, "", "/import/new");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Stage Books")).toBeInTheDocument();
  expect(await screen.findByText(/book\.txt/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Create and validate plan"));
  await waitFor(() => expect(apiMock.createImportPlan).toHaveBeenCalled());
  await waitFor(() => expect(apiMock.createImportPlan.mock.calls[0][0].shared_config.run_agents).toBe(true));
  expect((await screen.findAllByText("ready")).length).toBeGreaterThan(0);
});

test("renders runs page with job state", async () => {
  window.history.pushState({}, "", "/runs");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect((await screen.findAllByText("job-1")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("completed")).length).toBeGreaterThan(0);
});

test("renders decoder validation controls", async () => {
  window.history.pushState({}, "", "/stories");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Decoder Controls")).toBeInTheDocument();
  const validateButton = screen.getByText("Validate plan");
  await waitFor(() => expect(validateButton).not.toBeDisabled());
  fireEvent.click(validateButton);
  await waitFor(() => expect(apiMock.validateDecoderPlan).toHaveBeenCalled());
});

test("renders visual assets with prompt content", async () => {
  window.history.pushState({}, "", "/assets");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Hero")).toBeInTheDocument();
  expect(await screen.findByText(/series one/i)).toBeInTheDocument();
});

test("renders diagnostics with prompt metadata", async () => {
  window.history.pushState({}, "", "/diagnostics");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Diagnostics")).toBeInTheDocument();
  expect(await screen.findByText(/db_event_agent/)).toBeInTheDocument();
});
