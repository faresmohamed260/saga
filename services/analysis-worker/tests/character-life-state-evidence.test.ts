import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveCharacterLifeStateEvidence,
  validateCharacterLifeStateEvidence,
} from "../src/evaluation/character-life-state-evidence.js";
import { deriveEventSemanticQualifiers } from "../src/evaluation/event-semantic-qualifiers.js";
import {
  eventPredictionFingerprint,
  type EventParticipantPrediction,
  type EventProviderResult,
} from "../src/evaluation/event-evaluation.js";
import { deriveNarrativeTimelineEvidence } from "../src/evaluation/narrative-timeline-evidence.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const locator = "fixture:section";
const eventProvider = { name: "fixture-grounded-events", model: null, revision: "1" };

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, from = 0) {
  const start = text.indexOf(surface, from);
  if (start < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, start)),
    endOffset: cpLength(text.slice(0, start + surface.length)),
  };
}

function syntax(input: {
  text: string;
  surface: string;
  lemma?: string;
  tokenId: number;
  sentenceId?: number;
  head: number;
  dep: string;
  from?: number;
}) {
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
    entities: [],
    quotes: [],
    eventTriggers: triggers,
    syntaxTokens: tokens,
  };
}

function groundedEvents(input: Array<{
  eventId: string;
  trigger: SyntaxTokenEvidence;
  participants: EventParticipantPrediction[];
}>, inputFingerprint = fingerprint): EventProviderResult {
  const events = input.map((item) => ({
    eventId: item.eventId,
    sectionKey: "fixture-section",
    startOffset: item.trigger.startOffset,
    endOffset: item.trigger.endOffset,
    participants: item.participants,
    decisionReason: "fixture_grounded_event",
  }));
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider: eventProvider,
    normalizedInputFingerprint: inputFingerprint,
    events,
    outputFingerprint: eventPredictionFingerprint({ provider: eventProvider, normalizedInputFingerprint: inputFingerprint, events }),
  };
}

function compose(input: { literary: LocalLiteraryEvidenceBundle; events: EventProviderResult }) {
  const qualifiers = deriveEventSemanticQualifiers({
    normalizedInputFingerprint: input.events.normalizedInputFingerprint,
    literaryEvidence: input.literary,
  });
  const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence: input.literary, events: input.events });
  return deriveCharacterLifeStateEvidence({ literaryEvidence: input.literary, events: input.events, qualifiers, timeline });
}

function mentionParticipant(characterKey: string, role: "actor" | "patient", evidenceId: string): EventParticipantPrediction {
  return { characterKey, role, evidenceId };
}

