import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveCausalCandidateEvidence,
  validateCausalCandidateEvidence,
} from "../src/evaluation/causal-candidate-evidence.js";
import {
  eventPredictionFingerprint,
  type EventParticipantPrediction,
  type EventProviderResult,
} from "../src/evaluation/event-evaluation.js";
import { deriveNarrativeTimelineEvidence } from "../src/evaluation/narrative-timeline-evidence.js";
import type { EventTriggerEvidence, LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const locator = "fixture:section";
const eventProvider = { name: "fixture-events", model: null, revision: "1" };

function cpLength(value: string) { return Array.from(value).length; }
function locate(text: string, surface: string, from = 0) {
  const start = text.indexOf(surface, from);
  if (start < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return { startOffset: cpLength(text.slice(0, start)), endOffset: cpLength(text.slice(0, start + surface.length)) };
}
function token(input: { text: string; surface: string; lemma?: string; tokenId: number; sentenceId?: number; head: number; dep: string; from?: number }) {
  const span = locate(input.text, input.surface, input.from ?? 0);
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    startOffset: span.startOffset,
    endOffset: span.endOffset,
    structuralLocator: locator,
    paragraphId: 0,
    sentenceId: input.sentenceId ?? 0,
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
function literary(tokens: SyntaxTokenEvidence[], triggers: EventTriggerEvidence[], inputFingerprint = fingerprint): LocalLiteraryEvidenceBundle {
  const provider = { name: "fixture-literary", model: null, revision: "1" };
  return {
    provider,
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: { provider, normalizedInputFingerprint: inputFingerprint, mentions: [] },
    entities: [], quotes: [], eventTriggers: triggers, syntaxTokens: tokens,
  };
}
function events(items: Array<{ eventId: string; source: SyntaxTokenEvidence; participants?: EventParticipantPrediction[] }>, inputFingerprint = fingerprint): EventProviderResult {
  const rows = items.map((item) => ({
    eventId: item.eventId,
    sectionKey: "fixture-section",
    startOffset: item.source.startOffset,
    endOffset: item.source.endOffset,
    participants: item.participants ?? [],
    decisionReason: "fixture_event",
  }));
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider: eventProvider,
    normalizedInputFingerprint: inputFingerprint,
    events: rows,
    outputFingerprint: eventPredictionFingerprint({ provider: eventProvider, normalizedInputFingerprint: inputFingerprint, events: rows }),
  };
}
function participant(characterKey: string, role: "actor" | "patient", evidenceId = `mention:${characterKey}`): EventParticipantPrediction {
  return { characterKey, role, evidenceId };
}
function compose(source: LocalLiteraryEvidenceBundle, eventResult: EventProviderResult) {
  const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence: source, events: eventResult });
  return deriveCausalCandidateEvidence({ literaryEvidence: source, events: eventResult, timeline });
}

test("explicit causal cue is retained as unscoped evidence even with one event", () => {
  const text = "Because Alice left.";
  const because = token({ text, surface: "Because", lemma: "because", tokenId: 0, head: 2, dep: "mark" });
  const alice = token({ text, surface: "Alice", tokenId: 1, head: 2, dep: "nsubj" });
  const left = token({ text, surface: "left", lemma: "leave", tokenId: 2, head: 2, dep: "ROOT" });
  const source = literary([because, alice, left], [trigger(left)]);
  const result = compose(source, events([{ eventId: "leave", source: left }]));
  assert.equal(result.cues.length, 1);
  assert.equal(result.cues[0]?.lemma, "because");
  assert.deepEqual(result.cues[0]?.associatedEventIds, ["leave"]);
  assert.equal(result.pairCandidates.length, 0);
  assert.deepEqual(result.acceptedCausalEdges, []);
});

