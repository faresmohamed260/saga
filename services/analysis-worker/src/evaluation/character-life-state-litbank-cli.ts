import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  CHARACTER_LIFE_STATE_PREDICATES,
  deriveCharacterLifeStateEvidence,
  type CharacterLifeStatePredicate,
} from "./character-life-state-evidence.js";
import { predictDependencyGroundedEvents } from "./event-dependency-grounding.js";
import { deriveEventSemanticQualifiers } from "./event-semantic-qualifiers.js";
import {
  aggregateEventReports,
  evaluateLitBankComponentDocument,
  litBankDocumentSection,
  litBankGoldIdentityResult,
} from "./litbank-component-benchmark.js";
import { alignSingleSectionOracleIdentity } from "./litbank-oracle-section-alignment.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";
import { deriveNarrativeTimelineEvidence } from "./narrative-timeline-evidence.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const EXPECTED_EVENT_COUNT = 7445;

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
    throw new Error("usage: character-life-state-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function emptyAudit() {
  return {
    eventCandidateCount: 0,
    opportunityCount: 0,
    opportunityByPredicate: {} as Record<string, number>,
    uniqueRequiredTargetCount: 0,
    missingRequiredTargetCount: 0,
    multipleRequiredTargetCount: 0,
    targetMissingMentionEvidenceCount: 0,
    candidateCount: 0,
    candidateByPredicate: {} as Record<string, number>,
    candidateNegatedCount: 0,
    candidateModalizedCount: 0,
    candidateIrrealisCuedCount: 0,
    candidateWithAnyQualifierCount: 0,
    candidateFullyUndeterminedCount: 0,
    storyTimeNonUnresolvedCount: 0,
    stateApplicationCount: 0,
    sourceOrderViolationCount: 0,
    uniqueTargetCharacterCount: 0,
    repeatedTargetCharacterCount: 0,
    repeatedCandidateExcessCount: 0,
    maxCandidatesPerCharacter: 0,
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
    eventReport: ReturnType<typeof evaluateLitBankComponentDocument>["events"]["bookNlp"];
    audit: ReturnType<typeof emptyAudit>;
    stateOutputFingerprint: string;
  }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, quotationAnnotation, quotationTextRaw, eventTsv, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.ann`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "events", "tsv", `${documentId}.tsv`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      if (normalizeNewlines(quotationTextRaw) !== text) throw new Error("life_state_litbank_quotation_source_mismatch");
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
      const component = evaluateLitBankComponentDocument({
        documentId,
        text,
        corefAnnotation,
        quotationAnnotation,
        eventTsv,
        evidence: literaryEvidence,
      });
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = alignSingleSectionOracleIdentity({
        identity: litBankGoldIdentityResult(converted.gold),
        section,
      });
      const events = predictDependencyGroundedEvents({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence,
      });
      const qualifiers = deriveEventSemanticQualifiers({ normalizedInputFingerprint, literaryEvidence });
      const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence, events });
      const state = deriveCharacterLifeStateEvidence({ literaryEvidence, events, qualifiers, timeline });

      const audit = emptyAudit();
      audit.eventCandidateCount = events.events.length;
      audit.candidateCount = state.candidates.length;
      audit.stateApplicationCount = state.stateApplications.length;

      const eventBySpan = new Map(events.events.map((event) => [spanKey(event.startOffset, event.endOffset), event]));
      for (const trigger of literaryEvidence.eventTriggers) {
        const lemma = normalizeLemma(trigger.lemma);
        if (!(lemma in CHARACTER_LIFE_STATE_PREDICATES)) continue;
        const predicate = lemma as CharacterLifeStatePredicate;
        audit.opportunityCount += 1;
        increment(audit.opportunityByPredicate, predicate);
        const event = eventBySpan.get(spanKey(trigger.startOffset, trigger.endOffset));
        if (!event) throw new Error(`life_state_diagnostic_grounded_event_missing:${trigger.evidenceId}`);
        const role = CHARACTER_LIFE_STATE_PREDICATES[predicate];
        const targets = event.participants.filter((participant) => participant.role === role);
        if (targets.length === 0) audit.missingRequiredTargetCount += 1;
        else if (targets.length > 1) audit.multipleRequiredTargetCount += 1;
        else if (!targets[0]!.evidenceId) audit.targetMissingMentionEvidenceCount += 1;
        else audit.uniqueRequiredTargetCount += 1;
      }

      const byCharacter = new Map<string, number>();
      let previousSequence = -1;
      for (const candidate of state.candidates) {
        increment(audit.candidateByPredicate, candidate.predicate);
        if (candidate.polarity === "negated") audit.candidateNegatedCount += 1;
        if (candidate.modality === "modalized") audit.candidateModalizedCount += 1;
        if (candidate.realis === "irrealis_cued") audit.candidateIrrealisCuedCount += 1;
        if (candidate.qualifierCueEvidenceIds.length > 0) audit.candidateWithAnyQualifierCount += 1;
        if (
          candidate.polarity === "undetermined"
          && candidate.modality === "undetermined"
          && candidate.realis === "undetermined"
        ) audit.candidateFullyUndeterminedCount += 1;
        if (candidate.storyTimeStatus !== "unresolved") audit.storyTimeNonUnresolvedCount += 1;
        if (candidate.narrativeSequenceIndex < previousSequence) audit.sourceOrderViolationCount += 1;
        previousSequence = candidate.narrativeSequenceIndex;
        byCharacter.set(candidate.targetCharacterKey, (byCharacter.get(candidate.targetCharacterKey) ?? 0) + 1);
      }
      audit.uniqueTargetCharacterCount = byCharacter.size;
      for (const count of byCharacter.values()) {
        if (count > 1) {
          audit.repeatedTargetCharacterCount += 1;
          audit.repeatedCandidateExcessCount += count - 1;
        }
        audit.maxCandidatesPerCharacter = Math.max(audit.maxCandidatesPerCharacter, count);
      }

      if (audit.candidateCount !== audit.uniqueRequiredTargetCount) {
        throw new Error(`life_state_candidate_grounding_accounting_drift:${audit.candidateCount}:${audit.uniqueRequiredTargetCount}`);
      }
      if (audit.storyTimeNonUnresolvedCount !== 0 || audit.stateApplicationCount !== 0 || audit.sourceOrderViolationCount !== 0) {
        throw new Error("life_state_safety_invariant_violation");
      }

      completed.push({
        documentId,
        eventReport: component.events.bookNlp,
        audit,
        stateOutputFingerprint: state.outputFingerprint,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const eventAggregate = aggregateEventReports(completed.map((row) => row.eventReport));
  const audit = completed.reduce((total, row) => {
    for (const key of [
      "eventCandidateCount", "opportunityCount", "uniqueRequiredTargetCount", "missingRequiredTargetCount",
      "multipleRequiredTargetCount", "targetMissingMentionEvidenceCount", "candidateCount", "candidateNegatedCount",
      "candidateModalizedCount", "candidateIrrealisCuedCount", "candidateWithAnyQualifierCount",
      "candidateFullyUndeterminedCount", "storyTimeNonUnresolvedCount", "stateApplicationCount", "sourceOrderViolationCount",
      "uniqueTargetCharacterCount", "repeatedTargetCharacterCount", "repeatedCandidateExcessCount",
    ] as const) total[key] += row.audit[key];
    total.maxCandidatesPerCharacter = Math.max(total.maxCandidatesPerCharacter, row.audit.maxCandidatesPerCharacter);
    for (const [predicate, count] of Object.entries(row.audit.opportunityByPredicate)) increment(total.opportunityByPredicate, predicate, count);
    for (const [predicate, count] of Object.entries(row.audit.candidateByPredicate)) increment(total.candidateByPredicate, predicate, count);
    return total;
  }, emptyAudit());

  const fullCorpus = args.limit === null;
  if (fullCorpus && completed.length === 100 && failures.length === 0) {
    if (audit.eventCandidateCount !== EXPECTED_EVENT_COUNT || eventAggregate.predictedEventCount !== EXPECTED_EVENT_COUNT) {
      throw new Error(`life_state_event_count_drift:${audit.eventCandidateCount}:${eventAggregate.predictedEventCount}`);
    }
    if (eventAggregate.triggerDetection.precision.toFixed(4) !== "0.8003") throw new Error("life_state_trigger_precision_drift");
    if (eventAggregate.triggerDetection.recall.toFixed(4) !== "0.7591") throw new Error("life_state_trigger_recall_drift");
    if (eventAggregate.triggerDetection.f1.toFixed(4) !== "0.7791") throw new Error("life_state_trigger_f1_drift");
  }
  if (
    audit.uniqueRequiredTargetCount + audit.missingRequiredTargetCount + audit.multipleRequiredTargetCount
      + audit.targetMissingMentionEvidenceCount !== audit.opportunityCount
  ) throw new Error("life_state_opportunity_accounting_mismatch");
  if (audit.candidateCount !== audit.uniqueRequiredTargetCount) throw new Error("life_state_candidate_accounting_mismatch");
  if (audit.storyTimeNonUnresolvedCount !== 0 || audit.stateApplicationCount !== 0 || audit.sourceOrderViolationCount !== 0) {
    throw new Error("life_state_aggregate_safety_invariant_violation");
  }

  const semantic = {
    schemaVersion: "saga-character-life-state-litbank-diagnostic-v1",
    benchmark: "LitBank character life-status state-change candidate evidence diagnostic",
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
      eventExtractionChanged: false,
      triggerCorrectnessScored: true,
      stateCorrectnessScored: false,
      persistentStateApplied: false,
      storyTimeValidityClaimed: false,
      productionAdoptionClaimed: false,
      rawSourceTextEmitted: false,
    },
    policy: {
      predicates: CHARACTER_LIFE_STATE_PREDICATES,
      stateDimension: "life_status",
      candidateValue: "dead",
      targetPolicy: "exactly_one_grounded_character_in_required_role",
      candidateOnly: true,
      persistentStateApplication: false,
    },
    eventBaseline: {
      predictedEventCount: eventAggregate.predictedEventCount,
      triggerDetection: eventAggregate.triggerDetection,
      duplicatePredictionCount: eventAggregate.duplicatePredictionCount,
    },
    lifeState: {
      ...audit,
      opportunityRate: ratio(audit.opportunityCount, audit.eventCandidateCount),
      uniqueTargetYield: ratio(audit.uniqueRequiredTargetCount, audit.opportunityCount),
      missingTargetRate: ratio(audit.missingRequiredTargetCount, audit.opportunityCount),
      candidateWithAnyQualifierRate: ratio(audit.candidateWithAnyQualifierCount, audit.candidateCount),
      repeatedTargetCharacterRate: ratio(audit.repeatedTargetCharacterCount, audit.uniqueTargetCharacterCount),
    },
    caveat: "LitBank supplies event-trigger and character-coreference annotations, not S.A.G.A.-style life-state transition gold. Counts measure opportunity, grounding and qualifier coverage only; candidates are not asserted deaths or persistent state.",
    failures,
    perDocument: completed.map((row) => ({
      documentId: row.documentId,
      audit: row.audit,
      stateOutputFingerprint: row.stateOutputFingerprint,
    })),
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };
  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    scope: output.scope,
    policy: output.policy,
    eventBaseline: output.eventBaseline,
    lifeState: output.lifeState,
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
