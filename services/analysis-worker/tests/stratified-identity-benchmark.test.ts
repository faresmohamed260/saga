import assert from "node:assert/strict";
import test from "node:test";

import { buildStratifiedIdentityBenchmark } from "../src/evaluation/stratified-identity-benchmark.js";
import type { IdentityBenchmarkCounts, IdentityBenchmarkMetrics } from "../src/evaluation/types.js";

function counts(overrides: Partial<IdentityBenchmarkCounts> = {}): IdentityBenchmarkCounts {
  return {
    documentCount: 1,
    goldSeedEligibleCharacterCount: 2,
    predictedCanonicalCount: 2,
    pureCanonicalCount: 1,
    falseCanonicalCount: 0,
    incorrectMergeCount: 1,
    contaminatedCanonicalCount: 1,
    representedGoldCharacterCount: 1,
    fragmentationExcessCount: 0,
    relevantGoldMentionCount: 4,
    predictedMentionCount: 5,
    correctLinkedMentionCount: 2,
    linkedMentionCount: 3,
    unresolvedRelevantMentionCount: 1,
    quarantinedRelevantMentionCount: 0,
    nonPersonPredictedMentionCount: 1,
    nonPersonLinkedMentionCount: 0,
    nonPersonQuarantinedMentionCount: 1,
    linkedPersonMentionCount: 3,
    dominantClusterLinkedPersonMentionCount: 2,
    ...overrides,
  };
}

const metrics: IdentityBenchmarkMetrics = {
  canonicalPrecision: 0.5,
  canonicalRecall: 0.5,
  falseCanonicalRate: 0,
  incorrectMergeRate: 0.5,
  contaminatedCanonicalRate: 0.5,
  fragmentationRate: 0,
  linkedMentionPrecision: 2 / 3,
  linkedMentionRecall: 0.5,
  unresolvedRelevantMentionRate: 0.25,
  quarantinedRelevantMentionRate: 0,
  nonPersonQuarantineRate: 1,
  clusterPurity: 2 / 3,
};

const report = {
  schemaVersion: "fixture-provider-v1",
  dataset: { repository: "dbamman/litbank", commit: "fixture-commit" },
  provider: { name: "fixture", model: "small", revision: "fixture-v1" },
  aggregateOutputFingerprint: "a".repeat(64),
  perDocument: [
    { documentId: "a", outputFingerprint: "b".repeat(64), counts: counts(), metrics },
    {
      documentId: "b",
      outputFingerprint: "c".repeat(64),
      counts: counts({
        goldSeedEligibleCharacterCount: 1,
        predictedCanonicalCount: 1,
        pureCanonicalCount: 1,
        incorrectMergeCount: 0,
        contaminatedCanonicalCount: 0,
        representedGoldCharacterCount: 1,
        relevantGoldMentionCount: 2,
        predictedMentionCount: 2,
        correctLinkedMentionCount: 2,
        linkedMentionCount: 2,
        unresolvedRelevantMentionCount: 0,
        nonPersonPredictedMentionCount: 0,
        nonPersonQuarantinedMentionCount: 0,
        linkedPersonMentionCount: 2,
        dominantClusterLinkedPersonMentionCount: 2,
      }),
      metrics,
    },
  ],
};

const manifest = {
  schemaVersion: "saga-novel-diversity-matrix-v1" as const,
  dataset: {
    repository: "dbamman/litbank",
    commit: "fixture-commit",
    annotationLayer: "coref/tsv",
    license: "CC BY 4.0",
  },
  policy: {
    purpose: "fixture",
    adoptionRule: "fixture",
    minimumRepeatabilityRuns: 2,
  },
  litbankStrata: [
    {
      id: "mixed",
      dimension: "genre",
      label: "Mixed",
      requiredMinDocuments: 2,
      documentIds: ["a", "b"],
      rationale: "fixture",
    },
  ],
};

test("stratified identity benchmark aggregates count-weighted metrics deterministically", () => {
  const first = buildStratifiedIdentityBenchmark({ report, manifest });
  const second = buildStratifiedIdentityBenchmark({ report, manifest });

  assert.equal(first.reportFingerprint, second.reportFingerprint);
  assert.equal(first.coverage.stratumCount, 1);
  assert.equal(first.coverage.uniqueDocumentCount, 2);
  assert.equal(first.strata[0]?.aggregate.counts.documentCount, 2);
  assert.equal(first.strata[0]?.aggregate.counts.predictedCanonicalCount, 3);
  assert.equal(first.strata[0]?.aggregate.metrics.canonicalPrecision, 2 / 3);
  assert.equal(first.strata[0]?.aggregate.metrics.canonicalRecall, 2 / 3);
});

test("stratified identity benchmark fails closed when a required document is missing", () => {
  assert.throws(
    () => buildStratifiedIdentityBenchmark({
      report: { ...report, perDocument: [report.perDocument[0]!] },
      manifest,
    }),
    /diversity_missing_document:mixed:b/u,
  );
});

test("stratified identity benchmark rejects a different dataset revision", () => {
  assert.throws(
    () => buildStratifiedIdentityBenchmark({
      report,
      manifest: {
        ...manifest,
        dataset: { ...manifest.dataset, commit: "other-commit" },
      },
    }),
    /diversity_dataset_revision_mismatch/u,
  );
});
