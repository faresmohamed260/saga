import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  auditCharacterRelationshipCoverage,
  type CharacterRelationshipAuditResult,
} from "./character-relationship-audit.js";
import { deriveCharacterRelationshipEvidence } from "./character-relationship-evidence.js";
import {
  litBankDocumentSection,
  litBankGoldIdentityResult,
} from "./litbank-component-benchmark.js";
import { alignSingleSectionOracleIdentity } from "./litbank-oracle-section-alignment.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const EXPECTED_FULL_CORPUS = {
  predicateHitCount: 196,
  supportedBinarySyntaxCount: 48,
  groundedObservationCount: 23,
};

type AggregateAudit = Omit<CharacterRelationshipAuditResult, "syntaxItems" | "groundingItems">;

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let booknlpRoot: string | null = null;
  let out: string | null = null;
  let limit: number | null = null;
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--booknlp-root") booknlpRoot = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else throw new Error(`unknown argument: ${token}`);
  }
  if (!litbankRoot || !booknlpRoot || !out) {
    throw new Error("usage: character-relationship-audit-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
  }
  return { litbankRoot: resolve(litbankRoot), booknlpRoot: resolve(booknlpRoot), out: resolve(out), limit };
}

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/gu, "\n");
}

async function readBookNlpDocument(root: string, documentId: string) {
  const documentRoot = join(root, documentId);
  const [tokensTsv, entitiesTsv, quotesTsv] = await Promise.all([
    readFile(join(documentRoot, `${documentId}.tokens`), "utf8"),
    readFile(join(documentRoot, `${documentId}.entities`), "utf8"),
    readFile(join(documentRoot, `${documentId}.quotes`), "utf8"),
  ]);
  return { tokensTsv, entitiesTsv, quotesTsv };
}

function increment(target: Record<string, number>, key: string, amount: number) {
  target[key] = (target[key] ?? 0) + amount;
}

function addFlat(target: Record<string, number>, source: Record<string, number>) {
  for (const [key, value] of Object.entries(source)) increment(target, key, value);
}

function addNested(
  target: Record<string, Record<string, number>>,
  source: Record<string, Record<string, number>>,
) {
  for (const [outer, inner] of Object.entries(source)) {
    const targetInner = target[outer] ?? {};
    addFlat(targetInner, inner);
    target[outer] = targetInner;
  }
}