test("exactly two events with explicit cue create one unresolved undirected pair candidate", () => {
  const text = "Alice stumbled because Bob pushed.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const stumbled = token({ text, surface: "stumbled", lemma: "stumble", tokenId: 1, head: 1, dep: "ROOT" });
  const because = token({ text, surface: "because", tokenId: 2, head: 4, dep: "mark" });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 4, dep: "nsubj" });
  const pushed = token({ text, surface: "pushed", lemma: "push", tokenId: 4, head: 1, dep: "advcl" });
  const source = literary([alice, stumbled, because, bob, pushed], [trigger(stumbled), trigger(pushed)]);
  const result = compose(source, events([{ eventId: "push", source: pushed }, { eventId: "stumble", source: stumbled }]));
  assert.equal(result.pairCandidates.length, 1);
  const candidate = result.pairCandidates[0]!;
  assert.equal(candidate.firstEventId, "stumble");
  assert.equal(candidate.secondEventId, "push");
  assert.equal(candidate.causalRelationStatus, "unresolved");
  assert.equal(candidate.causalDirection, "unresolved");
  assert.deepEqual(result.acceptedCausalEdges, []);
});

test("three event candidates keep cue evidence but deliberately produce no pair", () => {
  const text = "Alice ran and fell because Bob shouted.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const ran = token({ text, surface: "ran", lemma: "run", tokenId: 1, head: 1, dep: "ROOT" });
  const fell = token({ text, surface: "fell", lemma: "fall", tokenId: 2, head: 1, dep: "conj" });
  const because = token({ text, surface: "because", tokenId: 3, head: 5, dep: "mark" });
  const bob = token({ text, surface: "Bob", tokenId: 4, head: 5, dep: "nsubj" });
  const shouted = token({ text, surface: "shouted", lemma: "shout", tokenId: 5, head: 1, dep: "advcl" });
  const source = literary([alice, ran, fell, because, bob, shouted], [trigger(ran), trigger(fell), trigger(shouted)]);
  const result = compose(source, events([{ eventId: "run", source: ran }, { eventId: "fall", source: fell }, { eventId: "shout", source: shouted }]));
  assert.equal(result.cues.length, 1);
  assert.equal(result.cues[0]?.associatedEventIds.length, 3);
  assert.equal(result.pairCandidates.length, 0);
});

test("excluded ambiguous terms do not become causal cues", () => {
  const text = "Alice left so Bob stayed since noon.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const left = token({ text, surface: "left", lemma: "leave", tokenId: 1, head: 1, dep: "ROOT" });
  const so = token({ text, surface: "so", tokenId: 2, head: 4, dep: "mark" });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 4, dep: "nsubj" });
  const stayed = token({ text, surface: "stayed", lemma: "stay", tokenId: 4, head: 1, dep: "conj" });
  const since = token({ text, surface: "since", tokenId: 5, head: 6, dep: "case" });
  const noon = token({ text, surface: "noon", tokenId: 6, head: 4, dep: "obl" });
  const source = literary([alice, left, so, bob, stayed, since, noon], [trigger(left), trigger(stayed)]);
  const result = compose(source, events([{ eventId: "leave", source: left }, { eventId: "stay", source: stayed }]));
  assert.equal(result.cues.length, 0);
  assert.equal(result.pairCandidates.length, 0);
});

test("shared canonical characters are features only and never accepted causal evidence", () => {
  const text = "Alice cried because Alice fell.";
  const alice1 = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const cried = token({ text, surface: "cried", lemma: "cry", tokenId: 1, head: 1, dep: "ROOT" });
  const because = token({ text, surface: "because", tokenId: 2, head: 4, dep: "mark" });
  const secondFrom = text.lastIndexOf("Alice");
  const alice2 = token({ text, surface: "Alice", tokenId: 3, head: 4, dep: "nsubj", from: secondFrom });
  const fell = token({ text, surface: "fell", lemma: "fall", tokenId: 4, head: 1, dep: "advcl" });
  const source = literary([alice1, cried, because, alice2, fell], [trigger(cried), trigger(fell)]);
  const result = compose(source, events([
    { eventId: "cry", source: cried, participants: [participant("alice", "actor", "mention:a1")] },
    { eventId: "fall", source: fell, participants: [participant("alice", "actor", "mention:a2")] },
  ]));
  assert.deepEqual(result.pairCandidates[0]?.sharedCharacterKeys, ["alice"]);
  assert.equal(result.pairCandidates[0]?.causalDirection, "unresolved");
  assert.deepEqual(result.acceptedCausalEdges, []);
});

