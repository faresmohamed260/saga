import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
import {
  auditEventSemanticQualifierCoverage,
  EVENT_NEGATION_AUDIT_LEMMAS,
  validateEventSemanticQualifierAuditResult,
  type EventQualifierAuditCueFamily,
  type EventQualifierAuditStructuralCategory,
  type EventSemanticQualifierAuditResult,
} from "./event-semantic-qualifier-audit.js";
import {
  EVENT_CONDITIONAL_MARKERS,
  EVENT_MODAL_LEMMAS,
} from "./event-semantic-qualifiers.js";
import {
  eventPredictionFingerprint,
  evaluateEvents,
  validateEventProviderResult,
  type EventEvaluationReport,
  type EventProviderResult,
  type EventReference,
} from "./event-evaluation.js";
import {
  aggregateEventReports,
  convertLitBankEventReference,
  litBankDocumentSection,
} from "./litbank-component-benchmark.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const PREVIOUS_TRIGGER_F1 = 0.7791;
const PREVIOUS_TRIGGER_COUNT = 7445;

const MODAL_LEMMA_SET = new Set<string>(EVENT_MODAL_LEMMAS);
const CONDITIONAL_MARKER_SET = new Set<string>(EVENT_CONDITIONAL_MARKERS);
const NEGATION_LEMMA_SET = new Set<string>(EVENT_NEGATION_AUDIT_LEMMAS);
const FAMILIES: EventQualifierAuditCueFamily[] = ["negation", "modal", "conditional"];
const STRUCTURAL_CATEGORIES: EventQualifierAuditStructuralCategory[] = [
  "captured_direct_trigger_child",
  "captured_auxiliary_child",
  "direct_child_nonqualifying",
  "descendant_depth_2_plus",
  "parent_or_ancestor",
  "sibling_shared_head",
  "other_connected_same_sentence",
  "disconnected_same_sentence",
];

type StructuralCounts = Record<EventQualifierAuditStructuralCategory, number>;

type FamilyAudit = {
  candidateCueTokenCount: number;
  associatedCueTokenCount: number;
  capturedAssociatedCueCount: number;
  uncapturedAssociatedCueCount: number;
  structuralCategoryCounts: StructuralCounts;
};

type LemmaAudit = FamilyAudit;

type AggregateAudit = {
  eventTriggerCount: number;
  candidateCueTokenCount: number;
  cueTokenWithEventSentenceCount: number;
  cueTokenWithoutEventSentenceCount: number;
  sameSentenceCueTriggerPairCount: number;
  capturedAssociatedCueCount: number;
  uncapturedAssociatedCueCount: number;
  byFamily: Record<EventQualifierAuditCueFamily, FamilyAudit>;
  byLemma: Record<EventQualifierAuditCueFamily, Record<string, LemmaAudit>>;
  byStructuralCategory: StructuralCounts;
  dependencyDistanceCounts: Record<string, number>;
};

function emptyStructuralCounts(): StructuralCounts {
  return Object.fromEntries(STRUCTURAL_CATEGORIES.map((category) => [category, 0])) as StructuralCounts;
}

function emptyFamilyAudit(): FamilyAudit {
  return {
    candidateCueTokenCount: 0,
    associatedCueTokenCount: 0,
    capturedAssociatedCueCount: 0,
    uncapturedAssociatedCueCount: 0,
    structuralCategoryCounts: emptyStructuralCounts(),
  };
}

