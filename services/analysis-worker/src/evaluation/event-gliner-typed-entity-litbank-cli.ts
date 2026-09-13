import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  normalizeGlinerEntityOutput,
  type GlinerRawEntityOutput,
} from "../local-analysis/typed-entity-evidence.js";
import { predictDependencyGroundedEvents } from "./event-dependency-grounding.js";
import {
  eventPredictionFingerprint,
  evaluateEvents,
  validateEventProviderResult,
  type EventEvaluationReport,
  type EventProviderResult,
  type EventReference,
} from "./event-evaluation.js";
import { collectTypedEntityEventParticipantsFromSource } from "./event-typed-entity-source.js";
import type {
  TypedEntityEventParticipantResult,
  TypedEntityParticipantCandidateStatus,
  TypedEntityParticipantRole,
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
const BOOKNLP_SOURCE_RUN_ID = 34727310506;
const BOOKNLP_SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const BOOKNLP_SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const PREVIOUS_TRIGGER_F1 = 0.7791;
const BOOKNLP_CANDIDATE_TOKEN_COUNT = 6701;
const BOOKNLP_TYPED_TOKEN_COUNT = 146;
const BOOKNLP_CANDIDATE_EVENT_COUNT = 5085;
const BOOKNLP_TYPED_EVENT_COUNT = 142;

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
  eventWithTypedNonPersonCount: number;
  typedNonPersonEvidenceCount: number;
  byStatus: Record<TypedEntityParticipantCandidateStatus, number>;
  byRole: Record<TypedEntityParticipantRole, number>;
  byDependencyPath: Record<string, number>;
  typedByCategory: Record<string, number>;
  typedByRoleAndCategory: Record<string, number>;
};

function emptyAudit(): AuditCounts {
  return {
    candidateTokenCount: 0,
    candidateEventCount: 0,
    actorCandidateTokenCount: 0,
    patientCandidateTokenCount: 0,
    eventWithTypedNonPersonCount: 0,
    typedNonPersonEvidenceCount: 0,
    byStatus: Object.fromEntries(STATUSES.map((status) => [status, 0])) as Record<TypedEntityParticipantCandidateStatus, number>,
    byRole: Object.fromEntries(ROLES.map((role) => [role, 0])) as Record<TypedEntityParticipantRole, number>,
    byDependencyPath: {},
    typedByCategory: {},
    typedByRoleAndCategory: {},
  };
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function auditResult(result: TypedEntityEventParticipantResult): AuditCounts {
  const audit = emptyAudit();
  const candidateEvents = new Set<string>();
  const typedEvents = new Set<string>();
  audit.candidateTokenCount = result.candidates.length;
  audit.typedNonPersonEvidenceCount = result.evidence.length;
  for (const candidate of result.candidates) {
    candidateEvents.add(candidate.eventId);
    audit.byStatus[candidate.status] += 1;
    audit.byRole[candidate.role] += 1;
    increment(audit.byDependencyPath, candidate.dependencyPath);
    if (candidate.role === "actor") audit.actorCandidateTokenCount += 1;
    else audit.patientCandidateTokenCount += 1;
  }
  for (const evidence of result.evidence) {
    typedEvents.add(evidence.eventId);
    increment(audit.typedByCategory, evidence.entityCategory);
    increment(audit.typedByRoleAndCategory, `${evidence.role}:${evidence.entityCategory}`);
  }
  audit.candidateEventCount = candidateEvents.size;
  audit.eventWithTypedNonPersonCount = typedEvents.size;
  return audit;
}

function addAudit(target: AuditCounts, source: AuditCounts) {
  target.candidateTokenCount += source.candidateTokenCount;
  target.candidateEventCount += source.candidateEventCount;
  target.actorCandidateTokenCount += source.actorCandidateTokenCount;
  target.patientCandidateTokenCount += source.patientCandidateTokenCount;
  target.eventWithTypedNonPersonCount += source.eventWithTypedNonPersonCount;
  target.typedNonPersonEvidenceCount += source.typedNonPersonEvidenceCount;
  for (const status of STATUSES) target.byStatus[status] += source.byStatus[status];
  for (const role of ROLES) target.byRole[role] += source.byRole[role];
  for (const [key, value] of Object.entries(source.byDependencyPath)) increment(target.byDependencyPath, key, value);
  for (const [key, value] of Object.entries(source.typedByCategory)) increment(target.typedByCategory, key, value);
  for (const [key, value] of Object.entries(source.typedByRoleAndCategory)) increment(target.typedByRoleAndCategory, key, value);
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function metricScore(tp: number, fp: number, fn: number) {
  const precision = tp + fp === 0 ? (tp + fn === 0 ? 1 : 0) : tp / (tp + fp);
  const recall = tp + fn === 0 ? 1 : tp / (tp + fn);
  return { truePositive: tp, falsePositive: fp, falseNegative: fn, precision, recall, f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall) };
}

function evaluateEventsAllowEmpty(input: { reference: EventReference; prediction: EventProviderResult }): EventEvaluationReport {
  if (input.reference.events.length > 0) return evaluateEvents(input);
  validateEventProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("event_input_fingerprint_mismatch");
  }
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    triggerDetection: metricScore(0, input.prediction.events.length, 0),
    participantGrounding: metricScore(0, 0, 0),
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
  return { schemaVersion: "saga-event-evaluation-v1", ...semantic, outputFingerprint: sha256Hex(canonicalJson(semantic)) };
}

