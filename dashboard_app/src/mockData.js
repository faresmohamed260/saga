export const mockOverview = {
  latest_run: {
    run_id: "20260528T104757Z",
    series_id: "acotar-full-booknlp-clean-v1",
    status: "success",
  },
  total_scenes: 249,
  failed_scenes: 0,
  contract_count: 5,
  report_count: 18,
  identity_file_count: 11,
  state_snapshot_count: 2,
  visual_world_state_count: 3,
  prompt_pack_count: 4,
  identity_provider_status: "booknlp_clean",
  neo4j_status: { implemented: false, connected: null, message: "Not wired yet" },
};

export const mockRuns = {
  items: [
    {
      id: "mock-run",
      series_id: "acotar-full-booknlp-clean-v1",
      run_id: "20260528T104757Z",
      status: "success",
      completed_books: 5,
      failed_books: 0,
      remaining_books: 0,
      contract_count: 5,
      report_count: 6,
      status_data: {
        books: [
          { title: "A Court of Thorns and Roses", status: "completed", total_scenes: 41, failed_scenes: 0 },
          { title: "A Court of Mist and Fury", status: "completed", total_scenes: 56, failed_scenes: 0 },
          { title: "A Court of Wings and Ruin", status: "completed", total_scenes: 64, failed_scenes: 0 },
        ],
      },
    },
  ],
};

export const mockContracts = {
  items: [
    {
      id: "mock-contract",
      name: "05_A Court of Silver Flames.epub.contract.json",
      display_path: "analysis_outputs/encode_runs/acotar-full-booknlp-clean-v1/.../contracts/05_A Court of Silver Flames.epub.contract.json",
      summary: {
        book_title: "A Court of Silver Flames",
        scene_count: 66,
        timeline_count: 329,
        event_ledger_count: 329,
        character_profile_count: 32,
        alias_count: 22,
        identity_provider: "booknlp_clean",
        analysis_model: "gpt_oss",
        scene_failure_policy: "fail_fast",
      },
    },
  ],
};

export const mockReports = {
  items: [
    {
      id: "mock-report",
      name: "acotar_full_booknlp_clean_v1_summary_20260527.md",
      display_path: "analysis_outputs/encoder_validation/acotar_full_booknlp_clean_v1_summary_20260527.md",
      modified_at: "2026-05-27T20:00:00+00:00",
    },
  ],
};

export const promptExamples = [
  {
    name: "Nesta Character Sheet",
    type: "character",
    score: 5,
    prompt:
      "high fae woman, pale intense features, dark loose hair, valkyrie training leathers, controlled fury, fantasy portrait lighting, cinematic realism",
  },
  {
    name: "House of Wind Concept",
    type: "location",
    score: 4,
    prompt:
      "mountain palace carved into stone, high balconies, dramatic moonlit sky, ancient library hidden below, fantasy architectural concept art",
  },
  {
    name: "Nesta + Cassian Training Beat",
    type: "scene",
    score: 4,
    prompt:
      "stone training ring open to mountain air, nesta and cassian mid-drill, disciplined combat posture, worn leathers, cold morning light, fantasy action still",
  },
];

export const mockNeo4jStatus = {
  implemented: true,
  connected: false,
  status: "unavailable",
  message: "Neo4j is not wired in this local environment yet.",
};

export const mockNeo4jSeries = {
  items: [
    { series_id: "acotar", title: "A Court of Thorns and Roses", book_count: 5, updated_at: "2026-05-28T00:00:00Z" },
  ],
};

export const mockNeo4jBooks = {
  items: [
    { series_id: "acotar", book_index: 1, title: "A Court of Thorns and Roses", analysis_model: "gpt_oss", identity_model: "gpt_oss" },
    { series_id: "acotar", book_index: 5, title: "A Court of Silver Flames", analysis_model: "gpt_oss", identity_model: "gpt_oss" },
  ],
};

export const mockNeo4jSummary = {
  implemented: true,
  connected: false,
  status: "unavailable",
  counts: {
    Series: 1,
    Book: 5,
    Chapter: 249,
    Scene: 249,
    Entity: 237,
    Event: 1244,
    StateTransition: 0,
    Relationships: 312,
  },
};

export const mockIdentities = {
  items: [
    {
      id: "mock-identity",
      name: "booknlp_small_pipeline_identity.json",
      display_path: "analysis_outputs/identity_series/acotar/book_05_acosf/booknlp_small_pipeline_identity.json",
    },
  ],
};

export const mockStateSnapshots = {
  items: [
    {
      id: "mock-snapshot",
      name: "acotar_post_acosf_character_states.json",
      display_path: "analysis_outputs/state_snapshots/acotar_post_acosf_character_states.json",
    },
  ],
};

export const mockVisualStates = {
  items: [
    {
      id: "mock-visual",
      name: "acosf_visual_world_state_20260528.json",
      display_path: "analysis_outputs/visual_state/acosf_visual_world_state_20260528.json",
    },
  ],
};

export const mockPromptPacks = {
  items: [
    {
      id: "mock-pack",
      name: "comfyui_acosf_prompt_pack_20260528.json",
      display_path: "analysis_outputs/visual_state/comfyui_acosf_prompt_pack_20260528.json",
    },
  ],
};

export const mockRetrievalContexts = {
  items: [
    {
      id: "mock-context",
      name: "acotar6_post_acosf_context_validation_20260528.json",
      display_path: "analysis_outputs/retrieval_validation/acotar6_post_acosf_context_validation_20260528.json",
    },
  ],
};
