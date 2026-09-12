import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { aggregateIdentityBenchmarkReports } from "./identity-benchmark.js";
import type { IdentityBenchmarkCounts, IdentityBenchmarkMetrics } from "./types.js";

export type StratifiedIdentityInputDocument = {
  documentId: string;
  outputFingerprint: string;
  counts: IdentityBenchmarkCounts;
  metrics: IdentityBenchmarkMetrics;
};

export type StratifiedIdentitySourceReport = {
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
  aggregateOutputFingerprint?: string;
  perDocument: StratifiedIdentityInputDocument[];
};

export type NovelDiversityStratum = {
  id: string;
  dimension: string;
  label: string;
  requiredMinDocuments: number;
  documentIds: string[];
  rationale: string;
};

export type NovelDiversityManifest = {
  schemaVersion: "saga-novel-diversity-matrix-v1";
  dataset: {
    repository: string;
    commit: string;
    annotationLayer: string;
    license: string;
  };
  policy: {
    purpose: string;
    adoptionRule: string;
    minimumRepeatabilityRuns: number;
  };
  litbankStrata: NovelDiversityStratum[];
};

function assertNonEmpty(value: string, code: string) {
  if (!value.trim()) throw new Error(code);
}

function validateManifest(manifest: NovelDiversityManifest) {
  if (manifest.schemaVersion !== "saga-novel-diversity-matrix-v1") {
    throw new Error("unsupported_novel_diversity_manifest");
  }
  assertNonEmpty(manifest.dataset.repository, "invalid_diversity_dataset_repository");
  assertNonEmpty(manifest.dataset.commit, "invalid_diversity_dataset_commit");
  if (!Number.isSafeInteger(manifest.policy.minimumRepeatabilityRuns) || manifest.policy.minimumRepeatabilityRuns < 2) {
    throw new Error("invalid_diversity_repeatability_requirement");
  }

  const stratumIds = new Set<string>();
  for (const stratum of manifest.litbankStrata) {
    assertNonEmpty(stratum.id, "invalid_diversity_stratum_id");
    assertNonEmpty(stratum.dimension, `invalid_diversity_stratum_dimension:${stratum.id}`);
    assertNonEmpty(stratum.label, `invalid_diversity_stratum_label:${stratum.id}`);
    if (stratumIds.has(stratum.id)) throw new Error(`duplicate_diversity_stratum:${stratum.id}`);
    stratumIds.add(stratum.id);
    if (!Number.isSafeInteger(stratum.requiredMinDocuments) || stratum.requiredMinDocuments < 1) {
      throw new Error(`invalid_diversity_minimum:${stratum.id}`);
    }
    const documents = new Set(stratum.documentIds);
    if (documents.size !== stratum.documentIds.length) {
      throw new Error(`duplicate_diversity_document:${stratum.id}`);
    }
    if (documents.size < stratum.requiredMinDocuments) {
      throw new Error(`insufficient_diversity_manifest_documents:${stratum.id}`);
    }
  }
}

export function buildStratifiedIdentityBenchmark(input: {
  report: StratifiedIdentitySourceReport;
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

    const aggregate = aggregateIdentityBenchmarkReports(
      selected.map((document) => ({
        counts: document.counts,
        metrics: document.metrics,
      })),
    );

    return {
      id: stratum.id,
      dimension: stratum.dimension,
      label: stratum.label,
      rationale: stratum.rationale,
      documentCount: selected.length,
      documentIds: selected.map((document) => document.documentId),
      aggregateOutputFingerprint: sha256Hex(canonicalJson(
        selected.map((document) => ({
          documentId: document.documentId,
          outputFingerprint: document.outputFingerprint,
        })),
      )),
      aggregate,
    };
  });

  const uniqueDocumentIds = [...new Set(strata.flatMap((stratum) => stratum.documentIds))].sort();
  const dimensions = [...new Set(strata.map((stratum) => stratum.dimension))].sort();
  const sourceReportFingerprint =
    report.aggregateOutputFingerprint ??
    sha256Hex(canonicalJson(
      report.perDocument
        .map((document) => ({
          documentId: document.documentId,
          outputFingerprint: document.outputFingerprint,
        }))
        .sort((a, b) => a.documentId.localeCompare(b.documentId)),
    ));

  const outputWithoutFingerprint = {
    schemaVersion: "saga-stratified-identity-benchmark-v1" as const,
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
