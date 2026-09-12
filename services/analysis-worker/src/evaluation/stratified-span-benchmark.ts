import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NovelDiversityManifest } from "./stratified-identity-benchmark.js";

export type SpanBenchmarkCounts = {
  documentCount: number;
  goldPersonMentionCount: number;
  goldPersonProperNameCount: number;
  predictedPersonMentionCount: number;
  predictedPersonProperNameCount: number;
  correctPersonMentionCount: number;
  representedGoldPersonMentionCount: number;
  correctPersonProperNameCount: number;
  representedGoldPersonProperNameCount: number;
  goldTypedMentionCount: number;
  predictedTypedMentionCount: number;
  correctTypedMentionCount: number;
  representedGoldTypedMentionCount: number;
};

export type SpanBenchmarkMetrics = {
  personSpanPrecision: number;
  personSpanRecall: number;
  properPersonSpanPrecision: number;
  properPersonSpanRecall: number;
  typedSpanPrecision: number;
  typedSpanRecall: number;
};

export type StratifiedSpanSourceReport = {
  schemaVersion: string;
  dataset: {
    repository: string;
    commit: string;
  };
  provider: {
    name: string;
    model: string | null;
    revision: string;
  };
  perDocument: Array<{
    documentId: string;
    counts: SpanBenchmarkCounts;
    metrics: SpanBenchmarkMetrics;
  }>;
};

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function metricsFromCounts(counts: SpanBenchmarkCounts): SpanBenchmarkMetrics {
  return {
    personSpanPrecision: ratio(counts.correctPersonMentionCount, counts.predictedPersonMentionCount),
    personSpanRecall: ratio(counts.representedGoldPersonMentionCount, counts.goldPersonMentionCount),
    properPersonSpanPrecision: ratio(
      counts.correctPersonProperNameCount,
      counts.predictedPersonProperNameCount,
    ),
    properPersonSpanRecall: ratio(
      counts.representedGoldPersonProperNameCount,
      counts.goldPersonProperNameCount,
    ),
    typedSpanPrecision: ratio(counts.correctTypedMentionCount, counts.predictedTypedMentionCount),
    typedSpanRecall: ratio(counts.representedGoldTypedMentionCount, counts.goldTypedMentionCount),
  };
}

function aggregateCounts(documents: StratifiedSpanSourceReport["perDocument"]): SpanBenchmarkCounts {
  const counts: SpanBenchmarkCounts = {
    documentCount: 0,
    goldPersonMentionCount: 0,
    goldPersonProperNameCount: 0,
    predictedPersonMentionCount: 0,
    predictedPersonProperNameCount: 0,
    correctPersonMentionCount: 0,
    representedGoldPersonMentionCount: 0,
    correctPersonProperNameCount: 0,
    representedGoldPersonProperNameCount: 0,
    goldTypedMentionCount: 0,
    predictedTypedMentionCount: 0,
    correctTypedMentionCount: 0,
    representedGoldTypedMentionCount: 0,
  };

  for (const document of documents) {
    for (const key of Object.keys(counts) as Array<keyof SpanBenchmarkCounts>) {
      counts[key] += document.counts[key];
    }
  }
  return counts;
}

function validateManifest(manifest: NovelDiversityManifest) {
  if (manifest.schemaVersion !== "saga-novel-diversity-matrix-v1") {
    throw new Error("unsupported_novel_diversity_manifest");
  }
  if (!Number.isSafeInteger(manifest.policy.minimumRepeatabilityRuns) || manifest.policy.minimumRepeatabilityRuns < 2) {
    throw new Error("invalid_diversity_repeatability_requirement");
  }
}

export function buildStratifiedSpanBenchmark(input: {
  report: StratifiedSpanSourceReport;
  manifest: NovelDiversityManifest;
}) {
  const { report, manifest } = input;
  validateManifest(manifest);

  if (
    report.dataset.repository !== manifest.dataset.repository ||
    report.dataset.commit !== manifest.dataset.commit
  ) {
    throw new Error("diversity_dataset_revision_mismatch");
  }

  const byDocument = new Map(report.perDocument.map((document) => [document.documentId, document]));
  if (byDocument.size !== report.perDocument.length) {
    throw new Error("duplicate_provider_report_document");
  }

  const strata = manifest.litbankStrata.map((stratum) => {
    const selected = stratum.documentIds.map((documentId) => {
      const document = byDocument.get(documentId);
      if (!document) throw new Error(`diversity_missing_document:${stratum.id}:${documentId}`);
      return document;
    });
    if (selected.length < stratum.requiredMinDocuments) {
      throw new Error(`diversity_stratum_below_minimum:${stratum.id}`);
    }
    const counts = aggregateCounts(selected);
    return {
      id: stratum.id,
      dimension: stratum.dimension,
      label: stratum.label,
      rationale: stratum.rationale,
      documentCount: selected.length,
      documentIds: selected.map((document) => document.documentId),
      aggregate: {
        counts,
        metrics: metricsFromCounts(counts),
      },
    };
  });

  const uniqueDocumentIds = [...new Set(strata.flatMap((stratum) => stratum.documentIds))].sort();
  const dimensions = [...new Set(strata.map((stratum) => stratum.dimension))].sort();
  const sourceReportFingerprint = sha256Hex(canonicalJson(
    report.perDocument
      .map((document) => ({ documentId: document.documentId, counts: document.counts }))
      .sort((a, b) => a.documentId.localeCompare(b.documentId)),
  ));

  const outputWithoutFingerprint = {
    schemaVersion: "saga-stratified-span-benchmark-v1" as const,
    sourceReport: {
      schemaVersion: report.schemaVersion,
      fingerprint: sourceReportFingerprint,
    },
    dataset: manifest.dataset,
    provider: report.provider,
    policy: manifest.policy,
    coverage: {
      stratumCount: strata.length,
      dimensionCount: dimensions.length,
      dimensions,
      uniqueDocumentCount: uniqueDocumentIds.length,
      uniqueDocumentIds,
    },
    strata,
  };

  return {
    ...outputWithoutFingerprint,
    reportFingerprint: sha256Hex(canonicalJson(outputWithoutFingerprint)),
  };
}
