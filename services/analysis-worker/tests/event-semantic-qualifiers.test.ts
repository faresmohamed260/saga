import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveEventSemanticQualifiers,
  validateEventSemanticQualifierResult,
} from "../src/evaluation/event-semantic-qualifiers.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const structuralLocator = "chapter-1:fixture:chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, fromCodeUnit = 0) {
  const codeUnitStart = text.indexOf(surface, fromCodeUnit);
  if (codeUnitStart < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, codeUnitStart)),
    endOffset: cpLength(text.slice(0, codeUnitStart + surface.length)),
  };
}

function syntaxToken(input: {
  text: string;
  surface: string;
  tokenId: number;
  head: number;
  dependency: string;
  lemma?: string;
  sentenceId?: number;
  fromCodeUnit?: number;
  locator?: string | null;
}): SyntaxTokenEvidence {
  const located = locate(input.text, input.surface, input.fromCodeUnit ?? 0);
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    ...located,
    structuralLocator: input.locator === undefined ? structuralLocator : input.locator,
    paragraphId: 0,
    sentenceId: input.sentenceId ?? 0,
    tokenIdWithinSentence: input.tokenId,
    tokenId: input.tokenId,
    posTag: input.dependency === "ROOT" ? "VERB" : "X",
    finePosTag: input.dependency === "ROOT" ? "VBD" : "X",
    dependencyRelation: input.dependency,
    syntacticHeadTokenId: input.head,
  };
}

function trigger(token: SyntaxTokenEvidence, locator = token.structuralLocator): EventTriggerEvidence {
  return {
    evidenceId: `event:${token.tokenId}`,
    surfaceText: token.surfaceText,
    lemma: token.lemma,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    structuralLocator: locator,
    sentenceId: token.sentenceId,
    tokenId: token.tokenId,
    dependencyRelation: token.dependencyRelation,
    syntacticHeadTokenId: token.syntacticHeadTokenId,
  };
}

function evidence(
  eventTriggers: EventTriggerEvidence[],
  syntaxTokens: SyntaxTokenEvidence[] | undefined,
  inputFingerprint = fingerprint,
): LocalLiteraryEvidenceBundle {
  const provider = { name: "booknlp-small", model: "small", revision: "fixture" };
  return {
    provider,
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: {
      provider,
      normalizedInputFingerprint: inputFingerprint,
      mentions: [],
    },
    entities: [],
    quotes: [],
    eventTriggers,
    ...(syntaxTokens === undefined ? {} : { syntaxTokens }),
  };
}

function derive(eventTriggers: EventTriggerEvidence[], syntaxTokens: SyntaxTokenEvidence[]) {
  return deriveEventSemanticQualifiers({
    normalizedInputFingerprint: fingerprint,
    literaryEvidence: evidence(eventTriggers, syntaxTokens),
  });
}

test("event qualifiers record direct dependency negation without asserting positive realis", () => {
  const text = "Alice did not leave.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 3, dependency: "nsubj" });
  const did = syntaxToken({ text, surface: "did", tokenId: 1, head: 3, dependency: "aux", lemma: "do" });
  const not = syntaxToken({ text, surface: "not", tokenId: 2, head: 3, dependency: "neg" });
  const leave = syntaxToken({ text, surface: "leave", tokenId: 3, head: 3, dependency: "ROOT" });

  const result = derive([trigger(leave)], [alice, did, not, leave]);
  assert.equal(result.events[0]!.polarity, "negated");
  assert.equal(result.events[0]!.modality, "undetermined");
  assert.equal(result.events[0]!.realis, "undetermined");
  assert.deepEqual(result.events[0]!.cues.map((cue) => cue.kind), ["negation"]);
  validateEventSemanticQualifierResult(result);
});

test("event qualifiers record modal auxiliary as modality and an irrealis cue", () => {
  const text = "Alice might leave.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 2, dependency: "nsubj" });
  const might = syntaxToken({ text, surface: "might", tokenId: 1, head: 2, dependency: "aux" });
  const leave = syntaxToken({ text, surface: "leave", tokenId: 2, head: 2, dependency: "ROOT" });

  const result = derive([trigger(leave)], [alice, might, leave]);
  assert.equal(result.events[0]!.polarity, "undetermined");
  assert.equal(result.events[0]!.modality, "modalized");
  assert.equal(result.events[0]!.realis, "irrealis_cued");
  assert.deepEqual(result.events[0]!.cues.map((cue) => [cue.kind, cue.lemma]), [["modal_auxiliary", "might"]]);
});

test("event qualifiers find negation attached to a direct modal auxiliary", () => {
  const text = "Alice could not leave.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 3, dependency: "nsubj" });
  const could = syntaxToken({ text, surface: "could", tokenId: 1, head: 3, dependency: "aux" });
  const not = syntaxToken({ text, surface: "not", tokenId: 2, head: 1, dependency: "neg" });
  const leave = syntaxToken({ text, surface: "leave", tokenId: 3, head: 3, dependency: "ROOT" });

  const result = derive([trigger(leave)], [alice, could, not, leave]);
  assert.equal(result.events[0]!.polarity, "negated");
  assert.equal(result.events[0]!.modality, "modalized");
  assert.equal(result.events[0]!.realis, "irrealis_cued");
  assert.deepEqual(result.events[0]!.cues.map((cue) => cue.kind), ["modal_auxiliary", "negation"]);
});