function triggerOnlyPrediction(prediction: EventProviderResult): EventProviderResult {
  const events = prediction.events.map((event) => ({ ...event, participants: [] }));
  return {
    ...prediction,
    events,
    outputFingerprint: eventPredictionFingerprint({ provider: prediction.provider, normalizedInputFingerprint: prediction.normalizedInputFingerprint, events }),
  };
}

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let booknlpRoot: string | null = null;
  let glinerRoot: string | null = null;
  let out: string | null = null;
  let limit: number | null = null;
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--booknlp-root") booknlpRoot = argv[++index] ?? null;
    else if (token === "--gliner-root") glinerRoot = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else throw new Error(`unknown argument: ${token}`);
  }
  if (!litbankRoot || !booknlpRoot || !glinerRoot || !out) {
    throw new Error("usage: event-gliner-typed-entity-litbank-cli --litbank-root <root> --booknlp-root <outputs> --gliner-root <outputs> --out <report.json> [--limit N]");
  }
  return { litbankRoot: resolve(litbankRoot), booknlpRoot: resolve(booknlpRoot), glinerRoot: resolve(glinerRoot), out: resolve(out), limit };
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const documentIds = (await readdir(corefDir))
    .filter((name) => name.endsWith(".ann"))
    .map((name) => basename(name, ".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (documentIds.length === 0) throw new Error("no LitBank coref annotations found");

  const completed: Array<{ documentId: string; triggerEvaluation: EventEvaluationReport; audit: AuditCounts; typedOutputFingerprint: string; entitySourceFingerprint: string }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, eventTsv, booknlp, glinerRawText] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "events", "tsv", `${documentId}.tsv`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
        readFile(join(args.glinerRoot, `${documentId}.json`), "utf8"),
      ]);
      const text = normalizeNewlines(textRaw);
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const syntaxAndEventEvidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [section],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const entityEvidenceSource = normalizeGlinerEntityOutput({
        normalizedText: text,
        normalizedInputFingerprint,
        sections: [section],
        raw: JSON.parse(glinerRawText) as GlinerRawEntityOutput,
      });
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = alignSingleSectionOracleIdentity({ identity: litBankGoldIdentityResult(converted.gold), section });
      const eventPrediction = predictDependencyGroundedEvents({ sections: [section], normalizedInputFingerprint, identity, literaryEvidence: syntaxAndEventEvidence });
      const typedResult = collectTypedEntityEventParticipantsFromSource({ normalizedInputFingerprint, identity, syntaxAndEventEvidence, entityEvidenceSource, eventPrediction });
      const reference = convertLitBankEventReference({ documentId, text, eventTsv });
      completed.push({
        documentId,
        triggerEvaluation: evaluateEventsAllowEmpty({ reference, prediction: triggerOnlyPrediction(eventPrediction) }),
        audit: auditResult(typedResult),
        typedOutputFingerprint: typedResult.outputFingerprint,
        entitySourceFingerprint: entityEvidenceSource.outputFingerprint,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const audit = emptyAudit();
  for (const row of completed) addAudit(audit, row.audit);
  const triggerEvaluation = aggregateEventReports(completed.map((row) => row.triggerEvaluation));
  const glinerTypedTokenRate = ratio(audit.byStatus.typed_non_person, audit.candidateTokenCount);
  const glinerTypedEventRate = ratio(audit.eventWithTypedNonPersonCount, audit.candidateEventCount);
  const bookNlpTypedTokenRate = BOOKNLP_TYPED_TOKEN_COUNT / BOOKNLP_CANDIDATE_TOKEN_COUNT;
  const bookNlpTypedEventRate = BOOKNLP_TYPED_EVENT_COUNT / BOOKNLP_CANDIDATE_EVENT_COUNT;
  const semantic = {
    schemaVersion: "saga-event-gliner-typed-entity-litbank-diagnostic-v1",
    dataset: { repository: "dbamman/litbank", commit: LITBANK_COMMIT, license: "CC BY 4.0", attemptedDocumentCount: documentIds.length, completedDocumentCount: completed.length, failedDocumentCount: failures.length },
    sourceEvidence: {
      syntaxAndEvents: { provider: BOOKNLP_SMALL_PROVIDER, sourceRunId: BOOKNLP_SOURCE_RUN_ID, sourceHeadSha: BOOKNLP_SOURCE_HEAD_SHA, artifactSha256: BOOKNLP_SOURCE_ARTIFACT_SHA256, inferenceReused: true },
      typedEntities: completed.length > 0 ? { providerName: "gliner_typed_entity", inferenceReused: false } : null,
    },
    scope: {
      actorRelations: ["nsubj", "agent->pobj"],
      patientRelations: ["dobj", "nsubjpass"],
      characterParticipantsExcluded: true,
      cleanTypedNonPersonOnly: true,
      structuralLocatorPolicy: "exact",
      dativeGrounding: false,
      conjunctionInheritance: false,
      providerClustersCanonical: false,
      participantQualityScored: false,
      rawSourceTextEmitted: false,
    },
    triggerEvaluation,
    triggerRegressionCheck: { previousPublicF1: PREVIOUS_TRIGGER_F1, currentF1: triggerEvaluation.triggerDetection.f1, absoluteDelta: triggerEvaluation.triggerDetection.f1 - PREVIOUS_TRIGGER_F1 },
    bookNlpBaseline: {
      candidateTokenCount: BOOKNLP_CANDIDATE_TOKEN_COUNT,
      typedTokenCount: BOOKNLP_TYPED_TOKEN_COUNT,
      typedTokenRate: bookNlpTypedTokenRate,
      candidateEventCount: BOOKNLP_CANDIDATE_EVENT_COUNT,
      typedEventCount: BOOKNLP_TYPED_EVENT_COUNT,
      typedEventRate: bookNlpTypedEventRate,
    },
    audit: {
      ...audit,
      typedNonPersonCandidateRate: glinerTypedTokenRate,
      eventGainRate: glinerTypedEventRate,
      candidateRateAbsoluteDeltaVsBookNlp: glinerTypedTokenRate - bookNlpTypedTokenRate,
      eventGainRateAbsoluteDeltaVsBookNlp: glinerTypedEventRate - bookNlpTypedEventRate,
      candidateCoverageMultiplierVsBookNlp: bookNlpTypedTokenRate === 0 ? null : glinerTypedTokenRate / bookNlpTypedTokenRate,
      eventCoverageMultiplierVsBookNlp: bookNlpTypedEventRate === 0 ? null : glinerTypedEventRate / bookNlpTypedEventRate,
    },
    caveat: "LitBank provides event-trigger gold but no S.A.G.A.-style non-character actor/patient gold. GLiNER participant counts are coverage/evidence diagnostics, not participant precision, recall, or accuracy.",
    failures,
    perDocument: completed,
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };
  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({ dataset: output.dataset, sourceEvidence: output.sourceEvidence, triggerRegressionCheck: output.triggerRegressionCheck, bookNlpBaseline: output.bookNlpBaseline, audit: output.audit, failures: output.failures, reportFingerprint: output.reportFingerprint }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
