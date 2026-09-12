import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { BOOKNLP_SMALL_PROVIDER } from "../src/local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";
import {
  aggregateDialogueReports,
  aggregateEventReports,
  bookNlpDialoguePrediction,
  convertLitBankEventReference,
  convertLitBankQuotationReference,
  evaluateLitBankComponentDocument,
} from "../src/evaluation/litbank-component-benchmark.js";
import { convertLitBankTsvDocument } from "../src/evaluation/litbank-tsv.js";

const text = 'Alice said , " Hello . "\nBob waved .';
const fingerprint = sha256Hex(text);
const corefAnnotation = [
  "MENTION\tT0\t0\t0\t0\t0\tAlice\tPER\tPROP",
  "MENTION\tT1\t1\t0\t1\t0\tBob\tPER\tPROP",
  "COREF\tT0\tAlice-1",
  "COREF\tT1\tBob-2",
].join("\n");
const quotationAnnotation = [
  'QUOTE\tQ1\t0\t3\t0\t6\t" Hello . "',
  "ATTRIB\tQ1\tAlice-1",
].join("\n");
const eventTsv = [
  "Alice\tO",
  "said\tO",
  ",\tO",
  '"\tO',
  "Hello\tO",
  ".\tO",
  '"\tO',
  "",
  "Bob\tO",
  "waved\tEVENT",
  ".\tO",
].join("\n");

function offsets(surface: string, from = 0) {
  const start = text.indexOf(surface, from);
  assert.notEqual(start, -1);
  return { start, end: start + surface.length };
}

function evidence(input: { includeQuote?: boolean; includeEvent?: boolean } = {}): LocalLiteraryEvidenceBundle {
  const includeQuote = input.includeQuote ?? true;
  const includeEvent = input.includeEvent ?? true;
  const quoteStart = text.indexOf('"');
  const quoteEnd = text.lastIndexOf('"') + 1;
  const alice = offsets("Alice");
  const waved = offsets("waved");
  return {
    provider: BOOKNLP_SMALL_PROVIDER,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: {
      provider: BOOKNLP_SMALL_PROVIDER,
      normalizedInputFingerprint: fingerprint,
      mentions: [],
    },
    entities: [],
    quotes: includeQuote ? [{
      evidenceId: "booknlp:quote:fixture",
      quoteText: text.slice(quoteStart, quoteEnd),
      startOffset: quoteStart,
      endOffset: quoteEnd,
      structuralLocator: "litbank:fixture:litbank:fixture",
      speakerSurfaceText: "Alice",
      speakerStartOffset: alice.start,
      speakerEndOffset: alice.end,
      speakerProviderClusterId: "booknlp:999",
    }] : [],
    eventTriggers: includeEvent ? [{
      evidenceId: "booknlp:event:fixture",
      surfaceText: "waved",
      lemma: "wave",
      startOffset: waved.start,
      endOffset: waved.end,
      structuralLocator: "litbank:fixture:litbank:fixture",
      sentenceId: 1,
      tokenId: 8,
      dependencyRelation: "ROOT",
      syntacticHeadTokenId: 8,
    }] : [],
  };
}

test("LitBank quotation conversion preserves exact span and gold speaker identity", () => {
  const reference = convertLitBankQuotationReference({ documentId: "fixture", text, annotation: quotationAnnotation });
  assert.equal(reference.quotes.length, 1);
  const quote = reference.quotes[0]!;
  assert.equal(text.slice(quote.startOffset, quote.endOffset), '" Hello . "');
  assert.equal(quote.speakerStatus, "known");
  assert.equal(quote.speakerKey, "Alice-1");
});

test("LitBank event conversion aligns every token and rejects source drift", () => {
  const reference = convertLitBankEventReference({ documentId: "fixture", text, eventTsv });
  assert.equal(reference.events.length, 1);
  const event = reference.events[0]!;
  assert.equal(text.slice(event.startOffset, event.endOffset), "waved");
  assert.equal(event.participantStatus, "unknown");

  assert.throws(
    () => convertLitBankEventReference({ documentId: "fixture", text, eventTsv: eventTsv.replace("Bob\tO", "Robert\tO") }),
    /litbank_event_token_mismatch/u,
  );
});

test("BookNLP speaker component maps attributed mention span through LitBank gold rather than BookNLP clustering", () => {
  const gold = convertLitBankTsvDocument({ documentId: "fixture", text, annotation: corefAnnotation }).gold;
  const result = bookNlpDialoguePrediction({ documentId: "fixture", evidence: evidence(), goldIdentity: gold });
  assert.equal(result.attributedMentionCount, 1);
  assert.equal(result.goldMappedMentionCount, 1);
  assert.equal(result.prediction.quotes[0]!.speakerKey, "Alice-1");
});

test("component benchmark compares BookNLP against deterministic floors with oracle identity isolation", () => {
  const result = evaluateLitBankComponentDocument({
    documentId: "fixture",
    text,
    corefAnnotation,
    quotationAnnotation,
    eventTsv,
    evidence: evidence(),
  });

  assert.equal(result.dialogue.bookNlp.quoteDetection.f1, 1);
  assert.equal(result.dialogue.bookNlp.speakerCorrectCount, 1);
  assert.equal(result.dialogue.bookNlp.endToEndSpeakerRecall, 1);
  assert.equal(result.dialogue.deterministicOracleIdentity.quoteDetection.f1, 1);
  assert.equal(result.dialogue.deterministicOracleIdentity.speakerCorrectCount, 1);

  assert.equal(result.events.bookNlp.triggerDetection.f1, 1);
  assert.equal(result.events.deterministicLexicalOracleIdentity.triggerDetection.f1, 0);
  assert.equal(result.events.bookNlp.knownParticipantEventCount, 0);
});

test("zero-gold quotation documents remain in scoring and expose false positives", () => {
  const noQuote = evidence({ includeEvent: true });
  noQuote.quotes = [];
  const clean = evaluateLitBankComponentDocument({
    documentId: "fixture",
    text,
    corefAnnotation,
    quotationAnnotation: "",
    eventTsv,
    evidence: noQuote,
  });
  assert.equal(clean.dialogue.bookNlp.quoteDetection.precision, 1);
  assert.equal(clean.dialogue.bookNlp.quoteDetection.recall, 1);

  const withFalsePositive = evaluateLitBankComponentDocument({
    documentId: "fixture",
    text,
    corefAnnotation,
    quotationAnnotation: "",
    eventTsv,
    evidence: evidence(),
  });
  assert.equal(withFalsePositive.dialogue.bookNlp.quoteDetection.falsePositive, 1);
  assert.equal(withFalsePositive.dialogue.bookNlp.quoteDetection.precision, 0);
});

test("component aggregate metrics are count-weighted rather than document-averaged", () => {
  const one = evaluateLitBankComponentDocument({
    documentId: "fixture",
    text,
    corefAnnotation,
    quotationAnnotation,
    eventTsv,
    evidence: evidence(),
  });
  const dialogue = aggregateDialogueReports([one.dialogue.bookNlp, one.dialogue.bookNlp]);
  const events = aggregateEventReports([one.events.bookNlp, one.events.bookNlp]);
  assert.equal(dialogue.quoteDetection.truePositive, 2);
  assert.equal(dialogue.quoteDetection.f1, 1);
  assert.equal(events.triggerDetection.truePositive, 2);
  assert.equal(events.triggerDetection.f1, 1);
  assert.equal(events.participantGroundingScored, false);
});
