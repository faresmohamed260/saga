import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveNarrativeTimelineEvidence,
  validateNarrativeTimelineEvidence,
} from "../src/evaluation/narrative-timeline-evidence.js";
import {
  eventPredictionFingerprint,
  type EventProviderResult,
} from "../src/evaluation/event-evaluation.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const inputFingerprint = "a".repeat(64);
const locator = "fixture:section";
const provider = { name: "fixture-events", model: null, revision: "1" };

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, fromCodeUnit = 0) {
  const start = text.indexOf(surface, fromCodeUnit);
  if (start < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, start)),
    endOffset: cpLength(text.slice(0, start + surface.length)),
    codeUnitStart: start,
  };
}

function token(input: {
  text: string;
  surface: string;
  tokenId: number;
  sentenceId: number;
  head: number;
  dep: string;
  lemma?: string;
  fromCodeUnit?: number;
  paragraphId?: number;
  structuralLocator?: string | null;
}) {
  const found = locate(input.text, input.surface, input.fromCodeUnit ?? 0);
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    startOffset: found.startOffset,
    endOffset: found.endOffset,
    structuralLocator: input.structuralLocator === undefined ? locator : input.structuralLocator,
    paragraphId: input.paragraphId ?? 0,
    sentenceId: input.sentenceId,
    tokenIdWithinSentence: input.tokenId,
    tokenId: input.tokenId,
    posTag: input.dep === "ROOT" ? "VERB" : "X",
    finePosTag: "X",
    dependencyRelation: input.dep,
    syntacticHeadTokenId: input.head,
  } satisfies SyntaxTokenEvidence;
}

function trigger(source: SyntaxTokenEvidence): EventTriggerEvidence {
  return {
    evidenceId: `trigger:${source.tokenId}`,
    surfaceText: source.surfaceText,
    lemma: source.lemma,
    startOffset: source.startOffset,
    endOffset: source.endOffset,
    structuralLocator: source.structuralLocator,
    sentenceId: source.sentenceId,
    tokenId: source.tokenId,
    dependencyRelation: source.dependencyRelation,
    syntacticHeadTokenId: source.syntacticHeadTokenId,
  };
}

function evidence(tokens: SyntaxTokenEvidence[], triggers: EventTriggerEvidence[], fingerprint = inputFingerprint): LocalLiteraryEvidenceBundle {
  const evidenceProvider = { name: "fixture-literary", model: null, revision: "1" };
  return {
    provider: evidenceProvider,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: {
      provider: evidenceProvider,
      normalizedInputFingerprint: fingerprint,
      mentions: [],
    },
    entities: [],
    quotes: [],
    eventTriggers: triggers,
    syntaxTokens: tokens,
  };
}

function events(items: Array<{ id: string; token: SyntaxTokenEvidence }>, fingerprint = inputFingerprint): EventProviderResult {
  const predictions = items.map(({ id, token: source }) => ({
    eventId: id,
    sectionKey: "fixture-section",
    startOffset: source.startOffset,
    endOffset: source.endOffset,
    participants: [],
    decisionReason: "fixture_event_candidate",
  }));
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: fingerprint,
    events: predictions,
    outputFingerprint: eventPredictionFingerprint({
      provider,
      normalizedInputFingerprint: fingerprint,
      events: predictions,
    }),
  };
}

test("timeline orders event candidates by source position regardless of provider array order", () => {
  const text = "Yesterday Alice arrived. Then Bob left.";
  const yesterday = token({ text, surface: "Yesterday", tokenId: 0, sentenceId: 0, head: 2, dep: "advmod" });
  const alice = token({ text, surface: "Alice", tokenId: 1, sentenceId: 0, head: 2, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 2, sentenceId: 0, head: 2, dep: "ROOT", lemma: "arrive" });
  const then = token({ text, surface: "Then", tokenId: 3, sentenceId: 1, head: 5, dep: "advmod" });
  const bob = token({ text, surface: "Bob", tokenId: 4, sentenceId: 1, head: 5, dep: "nsubj" });
  const left = token({ text, surface: "left", tokenId: 5, sentenceId: 1, head: 5, dep: "ROOT", lemma: "leave" });
  const literary = evidence([yesterday, alice, arrived, then, bob, left], [trigger(arrived), trigger(left)]);

  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: literary,
    events: events([{ id: "leave", token: left }, { id: "arrive", token: arrived }]),
  });

  assert.deepEqual(result.entries.map((entry) => entry.eventId), ["arrive", "leave"]);
  assert.deepEqual(result.entries.map((entry) => entry.narrativeSequenceIndex), [0, 1]);
  assert.ok(result.entries.every((entry) => entry.storyTimeStatus === "unresolved"));
  assert.deepEqual(result.storyTimeRelations, []);
});

test("timeline captures explicit same-sentence temporal cues without inferring scope", () => {
  const text = "Later Alice arrived.";
  const later = token({ text, surface: "Later", tokenId: 0, sentenceId: 0, head: 2, dep: "advmod", lemma: "later" });
  const alice = token({ text, surface: "Alice", tokenId: 1, sentenceId: 0, head: 2, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 2, sentenceId: 0, head: 2, dep: "ROOT", lemma: "arrive" });

  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: evidence([later, alice, arrived], [trigger(arrived)]),
    events: events([{ id: "arrive", token: arrived }]),
  });

  assert.equal(result.temporalCues.length, 1);
  assert.equal(result.temporalCues[0]?.lemma, "later");
  assert.equal(result.temporalCues[0]?.family, "relative_sequence");
  assert.equal(result.temporalCues[0]?.associationPolicy, "same_sentence_unscoped");
  assert.deepEqual(result.entries[0]?.temporalCueEvidenceIds, [result.temporalCues[0]?.cueEvidenceId]);
  assert.equal(result.entries[0]?.storyTimeStatus, "unresolved");
});