test("causal result is deterministic under event and trigger evidence order changes", () => {
  const text = "Alice stumbled because Bob pushed.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const stumbled = token({ text, surface: "stumbled", lemma: "stumble", tokenId: 1, head: 1, dep: "ROOT" });
  const because = token({ text, surface: "because", tokenId: 2, head: 4, dep: "mark" });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 4, dep: "nsubj" });
  const pushed = token({ text, surface: "pushed", lemma: "push", tokenId: 4, head: 1, dep: "advcl" });
  const eventResult = events([{ eventId: "push", source: pushed }, { eventId: "stumble", source: stumbled }]);
  const first = compose(literary([alice, stumbled, because, bob, pushed], [trigger(pushed), trigger(stumbled)]), eventResult);
  const second = compose(literary([alice, stumbled, because, bob, pushed], [trigger(stumbled), trigger(pushed)]), eventResult);
  assert.deepEqual(first.cues, second.cues);
  assert.deepEqual(first.pairCandidates, second.pairCandidates);
  assert.equal(first.outputFingerprint, second.outputFingerprint);
});

test("causal derivation fails closed on missing syntax and fingerprint drift", () => {
  const text = "Because Alice left.";
  const because = token({ text, surface: "Because", lemma: "because", tokenId: 0, head: 2, dep: "mark" });
  const alice = token({ text, surface: "Alice", tokenId: 1, head: 2, dep: "nsubj" });
  const left = token({ text, surface: "left", lemma: "leave", tokenId: 2, head: 2, dep: "ROOT" });
  const source = literary([because, alice, left], [trigger(left)]);
  const eventResult = events([{ eventId: "leave", source: left }]);
  const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence: source, events: eventResult });
  assert.throws(
    () => deriveCausalCandidateEvidence({ literaryEvidence: { ...source, syntaxTokens: undefined }, events: eventResult, timeline }),
    /causal_syntax_evidence_missing/,
  );
  assert.throws(
    () => deriveCausalCandidateEvidence({ literaryEvidence: literary([because, alice, left], [trigger(left)], "b".repeat(64)), events: eventResult, timeline }),
    /causal_literary_input_fingerprint_mismatch/,
  );
});

test("causal validation rejects accepted edges and resolved direction tampering", () => {
  const text = "Alice stumbled because Bob pushed.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const stumbled = token({ text, surface: "stumbled", lemma: "stumble", tokenId: 1, head: 1, dep: "ROOT" });
  const because = token({ text, surface: "because", tokenId: 2, head: 4, dep: "mark" });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 4, dep: "nsubj" });
  const pushed = token({ text, surface: "pushed", lemma: "push", tokenId: 4, head: 1, dep: "advcl" });
  const result = compose(literary([alice, stumbled, because, bob, pushed], [trigger(stumbled), trigger(pushed)]), events([{ eventId: "stumble", source: stumbled }, { eventId: "push", source: pushed }]));
  assert.throws(() => validateCausalCandidateEvidence({ ...result, acceptedCausalEdges: [{} as never] }), /accepted_causal_edges_not_allowed_v1/);
  const resolved = {
    ...result,
    pairCandidates: result.pairCandidates.map((candidate) => ({ ...candidate, causalDirection: "forward" as "unresolved" })),
  };
  assert.throws(() => validateCausalCandidateEvidence(resolved), /causal_candidate_relation_resolved/);
});
