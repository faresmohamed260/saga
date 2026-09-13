import assert from "node:assert/strict";
import test from "node:test";

import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../src/local-analysis/types.js";
import {
  deriveCharacterRelationshipEvidence,
  validateCharacterRelationshipEvidenceResult,
} from "../src/evaluation/character-relationship-evidence.js";

const fingerprint = "a".repeat(64);
const identityFingerprint = "b".repeat(64);
const locator = "chapter-1:fixture:chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, fromCodeUnit = 0) {
  const start = text.indexOf(surface, fromCodeUnit);
  if (start < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, start)),
    endOffset: cpLength(text.slice(0, start + surface.length)),
  };
}

function token(input: {
  text: string;
  surface: string;
  tokenId: number;
  head: number;
  dep: string;
  lemma?: string;
  sentenceId?: number;
  fromCodeUnit?: number;
  posTag?: string;
}): SyntaxTokenEvidence {
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    ...locate(input.text, input.surface, input.fromCodeUnit ?? 0),
    structuralLocator: locator,
    paragraphId: 0,
    sentenceId: input.sentenceId ?? 0,
    tokenIdWithinSentence: input.tokenId,
    tokenId: input.tokenId,
    posTag: input.posTag ?? (input.dep === "ROOT" ? "VERB" : "X"),
    finePosTag: "X",
    dependencyRelation: input.dep,
    syntacticHeadTokenId: input.head,
  };
}

function mention(input: {
  evidenceId: string;
  characterKey: string | null;
  token: SyntaxTokenEvidence;
  state?: "linked" | "unresolved" | "quarantined";
}): ResolvedIdentityMention {
  return {
    evidenceId: input.evidenceId,
    characterKey: input.characterKey,
    surfaceText: input.token.surfaceText,
    startOffset: input.token.startOffset,
    endOffset: input.token.endOffset,
    structuralLocator: input.token.structuralLocator,
    mentionKind: input.token.posTag === "PRON" ? "pronoun" : "proper_name",
    resolutionState: input.state ?? "linked",
    evidenceTier: input.state === "quarantined" ? "quarantined" : "attachment",
    decisionReason: "fixture",
  };
}

function identity(mentions: ResolvedIdentityMention[]): CharacterIdentityResult {
  const keys = [...new Set(mentions.flatMap((item) => item.characterKey ? [item.characterKey] : []))].sort();
  return {
    resolverVersion: "fixture-resolver-v1",
    resolverConfigFingerprint: "c".repeat(64),
    provider: { name: "fixture", model: null, revision: "1" },
    normalizedInputFingerprint: fingerprint,
    outputFingerprint: identityFingerprint,
    characters: keys.map((key) => ({
      characterKey: key,
      canonicalName: key,
      admissionTier: "stabilized" as const,
      evidenceCount: 1,
      aliases: [],
    })),
    mentions,
  };
}

function evidence(tokens: SyntaxTokenEvidence[], inputFingerprint = fingerprint): LocalLiteraryEvidenceBundle {
  const provider = { name: "booknlp-small", model: "small", revision: "fixture" };
  return {
    provider,
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: { provider, normalizedInputFingerprint: inputFingerprint, mentions: [] },
    entities: [],
    quotes: [],
    eventTriggers: [],
    syntaxTokens: tokens,
  };
}

function derive(tokens: SyntaxTokenEvidence[], mentions: ResolvedIdentityMention[]) {
  return deriveCharacterRelationshipEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: identity(mentions),
    literaryEvidence: evidence(tokens),
  });
}

