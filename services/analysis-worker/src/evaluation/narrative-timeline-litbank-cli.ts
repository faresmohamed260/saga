import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  aggregateEventReports,
  bookNlpEventPrediction,
  evaluateLitBankComponentDocument,
  litBankDocumentSection,
} from "./litbank-component-benchmark.js";
import {
  deriveNarrativeTimelineEvidence,
  type NarrativeTimelineEvidenceResult,
  type TemporalCueFamily,
  type TemporalCueLemma,
} from "./narrative-timeline-evidence.js";

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
    throw new Error("usage: narrative-timeline-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function sentenceKey(locator: string | null, sentenceId: number) {
  return `${locator ?? "<null>"}:${sentenceId}`;
}

function documentTimelineAudit(timeline: NarrativeTimelineEvidenceResult) {
  const familyCounts: Record<TemporalCueFamily, number> = {
    relative_sequence: 0,
    simultaneity: 0,
    deictic: 0,
    interval_boundary: 0,
    relative_distance: 0,
  };
  const lemmaCounts: Partial<Record<TemporalCueLemma, number>> = {};
  const eventSentenceCounts = new Map<string, number>();
  const cueSentenceCounts = new Map<string, number>();
  let eventWithCueCount = 0;
  let eventWithMultipleCuesCount = 0;
  let cueAttachmentCount = 0;
  let maxCuesPerEvent = 0;
  let storyTimeResolvedCount = 0;
  let narrativeOrderViolationCount = 0;

  for (const cue of timeline.temporalCues) {
    familyCounts[cue.family] += 1;
    lemmaCounts[cue.lemma] = (lemmaCounts[cue.lemma] ?? 0) + 1;
    increment(cueSentenceCounts as unknown as Record<string, number>, sentenceKey(cue.structuralLocator, cue.sentenceId));
  }

  for (let index = 0; index < timeline.entries.length; index += 1) {
    const entry = timeline.entries[index]!;
    const key = sentenceKey(entry.structuralLocator, entry.sentenceId);
    eventSentenceCounts.set(key, (eventSentenceCounts.get(key) ?? 0) + 1);
    const cueCount = entry.temporalCueEvidenceIds.length;
    cueAttachmentCount += cueCount;
    if (cueCount > 0) eventWithCueCount += 1;
    if (cueCount > 1) eventWithMultipleCuesCount += 1;
    if (cueCount > maxCuesPerEvent) maxCuesPerEvent = cueCount;
    if (entry.storyTimeStatus !== "unresolved") storyTimeResolvedCount += 1;
    if (entry.narrativeSequenceIndex !== index) narrativeOrderViolationCount += 1;
    if (index > 0) {
      const previous = timeline.entries[index - 1]!;
      if (
        previous.eventStartOffset > entry.eventStartOffset
        || (
          previous.eventStartOffset === entry.eventStartOffset
          && previous.eventEndOffset > entry.eventEndOffset
        )
      ) narrativeOrderViolationCount += 1;
    }
  }

  let multiEventSentenceCount = 0;
  let multiCueSentenceCount = 0;
  let eventBearingSentenceWithCueCount = 0;
  let multiEventAndCueSentenceCount = 0;
  for (const [key, count] of eventSentenceCounts) {
    const cueCount = cueSentenceCounts.get(key) ?? 0;
    if (count > 1) multiEventSentenceCount += 1;
    if (cueCount > 0) eventBearingSentenceWithCueCount += 1;
    if (count > 1 && cueCount > 0) multiEventAndCueSentenceCount += 1;
  }
  for (const count of cueSentenceCounts.values()) {
    if (count > 1) multiCueSentenceCount += 1;
  }

  return {
    eventCandidateCount: timeline.entries.length,
    temporalCueCount: timeline.temporalCues.length,
    eventWithCueCount,
    eventWithoutCueCount: timeline.entries.length - eventWithCueCount,
    eventWithMultipleCuesCount,
    cueAttachmentCount,
    maxCuesPerEvent,
    eventBearingSentenceCount: eventSentenceCounts.size,
    eventBearingSentenceWithCueCount,
    multiEventSentenceCount,
    multiCueSentenceCount,
    multiEventAndCueSentenceCount,
    storyTimeResolvedCount,
    storyTimeRelationCount: timeline.storyTimeRelations.length,
    narrativeOrderViolationCount,
    familyCounts,
    lemmaCounts,
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
    timelineOutputFingerprint: string;
    audit: ReturnType<typeof documentTimelineAudit>;
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
      const quotationText = normalizeNewlines(quotationTextRaw);
      if (quotationText !== text) throw new Error("timeline_litbank_quotation_source_mismatch");
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
      const events = bookNlpEventPrediction({ documentId, evidence: literaryEvidence });
      const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence, events });
      completed.push({
        documentId,
        eventReport: component.events.bookNlp,
        timelineOutputFingerprint: timeline.outputFingerprint,
        audit: documentTimelineAudit(timeline),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const eventAggregate = aggregateEventReports(completed.map((row) => row.eventReport));
  const timelineAudit = completed.reduce((total, row) => {
    total.eventCandidateCount += row.audit.eventCandidateCount;
    total.temporalCueCount += row.audit.temporalCueCount;
    total.eventWithCueCount += row.audit.eventWithCueCount;
    total.eventWithoutCueCount += row.audit.eventWithoutCueCount;
    total.eventWithMultipleCuesCount += row.audit.eventWithMultipleCuesCount;
    total.cueAttachmentCount += row.audit.cueAttachmentCount;
    total.maxCuesPerEvent = Math.max(total.maxCuesPerEvent, row.audit.maxCuesPerEvent);
    total.eventBearingSentenceCount += row.audit.eventBearingSentenceCount;
    total.eventBearingSentenceWithCueCount += row.audit.eventBearingSentenceWithCueCount;
    total.multiEventSentenceCount += row.audit.multiEventSentenceCount;
    total.multiCueSentenceCount += row.audit.multiCueSentenceCount;
    total.multiEventAndCueSentenceCount += row.audit.multiEventAndCueSentenceCount;
    total.storyTimeResolvedCount += row.audit.storyTimeResolvedCount;
    total.storyTimeRelationCount += row.audit.storyTimeRelationCount;
    total.narrativeOrderViolationCount += row.audit.narrativeOrderViolationCount;
    for (const [family, count] of Object.entries(row.audit.familyCounts)) increment(total.familyCounts, family, count);
    for (const [lemma, count] of Object.entries(row.audit.lemmaCounts)) increment(total.lemmaCounts, lemma, count);
    return total;
  }, {
    eventCandidateCount: 0,
    temporalCueCount: 0,
    eventWithCueCount: 0,
    eventWithoutCueCount: 0,
    eventWithMultipleCuesCount: 0,
    cueAttachmentCount: 0,
    maxCuesPerEvent: 0,
    eventBearingSentenceCount: 0,
    eventBearingSentenceWithCueCount: 0,
    multiEventSentenceCount: 0,
    multiCueSentenceCount: 0,
    multiEventAndCueSentenceCount: 0,
    storyTimeResolvedCount: 0,
    storyTimeRelationCount: 0,
    narrativeOrderViolationCount: 0,
    familyCounts: {} as Record<string, number>,
    lemmaCounts: {} as Record<string, number>,
  });

  const fullCorpus = args.limit === null;
  if (fullCorpus && completed.length === 100 && failures.length === 0) {
    if (timelineAudit.eventCandidateCount !== EXPECTED_EVENT_COUNT) {
      throw new Error(`timeline_event_count_drift:${timelineAudit.eventCandidateCount}:${EXPECTED_EVENT_COUNT}`);
    }
    if (eventAggregate.predictedEventCount !== EXPECTED_EVENT_COUNT) {
      throw new Error(`timeline_trigger_prediction_count_drift:${eventAggregate.predictedEventCount}:${EXPECTED_EVENT_COUNT}`);
    }
    if (eventAggregate.triggerDetection.precision.toFixed(4) !== "0.8003") {
      throw new Error(`timeline_trigger_precision_drift:${eventAggregate.triggerDetection.precision}`);
    }
    if (eventAggregate.triggerDetection.recall.toFixed(4) !== "0.7591") {
      throw new Error(`timeline_trigger_recall_drift:${eventAggregate.triggerDetection.recall}`);
    }
    if (eventAggregate.triggerDetection.f1.toFixed(4) !== "0.7791") {
      throw new Error(`timeline_trigger_f1_drift:${eventAggregate.triggerDetection.f1}`);
    }
  }
  if (timelineAudit.storyTimeResolvedCount !== 0 || timelineAudit.storyTimeRelationCount !== 0) {
    throw new Error("timeline_story_time_inference_detected");
  }
  if (timelineAudit.narrativeOrderViolationCount !== 0) {
    throw new Error(`timeline_narrative_order_violation:${timelineAudit.narrativeOrderViolationCount}`);
  }
  if (timelineAudit.eventWithCueCount + timelineAudit.eventWithoutCueCount !== timelineAudit.eventCandidateCount) {
    throw new Error("timeline_event_cue_accounting_mismatch");
  }

  const semantic = {
    schemaVersion: "saga-narrative-timeline-litbank-diagnostic-v1",
    benchmark: "LitBank deterministic narrative-order and temporal-cue evidence diagnostic",
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
      timelineCorrectnessScored: false,
      chronologyAccuracyClaimed: false,
      storyTimeInferencePerformed: false,
      flashbackInferencePerformed: false,
      productionAdoptionClaimed: false,
      rawSourceTextEmitted: false,
    },
    eventBaseline: {
      predictedEventCount: eventAggregate.predictedEventCount,
      triggerDetection: eventAggregate.triggerDetection,
      duplicatePredictionCount: eventAggregate.duplicatePredictionCount,
      unsupportedPredictionCount: eventAggregate.unsupportedPredictionCount,
    },
    timeline: {
      ...timelineAudit,
      eventWithCueRate: timelineAudit.eventCandidateCount === 0 ? 0 : timelineAudit.eventWithCueCount / timelineAudit.eventCandidateCount,
      cueAttachmentRatePerEvent: timelineAudit.eventCandidateCount === 0 ? 0 : timelineAudit.cueAttachmentCount / timelineAudit.eventCandidateCount,
      eventBearingSentenceWithCueRate: timelineAudit.eventBearingSentenceCount === 0
        ? 0
        : timelineAudit.eventBearingSentenceWithCueCount / timelineAudit.eventBearingSentenceCount,
    },
    failures,
    perDocument: completed.map((row) => ({
      documentId: row.documentId,
      timelineOutputFingerprint: row.timelineOutputFingerprint,
      eventCandidateCount: row.audit.eventCandidateCount,
      temporalCueCount: row.audit.temporalCueCount,
      eventWithCueCount: row.audit.eventWithCueCount,
      cueAttachmentCount: row.audit.cueAttachmentCount,
      eventBearingSentenceCount: row.audit.eventBearingSentenceCount,
      eventBearingSentenceWithCueCount: row.audit.eventBearingSentenceWithCueCount,
      storyTimeResolvedCount: row.audit.storyTimeResolvedCount,
      storyTimeRelationCount: row.audit.storyTimeRelationCount,
      narrativeOrderViolationCount: row.audit.narrativeOrderViolationCount,
    })),
    caveat:
      "This diagnostic measures deterministic narrative/source ordering and explicit same-sentence temporal-cue availability only. LitBank provides no S.A.G.A.-style story-time/flashback relation gold here; cue presence does not establish temporal scope or chronology truth.",
  };
  const output = {
    ...semantic,
    reportFingerprint: sha256Hex(canonicalJson(semantic)),
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    eventBaseline: output.eventBaseline,
    timeline: output.timeline,
    failures: output.failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