function aggregateAudits(audits: CharacterRelationshipAuditResult[]): AggregateAudit {
  const aggregate = {
    predicateHitCount: 0,
    supportedBinarySyntaxCount: 0,
    groundedObservationCount: 0,
    syntaxCategoryCounts: {},
    groundingCategoryCounts: {},
    subjectRoleStatusCounts: {},
    objectRoleStatusCounts: {},
    directChildSignatureCounts: {},
    byPredicateAndSyntaxCategory: {},
    byPredicateAndGroundingCategory: {},
    noCharacterArgumentPosTags: {},
    noCharacterArgumentFinePosTags: {},
  } as unknown as AggregateAudit;

  for (const audit of audits) {
    aggregate.predicateHitCount += audit.predicateHitCount;
    aggregate.supportedBinarySyntaxCount += audit.supportedBinarySyntaxCount;
    aggregate.groundedObservationCount += audit.groundedObservationCount;
    addFlat(aggregate.syntaxCategoryCounts, audit.syntaxCategoryCounts);
    addFlat(aggregate.groundingCategoryCounts, audit.groundingCategoryCounts);
    addFlat(aggregate.subjectRoleStatusCounts, audit.subjectRoleStatusCounts);
    addFlat(aggregate.objectRoleStatusCounts, audit.objectRoleStatusCounts);
    addFlat(aggregate.directChildSignatureCounts, audit.directChildSignatureCounts);
    addNested(aggregate.byPredicateAndSyntaxCategory, audit.byPredicateAndSyntaxCategory);
    addNested(aggregate.byPredicateAndGroundingCategory, audit.byPredicateAndGroundingCategory);
    addFlat(aggregate.noCharacterArgumentPosTags, audit.noCharacterArgumentPosTags);
    addFlat(aggregate.noCharacterArgumentFinePosTags, audit.noCharacterArgumentFinePosTags);
  }
  return aggregate;
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function assertAggregateAccounting(audit: AggregateAudit) {
  const syntaxClassified = Object.values(audit.syntaxCategoryCounts).reduce((sum, value) => sum + value, 0);
  const groundingClassified = Object.values(audit.groundingCategoryCounts).reduce((sum, value) => sum + value, 0);
  const supportedFromSyntax =
    (audit.syntaxCategoryCounts.accepted_active_shape ?? 0)
    + (audit.syntaxCategoryCounts.accepted_passive_shape ?? 0);
  if (syntaxClassified !== audit.predicateHitCount) {
    throw new Error(`relationship_audit_aggregate_syntax_mismatch:${syntaxClassified}:${audit.predicateHitCount}`);
  }
  if (supportedFromSyntax !== audit.supportedBinarySyntaxCount) {
    throw new Error(`relationship_audit_aggregate_supported_mismatch:${supportedFromSyntax}:${audit.supportedBinarySyntaxCount}`);
  }
  if (groundingClassified !== audit.supportedBinarySyntaxCount) {
    throw new Error(`relationship_audit_aggregate_grounding_mismatch:${groundingClassified}:${audit.supportedBinarySyntaxCount}`);
  }
  if ((audit.groundingCategoryCounts.grounded_distinct_characters ?? 0) !== audit.groundedObservationCount) {
    throw new Error("relationship_audit_aggregate_observation_mismatch");
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const annotationNames = (await readdir(corefDir))
    .filter((name) => name.endsWith(".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (annotationNames.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const completed: Array<{
    documentId: string;
    predicateHitCount: number;
    supportedBinarySyntaxCount: number;
    groundedObservationCount: number;
  }> = [];
  const perDocumentAudits: CharacterRelationshipAuditResult[] = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const annotationName of annotationNames) {
    const documentId = basename(annotationName, ".ann");
    try {
      const [textRaw, corefAnnotation, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(corefDir, annotationName), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const literaryEvidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [section],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const gold = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation }).gold;
      const identity = alignSingleSectionOracleIdentity({
        identity: litBankGoldIdentityResult(gold),
        section,
      });
      const relationships = deriveCharacterRelationshipEvidence({
        normalizedInputFingerprint,
        identity,
        literaryEvidence,
      });
      const audit = auditCharacterRelationshipCoverage({ literaryEvidence, identity, relationships });
      perDocumentAudits.push(audit);
      completed.push({
        documentId,
        predicateHitCount: audit.predicateHitCount,
        supportedBinarySyntaxCount: audit.supportedBinarySyntaxCount,
        groundedObservationCount: audit.groundedObservationCount,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const audit = aggregateAudits(perDocumentAudits);
  assertAggregateAccounting(audit);
  const fullCorpus = args.limit === null;
  if (fullCorpus && completed.length === 100 && failures.length === 0) {
    for (const [key, expected] of Object.entries(EXPECTED_FULL_CORPUS)) {
      const actual = audit[key as keyof typeof EXPECTED_FULL_CORPUS];
      if (actual !== expected) throw new Error(`relationship_audit_baseline_drift:${key}:${actual}:${expected}`);
    }
  }

  const unsupportedSyntaxCount = audit.predicateHitCount - audit.supportedBinarySyntaxCount;
  const groundingFailureCount = audit.supportedBinarySyntaxCount - audit.groundedObservationCount;
  const reportBase = {
    schemaVersion: "saga-character-relationship-failure-audit-v1",
    benchmark: "LitBank explicit character-relationship structural failure-mode audit",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      attemptedDocumentCount: annotationNames.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    sourceEvidence: {
      sourceRunId: SOURCE_RUN_ID,
      sourceHeadSha: SOURCE_HEAD_SHA,
      nativeArtifactName: SOURCE_ARTIFACT_NAME,
      nativeArtifactSha256: SOURCE_ARTIFACT_SHA256,
      inferenceReused: true,
    },
    baseline: {
      expectedFullCorpus: EXPECTED_FULL_CORPUS,
      preserved:
        audit.predicateHitCount === EXPECTED_FULL_CORPUS.predicateHitCount
        && audit.supportedBinarySyntaxCount === EXPECTED_FULL_CORPUS.supportedBinarySyntaxCount
        && audit.groundedObservationCount === EXPECTED_FULL_CORPUS.groundedObservationCount,
    },
    scope: {
      newModelInference: false,
      correctnessScored: false,
      relationshipAccuracyClaimed: false,
      productionAdoptionClaimed: false,
      extractionPolicyChanged: false,
      rawSourceTextEmitted: false,
      storyTimeInferred: false,
      persistenceClaimed: false,
    },
    audit: {
      ...audit,
      unsupportedSyntaxCount,
      groundingFailureCount,
      supportedSyntaxRate: ratio(audit.supportedBinarySyntaxCount, audit.predicateHitCount),
      groundedObservationRatePerPredicateHit: ratio(audit.groundedObservationCount, audit.predicateHitCount),
      twoCharacterGroundingYield: ratio(audit.groundedObservationCount, audit.supportedBinarySyntaxCount),
    },
    completed,
    failures,
    caveat:
      "LitBank supplies character/coreference gold for benchmark-only oracle identity but no S.A.G.A.-style interpersonal relationship/state gold. This audit explains structural coverage drop-off only; it does not measure relationship precision, recall, accuracy, persistence, reciprocity, or narrative-time truth.",
  };
  const report = {
    ...reportBase,
    reportFingerprint: sha256Hex(canonicalJson(reportBase)),
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: report.dataset,
    baseline: report.baseline,
    audit: report.audit,
    reportFingerprint: report.reportFingerprint,
  }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
