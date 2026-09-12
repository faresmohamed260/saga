import assert from "node:assert/strict";
import test from "node:test";

import { evaluateIdentityBenchmarkCase } from "../src/evaluation/identity-benchmark.js";
import type { CharacterIdentityResult, NormalizedIdentityEvidence } from "../src/identity/types.js";
import type { GoldIdentityDocument } from "../src/evaluation/types.js";

const gold: GoldIdentityDocument = {
  documentId: "metric-fixture",
  text: "Ada met Ada. Bea left. The tower stood.",
  mentions: [
    { mentionId: "a1", surfaceText: "Ada", startOffset: 0, endOffset: 3, mentionKind: "proper_name", entityType: "person", goldCharacterId: "gold-ada" },
    { mentionId: "a2", surfaceText: "Ada", startOffset: 8, endOffset: 11, mentionKind: "proper_name", entityType: "person", goldCharacterId: "gold-ada" },
    { mentionId: "b1", surfaceText: "Bea", startOffset: 13, endOffset: 16, mentionKind: "proper_name", entityType: "person", goldCharacterId: "gold-bea" },
    { mentionId: "tower", surfaceText: "The tower", startOffset: 23, endOffset: 32, mentionKind: "nominal", entityType: "non_person", goldCharacterId: null },
  ],
};

const evidence: NormalizedIdentityEvidence = {
  provider: { name: "metric-fixture", model: null, revision: "v1" },
  normalizedInputFingerprint: "a".repeat(64),
  mentions: [],
};

const result: CharacterIdentityResult = {
  resolverVersion: "metric-fixture",
  resolverConfigFingerprint: "b".repeat(64),
  provider: evidence.provider,
  normalizedInputFingerprint: evidence.normalizedInputFingerprint,
  outputFingerprint: "c".repeat(64),
  characters: [
    { characterKey: "p1", canonicalName: "Ada", admissionTier: "canonical_seed", evidenceCount: 1, aliases: [] },
    { characterKey: "p2", canonicalName: "Ada Bea", admissionTier: "canonical_seed", evidenceCount: 2, aliases: [] },
    { characterKey: "p3", canonicalName: "Tower", admissionTier: "canonical_seed", evidenceCount: 1, aliases: [] },
  ],
  mentions: [
    { evidenceId: "a1", characterKey: "p1", surfaceText: "Ada", startOffset: 0, endOffset: 3, structuralLocator: null, mentionKind: "proper_name", resolutionState: "linked", evidenceTier: "canonical_seed", decisionReason: "fixture" },
    { evidenceId: "a2", characterKey: "p2", surfaceText: "Ada", startOffset: 8, endOffset: 11, structuralLocator: null, mentionKind: "proper_name", resolutionState: "linked", evidenceTier: "canonical_seed", decisionReason: "fixture" },
    { evidenceId: "b1", characterKey: "p2", surfaceText: "Bea", startOffset: 13, endOffset: 16, structuralLocator: null, mentionKind: "proper_name", resolutionState: "linked", evidenceTier: "canonical_seed", decisionReason: "fixture" },
    { evidenceId: "tower", characterKey: "p3", surfaceText: "The tower", startOffset: 23, endOffset: 32, structuralLocator: null, mentionKind: "nominal", resolutionState: "linked", evidenceTier: "attachment", decisionReason: "fixture" },
  ],
};

test("benchmark counts false canonicals, incorrect merges, fragmentation, and contamination separately", () => {
  const report = evaluateIdentityBenchmarkCase({ gold, evidence, result });

  assert.equal(report.counts.goldSeedEligibleCharacterCount, 2);
  assert.equal(report.counts.predictedCanonicalCount, 3);
  assert.equal(report.counts.pureCanonicalCount, 1);
  assert.equal(report.counts.falseCanonicalCount, 1);
  assert.equal(report.counts.incorrectMergeCount, 1);
  assert.equal(report.counts.contaminatedCanonicalCount, 1);
  assert.equal(report.counts.fragmentationExcessCount, 1);
  assert.equal(report.counts.correctLinkedMentionCount, 1);
  assert.equal(report.counts.linkedMentionCount, 4);

  assert.equal(report.metrics.canonicalPrecision, 1 / 3);
  assert.equal(report.metrics.canonicalRecall, 1 / 2);
  assert.equal(report.metrics.falseCanonicalRate, 1 / 3);
  assert.equal(report.metrics.incorrectMergeRate, 1 / 3);
  assert.equal(report.metrics.fragmentationRate, 1 / 2);
  assert.equal(report.metrics.linkedMentionPrecision, 1 / 4);
  assert.equal(report.metrics.linkedMentionRecall, 1 / 3);
  assert.equal(report.metrics.clusterPurity, 2 / 3);
});
