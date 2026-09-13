import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import { predictDependencyGroundedEvents } from "./event-dependency-grounding.js";
import {
  eventPredictionFingerprint,
  evaluateEvents,
  validateEventProviderResult,
  type EventEvaluationReport,
  type EventProviderResult,
  type EventReference,
} from "./event-evaluation.js";
import {
  collectTypedEntityEventParticipantEvidence,
  type TypedEntityEventParticipantResult,
  type TypedEntityParticipantCandidateStatus,
  type TypedEntityParticipantRole,
  type TypedNonPersonEntityCategory,
} from "./event-typed-entity-participants.js";
import {
  aggregateEventReports,
  convertLitBankEventReference,
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
const PREVIOUS_TRIGGER_F1 = 0.7791;
const PREVIOUS_PATIENT_PROVIDER_NON_PERSON_COUNT = 15;
const PREVIOUS_PATIENT_CANDIDATE_COUNT = 2546;

const STATUSES: TypedEntityParticipantCandidateStatus[] = [
  "character_grounded",
  "typed_non_person",
  "ambiguous_non_person",
  "malformed_non_person",
  "structural_locator_mismatch",
  "person_only",
  "unknown_only",
  "no_entity_evidence",
];

const ROLES: TypedEntityParticipantRole[] = ["actor", "patient"];

type AuditCounts = {
  candidateTokenCount: number;
  candidateEventCount: number;
  actorCandidateTokenCount: number;
  patientCandidateTokenCount: number;
  actorCandidateEventCount: number;
  patientCandidateEventCount: number;
  eventWithTypedNonPersonCount: number;
  typedNonPersonEvidenceCount: number;
  byStatus: Record<TypedEntityParticipantCandidateStatus, number>;
  byRole: Record<TypedEntityParticipantRole, number>;
  byDependencyPath: Record<string, number>;
  typedByRoleAndCategory: Record<string, number>;
  typedByDependencyAndCategory: Record<string, number>;
  typedByCategory: Record<string, number>;
};

function emptyStatusCounts(): Record<TypedEntityParticipantCandidateStatus, number> {
  return Object.fromEntries(STATUSES.map((status) => [status, 0])) as Record<TypedEntityParticipantCandidateStatus, number>;
}

function emptyRoleCounts(): Record<TypedEntityParticipantRole, number> {
  return Object.fromEntries(ROLES.map((role) => [role, 0])) as Record<TypedEntityParticipantRole, number>;
}

function emptyAudit(): AuditCounts {
  return {
    candidateTokenCount: 0,
    candidateEventCount: 0,
    actorCandidateTokenCount: 0,
    patientCandidateTokenCount: 0,
    actorCandidateEventCount: 0,
    patientCandidateEventCount: 0,
    eventWithTypedNonPersonCount: 0,
    typedNonPersonEvidenceCount: 0,
    byStatus: emptyStatusCounts(),
    byRole: emptyRoleCounts(),
    byDependencyPath: {},
    typedByRoleAndCategory: {},
    typedByDependencyAndCategory: {},
    typedByCategory: {},
  };
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function addAudit(target: AuditCounts, source: AuditCounts) {
  target.candidateTokenCount += source.candidateTokenCount;
  target.candidateEventCount += source.candidateEventCount;
  target.actorCandidateTokenCount += source.actorCandidateTokenCount;
  target.patientCandidateTokenCount += source.patientCandidateTokenCount;
  target.actorCandidateEventCount += source.actorCandidateEventCount;
  target.patientCandidateEventCount += source.patientCandidateEventCount;
  target.eventWithTypedNonPersonCount += source.eventWithTypedNonPersonCount;
  target.typedNonPersonEvidenceCount += source.typedNonPersonEvidenceCount;
  for (const status of STATUSES) target.byStatus[status] += source.byStatus[status];
  for (const role of ROLES) target.byRole[role] += source.byRole[role];
  for (const [key, value] of Object.entries(source.byDependencyPath)) increment(target.byDependencyPath, key, value);
  for (const [key, value] of Object.entries(source.typedByRoleAndCategory)) increment(target.typedByRoleAndCategory, key, value);
  for (const [key, value] of Object.entries(source.typedByDependencyAndCategory)) increment(target.typedByDependencyAndCategory, key, value);
  for (const [key, value] of Object.entries(source.typedByCategory)) increment(target.typedByCategory, key, value);
}

function auditResult(result: TypedEntityEventParticipantResult): AuditCounts {
  const audit = emptyAudit();
  audit.candidateTokenCount = result.candidates.length;
  audit.typedNonPersonEvidenceCount = result.evidence.length;
  const candidateEvents = new Set<string>();
  const actorEvents = new Set<string>();
  const patientEvents = new Set<string>();
  const typedEvents = new Set<string>();

  for (const candidate of result.candidates) {
    candidateEvents.add(candidate.eventId);
    audit.byStatus[candidate.status] += 1;
    audit.byRole[candidate.role] += 1;
    increment(audit.byDependencyPath, candidate.dependencyPath);
    if (candidate.role === "actor") {
      audit.actorCandidateTokenCount += 1;
      actorEvents.add(candidate.eventId);
    } else {
      audit.patientCandidateTokenCount += 1;
      patientEvents.add(candidate.eventId);
    }
  }

  for (const evidence of result.evidence) {
    typedEvents.add(evidence.eventId);
    increment(audit.typedByCategory, evidence.entityCategory);
    increment(audit.typedByRoleAndCategory, `${evidence.role}:${evidence.entityCategory}`);
    increment(audit.typedByDependencyAndCategory, `${evidence.dependencyPath}:${evidence.entityCategory}`);
  }

  audit.candidateEventCount = candidateEvents.size;
  audit.actorCandidateEventCount = actorEvents.size;
  audit.patientCandidateEventCount = patientEvents.size;
  audit.eventWithTypedNonPersonCount = typedEvents.size;
  return audit;
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function rates(counts: Record<string, number>, denominator: number) {
  return Object.fromEntries(
    Object.entries(counts).map(([key, value]) => [key, ratio(value, denominator)]),
  );
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
    throw new Error("usage: event-typed-entity-participant-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function triggerOnlyPrediction(prediction: EventProviderResult): EventProviderResult {
  const events = prediction.events.map((event) => ({ ...event, participants: [] }));
  return {
    ...prediction,
    events,
    outputFingerprint: eventPredictionFingerprint({
      provider: prediction.provider,
      normalizedInputFingerprint: prediction.normalizedInputFingerprint,
      events,
    }),
  };
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

  const completed: Array<{
    documentId: string;
    triggerEvaluation: EventEvaluationReport;
    audit: AuditCounts;
    typedOutputFingerprint: string;
  }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, eventTsv, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "events", "tsv", `${documentId}.tsv`), "utf8"),
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
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = alignSingleSectionOracleIdentity({
        identity: litBankGoldIdentityResult(converted.gold),
        section,
      });
      const eventPrediction = predictDependencyGroundedEvents({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence,
      });
      const typedResult = collectTypedEntityEventParticipantEvidence({
        normalizedInputFingerprint,
        identity,
        literaryEvidence,
        eventPrediction,
      });
      const reference = convertLitBankEventReference({ documentId, text, eventTsv });
      completed.push({
        documentId,
        triggerEvaluation: evaluateEventsAllowEmpty({
          reference,
          prediction: triggerOnlyPrediction(eventPrediction),
        }),
        audit: auditResult(typedResult),
        typedOutputFingerprint: typedResult.outputFingerprint,
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
    schemaVersion: "saga-event-typed-entity-participant-litbank-diagnostic-v1",
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
      actorRelations: ["nsubj", "agent->pobj"],
      patientRelations: ["dobj", "nsubjpass"],
      characterParticipantsExcluded: true,
      cleanTypedNonPersonOnly: true,
      structuralLocatorPolicy: "exact",
      ambiguousTypedEntitiesRemainUnresolved: true,
      dativeGrounding: false,
      conjunctionInheritance: false,
      providerClusterIdsCanonical: false,
      participantQualityScored: false,
      rawSourceTextEmitted: false,
    },
    triggerEvaluation,
    triggerRegressionCheck: {
      previousPublicF1: PREVIOUS_TRIGGER_F1,
      currentF1: triggerEvaluation.triggerDetection.f1,
      absoluteDelta: triggerEvaluation.triggerDetection.f1 - PREVIOUS_TRIGGER_F1,
    },
    baselineComparison: {
      previousPatientOnlyProviderNonPersonCount: PREVIOUS_PATIENT_PROVIDER_NON_PERSON_COUNT,
      previousPatientCandidateCount: PREVIOUS_PATIENT_CANDIDATE_COUNT,
      previousPatientOnlyProviderNonPersonRate:
        PREVIOUS_PATIENT_PROVIDER_NON_PERSON_COUNT / PREVIOUS_PATIENT_CANDIDATE_COUNT,
    },
    audit: {
      ...audit,
      typedNonPersonCandidateRate: ratio(audit.byStatus.typed_non_person, audit.candidateTokenCount),
      eventGainRate: ratio(audit.eventWithTypedNonPersonCount, audit.candidateEventCount),
      statusRates: rates(audit.byStatus, audit.candidateTokenCount),
      roleRates: rates(audit.byRole, audit.candidateTokenCount),
      dependencyPathRates: rates(audit.byDependencyPath, audit.candidateTokenCount),
    },
    caveat: "LitBank provides event-trigger gold but no S.A.G.A.-style non-character actor/patient gold. Typed non-character counts are coverage/evidence diagnostics, not participant precision, recall, or accuracy.",
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
    baselineComparison: output.baselineComparison,
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