test("timeline never leaks temporal cues across sentence boundaries", () => {
  const text = "Yesterday Alice arrived. Bob left.";
  const yesterday = token({ text, surface: "Yesterday", tokenId: 0, sentenceId: 0, head: 2, dep: "advmod" });
  const alice = token({ text, surface: "Alice", tokenId: 1, sentenceId: 0, head: 2, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 2, sentenceId: 0, head: 2, dep: "ROOT", lemma: "arrive" });
  const bobStart = text.indexOf("Bob");
  const bob = token({ text, surface: "Bob", tokenId: 3, sentenceId: 1, head: 4, dep: "nsubj", fromCodeUnit: bobStart });
  const left = token({ text, surface: "left", tokenId: 4, sentenceId: 1, head: 4, dep: "ROOT", lemma: "leave", fromCodeUnit: bobStart });

  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: evidence([yesterday, alice, arrived, bob, left], [trigger(arrived), trigger(left)]),
    events: events([{ id: "arrive", token: arrived }, { id: "leave", token: left }]),
  });

  assert.equal(result.entries[0]?.temporalCueEvidenceIds.length, 1);
  assert.equal(result.entries[1]?.temporalCueEvidenceIds.length, 0);
});

test("multiple events in one sentence may share unscoped cue evidence without creating story-time edges", () => {
  const text = "Then Alice arrived and Bob left.";
  const then = token({ text, surface: "Then", tokenId: 0, sentenceId: 0, head: 2, dep: "advmod" });
  const alice = token({ text, surface: "Alice", tokenId: 1, sentenceId: 0, head: 2, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 2, sentenceId: 0, head: 2, dep: "ROOT", lemma: "arrive" });
  const bob = token({ text, surface: "Bob", tokenId: 3, sentenceId: 0, head: 4, dep: "nsubj" });
  const left = token({ text, surface: "left", tokenId: 4, sentenceId: 0, head: 2, dep: "conj", lemma: "leave" });

  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: evidence([then, alice, arrived, bob, left], [trigger(arrived), trigger(left)]),
    events: events([{ id: "arrive", token: arrived }, { id: "leave", token: left }]),
  });

  assert.equal(result.temporalCues.length, 1);
  assert.equal(result.entries.length, 2);
  assert.equal(result.entries[0]?.temporalCueEvidenceIds.length, 1);
  assert.equal(result.entries[1]?.temporalCueEvidenceIds.length, 1);
  assert.deepEqual(result.storyTimeRelations, []);
});

test("timeline ignores temporal-looking words outside the pinned cue lexicon", () => {
  const text = "Someday Alice arrived.";
  const someday = token({ text, surface: "Someday", tokenId: 0, sentenceId: 0, head: 2, dep: "advmod", lemma: "someday" });
  const alice = token({ text, surface: "Alice", tokenId: 1, sentenceId: 0, head: 2, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 2, sentenceId: 0, head: 2, dep: "ROOT", lemma: "arrive" });
  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: evidence([someday, alice, arrived], [trigger(arrived)]),
    events: events([{ id: "arrive", token: arrived }]),
  });
  assert.equal(result.temporalCues.length, 0);
  assert.equal(result.entries[0]?.temporalCueEvidenceIds.length, 0);
});

test("timeline fails closed on missing syntax, input drift, and missing trigger binding", () => {
  const text = "Alice arrived.";
  const alice = token({ text, surface: "Alice", tokenId: 0, sentenceId: 0, head: 1, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 1, sentenceId: 0, head: 1, dep: "ROOT", lemma: "arrive" });
  const literary = evidence([alice, arrived], [trigger(arrived)]);
  const predicted = events([{ id: "arrive", token: arrived }]);
  const { syntaxTokens: _syntaxTokens, ...withoutSyntax } = literary;

  assert.throws(
    () => deriveNarrativeTimelineEvidence({ literaryEvidence: withoutSyntax, events: predicted }),
    /timeline_syntax_evidence_missing/,
  );
  assert.throws(
    () => deriveNarrativeTimelineEvidence({ literaryEvidence: evidence([alice, arrived], [trigger(arrived)], "c".repeat(64)), events: predicted }),
    /timeline_event_evidence_fingerprint_mismatch/,
  );
  assert.throws(
    () => deriveNarrativeTimelineEvidence({ literaryEvidence: evidence([alice, arrived], []), events: predicted }),
    /timeline_event_trigger_binding_count/,
  );
});

test("timeline fails closed on malformed dependency heads and semantic result tampering", () => {
  const text = "Alice arrived.";
  const alice = token({ text, surface: "Alice", tokenId: 0, sentenceId: 0, head: 1, dep: "nsubj" });
  const arrived = token({ text, surface: "arrived", tokenId: 1, sentenceId: 0, head: 1, dep: "ROOT", lemma: "arrive" });
  const malformedAlice = { ...alice, syntacticHeadTokenId: 99 };
  assert.throws(
    () => deriveNarrativeTimelineEvidence({
      literaryEvidence: evidence([malformedAlice, arrived], [trigger(arrived)]),
      events: events([{ id: "arrive", token: arrived }]),
    }),
    /timeline_missing_syntax_head/,
  );

  const result = deriveNarrativeTimelineEvidence({
    literaryEvidence: evidence([alice, arrived], [trigger(arrived)]),
    events: events([{ id: "arrive", token: arrived }]),
  });
  const tampered = {
    ...result,
    entries: result.entries.map((entry) => ({ ...entry, storyTimeStatus: "resolved" as "unresolved" })),
  };
  assert.throws(() => validateNarrativeTimelineEvidence(tampered), /timeline_invalid_event_status/);
});
