import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";

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
  seriesBooks: vi.fn(async () => ({ books: [{ book_id: "book-1", title: "Book One", run_status: "success" }] })),
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
  assets: vi.fn(async () => ({ total: 1, entities: [{ id: "entity-1", name: "Hero", entity_type: "character", series_id: "series-1", series_title: "Series One", book_title: "Book One", image_count: 1, prompt_count: 1, render_status: "completed", generated_thumbnail_path: "", generated_image_path: "" }] })),
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

test("renders the production dashboard shell", async () => {
  window.history.pushState({}, "", "/overview");
  render(<BrowserRouter><App /></BrowserRouter>);
  expect(await screen.findByText("S.A.G.A. Operations Console")).toBeInTheDocument();
  expect(screen.getByText("Import")).toBeInTheDocument();
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

test("renders runs page with persisted job state", async () => {
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

test("renders visual assets with database-backed prompt content", async () => {
  window.history.pushState({}, "", "/assets");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Hero")).toBeInTheDocument();
  expect(await screen.findByText(/series one/i)).toBeInTheDocument();
});

test("renders diagnostics with prompt metadata instead of raw dumps", async () => {
  window.history.pushState({}, "", "/diagnostics");
  render(<BrowserRouter><App /></BrowserRouter>);

  expect(await screen.findByText("Diagnostics")).toBeInTheDocument();
  expect(await screen.findByText(/db_event_agent/)).toBeInTheDocument();
});
