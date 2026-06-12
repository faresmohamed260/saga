import { describe, expect, test } from "vitest";
import {
  buildCharacterSnapshotCommand,
  buildEncodeStoreCommand,
  buildNeo4jDeleteCypher,
  buildPromptPackCommand,
  buildValidateContractCommand,
} from "./commandBuilder";

describe("commandBuilder", () => {
  test("builds encode-store command", () => {
    const command = buildEncodeStoreCommand({
      books: ["A.epub", "B.epub"],
      seriesId: "acotar",
      seriesTitle: "ACOTAR",
      seriesIdentityJson: "analysis_outputs\\identity_series\\acotar\\acotar_series_pipeline_identity.json",
      identityProvider: "booknlp_clean",
    });
    expect(command).toContain("saga_tools.py encode-store");
    expect(command).toContain("--book \"A.epub\"");
    expect(command).toContain("--identity-provider booknlp_clean");
  });

  test("builds validate contract command", () => {
    const command = buildValidateContractCommand("analysis_outputs\\encode_runs\\x.contract.json", { identityProvider: "booknlp_clean" });
    expect(command).toContain("validate-encoder-artifacts");
    expect(command).toContain("--contract \"analysis_outputs\\encode_runs\\x.contract.json\"");
  });

  test("builds snapshot and prompt commands", () => {
    expect(buildCharacterSnapshotCommand({ contractPaths: ["a.json"] })).toContain("build-character-state-snapshot");
    expect(buildPromptPackCommand({ visualStatePath: "v.json" })).toContain("build-comfyui-prompt-pack");
  });

  test("requires explicit neo4j delete cypher target", () => {
    expect(buildNeo4jDeleteCypher("acotar")).toContain("MATCH (s:Series");
    expect(buildNeo4jDeleteCypher("acotar", "Book")).toContain("MATCH (b:Book");
  });
});
