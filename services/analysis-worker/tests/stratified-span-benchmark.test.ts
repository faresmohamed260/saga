import assert from "node:assert/strict";
import test from "node:test";

import type { NovelDiversityManifest } from "../src/evaluation/stratified-identity-benchmark.js";
import {
  buildStratifiedSpanBenchmark,
  type SpanBenchmarkCounts,
  type StratifiedSpanSourceReport,
} from "../src/evaluation/stratified-span-benchmark.js";

function counts(overrides: Partial<SpanBenchmarkCounts> = {}): SpanBenchmarkCounts {
  return {
    documentCount: 1,
    goldPersonMentionCount: 10,
    goldPersonProperNameCount: 4,
    predictedPersonMentionCount: 5,
    predictedPersonProperNameCount: 3,
    correctPersonMentionCount: 4,
    representedGoldPersonMentionCount: 4,
    correctPersonProperNameCount: 2,
    representedGoldPersonProperNameCount: 2,
    goldTypedMentionCount: 12,
    predictedTypedMentionCount: 6,
    correctTypedMentionCount: 4,
    representedGoldTypedMentionCount: 4,
    ...overrides,
  };
}

function manifest(): NovelDiversityManifest {
  return {
    schemaVersion: "saga-novel-diversity-matrix-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: "litbank-pin",
      annotationLayer: "coref/tsv",
      license: "CC BY 4.0",
    },
    policy: {
      purpose: "test",
      adoptionRule: "report strata",
      minimumRepeatabilityRuns: 2,
    },
    litbankStrata: [
      {
        id: "mixed",
        dimension: "genre",
        label: "Mixed",
        requiredMinDocuments: 2,
        documentIds: ["a", "b"],
        rationale: "test aggregation",
      },
    ],
  };
}

function sourceReport(): StratifiedSpanSourceReport {
  const makeMetrics = () => ({
    personSpanPrecision: 0,
    personSpanRecall: 0,
    properPersonSpanPrecision: 0,
    properPersonSpanRecall: 0,
    typedSpanPrecision: 0,
    typedSpanRecall: 0,
  });
  return {
    schemaVersion: "saga-gliner-litbank-span-benchmark-v1",
    dataset: { repository: "dbamman/litbank", commit: "litbank-pin" },
    provider: { name: "gliner", model: "test", revision: "r1" },
    perDocument: [
      { documentId: "a", counts: counts(), metrics: makeMetrics() },
      {
        documentId: "b",
        counts: counts({
          goldPersonMentionCount: 30,
          predictedPersonMentionCount: 15,
          correctPersonMentionCount: 6,
          representedGoldPersonMentionCount: 6,
        }),
        metrics: makeMetrics(),
      },
    ],
  };
}

test("stratified span benchmark aggregates counts rather than averaging document metrics", () => {
  const output = buildStratifiedSpanBenchmark({ report: sourceReport(), manifest: manifest() });
  const stratum = output.strata[0]!;
  assert.equal(stratum.documentCount, 2);
  assert.equal(stratum.aggregate.counts.goldPersonMentionCount, 40);
  assert.equal(stratum.aggregate.counts.predictedPersonMentionCount, 20);
  assert.equal(stratum.aggregate.counts.correctPersonMentionCount, 10);
  assert.equal(stratum.aggregate.metrics.personSpanPrecision, 0.5);
  assert.equal(stratum.aggregate.metrics.personSpanRecall, 0.25);
  assert.equal(output.coverage.stratumCount, 1);
  assert.equal(output.reportFingerprint.length, 64);
});

test("stratified span benchmark fails closed when a required novel is absent", () => {
  const report = sourceReport();
  report.perDocument = report.perDocument.filter((document) => document.documentId !== "b");
  assert.throws(
    () => buildStratifiedSpanBenchmark({ report, manifest: manifest() }),
    /diversity_missing_document:mixed:b/,
  );
});

test("stratified span benchmark rejects a different dataset revision", () => {
  const report = sourceReport();
  report.dataset.commit = "different";
  assert.throws(
    () => buildStratifiedSpanBenchmark({ report, manifest: manifest() }),
    /diversity_dataset_revision_mismatch/,
  );
});
