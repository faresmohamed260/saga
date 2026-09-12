import assert from "node:assert/strict";
import test from "node:test";

import { createAnalysisExperimentRecord } from "../src/evaluation/experiment-record.js";
import type { AnalysisBenchmarkManifest } from "../src/local-analysis/types.js";

const benchmark: AnalysisBenchmarkManifest = {
  schemaVersion: "saga-analysis-benchmark-v1",
  benchmarkId: "fixture-booknlp-small",
  source: {
    id: "fixture",
    sha256: "a".repeat(64),
    codePointCount: 123,
    utf8ByteCount: 130,
  },
  provider: {
    name: "booknlp_small",
    model: "booknlp-small",
    revision: "booknlp:1.0.7",
  },
  hardware: {
    hostLabel: "fixture-host",
    cpu: "fixture-cpu",
    logicalCpuCount: 8,
    ramMb: 16384,
    gpu: null,
    vramMb: null,
  },
  configurationFingerprint: "b".repeat(64),
  resources: {
    wallClockMs: 1250,
    peakResidentMemoryMb: 1024,
    peakVramMb: null,
    modelArtifactBytes: 512000000,
  },
  outputCounts: {
    identityMentions: 10,
    entities: 12,
    quotes: 4,
    eventTriggers: 18,
  },
};

function makeRecord() {
  return createAnalysisExperimentRecord({
    experimentId: "booknlp-small-litbank-v1",
    capability: "character_identity",
    candidate: {
      provider: benchmark.provider,
      variant: "small",
      implementation: "BookNLP 1.0.7",
      license: "MIT",
      source: "https://github.com/booknlp/booknlp",
      modelArtifactSha256: null,
    },
    benchmark,
    quality: [
      {
        datasetId: "litbank",
        datasetRevision: "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8",
        sampleCount: 100,
        metrics: {
          canonicalPrecision: 0.95,
          canonicalRecall: 0.91,
        },
      },
    ],
    repeatability: {
      attemptedRuns: 2,
      completedRuns: 2,
      outputFingerprints: ["c".repeat(64), "c".repeat(64)],
      failureCodes: [],
    },
    decision: {
      status: "candidate",
      rationale: "Recorded for comparison; no adoption decision yet.",
      comparedAgainst: ["oracle-policy-baseline"],
      decidedAt: null,
    },
    limitations: ["Fixture resource sample is synthetic."],
    notes: ["Normal CI never downloads the heavyweight model."],
  });
}

test("experiment records are deterministic and derive repeatability", () => {
  const first = makeRecord();
  const second = makeRecord();

  assert.equal(first.recordFingerprint, second.recordFingerprint);
  assert.equal(first.repeatability.stableOutput, true);
  assert.deepEqual(first.repeatability.failureCodes, []);
  assert.equal(first.schemaVersion, "saga-analysis-experiment-v1");
});

test("repeatability fails closed when completed runs do not have fingerprints", () => {
  assert.throws(
    () => createAnalysisExperimentRecord({
      ...makeRecord(),
      repeatability: {
        attemptedRuns: 2,
        completedRuns: 2,
        outputFingerprints: ["c".repeat(64)],
        failureCodes: [],
      },
    }),
    /fingerprint_count_mismatch/u,
  );
});

test("production adoption requires completed quality evidence", () => {
  const candidate = makeRecord();
  assert.throws(
    () => createAnalysisExperimentRecord({
      experimentId: candidate.experimentId,
      capability: candidate.capability,
      candidate: candidate.candidate,
      benchmark: candidate.benchmark,
      quality: [],
      repeatability: {
        attemptedRuns: 1,
        completedRuns: 1,
        outputFingerprints: ["d".repeat(64)],
        failureCodes: [],
      },
      decision: {
        status: "adopted",
        rationale: "Should be rejected by the record contract.",
        comparedAgainst: [],
        decidedAt: "2026-09-12T00:00:00Z",
      },
      limitations: [],
      notes: [],
    }),
    /adoption_requires_quality_evidence/u,
  );
});
