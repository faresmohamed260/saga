import { describe, expect, test, vi } from "vitest";
import { buildArtifactIndex } from "./artifactIndexer";
import { ARTIFACT_TYPES, classifyArtifactPath } from "./artifactTypes";

vi.mock("./jsonLoader", () => ({
  summarizeJsonText: async (text, artifactType) => {
    const payload = JSON.parse(text);
    if (artifactType === "contract") {
      return {
        artifactType,
        bookTitle: payload.metadata?.book_title || "",
        sceneCount: (payload.outputs?.resolved_scene_analyses || []).length,
        timelineCount: (payload.outputs?.timeline || []).length,
        eventLedgerCount: (payload.outputs?.event_ledger || []).length,
        entityRegistryCount: (payload.outputs?.entity_registry || []).length,
        characterProfileCount: (payload.outputs?.character_profiles || []).length,
        stableCharacterStateCount: (payload.outputs?.stable_character_states || []).length,
      };
    }
    return { artifactType };
  },
}));

function createFileHandle(name, text, lastModified = 1) {
  return {
    name,
    kind: "file",
    async getFile() {
      return {
        size: text.length,
        lastModified,
        async text() {
          return text;
        },
      };
    },
  };
}

function createDirectoryHandle(name, children) {
  return {
    name,
    kind: "directory",
    async getDirectoryHandle(childName) {
      const child = children[childName];
      if (!child || child.kind !== "directory") throw new Error("missing");
      return child;
    },
    async *values() {
      for (const value of Object.values(children)) {
        yield value;
      }
    },
  };
}

describe("artifactIndexer", () => {
  test("classifies contract and report paths", () => {
    expect(classifyArtifactPath("analysis_outputs/contract_exports/acotar/20260612T123219Z/contracts/01_book.contract.json")).toBe(ARTIFACT_TYPES.CONTRACT);
    expect(classifyArtifactPath("analysis_outputs/dashboard/report.md")).toBe(ARTIFACT_TYPES.REPORT);
  });

  test("does not classify series-level latest_status or helper folders as runs", () => {
    expect(classifyArtifactPath("analysis_outputs/pipeline_runtime/acotar/latest_status.json")).not.toBe(ARTIFACT_TYPES.RUN_STATUS);
    expect(classifyArtifactPath("analysis_outputs/pipeline_runtime/acotar/resume_checkpoints/latest_status.json")).not.toBe(ARTIFACT_TYPES.RUN_STATUS);
    expect(classifyArtifactPath("analysis_outputs/pipeline_runtime/acotar/20260612T123219Z/latest_status.json")).toBe(ARTIFACT_TYPES.RUN_STATUS);
  });

  test("indexes contract and report artifacts from workspace", async () => {
    const contractJson = JSON.stringify({
      metadata: { book_title: "Book One" },
      outputs: { resolved_scene_analyses: [{ scene_id: "s1" }], timeline: [], event_ledger: [], entity_registry: [], character_profiles: [] },
    });
    const reportMd = "# Audit\n\nHello";
    const root = createDirectoryHandle("graduationProject", {
      analysis_outputs: createDirectoryHandle("analysis_outputs", {
        contract_exports: createDirectoryHandle("contract_exports", {
          acotar: createDirectoryHandle("acotar", {
            "20260612T123219Z": createDirectoryHandle("20260612T123219Z", {
              contracts: createDirectoryHandle("contracts", {
                "01_book.contract.json": createFileHandle("01_book.contract.json", contractJson),
              }),
            }),
          }),
        }),
        dashboard: createDirectoryHandle("dashboard", {
          "report.md": createFileHandle("report.md", reportMd),
        }),
        encoder_validation: createDirectoryHandle("encoder_validation", {}),
        identity_series: createDirectoryHandle("identity_series", {}),
        state_snapshots: createDirectoryHandle("state_snapshots", {}),
        visual_state: createDirectoryHandle("visual_state", {}),
        retrieval_validation: createDirectoryHandle("retrieval_validation", {}),
      }),
    });
    const result = await buildArtifactIndex(root);
    expect(result.items.length).toBe(2);
    expect(result.counts.contract).toBe(1);
    expect(result.counts.report).toBe(1);
  });
});