test("die emits an unapplied life-status candidate for exactly one grounded actor", () => {
  const text = "Alice died.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const died = syntax({ text, surface: "died", lemma: "die", tokenId: 1, head: 1, dep: "ROOT" });
  const source = literary([alice, died], [trigger(died)]);
  const events = groundedEvents([{ eventId: "event-die", trigger: died, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]);

  const result = compose({ literary: source, events });

  assert.equal(result.candidates.length, 1);
  assert.equal(result.candidates[0]?.predicate, "die");
  assert.equal(result.candidates[0]?.targetRole, "actor");
  assert.equal(result.candidates[0]?.targetCharacterKey, "alice");
  assert.equal(result.candidates[0]?.candidateValue, "dead");
  assert.equal(result.candidates[0]?.storyTimeStatus, "unresolved");
  assert.equal(result.candidates[0]?.applicationStatus, "not_applied_candidate_only");
  assert.deepEqual(result.stateApplications, []);
});

test("kill targets the uniquely grounded patient rather than the actor", () => {
  const text = "Alice killed Bob.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const killed = syntax({ text, surface: "killed", lemma: "kill", tokenId: 1, head: 1, dep: "ROOT" });
  const bob = syntax({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const source = literary([alice, killed, bob], [trigger(killed)]);
  const events = groundedEvents([{
    eventId: "event-kill",
    trigger: killed,
    participants: [mentionParticipant("alice", "actor", "mention:alice"), mentionParticipant("bob", "patient", "mention:bob")],
  }]);

  const result = compose({ literary: source, events });

  assert.equal(result.candidates.length, 1);
  assert.equal(result.candidates[0]?.targetCharacterKey, "bob");
  assert.equal(result.candidates[0]?.targetMentionEvidenceId, "mention:bob");
  assert.equal(result.candidates[0]?.targetRole, "patient");
});

test("missing or multiple required target roles emit no state candidate", () => {
  const text = "Alice killed them.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const killed = syntax({ text, surface: "killed", lemma: "kill", tokenId: 1, head: 1, dep: "ROOT" });
  const them = syntax({ text, surface: "them", tokenId: 2, head: 1, dep: "dobj" });
  const source = literary([alice, killed, them], [trigger(killed)]);

  const missing = compose({
    literary: source,
    events: groundedEvents([{ eventId: "event-kill", trigger: killed, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]),
  });
  assert.equal(missing.candidates.length, 0);

  const multiple = compose({
    literary: source,
    events: groundedEvents([{
      eventId: "event-kill",
      trigger: killed,
      participants: [
        mentionParticipant("bob", "patient", "mention:bob"),
        mentionParticipant("carol", "patient", "mention:carol"),
      ],
    }]),
  });
  assert.equal(multiple.candidates.length, 0);
});

test("negation and modality remain evidence and never become state application", () => {
  const text = "Alice might not die.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 3, dep: "nsubj" });
  const might = syntax({ text, surface: "might", lemma: "might", tokenId: 1, head: 3, dep: "aux" });
  const not = syntax({ text, surface: "not", lemma: "not", tokenId: 2, head: 1, dep: "neg" });
  const die = syntax({ text, surface: "die", lemma: "die", tokenId: 3, head: 3, dep: "ROOT" });
  const source = literary([alice, might, not, die], [trigger(die)]);
  const events = groundedEvents([{ eventId: "event-die", trigger: die, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]);

  const result = compose({ literary: source, events });
  const candidate = result.candidates[0]!;

  assert.equal(candidate.polarity, "negated");
  assert.equal(candidate.modality, "modalized");
  assert.equal(candidate.realis, "irrealis_cued");
  assert.deepEqual(candidate.qualifierCueEvidenceIds.sort(), ["syntax:1", "syntax:2"]);
  assert.equal(candidate.applicationStatus, "not_applied_candidate_only");
  assert.deepEqual(result.stateApplications, []);
});

test("non-pinned event predicates cannot become life-state candidates", () => {
  const text = "Alice slept.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const slept = syntax({ text, surface: "slept", lemma: "sleep", tokenId: 1, head: 1, dep: "ROOT" });
  const source = literary([alice, slept], [trigger(slept)]);
  const events = groundedEvents([{ eventId: "event-sleep", trigger: slept, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]);

  assert.equal(compose({ literary: source, events }).candidates.length, 0);
});

test("life-state candidates preserve narrative source order under shuffled literary trigger input", () => {
  const text = "Alice died. Bob killed Carol.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, sentenceId: 0, head: 1, dep: "nsubj" });
  const died = syntax({ text, surface: "died", lemma: "die", tokenId: 1, sentenceId: 0, head: 1, dep: "ROOT" });
  const bobFrom = text.indexOf("Bob");
  const bob = syntax({ text, surface: "Bob", tokenId: 2, sentenceId: 1, head: 3, dep: "nsubj", from: bobFrom });
  const killed = syntax({ text, surface: "killed", lemma: "kill", tokenId: 3, sentenceId: 1, head: 3, dep: "ROOT", from: bobFrom });
  const carol = syntax({ text, surface: "Carol", tokenId: 4, sentenceId: 1, head: 3, dep: "dobj", from: bobFrom });
  const tokens = [alice, died, bob, killed, carol];
  const events = groundedEvents([
    { eventId: "event-kill", trigger: killed, participants: [mentionParticipant("carol", "patient", "mention:carol")] },
    { eventId: "event-die", trigger: died, participants: [mentionParticipant("alice", "actor", "mention:alice")] },
  ]);

  const first = compose({ literary: literary(tokens, [trigger(killed), trigger(died)]), events });
  const second = compose({ literary: literary(tokens, [trigger(died), trigger(killed)]), events });

  assert.deepEqual(first.candidates.map((candidate) => candidate.sourceEventId), ["event-die", "event-kill"]);
  assert.deepEqual(first.candidates, second.candidates);
});

test("life-state derivation fails closed on fingerprint and timeline binding drift", () => {
  const text = "Alice died.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const died = syntax({ text, surface: "died", lemma: "die", tokenId: 1, head: 1, dep: "ROOT" });
  const source = literary([alice, died], [trigger(died)]);
  const events = groundedEvents([{ eventId: "event-die", trigger: died, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]);
  const qualifiers = deriveEventSemanticQualifiers({ normalizedInputFingerprint: fingerprint, literaryEvidence: source });
  const timeline = deriveNarrativeTimelineEvidence({ literaryEvidence: source, events });

  assert.throws(
    () => deriveCharacterLifeStateEvidence({ literaryEvidence: literary([alice, died], [trigger(died)], "b".repeat(64)), events, qualifiers, timeline }),
    /life_state_literary_input_fingerprint_mismatch/,
  );

  const driftedTimeline = {
    ...timeline,
    eventOutputFingerprint: "c".repeat(64),
  };
  assert.throws(
    () => deriveCharacterLifeStateEvidence({ literaryEvidence: source, events, qualifiers, timeline: driftedTimeline }),
    /timeline_output_fingerprint_mismatch|life_state_timeline_event_fingerprint_mismatch/,
  );
});

test("life-state result validation rejects semantic tampering and any application", () => {
  const text = "Alice died.";
  const alice = syntax({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const died = syntax({ text, surface: "died", lemma: "die", tokenId: 1, head: 1, dep: "ROOT" });
  const result = compose({
    literary: literary([alice, died], [trigger(died)]),
    events: groundedEvents([{ eventId: "event-die", trigger: died, participants: [mentionParticipant("alice", "actor", "mention:alice")] }]),
  });

  const applied = { ...result, stateApplications: [{} as never] };
  assert.throws(() => validateCharacterLifeStateEvidence(applied), /life_state_applications_not_allowed_v1/);

  const tampered = {
    ...result,
    candidates: result.candidates.map((candidate) => ({ ...candidate, candidateValue: "alive" as "dead" })),
  };
  assert.throws(() => validateCharacterLifeStateEvidence(tampered), /invalid_life_state_value/);
});
