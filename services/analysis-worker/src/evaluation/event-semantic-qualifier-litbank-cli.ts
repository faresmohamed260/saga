import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import {
  deriveEventSemanticQualifiers,
  type EventSemanticQualifierResult,
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

type QualifierAudit = {
  triggerCount: number;
  eventWithAnyCueCount: number;
  unmarkedEventCount: number;
  negatedEventCount: number;
  modalizedEventCount: number;
  conditionalCueEventCount: number;
  irrealisCuedEventCount: number;
  negatedAndModalizedCount: number;
  negatedAndConditionalCount: number;
  modalizedAndConditionalCount: number;
  allThreeCount: number;
  negationCueCount: number;
  modalCueCount: number;
  conditionalCueCount: number;
  modalLemmaCounts: Record<string, number>;
  conditionalLemmaCounts: Record<string, number>;
};

function emptyAudit(): QualifierAudit {
  return {
    triggerCount: 0,
    eventWithAnyCueCount: 0,
    unmarkedEventCount: 0,
    negatedEventCount: 0,
    modalizedEventCount: 0,
    conditionalCueEventCount: 0,
    irrealisCuedEventCount: 0,
    negatedAndModalizedCount: 0,
    negatedAndConditionalCount: 0,
    modalizedAndConditionalCount: 0,
    allThreeCount: 0,
    negationCueCount: 0,
    modalCueCount: 0,
    conditionalCueCount: 0,
    modalLemmaCounts: {},
    conditionalLemmaCounts: {},
  };
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function addAudit(target: QualifierAudit, source: QualifierAudit) {
  target.triggerCount += source.triggerCount;
  target.eventWithAnyCueCount += source.eventWithAnyCueCount;
  target.unmarkedEventCount += source.unmarkedEventCount;
  target.negatedEventCount += source.negatedEventCount;
  target.modalizedEventCount += source.modalizedEventCount;
  target.conditionalCueEventCount += source.conditionalCueEventCount;
  target.irrealisCuedEventCount += source.irrealisCuedEventCount;
  target.negatedAndModalizedCount += source.negatedAndModalizedCount;
  target.negatedAndConditionalCount += source.negatedAndConditionalCount;
  target.modalizedAndConditionalCount += source.modalizedAndConditionalCount;
  target.allThreeCount += source.allThreeCount;
  target.negationCueCount += source.negationCueCount;
  target.modalCueCount += source.modalCueCount;
  target.conditionalCueCount += source.conditionalCueCount;
  for (const [lemma, count] of Object.entries(source.modalLemmaCounts)) increment(target.modalLemmaCounts, lemma, count);
  for (const [lemma, count] of Object.entries(source.conditionalLemmaCounts)) increment(target.conditionalLemmaCounts, lemma, count);
}

function auditQualifiers(result: EventSemanticQualifierResult): QualifierAudit {
  const audit = emptyAudit();
  audit.triggerCount = result.events.length;

  for (const event of result.events) {
    const negated = event.polarity === "negated";
    const modalized = event.modality === "modalized";
    const conditional = event.cues.some((cue) => cue.kind === "conditional_marker");
    const anyCue = event.cues.length > 0;

    if (anyCue) audit.eventWithAnyCueCount += 1;
    else audit.unmarkedEventCount += 1;
    if (negated) audit.negatedEventCount += 1;
    if (modalized) audit.modalizedEventCount += 1;
    if (conditional) audit.conditionalCueEventCount += 1;
    if (event.realis === "irrealis_cued") audit.irrealisCuedEventCount += 1;
    if (negated && modalized) audit.negatedAndModalizedCount += 1;
    if (negated && conditional) audit.negatedAndConditionalCount += 1;
    if (modalized && conditional) audit.modalizedAndConditionalCount += 1;
    if (negated && modalized && conditional) audit.allThreeCount += 1;

    for (const cue of event.cues) {
      const lemma = cue.lemma.trim().toLocaleLowerCase("en-US");
      if (cue.kind === "negation") audit.negationCueCount += 1;
      else if (cue.kind === "modal_auxiliary") {
        audit.modalCueCount += 1;
        increment(audit.modalLemmaCounts, lemma);
      } else {
        audit.conditionalCueCount += 1;
        increment(audit.conditionalLemmaCounts, lemma);
      }
    }
  }

  return audit;
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
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
    throw new Error("usage: event-semantic-qualifier-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

  const completed: Array<{
    documentId: string;
    triggerEvaluation: EventEvaluationReport;
    qualifierOutputFingerprint: string;
    audit: QualifierAudit;
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
      const qualifiers = deriveEventSemanticQualifiers({
        normalizedInputFingerprint,
        literaryEvidence,
      });
      const reference = convertLitBankEventReference({ documentId, text, eventTsv });
      completed.push({
        documentId,
        triggerEvaluation: evaluateEventsAllowEmpty({
          reference,
          prediction: triggerOnlyPrediction({ literaryEvidence, sectionKey: section.stable_key }),
        }),
        qualifierOutputFingerprint: qualifiers.outputFingerprint,
        audit: auditQualifiers(qualifiers),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const audit = emptyAudit();
  for (const row of completed) addAudit(audit, row.audit);
  const triggerEvaluation = aggregateEventReports(completed.map((row) => row.triggerEvaluation));
  const semantic = {
    schemaVersion: "saga-event-semantic-qualifier-litbank-diagnostic-v1",
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
      triggerPolicyChanged: false,
      participantPolicyChanged: false,
      negationPolicy: "neg child of trigger or direct auxiliary",
      modalPolicy: "direct aux/auxpass child in pinned modal lemma set",
      conditionalPolicy: "direct mark child with if/unless lemma",
      realisPolicy: "irrealis_cued only from modal/conditional positive evidence; otherwise undetermined",
      crossSentenceTraversal: false,
      correctnessScored: false,
      rawSourceTextEmitted: false,
    },
    triggerEvaluation,
    triggerRegressionCheck: {
      previousPublicF1: PREVIOUS_TRIGGER_F1,
      currentF1: triggerEvaluation.triggerDetection.f1,
      absoluteDelta: triggerEvaluation.triggerDetection.f1 - PREVIOUS_TRIGGER_F1,
      previousTriggerCount: PREVIOUS_TRIGGER_COUNT,
      currentTriggerCount: audit.triggerCount,
      triggerCountDelta: audit.triggerCount - PREVIOUS_TRIGGER_COUNT,
    },
    audit: {
      ...audit,
      eventWithAnyCueRate: ratio(audit.eventWithAnyCueCount, audit.triggerCount),
      unmarkedEventRate: ratio(audit.unmarkedEventCount, audit.triggerCount),
      negatedEventRate: ratio(audit.negatedEventCount, audit.triggerCount),
      modalizedEventRate: ratio(audit.modalizedEventCount, audit.triggerCount),
      conditionalCueEventRate: ratio(audit.conditionalCueEventCount, audit.triggerCount),
      irrealisCuedEventRate: ratio(audit.irrealisCuedEventCount, audit.triggerCount),
      negatedAndModalizedRate: ratio(audit.negatedAndModalizedCount, audit.triggerCount),
      negatedAndConditionalRate: ratio(audit.negatedAndConditionalCount, audit.triggerCount),
      modalizedAndConditionalRate: ratio(audit.modalizedAndConditionalCount, audit.triggerCount),
      allThreeRate: ratio(audit.allThreeCount, audit.triggerCount),
    },
    caveat: "LitBank supplies event-trigger gold but not S.A.G.A.-style event polarity/modality/realis gold. Qualifier counts are source-grounded prevalence/coverage diagnostics, not semantic precision, recall, factuality, or accuracy.",
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
