import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

const runtimeState = {
  workspace: {
    root: "B:\\Documents\\PyCharm\\graduationProject",
    outputs: "analysis_outputs",
    uploads: "analysis_outputs\\dashboard\\uploads",
  },
  defaults: {
    books: ["book1.epub", "book2.epub"],
    models: ["gpt_oss"],
    provider_modes: ["same_provider_rotating"],
  },
  artifacts: {
    counts: { runs: 1, contracts: 1, total_scenes: 2, identities: 1, visual_states: 1 },
    runs: [],
    contracts: [],
    reports: [],
    visual_states: [],
    identities: [],
  },
  jobs: [],
  providers: {
    ollama: { active_index: 0, accounts: [] },
    codex: { active_index: 0, accounts: [] },
  },
  prompts: [
    {
      path: "analysis/db_event_agent.py",
      name: "db_event_agent.py",
      line_count: 10,
      prompt_hits: ["You are an event extraction analyst."],
      content: "You are an event extraction analyst.",
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(runtimeState),
      }),
    ),
  );
});

test("renders project-owned local dashboard without workspace picker", async () => {
  render(<App />);
  expect(await screen.findByText("S.A.G.A. Operations Console")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analysis" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Decoder" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Diagnostics" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Providers" })).toBeInTheDocument();
  expect(screen.queryByText(/Select Project Workspace/i)).not.toBeInTheDocument();
});
