import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { IdentityProviderDescriptor } from "../identity/types.js";
import type { AnalysisBenchmarkManifest } from "../local-analysis/types.js";

export type AnalysisExperimentDecisionStatus = "candidate" | "adopted" | "rejected" | "deferred";

export type AnalysisExperimentCapability =
  | "character_identity"
  | "entity_extraction"
  | "speaker_attribution"
  | "event_detection"
  | "participant_grounding"
  | "local_structured_reasoning"
  | "other";

export type AnalysisExperimentCandidate = {
  provider: IdentityProviderDescriptor;
  variant: string;
  implementation: string;
  license: string;
  source: string;
  modelArtifactSha256: string | null;
};

export type AnalysisExperimentQuality = {
  datasetId: string;
  datasetRevision: string;
  sampleCount: number;
  metrics: Record<string, number | null>;
};

export type AnalysisExperimentRepeatability = {
  attemptedRuns: number;
  completedRuns: number;
  outputFingerprints: string[];
  stableOutput: boolean;
  failureCodes: string[];
};

export type AnalysisExperimentDecision = {
  status: AnalysisExperimentDecisionStatus;
  rationale: string;
  comparedAgainst: string[];
  decidedAt: string | null;
};

export type AnalysisExperimentRecord = {
  schemaVersion: "saga-analysis-experiment-v1";
  experimentId: string;
  capability: AnalysisExperimentCapability;
  candidate: AnalysisExperimentCandidate;
  benchmark: AnalysisBenchmarkManifest;
  quality: AnalysisExperimentQuality[];
  repeatability: AnalysisExperimentRepeatability;
  decision: AnalysisExperimentDecision;
  limitations: string[];
  notes: string[];
  recordFingerprint: string;
};

export type CreateAnalysisExperimentRecordInput = Omit<
  AnalysisExperimentRecord,
  "schemaVersion" | "repeatability" | "recordFingerprint"
> & {
  repeatability: Omit<AnalysisExperimentRepeatability, "stableOutput">;
};

function assertNonNegativeInteger(value: number, field: string) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new Error(`invalid_experiment_integer:${field}`);
  }
}

function assertFiniteMetric(value: number | null, field: string) {
  if (value !== null && !Number.isFinite(value)) {
    throw new Error(`invalid_experiment_metric:${field}`);
  }
}

function normalizeUniqueStrings(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort();
}

function deriveStableOutput(completedRuns: number, outputFingerprints: string[]) {
  if (completedRuns < 2 || outputFingerprints.length !== completedRuns) return false;
  return new Set(outputFingerprints).size === 1;
}

export function experimentRecordFingerprint(
  record: Omit<AnalysisExperimentRecord, "recordFingerprint">,
) {
  return sha256Hex(canonicalJson(record));
}

export function createAnalysisExperimentRecord(
  input: CreateAnalysisExperimentRecordInput,
): AnalysisExperimentRecord {
  const experimentId = input.experimentId.trim();
  if (!experimentId) throw new Error("invalid_experiment_id");
  if (!input.candidate.variant.trim()) throw new Error("invalid_experiment_candidate_variant");
  if (!input.candidate.implementation.trim()) throw new Error("invalid_experiment_candidate_implementation");
  if (!input.candidate.license.trim()) throw new Error("invalid_experiment_candidate_license");
  if (!input.candidate.source.trim()) throw new Error("invalid_experiment_candidate_source");

  assertNonNegativeInteger(input.repeatability.attemptedRuns, "attemptedRuns");
  assertNonNegativeInteger(input.repeatability.completedRuns, "completedRuns");
  if (input.repeatability.completedRuns > input.repeatability.attemptedRuns) {
    throw new Error("invalid_experiment_repeatability_counts");
  }

  const outputFingerprints = input.repeatability.outputFingerprints.map((value) => value.trim()).filter(Boolean);
  if (outputFingerprints.length !== input.repeatability.completedRuns) {
    throw new Error("experiment_output_fingerprint_count_mismatch");
  }

  for (const quality of input.quality) {
    if (!quality.datasetId.trim() || !quality.datasetRevision.trim()) {
      throw new Error("invalid_experiment_dataset_identity");
    }
    assertNonNegativeInteger(quality.sampleCount, `${quality.datasetId}.sampleCount`);
    for (const [metric, value] of Object.entries(quality.metrics)) {
      assertFiniteMetric(value, `${quality.datasetId}.${metric}`);
    }
  }

  if (
    (input.decision.status === "adopted" || input.decision.status === "rejected") &&
    input.repeatability.completedRuns === 0
  ) {
    throw new Error("experiment_decision_requires_completed_run");
  }

  if (input.decision.status === "adopted" && input.quality.length === 0) {
    throw new Error("experiment_adoption_requires_quality_evidence");
  }

  if (input.decision.status === "adopted" && input.repeatability.completedRuns < 2) {
    throw new Error("experiment_adoption_requires_repeatability_evidence");
  }

  const repeatability: AnalysisExperimentRepeatability = {
    attemptedRuns: input.repeatability.attemptedRuns,
    completedRuns: input.repeatability.completedRuns,
    outputFingerprints,
    stableOutput: deriveStableOutput(input.repeatability.completedRuns, outputFingerprints),
    failureCodes: normalizeUniqueStrings(input.repeatability.failureCodes),
  };

  const recordWithoutFingerprint: Omit<AnalysisExperimentRecord, "recordFingerprint"> = {
    schemaVersion: "saga-analysis-experiment-v1",
    experimentId,
    capability: input.capability,
    candidate: {
      ...input.candidate,
      variant: input.candidate.variant.trim(),
      implementation: input.candidate.implementation.trim(),
      license: input.candidate.license.trim(),
      source: input.candidate.source.trim(),
    },
    benchmark: input.benchmark,
    quality: input.quality.map((quality) => ({
      datasetId: quality.datasetId.trim(),
      datasetRevision: quality.datasetRevision.trim(),
      sampleCount: quality.sampleCount,
      metrics: Object.fromEntries(Object.entries(quality.metrics).sort(([a], [b]) => a.localeCompare(b))),
    })),
    repeatability,
    decision: {
      status: input.decision.status,
      rationale: input.decision.rationale.trim(),
      comparedAgainst: normalizeUniqueStrings(input.decision.comparedAgainst),
      decidedAt: input.decision.decidedAt,
    },
    limitations: normalizeUniqueStrings(input.limitations),
    notes: normalizeUniqueStrings(input.notes),
  };

  return {
    ...recordWithoutFingerprint,
    recordFingerprint: experimentRecordFingerprint(recordWithoutFingerprint),
  };
}
