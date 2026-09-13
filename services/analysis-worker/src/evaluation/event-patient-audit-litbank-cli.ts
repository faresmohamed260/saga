import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LiteraryEntityCategory } from "../local-analysis/types.js";
import { predictDependencyGroundedEvents } from "./event-dependency-grounding.js";
import {
  auditPatientGrounding,
  type PatientAuditCategory,
  type PatientAuditResult,
} from "./event-patient-audit.js";
import { litBankDocumentSection, litBankGoldIdentityResult } from "./litbank-component-benchmark.js";
import { alignSingleSectionOracleIdentity } from "./litbank-oracle-section-alignment.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const GROUNDING_REPORT_FINGERPRINT = "d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0";

const CATEGORIES: PatientAuditCategory[] = [
  "grounded_character",
  "same_character_grounded_other_mention",
  "linked_character_not_grounded",
  "ambiguous_linked_character",
  "structural_locator_mismatch",
  "gold_linked_person_missing_identity",
  "unresolved_person_gold",
  "non_person_gold",
  "provider_non_person",
  "provider_person_only",
  "no_entity_evidence",
];

function emptyCategoryCounts(): Record<PatientAuditCategory, number> {
  return Object.fromEntries(CATEGORIES.map((category) => [category, 0])) as Record<PatientAuditCategory, number>;
}

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
    throw new Error("usage: event-patient-audit-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function addMap(target: Record<string, number>, source: Record<string, number>) {
  for (const [key, value] of Object.entries(source)) target[key] = (target[key] ?? 0) + value;
}

function addNestedMap(target: Record<string, Record<string, number>>, source: Record<string, Record<string, number>>) {
  for (const [outer, values] of Object.entries(source)) {
    const current = target[outer] ?? {};
    addMap(current, values);
    target[outer] = current;
  }
}

function aggregate(rows: PatientAuditResult[]) {
  const byCategory = emptyCategoryCounts();
  const byRelation: Record<string, number> = {};
  const byRelationAndCategory: Record<string, Record<PatientAuditCategory, number>> = {};
  const providerNonPersonCategories: Partial<Record<LiteraryEntityCategory, number>> = {};
  const noEntityPosTags: Record<string, number> = {};
  const noEntityFinePosTags: Record<string, number> = {};
  const noEntityByRelationAndPos: Record<string, Record<string, number>> = {};
  let candidateTokenCount = 0;
  let eventWithPatientCandidateCount = 0;
  let eventWithMultiplePatientCandidatesCount = 0;

  for (const row of rows) {
    candidateTokenCount += row.candidateTokenCount;
    eventWithPatientCandidateCount += row.eventWithPatientCandidateCount;
    eventWithMultiplePatientCandidatesCount += row.eventWithMultiplePatientCandidatesCount;
    addMap(byRelation, row.byRelation);
    for (const category of CATEGORIES) byCategory[category] += row.byCategory[category];
    for (const [relation, categories] of Object.entries(row.byRelationAndCategory)) {
      const target = byRelationAndCategory[relation] ?? emptyCategoryCounts();
      for (const category of CATEGORIES) target[category] += categories[category];
      byRelationAndCategory[relation] = target;
    }
    for (const [category, count] of Object.entries(row.providerNonPersonCategories)) {
      const typed = category as LiteraryEntityCategory;
      providerNonPersonCategories[typed] = (providerNonPersonCategories[typed] ?? 0) + count;
    }
    addMap(noEntityPosTags, row.noEntityPosTags);
    addMap(noEntityFinePosTags, row.noEntityFinePosTags);
    addNestedMap(noEntityByRelationAndPos, row.noEntityByRelationAndPos);
  }

  return {
    candidateTokenCount,
    eventWithPatientCandidateCount,
    eventWithMultiplePatientCandidatesCount,
    byRelation,
    byCategory,
    byRelationAndCategory,
    providerNonPersonCategories,
    noEntityPosTags,
    noEntityFinePosTags,
    noEntityByRelationAndPos,
  };
}

function rates(counts: Record<string, number>, denominator: number) {
  return Object.fromEntries(
    Object.entries(counts).map(([key, value]) => [key, denominator === 0 ? 0 : value / denominator]),
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const documentIds = (await readdir(corefDir))
    .filter((name) => name.endsWith(".ann"))
    .map((name) => basename(name, ".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (documentIds.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const completed: Array<{ documentId: string; audit: PatientAuditResult }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [section],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = alignSingleSectionOracleIdentity({
        identity: litBankGoldIdentityResult(converted.gold),
        section,
      });
      const prediction = predictDependencyGroundedEvents({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence: evidence,
      });
      completed.push({
        documentId,
        audit: auditPatientGrounding({
          evidence,
          gold: converted.gold,
          identity,
          prediction,
        }),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const audit = aggregate(completed.map((row) => row.audit));
  const semantic = {
    schemaVersion: "saga-event-patient-audit-litbank-v2",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      attemptedDocumentCount: documentIds.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    sourceEvidence: {
      sourceRunId: SOURCE_RUN_ID,
      sourceHeadSha: SOURCE_HEAD_SHA,
      nativeArtifactName: SOURCE_ARTIFACT_NAME,
      nativeArtifactSha256: SOURCE_ARTIFACT_SHA256,
      inferenceReused: true,
      groundingReportFingerprint: GROUNDING_REPORT_FINGERPRINT,
    },
    scope: {
      patientRelations: ["dobj", "nsubjpass"],
      purpose: "classify why direct syntactic patient candidates do or do not map to canonical character identity",
      participantQualityScored: false,
      providerClusterIdsCanonical: false,
      rawSourceTextEmitted: false,
      noEntityProfile: "POS and fine-POS counts only; no source surfaces are emitted",
    },
    audit: {
      ...audit,
      categoryRates: rates(audit.byCategory, audit.candidateTokenCount),
      relationRates: rates(audit.byRelation, audit.candidateTokenCount),
      relationCategoryRates: Object.fromEntries(
        Object.entries(audit.byRelationAndCategory).map(([relation, categories]) => [
          relation,
          rates(categories, audit.byRelation[relation] ?? 0),
        ]),
      ),
      noEntityPosRates: rates(audit.noEntityPosTags, audit.byCategory.no_entity_evidence),
      noEntityFinePosRates: rates(audit.noEntityFinePosTags, audit.byCategory.no_entity_evidence),
    },
    failures,
    perDocument: completed,
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };
  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    sourceEvidence: output.sourceEvidence,
    scope: output.scope,
    audit: output.audit,
    failures: output.failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