function emptyAggregateAudit(): AggregateAudit {
  return {
    eventTriggerCount: 0,
    candidateCueTokenCount: 0,
    cueTokenWithEventSentenceCount: 0,
    cueTokenWithoutEventSentenceCount: 0,
    sameSentenceCueTriggerPairCount: 0,
    capturedAssociatedCueCount: 0,
    uncapturedAssociatedCueCount: 0,
    byFamily: {
      negation: emptyFamilyAudit(),
      modal: emptyFamilyAudit(),
      conditional: emptyFamilyAudit(),
    },
    byLemma: {
      negation: {},
      modal: {},
      conditional: {},
    },
    byStructuralCategory: emptyStructuralCounts(),
    dependencyDistanceCounts: {},
  };
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function cueFamily(token: SyntaxTokenEvidence): EventQualifierAuditCueFamily | null {
  const lemma = normalizeLemma(token.lemma);
  if (token.dependencyRelation === "neg" || NEGATION_LEMMA_SET.has(lemma)) return "negation";
  if (MODAL_LEMMA_SET.has(lemma)) return "modal";
  if (CONDITIONAL_MARKER_SET.has(lemma)) return "conditional";
  return null;
}

function lemmaAudit(target: AggregateAudit, family: EventQualifierAuditCueFamily, lemma: string) {
  const current = target.byLemma[family][lemma];
  if (current) return current;
  const created = emptyFamilyAudit();
  target.byLemma[family][lemma] = created;
  return created;
}

function addCandidateTokens(target: AggregateAudit, syntaxTokens: SyntaxTokenEvidence[]) {
  let count = 0;
  for (const token of syntaxTokens) {
    const family = cueFamily(token);
    if (!family) continue;
    const lemma = normalizeLemma(token.lemma);
    count += 1;
    target.candidateCueTokenCount += 1;
    target.byFamily[family].candidateCueTokenCount += 1;
    lemmaAudit(target, family, lemma).candidateCueTokenCount += 1;
  }
  return count;
}

function addDocumentAudit(target: AggregateAudit, result: EventSemanticQualifierAuditResult) {
  target.eventTriggerCount += result.eventTriggerCount;
  target.cueTokenWithEventSentenceCount += result.cueTokenWithEventSentenceCount;
  target.cueTokenWithoutEventSentenceCount += result.cueTokenWithoutEventSentenceCount;
  target.sameSentenceCueTriggerPairCount += result.sameSentenceCueTriggerPairCount;

  for (const association of result.associations) {
    const family = target.byFamily[association.cueFamily];
    const lemma = lemmaAudit(target, association.cueFamily, association.cueLemma);
    family.associatedCueTokenCount += 1;
    lemma.associatedCueTokenCount += 1;
    family.structuralCategoryCounts[association.structuralCategory] += 1;
    lemma.structuralCategoryCounts[association.structuralCategory] += 1;
    target.byStructuralCategory[association.structuralCategory] += 1;
    const distanceKey = association.dependencyDistance === null ? "disconnected" : String(association.dependencyDistance);
    target.dependencyDistanceCounts[distanceKey] = (target.dependencyDistanceCounts[distanceKey] ?? 0) + 1;
    if (association.capturedByCurrentPolicy) {
      target.capturedAssociatedCueCount += 1;
      family.capturedAssociatedCueCount += 1;
      lemma.capturedAssociatedCueCount += 1;
    } else {
      target.uncapturedAssociatedCueCount += 1;
      family.uncapturedAssociatedCueCount += 1;
      lemma.uncapturedAssociatedCueCount += 1;
    }
  }
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function withRates(summary: FamilyAudit) {
  return {
    ...summary,
    associationRate: ratio(summary.associatedCueTokenCount, summary.candidateCueTokenCount),
    capturedRateAmongAssociated: ratio(summary.capturedAssociatedCueCount, summary.associatedCueTokenCount),
  };
}

function finalizeAudit(audit: AggregateAudit) {
  const byFamily = Object.fromEntries(FAMILIES.map((family) => [family, withRates(audit.byFamily[family])])) as Record<EventQualifierAuditCueFamily, ReturnType<typeof withRates>>;
  const byLemma = Object.fromEntries(FAMILIES.map((family) => [
    family,
    Object.fromEntries(
      Object.entries(audit.byLemma[family])
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([lemma, summary]) => [lemma, withRates(summary)]),
    ),
  ])) as Record<EventQualifierAuditCueFamily, Record<string, ReturnType<typeof withRates>>>;
  return {
    ...audit,
    byFamily,
    byLemma,
    cueTokenAssociationRate: ratio(audit.cueTokenWithEventSentenceCount, audit.candidateCueTokenCount),
    capturedRateAmongAssociated: ratio(audit.capturedAssociatedCueCount, audit.cueTokenWithEventSentenceCount),
  };
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
    throw new Error("usage: event-semantic-qualifier-audit-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function metricScore(tp: number, fp: number, fn: number) {
  const precision = tp + fp === 0 ? (tp + fn === 0 ? 1 : 0) : tp / (tp + fp);
  const recall = tp + fn === 0 ? 1 : tp / (tp + fn);
  return {
    truePositive: tp,
    falsePositive: fp,
    falseNegative: fn,
    precision,
    recall,
    f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall),
  };
}

function evaluateEventsAllowEmpty(input: {
  reference: EventReference;
  prediction: EventProviderResult;
}): EventEvaluationReport {
  if (input.reference.events.length > 0) return evaluateEvents(input);
  validateEventProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("event_input_fingerprint_mismatch");
  }
  const triggerDetection = metricScore(0, input.prediction.events.length, 0);
  const participantGrounding = metricScore(0, 0, 0);
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    triggerDetection,
    participantGrounding,
    goldEventCount: 0,
    predictedEventCount: input.prediction.events.length,
    duplicatePredictionCount: 0,
    duplicatePredictionRate: 0,
    unsupportedPredictionCount: input.prediction.events.length,
    unsupportedPredictionRate: input.prediction.events.length === 0 ? 0 : 1,
    knownParticipantEventCount: 0,
    matchedKnownParticipantEventCount: 0,
    missedKnownParticipantEventCount: 0,
    unknownParticipantEventMatchedCount: 0,
    unscoredParticipantAssignmentCount: 0,
  };
  return {
    schemaVersion: "saga-event-evaluation-v1",
    ...semantic,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
  };
}

