import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { codePointLength, normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import { predictCombinedSpeakerDialogue } from "./combined-speaker.js";
import {
  evaluateDialogue,
  validateDialogueProviderResult,
  type DialogueEvaluationReport,
  type DialogueProviderResult,
  type DialogueReference,
} from "./dialogue-evaluation.js";
import {
  aggregateDialogueReports,
  convertLitBankQuotationReference,
  evaluateLitBankComponentDocument,
  litBankDocumentSection,
  litBankGoldIdentityResult,
} from "./litbank-component-benchmark.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";

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
    throw new Error("usage: combined-speaker-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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
  const quoteDetection = metricScore(0, input.prediction.quotes.length, 0);
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    quoteDetection,
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

function fusionCounts(prediction: DialogueProviderResult) {
  const counts = {
    agreement: 0,
    providerFallback: 0,
    deterministicOnly: 0,
    conflictUnresolved: 0,
    unresolved: 0,
  };
  for (const quote of prediction.quotes) {
    if (quote.decisionReason.startsWith("combined_agreement:")) counts.agreement += 1;
    else if (quote.decisionReason.startsWith("combined_provider_fallback:")) counts.providerFallback += 1;
    else if (quote.decisionReason.startsWith("combined_deterministic_only:")) counts.deterministicOnly += 1;
    else if (quote.decisionReason.startsWith("combined_conflict_unresolved:")) counts.conflictUnresolved += 1;
    else counts.unresolved += 1;
  }
  return counts;
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
    fusion: ReturnType<typeof fusionCounts>;
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
      if (normalizeNewlines(quotationTextRaw) !== text) throw new Error("litbank_component_quotation_source_mismatch");
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [{
          stable_key: section.stable_key,
          ordinal: section.ordinal,
          section_kind: section.section_kind,
          title: section.title,
          source_locator: section.source_locator,
          start_offset: section.start_offset,
          end_offset: codePointLength(text),
          normalized_text: text,
        }],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const converted = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation });
      const identity = litBankGoldIdentityResult(converted.gold);
      const reference = convertLitBankQuotationReference({ documentId, text, annotation: quotationAnnotation });
      const prediction = predictCombinedSpeakerDialogue({
        sections: [section],
        normalizedInputFingerprint,
        identity,
        literaryEvidence: evidence,
      });
      const baseline = evaluateLitBankComponentDocument({
        documentId,
        text,
        corefAnnotation,
        quotationAnnotation,
        eventTsv,
        evidence,
      });
      completed.push({
        documentId,
        combined: evaluateDialogueAllowEmpty({ reference, prediction }),
        bookNlp: baseline.dialogue.bookNlp,
        deterministic: baseline.dialogue.deterministicOracleIdentity,
        fusion: fusionCounts(prediction),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const aggregateFusion = completed.reduce((total, row) => ({
    agreement: total.agreement + row.fusion.agreement,
    providerFallback: total.providerFallback + row.fusion.providerFallback,
    deterministicOnly: total.deterministicOnly + row.fusion.deterministicOnly,
    conflictUnresolved: total.conflictUnresolved + row.fusion.conflictUnresolved,
    unresolved: total.unresolved + row.fusion.unresolved,
  }), { agreement: 0, providerFallback: 0, deterministicOnly: 0, conflictUnresolved: 0, unresolved: 0 });

  const combined = aggregateDialogueReports(completed.map((row) => row.combined));
  const bookNlp = aggregateDialogueReports(completed.map((row) => row.bookNlp));
  const deterministic = aggregateDialogueReports(completed.map((row) => row.deterministic));
  const semantic = {
    schemaVersion: "saga-combined-speaker-litbank-benchmark-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      attemptedDocumentCount: documentIds.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    policy: {
      quoteBoundarySource: "saga_deterministic_dialogue_baseline",
      providerSpeakerSource: BOOKNLP_SMALL_PROVIDER,
      identitySource: "litbank_gold_oracle_for_component_isolation_only",
      quoteMatch: "exact_span_only",
      speakerMatch: "exact_resolved_identity_span_only",
      conflict: "unresolved",
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
      fusionCounts: aggregateFusion,
    },
    failures,
    perDocument: completed,
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
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
