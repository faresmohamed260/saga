import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { codePointLength, normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import { predictCombinedSpeakerDialogue } from "./combined-speaker.js";
import { predictDeterministicDialogue } from "./dialogue-deterministic-baseline.js";
import {
  evaluateDialogue,
  validateDialogueProviderResult,
  type DialogueEvaluationReport,
  type DialogueProviderResult,
  type DialogueReference,
} from "./dialogue-evaluation.js";
import {
  aggregateDialogueReports,
  bookNlpDialoguePrediction,
  convertLitBankQuotationReference,
  litBankDocumentSection,
  litBankGoldIdentityResult,
} from "./litbank-component-benchmark.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";

type FusionCounts = {
  agreement: number;
  providerFallback: number;
  deterministicOnly: number;
  conflictProviderAfter: number;
  conflictUnresolved: number;
  unresolved: number;
};

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
    throw new Error("usage: combined-speaker-v2-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
  }
  return { litbankRoot: resolve(litbankRoot), booknlpRoot: resolve(booknlpRoot), out: resolve(out), limit };
}

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/gu, "\n");
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

function evaluateDialogueAllowEmpty(input: {
  reference: DialogueReference;
  prediction: DialogueProviderResult;
}): DialogueEvaluationReport {
  if (input.reference.quotes.length > 0) return evaluateDialogue(input);
  validateDialogueProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("dialogue_input_fingerprint_mismatch");
  }
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    quoteDetection: metricScore(0, input.prediction.quotes.length, 0),
    knownSpeakerGoldCount: 0,
    matchedKnownSpeakerCount: 0,
    knownSpeakerMissedQuoteCount: 0,
    speakerCorrectCount: 0,
    speakerIncorrectCount: 0,
    speakerUnresolvedCount: 0,
    speakerAccuracyOnMatchedQuotes: 0,
    resolvedSpeakerAccuracy: 0,
    speakerUnresolvedRateOnMatchedQuotes: 0,
    crossCharacterContaminationRateOnMatchedQuotes: 0,
    endToEndSpeakerRecall: 0,
    unknownSpeakerMatchedCount: 0,
    ambiguousSpeakerMatchedCount: 0,
    unscoredSpeakerAssignmentCount: 0,
  };
  return {
    schemaVersion: "saga-dialogue-evaluation-v1",
    ...semantic,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
  };
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

function emptyFusionCounts(): FusionCounts {
  return {
    agreement: 0,
    providerFallback: 0,
    deterministicOnly: 0,
    conflictProviderAfter: 0,
    conflictUnresolved: 0,
    unresolved: 0,
  };
}

function fusionCounts(prediction: DialogueProviderResult) {
  const counts = emptyFusionCounts();
  for (const quote of prediction.quotes) {
    const reason = quote.decisionReason;
    if (reason.startsWith("combined_agreement:")) counts.agreement += 1;
    else if (reason.startsWith("combined_provider_fallback:")) counts.providerFallback += 1;
    else if (reason.startsWith("combined_deterministic_only:")) counts.deterministicOnly += 1;
    else if (reason.startsWith("combined_conflict_provider_after:")) counts.conflictProviderAfter += 1;
    else if (reason.startsWith("combined_conflict_unresolved:")) counts.conflictUnresolved += 1;
    else counts.unresolved += 1;
  }
  return counts;
}