test("explicit active relationship predicate grounds one directed observation", () => {
  const text = "Alice loves Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });

  const result = derive([alice, loves, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  assert.equal(result.observations.length, 1);
  assert.deepEqual(result.observations[0], {
    ...result.observations[0],
    subjectCharacterKey: "alice",
    objectCharacterKey: "bob",
    predicate: "love",
    voice: "active",
    polarity: "unmarked",
    modality: "unmarked",
    conditionality: "unmarked",
  });
  assert.equal(result.sourceOrderLedger.length, 1);
  assert.equal(result.sourceOrderLedger[0]!.observationCount, 1);
  validateCharacterRelationshipEvidenceResult(result);
});

test("passive relationship predicate preserves semantic agent-to-patient direction", () => {
  const text = "Bob was betrayed by Alice.";
  const bob = token({ text, surface: "Bob", tokenId: 0, head: 2, dep: "nsubjpass" });
  const was = token({ text, surface: "was", tokenId: 1, head: 2, dep: "auxpass", lemma: "be" });
  const betrayed = token({ text, surface: "betrayed", tokenId: 2, head: 2, dep: "ROOT", lemma: "betray" });
  const by = token({ text, surface: "by", tokenId: 3, head: 2, dep: "agent" });
  const alice = token({ text, surface: "Alice", tokenId: 4, head: 3, dep: "pobj" });

  const result = derive([bob, was, betrayed, by, alice], [
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
  ]);
  assert.equal(result.observations.length, 1);
  assert.equal(result.observations[0]!.subjectCharacterKey, "alice");
  assert.equal(result.observations[0]!.objectCharacterKey, "bob");
  assert.equal(result.observations[0]!.voice, "passive");
});

test("relationship extraction never invents reciprocal observations", () => {
  const text = "Alice married Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const married = token({ text, surface: "married", tokenId: 1, head: 1, dep: "ROOT", lemma: "marry" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const result = derive([alice, married, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  assert.equal(result.observations.length, 1);
  assert.equal(result.observations.some((row) => row.subjectCharacterKey === "bob"), false);
});

test("direct negation modal and conditional cues stay attached to the observation", () => {
  const text = "If Alice might not love Bob.";
  const ifToken = token({ text, surface: "If", tokenId: 0, head: 4, dep: "mark", lemma: "if" });
  const alice = token({ text, surface: "Alice", tokenId: 1, head: 4, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 2, head: 4, dep: "aux", lemma: "might" });
  const not = token({ text, surface: "not", tokenId: 3, head: 2, dep: "neg", lemma: "not" });
  const love = token({ text, surface: "love", tokenId: 4, head: 4, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 5, head: 4, dep: "dobj" });

  const result = derive([ifToken, alice, might, not, love, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  const observation = result.observations[0]!;
  assert.equal(observation.polarity, "negated");
  assert.equal(observation.modality, "modalized");
  assert.equal(observation.conditionality, "conditional_cued");
  assert.deepEqual(observation.qualifierCues.map((cue) => cue.kind).sort(), [
    "conditional_marker",
    "modal_auxiliary",
    "negation",
  ]);
});

test("self relations and unresolved or ambiguous identity arguments remain unobserved", () => {
  const text = "Alice loves herself.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const herself = token({ text, surface: "herself", tokenId: 2, head: 1, dep: "dobj", posTag: "PRON" });
  assert.equal(derive([alice, loves, herself], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "self", characterKey: "alice", token: herself }),
  ]).observations.length, 0);

  assert.equal(derive([alice, loves, herself], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "self", characterKey: null, token: herself, state: "unresolved" }),
  ]).observations.length, 0);

  const bobMention = mention({ evidenceId: "bob", characterKey: "bob", token: herself });
  const carolMention = mention({ evidenceId: "carol", characterKey: "carol", token: herself });
  assert.equal(derive([alice, loves, herself], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    bobMention,
    carolMention,
  ]).observations.length, 0);
});

test("conjunctions do not inherit relationship object roles", () => {
  const text = "Alice loves Bob and Carol.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const and = token({ text, surface: "and", tokenId: 3, head: 4, dep: "cc" });
  const carol = token({ text, surface: "Carol", tokenId: 4, head: 2, dep: "conj" });
  const result = derive([alice, loves, bob, and, carol], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
    mention({ evidenceId: "carol", characterKey: "carol", token: carol }),
  ]);
  assert.equal(result.observations.length, 1);
  assert.equal(result.observations[0]!.objectCharacterKey, "bob");
});