test("event qualifiers treat explicit if/unless markers as irrealis cues", () => {
  const text = "If Alice left.";
  const ifToken = syntaxToken({ text, surface: "If", tokenId: 0, head: 2, dependency: "mark", lemma: "if" });
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 1, head: 2, dependency: "nsubj" });
  const left = syntaxToken({ text, surface: "left", tokenId: 2, head: 2, dependency: "ROOT", lemma: "leave" });

  const result = derive([trigger(left)], [ifToken, alice, left]);
  assert.equal(result.events[0]!.realis, "irrealis_cued");
  assert.equal(result.events[0]!.modality, "undetermined");
  assert.deepEqual(result.events[0]!.cues.map((cue) => [cue.kind, cue.lemma]), [["conditional_marker", "if"]]);
});

test("combined qualifier cues are deterministic, source anchored and stably fingerprinted", () => {
  const text = "If Alice could not leave.";
  const ifToken = syntaxToken({ text, surface: "If", tokenId: 0, head: 4, dependency: "mark", lemma: "if" });
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 1, head: 4, dependency: "nsubj" });
  const could = syntaxToken({ text, surface: "could", tokenId: 2, head: 4, dependency: "aux" });
  const not = syntaxToken({ text, surface: "not", tokenId: 3, head: 2, dependency: "neg" });
  const leave = syntaxToken({ text, surface: "leave", tokenId: 4, head: 4, dependency: "ROOT" });
  const input = [ifToken, alice, could, not, leave];

  const first = derive([trigger(leave)], input);
  const second = derive([trigger(leave)], [...input].reverse());
  assert.equal(first.outputFingerprint, second.outputFingerprint);
  assert.equal(first.events[0]!.polarity, "negated");
  assert.equal(first.events[0]!.modality, "modalized");
  assert.equal(first.events[0]!.realis, "irrealis_cued");
  assert.deepEqual(first.events[0]!.cues.map((cue) => cue.kind), [
    "conditional_marker",
    "modal_auxiliary",
    "negation",
  ]);
  assert.ok(first.events[0]!.cues.every((cue) => cue.structuralLocator === structuralLocator));
});

test("qualifier cues do not leak from another event in the same sentence and unmarked events remain undetermined", () => {
  const text = "Alice might sing before Bob left.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 2, dependency: "nsubj" });
  const might = syntaxToken({ text, surface: "might", tokenId: 1, head: 2, dependency: "aux" });
  const sing = syntaxToken({ text, surface: "sing", tokenId: 2, head: 2, dependency: "ROOT" });
  const before = syntaxToken({ text, surface: "before", tokenId: 3, head: 5, dependency: "mark" });
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 4, head: 5, dependency: "nsubj" });
  const left = syntaxToken({ text, surface: "left", tokenId: 5, head: 2, dependency: "advcl", lemma: "leave" });

  const result = derive([trigger(left)], [alice, might, sing, before, bob, left]);
  assert.deepEqual(result.events[0]!.cues, []);
  assert.equal(result.events[0]!.polarity, "undetermined");
  assert.equal(result.events[0]!.modality, "undetermined");
  assert.equal(result.events[0]!.realis, "undetermined");
});

test("event qualifier derivation fails closed on missing syntax, fingerprint drift, malformed heads and locator mismatch", () => {
  const text = "Alice left.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 1, dependency: "nsubj" });
  const left = syntaxToken({ text, surface: "left", tokenId: 1, head: 1, dependency: "ROOT", lemma: "leave" });

  assert.throws(
    () => deriveEventSemanticQualifiers({
      normalizedInputFingerprint: fingerprint,
      literaryEvidence: evidence([trigger(left)], undefined),
    }),
    /event_qualifier_syntax_evidence_missing/u,
  );

  assert.throws(
    () => deriveEventSemanticQualifiers({
      normalizedInputFingerprint: fingerprint,
      literaryEvidence: evidence([trigger(left)], [alice, left], "b".repeat(64)),
    }),
    /event_qualifier_provider_input_fingerprint_mismatch/u,
  );

  const brokenHead = { ...alice, syntacticHeadTokenId: 99 };
  assert.throws(
    () => derive([trigger(left)], [brokenHead, left]),
    /event_qualifier_missing_syntax_head/u,
  );

  const crossSentence = { ...alice, sentenceId: 1 };
  assert.throws(
    () => derive([trigger(left)], [crossSentence, left]),
    /event_qualifier_cross_sentence_syntax_head/u,
  );

  assert.throws(
    () => derive([trigger(left, "other:locator")], [alice, left]),
    /event_qualifier_trigger_syntax_mismatch/u,
  );
});

test("event qualifier validation detects semantic fingerprint tampering", () => {
  const text = "Alice might leave.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 2, dependency: "nsubj" });
  const might = syntaxToken({ text, surface: "might", tokenId: 1, head: 2, dependency: "aux" });
  const leave = syntaxToken({ text, surface: "leave", tokenId: 2, head: 2, dependency: "ROOT" });
  const result = derive([trigger(leave)], [alice, might, leave]);

  const tampered = structuredClone(result);
  tampered.events[0]!.modality = "undetermined";
  assert.throws(
    () => validateEventSemanticQualifierResult(tampered),
    /event_qualifier_output_fingerprint_mismatch/u,
  );
});