function triggerOnlyPrediction(input: {
  literaryEvidence: LocalLiteraryEvidenceBundle;
  sectionKey: string;
}): EventProviderResult {
  const provider = {
    name: "booknlp-small-event-trigger-reuse",
    model: input.literaryEvidence.provider.model,
    revision: input.literaryEvidence.provider.revision,
  };
  const events = input.literaryEvidence.eventTriggers.map((trigger) => ({
    eventId: trigger.evidenceId,
    sectionKey: input.sectionKey,
    startOffset: trigger.startOffset,
    endOffset: trigger.endOffset,
    participants: [],
    decisionReason: "preserved_booknlp_event_trigger",
  }));
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: input.literaryEvidence.normalizedInputFingerprint,
    events,
    outputFingerprint: eventPredictionFingerprint({
      provider,
      normalizedInputFingerprint: input.literaryEvidence.normalizedInputFingerprint,
      events,
    }),
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const eventDir = join(args.litbankRoot, "events", "tsv");
  const documentIds = (await readdir(eventDir))
    .filter((name) => name.endsWith(".tsv"))
    .map((name) => basename(name, ".tsv"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (documentIds.length === 0) throw new Error("no LitBank event annotations found");

  const aggregateAudit = emptyAggregateAudit();
  const completed: Array<{
    documentId: string;
    triggerEvaluation: EventEvaluationReport;
    auditOutputFingerprint: string;
    eventTriggerCount: number;
    candidateCueTokenCount: number;
    associatedCueTokenCount: number;
    cueTokenWithoutEventSentenceCount: number;
    capturedAssociatedCueCount: number;
  }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [textRaw, eventTsv, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(eventDir, `${documentId}.tsv`), "utf8"),
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
      const audit = auditEventSemanticQualifierCoverage({ normalizedInputFingerprint, literaryEvidence });
      validateEventSemanticQualifierAuditResult(audit);
      const scannedCandidateCount = addCandidateTokens(aggregateAudit, literaryEvidence.syntaxTokens ?? []);
      if (scannedCandidateCount !== audit.candidateCueTokenCount) {
        throw new Error(`event_qualifier_audit_candidate_scan_mismatch:${scannedCandidateCount}:${audit.candidateCueTokenCount}`);
      }
      addDocumentAudit(aggregateAudit, audit);
      const reference = convertLitBankEventReference({ documentId, text, eventTsv });
      completed.push({
        documentId,
        triggerEvaluation: evaluateEventsAllowEmpty({
          reference,
          prediction: triggerOnlyPrediction({ literaryEvidence, sectionKey: section.stable_key }),
        }),
        auditOutputFingerprint: audit.outputFingerprint,
        eventTriggerCount: audit.eventTriggerCount,
        candidateCueTokenCount: audit.candidateCueTokenCount,
        associatedCueTokenCount: audit.cueTokenWithEventSentenceCount,
        cueTokenWithoutEventSentenceCount: audit.cueTokenWithoutEventSentenceCount,
        capturedAssociatedCueCount: audit.associations.filter((association) => association.capturedByCurrentPolicy).length,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const triggerEvaluation = aggregateEventReports(completed.map((row) => row.triggerEvaluation));
  const audit = finalizeAudit(aggregateAudit);
  const semantic = {
    schemaVersion: "saga-event-semantic-qualifier-coverage-audit-litbank-v1",
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
    },
    scope: {
      newModelInference: false,
      qualifierPolicyChanged: false,
      triggerPolicyChanged: false,
      participantPolicyChanged: false,
      associationPolicy: "nearest event trigger in same sentence by undirected dependency distance",
      cueFamilies: "neg relation plus not/never; pinned modal lemmas; if/unless",
      correctnessScored: false,
      rawSourceTextEmitted: false,
    },
    triggerEvaluation,
    triggerRegressionCheck: {
      previousPublicF1: PREVIOUS_TRIGGER_F1,
      currentF1: triggerEvaluation.triggerDetection.f1,
      absoluteDelta: triggerEvaluation.triggerDetection.f1 - PREVIOUS_TRIGGER_F1,
      previousTriggerCount: PREVIOUS_TRIGGER_COUNT,
      currentTriggerCount: audit.eventTriggerCount,
      triggerCountDelta: audit.eventTriggerCount - PREVIOUS_TRIGGER_COUNT,
    },
    audit,
    caveat: "This is a structural coverage/failure-mode audit. LitBank does not provide S.A.G.A.-style polarity/modality/realis correctness gold, so captured/uncaptured counts are not semantic precision, recall, accuracy or factuality metrics.",
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
    triggerEvaluation: output.triggerEvaluation,
    triggerRegressionCheck: output.triggerRegressionCheck,
    audit: output.audit,
    caveat: output.caveat,
    failures: output.failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