test("non-pinned interpersonal or interaction verbs do not become relationship evidence", () => {
  const text = "Alice greeted Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const greeted = token({ text, surface: "greeted", tokenId: 1, head: 1, dep: "ROOT", lemma: "greet" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const result = derive([alice, greeted, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  assert.equal(result.observations.length, 0);
  assert.equal(result.sourceOrderLedger.length, 0);
});

test("source-order ledger preserves repeated evidence without claiming persistence", () => {
  const text = "Alice trusted Bob. Alice trusted Bob.";
  const alice1 = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const trusted1 = token({ text, surface: "trusted", tokenId: 1, head: 1, dep: "ROOT", lemma: "trust" });
  const bob1 = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const second = text.indexOf("Alice", 1);
  const alice2 = token({ text, surface: "Alice", tokenId: 3, head: 4, dep: "nsubj", sentenceId: 1, fromCodeUnit: second });
  const trusted2 = token({ text, surface: "trusted", tokenId: 4, head: 4, dep: "ROOT", lemma: "trust", sentenceId: 1, fromCodeUnit: second });
  const bob2 = token({ text, surface: "Bob", tokenId: 5, head: 4, dep: "dobj", sentenceId: 1, fromCodeUnit: second });
  const result = derive([alice1, trusted1, bob1, alice2, trusted2, bob2], [
    mention({ evidenceId: "alice-1", characterKey: "alice", token: alice1 }),
    mention({ evidenceId: "bob-1", characterKey: "bob", token: bob1 }),
    mention({ evidenceId: "alice-2", characterKey: "alice", token: alice2 }),
    mention({ evidenceId: "bob-2", characterKey: "bob", token: bob2 }),
  ]);
  assert.equal(result.observations.length, 2);
  assert.equal(result.sourceOrderLedger.length, 1);
  assert.equal(result.sourceOrderLedger[0]!.observationCount, 2);
  assert.deepEqual(result.sourceOrderLedger[0]!.observationIds, result.observations.map((row) => row.observationId));
  assert.ok(result.sourceOrderLedger[0]!.firstSourceOffset < result.sourceOrderLedger[0]!.lastSourceOffset);
});

test("relationship result is deterministic under evidence input order changes", () => {
  const text = "Alice hates Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const hates = token({ text, surface: "hates", tokenId: 1, head: 1, dep: "ROOT", lemma: "hate" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const mentions = [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ];
  const first = derive([alice, hates, bob], mentions);
  const second = derive([bob, hates, alice], [...mentions].reverse());
  assert.equal(first.outputFingerprint, second.outputFingerprint);
});

test("relationship evidence fails closed on fingerprint and syntax drift", () => {
  const text = "Alice loves Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const mentions = [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ];

  assert.throws(() => deriveCharacterRelationshipEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: { ...identity(mentions), normalizedInputFingerprint: "d".repeat(64) },
    literaryEvidence: evidence([alice, loves, bob]),
  }), /relationship_identity_input_fingerprint_mismatch/u);

  const missingSyntax = evidence([alice, loves, bob]);
  delete missingSyntax.syntaxTokens;
  assert.throws(() => deriveCharacterRelationshipEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: identity(mentions),
    literaryEvidence: missingSyntax,
  }), /relationship_syntax_evidence_missing/u);

  assert.throws(() => derive([{ ...alice, syntacticHeadTokenId: 99 }, loves, bob], mentions), /relationship_missing_syntax_head/u);
  assert.throws(() => derive([{ ...alice, sentenceId: 1 }, loves, bob], mentions), /relationship_cross_sentence_syntax_head/u);
});

test("relationship result validation detects semantic and ledger tampering", () => {
  const text = "Alice loves Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const result = derive([alice, loves, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);

  const semanticTamper = structuredClone(result);
  semanticTamper.observations[0]!.objectCharacterKey = "carol";
  assert.throws(() => validateCharacterRelationshipEvidenceResult(semanticTamper), /relationship_ledger_group_mismatch|relationship_output_fingerprint_mismatch/u);

  const ledgerTamper = structuredClone(result);
  ledgerTamper.sourceOrderLedger[0]!.observationIds = [];
  assert.throws(() => validateCharacterRelationshipEvidenceResult(ledgerTamper), /invalid_relationship_ledger_entry/u);
});