function addFusionCounts(target: FusionCounts, source: FusionCounts) {
  target.agreement += source.agreement;
  target.providerFallback += source.providerFallback;
  target.deterministicOnly += source.deterministicOnly;
  target.conflictProviderAfter += source.conflictProviderAfter;
  target.conflictUnresolved += source.conflictUnresolved;
  target.unresolved += source.unresolved;
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
    combined: DialogueEvaluationReport;
    bookNlp: DialogueEvaluationReport;
    deterministic: DialogueEvaluationReport;
    fusion: FusionCounts;
  }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, quotationAnnotation, quotationTextRaw, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.ann`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.txt`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      if (normalizeNewlines(quotationTextRaw) !== text) throw new Error("litbank_component_quotation_source_mismatch");
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [{ ...section, end_offset: codePointLength(text), normalized_text: text }],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = litBankGoldIdentityResult(converted.gold);
      const reference = convertLitBankQuotationReference({ documentId, text, annotation: quotationAnnotation });
      const deterministicPrediction = predictDeterministicDialogue({ sections: [section], normalizedInputFingerprint, identity });
      const bookNlpPrediction = bookNlpDialoguePrediction({ documentId, evidence, goldIdentity: converted.gold }).prediction;
      const combinedPrediction = predictCombinedSpeakerDialogue({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence: evidence,
      });

      completed.push({
        documentId,
        combined: evaluateDialogueAllowEmpty({ reference, prediction: combinedPrediction }),
        bookNlp: evaluateDialogueAllowEmpty({ reference, prediction: bookNlpPrediction }),
        deterministic: evaluateDialogueAllowEmpty({ reference, prediction: deterministicPrediction }),
        fusion: fusionCounts(combinedPrediction),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const combined = aggregateDialogueReports(completed.map((row) => row.combined));
  const bookNlp = aggregateDialogueReports(completed.map((row) => row.bookNlp));
  const deterministic = aggregateDialogueReports(completed.map((row) => row.deterministic));
  const fusion = emptyFusionCounts();
  for (const row of completed) addFusionCounts(fusion, row.fusion);

  const semantic = {
    schemaVersion: "saga-combined-speaker-litbank-benchmark-v3",
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
    policy: {
      quoteBoundarySource: "saga_deterministic_dialogue_baseline",
      providerSpeakerSource: BOOKNLP_SMALL_PROVIDER,
      identitySource: "litbank_gold_oracle_for_component_isolation_only",
      quoteMatch: "exact_span_only",
      speakerMatch: "exact_resolved_identity_span_only",
      conflict: "provider_wins_only_when_deterministic_reason_is_post_quote_speech_tag",
      beforeQuoteConflict: "unresolved",
      providerClusterIdsCanonical: false,
    },
    dialogue: {
      combined,
      bookNlp,
      deterministicOracleIdentity: deterministic,
      deltaVsBookNlp: {
        matchedKnownSpeakerAccuracy: combined.speakerAccuracyOnMatchedQuotes - bookNlp.speakerAccuracyOnMatchedQuotes,
        resolvedSpeakerAccuracy: combined.resolvedSpeakerAccuracy - bookNlp.resolvedSpeakerAccuracy,
        endToEndSpeakerRecall: combined.endToEndSpeakerRecall - bookNlp.endToEndSpeakerRecall,
        unresolvedRate: combined.speakerUnresolvedRateOnMatchedQuotes - bookNlp.speakerUnresolvedRateOnMatchedQuotes,
        crossCharacterContamination: combined.crossCharacterContaminationRateOnMatchedQuotes - bookNlp.crossCharacterContaminationRateOnMatchedQuotes,
      },
      deltaVsDeterministic: {
        matchedKnownSpeakerAccuracy: combined.speakerAccuracyOnMatchedQuotes - deterministic.speakerAccuracyOnMatchedQuotes,
        resolvedSpeakerAccuracy: combined.resolvedSpeakerAccuracy - deterministic.resolvedSpeakerAccuracy,
        endToEndSpeakerRecall: combined.endToEndSpeakerRecall - deterministic.endToEndSpeakerRecall,
        unresolvedRate: combined.speakerUnresolvedRateOnMatchedQuotes - deterministic.speakerUnresolvedRateOnMatchedQuotes,
        crossCharacterContamination: combined.crossCharacterContaminationRateOnMatchedQuotes - deterministic.crossCharacterContaminationRateOnMatchedQuotes,
      },
      fusionCounts: fusion,
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
    policy: output.policy,
    dialogue: output.dialogue,
    failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
