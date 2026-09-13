import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
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
const FAILED_V1_REPORT_FINGERPRINT = "8c5adb349913ae54a65d3002209d7930833b66640a92f33d0557c301486e24f6";

type Coverage = {
  triggerCount: number;
  eventWithAnyParticipant: number;
  eventWithActor: number;
  eventWithPatient: number;
  eventWithActorAndPatient: number;
  actorAssignments: number;
  patientAssignments: number;
  actorSyntaxOpportunityEvents: number;
  patientSyntaxOpportunityEvents: number;
  actorSyntaxCandidateTokens: number;
  patientSyntaxCandidateTokens: number;
};

function emptyCoverage(): Coverage {
  return {
    triggerCount: 0,
    eventWithAnyParticipant: 0,
    eventWithActor: 0,
    eventWithPatient: 0,
    eventWithActorAndPatient: 0,
    actorAssignments: 0,
    patientAssignments: 0,
    actorSyntaxOpportunityEvents: 0,
    patientSyntaxOpportunityEvents: 0,
    actorSyntaxCandidateTokens: 0,
    patientSyntaxCandidateTokens: 0,
  };
}

function addCoverage(target: Coverage, source: Coverage) {
  for (const key of Object.keys(target) as Array<keyof Coverage>) target[key] += source[key];
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
    throw new Error("usage: event-dependency-litbank-v2-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function syntaxChildren(tokens: SyntaxTokenEvidence[]) {
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const current = children.get(token.syntacticHeadTokenId) ?? [];
    current.push(token);
    children.set(token.syntacticHeadTokenId, current);
  }
  return children;
}

function coverageForDocument(evidence: LocalLiteraryEvidenceBundle, prediction: EventProviderResult): Coverage {
  if (!evidence.syntaxTokens) throw new Error("event_dependency_diagnostic_missing_syntax");
  const byTokenId = new Map(evidence.syntaxTokens.map((token) => [token.tokenId, token]));
  const children = syntaxChildren(evidence.syntaxTokens);
  const result = emptyCoverage();
  result.triggerCount = evidence.eventTriggers.length;

  for (const trigger of evidence.eventTriggers) {
    const token = byTokenId.get(trigger.tokenId);
    if (!token) throw new Error(`event_dependency_diagnostic_missing_trigger_token:${trigger.evidenceId}`);
    const direct = children.get(token.tokenId) ?? [];
    const activeSubjects = direct.filter((candidate) => candidate.dependencyRelation === "nsubj");
    const directObjects = direct.filter((candidate) => candidate.dependencyRelation === "dobj");
    const passiveSubjects = direct.filter((candidate) => candidate.dependencyRelation === "nsubjpass");
    const agents = direct.filter((candidate) => candidate.dependencyRelation === "agent");
    const agentObjects = agents.flatMap((agent) =>
      (children.get(agent.tokenId) ?? []).filter((candidate) => candidate.dependencyRelation === "pobj")
    );
    const actorCandidates = activeSubjects.length + agentObjects.length;
    const patientCandidates = directObjects.length + passiveSubjects.length;
    result.actorSyntaxCandidateTokens += actorCandidates;
    result.patientSyntaxCandidateTokens += patientCandidates;
    if (actorCandidates > 0) result.actorSyntaxOpportunityEvents += 1;
    if (patientCandidates > 0) result.patientSyntaxOpportunityEvents += 1;
  }

  for (const event of prediction.events) {
    const actors = event.participants.filter((participant) => participant.role === "actor").length;
    const patients = event.participants.filter((participant) => participant.role === "patient").length;
    result.actorAssignments += actors;
    result.patientAssignments += patients;
    if (actors + patients > 0) result.eventWithAnyParticipant += 1;
    if (actors > 0) result.eventWithActor += 1;
    if (patients > 0) result.eventWithPatient += 1;
    if (actors > 0 && patients > 0) result.eventWithActorAndPatient += 1;
  }
  return result;
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

  const completed: Array<{ documentId: string; triggerEvaluation: EventEvaluationReport; coverage: Coverage }> = [];
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
      const rawIdentity = litBankGoldIdentityResult(converted.gold);
      const identity = alignSingleSectionOracleIdentity({ identity: rawIdentity, section });
      const prediction = predictDependencyGroundedEvents({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence: evidence,
      });
      const reference = convertLitBankEventReference({ documentId, text, eventTsv });
      completed.push({
        documentId,
        triggerEvaluation: evaluateEventsAllowEmpty({ reference, prediction: triggerOnlyPrediction(prediction) }),
        coverage: coverageForDocument(evidence, prediction),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const coverage = emptyCoverage();
  for (const row of completed) addCoverage(coverage, row.coverage);
  const semantic = {
    schemaVersion: "saga-event-dependency-litbank-diagnostic-v2",
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
    correctedDiagnostic: {
      failedV1ReportFingerprint: FAILED_V1_REPORT_FINGERPRINT,
      failureMode: "LitBank oracle identity locator used section key only while provider syntax used stable_key:source_locator; strict production locator matching correctly rejected every attachment.",
      correction: "benchmark-only oracle locator aligned to canonical single-section provider locator; production grounding policy unchanged",
    },
    policy: {
      triggerSource: BOOKNLP_SMALL_PROVIDER,
      identitySource: "litbank_gold_oracle_for_grounding_isolation_only",
      actorRelations: ["nsubj", "agent->pobj"],
      patientRelations: ["dobj", "nsubjpass"],
      dativeGrounding: false,
      conjunctionInheritance: false,
      providerClusterIdsCanonical: false,
      participantQualityScored: false,
    },
    triggerEvaluation: aggregateEventReports(completed.map((row) => row.triggerEvaluation)),
    groundingCoverage: {
      ...coverage,
      eventWithAnyParticipantRate: ratio(coverage.eventWithAnyParticipant, coverage.triggerCount),
      eventWithActorRate: ratio(coverage.eventWithActor, coverage.triggerCount),
      eventWithPatientRate: ratio(coverage.eventWithPatient, coverage.triggerCount),
      eventWithActorAndPatientRate: ratio(coverage.eventWithActorAndPatient, coverage.triggerCount),
      actorOpportunityGroundingYield: ratio(coverage.eventWithActor, coverage.actorSyntaxOpportunityEvents),
      patientOpportunityGroundingYield: ratio(coverage.eventWithPatient, coverage.patientSyntaxOpportunityEvents),
    },
    caveat: "LitBank event TSV provides trigger labels but no S.A.G.A.-style actor/patient gold. Grounding rates use LitBank gold identity only to isolate span attachment coverage; they are not participant precision/recall/accuracy.",
    failures,
    perDocument: completed,
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };
  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    sourceEvidence: output.sourceEvidence,
    correctedDiagnostic: output.correctedDiagnostic,
    policy: output.policy,
    triggerEvaluation: output.triggerEvaluation,
    groundingCoverage: output.groundingCoverage,
    caveat: output.caveat,
    failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
