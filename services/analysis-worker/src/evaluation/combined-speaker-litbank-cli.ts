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
  type DialogueQuotePrediction,
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

type FusionCategory =
  | "agreement"
  | "providerFallback"
  | "deterministicOnly"
  | "conflictUnresolved"
  | "unresolved";

type ConflictReasonAudit = {
  count: number;
  bookNlpCorrect: number;
  deterministicCorrect: number;
  bothWrong: number;
};

type FusionGoldAudit = {
  knownGoldQuoteCount: number;
  deterministicMatchedKnownQuoteCount: number;
  missedDeterministicQuoteCount: number;
  agreement: { count: number; correct: number; wrong: number };
  providerFallback: { count: number; correct: number; wrong: number; unresolved: number };
  deterministicOnly: { count: number; correct: number; wrong: number; unresolved: number };
  conflict: {
    count: number;
    bookNlpCorrectDeterministicWrong: number;
    deterministicCorrectBookNlpWrong: number;
    bothWrong: number;
    bookNlpUnresolved: number;
    deterministicUnresolved: number;
  };
  unresolved: { count: number };
  conflictByDeterministicReason: Record<string, ConflictReasonAudit>;
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

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function bySpan(prediction: DialogueProviderResult) {
  return new Map(prediction.quotes.map((quote) => [spanKey(quote.startOffset, quote.endOffset), quote]));
}

function fusionCategory(quote: DialogueQuotePrediction): FusionCategory {
  if (quote.decisionReason.startsWith("combined_agreement:")) return "agreement";
  if (quote.decisionReason.startsWith("combined_provider_fallback:")) return "providerFallback";
  if (quote.decisionReason.startsWith("combined_deterministic_only:")) return "deterministicOnly";
  if (quote.decisionReason.startsWith("combined_conflict_unresolved:")) return "conflictUnresolved";
  return "unresolved";
}

function fusionCounts(prediction: DialogueProviderResult) {
  const counts = {
    agreement: 0,
    providerFallback: 0,
    deterministicOnly: 0,
    conflictUnresolved: 0,
    unresolved: 0,
  };
  for (const quote of prediction.quotes) counts[fusionCategory(quote)] += 1;
  return counts;
}

function emptyFusionGoldAudit(): FusionGoldAudit {
  return {
    knownGoldQuoteCount: 0,
    deterministicMatchedKnownQuoteCount: 0,
    missedDeterministicQuoteCount: 0,
    agreement: { count: 0, correct: 0, wrong: 0 },
    providerFallback: { count: 0, correct: 0, wrong: 0, unresolved: 0 },
    deterministicOnly: { count: 0, correct: 0, wrong: 0, unresolved: 0 },
    conflict: {
      count: 0,
      bookNlpCorrectDeterministicWrong: 0,
      deterministicCorrectBookNlpWrong: 0,
      bothWrong: 0,
      bookNlpUnresolved: 0,
      deterministicUnresolved: 0,
    },
    unresolved: { count: 0 },
    conflictByDeterministicReason: {},
  };
}

function incrementResolvedOutcome(
  target: { count: number; correct: number; wrong: number; unresolved?: number },
  speakerKey: string | null,
  goldSpeakerKey: string,
) {
  target.count += 1;
  if (speakerKey === null) {
    if (target.unresolved !== undefined) target.unresolved += 1;
  } else if (speakerKey === goldSpeakerKey) target.correct += 1;
  else target.wrong += 1;
}

function auditFusionAgainstKnownGold(input: {
  reference: DialogueReference;
  deterministic: DialogueProviderResult;
  bookNlp: DialogueProviderResult;
  combined: DialogueProviderResult;
}): FusionGoldAudit {
  const audit = emptyFusionGoldAudit();
  const deterministicBySpan = bySpan(input.deterministic);
  const bookNlpBySpan = bySpan(input.bookNlp);
  const combinedBySpan = bySpan(input.combined);

  for (const gold of input.reference.quotes) {
    if (gold.speakerStatus !== "known" || gold.speakerKey === null) continue;
    audit.knownGoldQuoteCount += 1;
    const key = spanKey(gold.startOffset, gold.endOffset);
    const deterministic = deterministicBySpan.get(key) ?? null;
    const combined = combinedBySpan.get(key) ?? null;
    if (!deterministic || !combined) {
      audit.missedDeterministicQuoteCount += 1;
      continue;
    }
    audit.deterministicMatchedKnownQuoteCount += 1;
    const bookNlp = bookNlpBySpan.get(key) ?? null;
    const category = fusionCategory(combined);

    if (category === "agreement") {
      incrementResolvedOutcome(audit.agreement, combined.speakerKey, gold.speakerKey);
      continue;
    }
    if (category === "providerFallback") {
      incrementResolvedOutcome(audit.providerFallback, bookNlp?.speakerKey ?? null, gold.speakerKey);
      continue;
    }
    if (category === "deterministicOnly") {
      incrementResolvedOutcome(audit.deterministicOnly, deterministic.speakerKey, gold.speakerKey);
      continue;
    }
    if (category === "conflictUnresolved") {
      audit.conflict.count += 1;
      const deterministicSpeaker = deterministic.speakerKey;
      const bookNlpSpeaker = bookNlp?.speakerKey ?? null;
      if (deterministicSpeaker === null) audit.conflict.deterministicUnresolved += 1;
      if (bookNlpSpeaker === null) audit.conflict.bookNlpUnresolved += 1;
      if (bookNlpSpeaker === gold.speakerKey && deterministicSpeaker !== gold.speakerKey) {
        audit.conflict.bookNlpCorrectDeterministicWrong += 1;
      } else if (deterministicSpeaker === gold.speakerKey && bookNlpSpeaker !== gold.speakerKey) {
        audit.conflict.deterministicCorrectBookNlpWrong += 1;
      } else if (deterministicSpeaker !== gold.speakerKey && bookNlpSpeaker !== gold.speakerKey) {
        audit.conflict.bothWrong += 1;
      }
      const reason = deterministic.decisionReason;
      const current = audit.conflictByDeterministicReason[reason] ?? {
        count: 0,
        bookNlpCorrect: 0,
        deterministicCorrect: 0,
        bothWrong: 0,
      };
      current.count += 1;
      if (bookNlpSpeaker === gold.speakerKey) current.bookNlpCorrect += 1;
      else if (deterministicSpeaker === gold.speakerKey) current.deterministicCorrect += 1;
      else current.bothWrong += 1;
      audit.conflictByDeterministicReason[reason] = current;
      continue;
    }
    audit.unresolved.count += 1;
  }
  return audit;
}

function aggregateFusionGoldAudits(audits: FusionGoldAudit[]): FusionGoldAudit {
  const total = emptyFusionGoldAudit();
  for (const audit of audits) {
    total.knownGoldQuoteCount += audit.knownGoldQuoteCount;
    total.deterministicMatchedKnownQuoteCount += audit.deterministicMatchedKnownQuoteCount;
    total.missedDeterministicQuoteCount += audit.missedDeterministicQuoteCount;
    for (const key of ["agreement", "providerFallback", "deterministicOnly"] as const) {
      total[key].count += audit[key].count;
      total[key].correct += audit[key].correct;
      total[key].wrong += audit[key].wrong;
      if ("unresolved" in total[key] && "unresolved" in audit[key]) total[key].unresolved += audit[key].unresolved;
    }
    total.conflict.count += audit.conflict.count;
    total.conflict.bookNlpCorrectDeterministicWrong += audit.conflict.bookNlpCorrectDeterministicWrong;
    total.conflict.deterministicCorrectBookNlpWrong += audit.conflict.deterministicCorrectBookNlpWrong;
    total.conflict.bothWrong += audit.conflict.bothWrong;
    total.conflict.bookNlpUnresolved += audit.conflict.bookNlpUnresolved;
    total.conflict.deterministicUnresolved += audit.conflict.deterministicUnresolved;
    total.unresolved.count += audit.unresolved.count;
    for (const [reason, values] of Object.entries(audit.conflictByDeterministicReason)) {
      const current = total.conflictByDeterministicReason[reason] ?? {
        count: 0,
        bookNlpCorrect: 0,
        deterministicCorrect: 0,
        bothWrong: 0,
      };
      current.count += values.count;
      current.bookNlpCorrect += values.bookNlpCorrect;
      current.deterministicCorrect += values.deterministicCorrect;
      current.bothWrong += values.bothWrong;
      total.conflictByDeterministicReason[reason] = current;
    }
  }
  total.conflictByDeterministicReason = Object.fromEntries(
    Object.entries(total.conflictByDeterministicReason)
      .sort(([, left], [, right]) => right.count - left.count),
  );
  return total;
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
    goldAudit: FusionGoldAudit;
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
      const deterministicPrediction = predictDeterministicDialogue({
        sections: [section],
        normalizedInputFingerprint,
        identity,
      });
      const bookNlpPrediction = bookNlpDialoguePrediction({
        documentId,
        evidence,
        goldIdentity: converted.gold,
      }).prediction;
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
        goldAudit: auditFusionAgainstKnownGold({
          reference,
          deterministic: deterministicPrediction,
          bookNlp: bookNlpPrediction,
          combined: combinedPrediction,
        }),
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
  const goldAudit = aggregateFusionGoldAudits(completed.map((row) => row.goldAudit));
  const semantic = {
    schemaVersion: "saga-combined-speaker-litbank-benchmark-v2",
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
      goldAudit,
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
