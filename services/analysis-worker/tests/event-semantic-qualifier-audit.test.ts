import assert from "node:assert/strict";
import test from "node:test";

import {
  auditEventSemanticQualifierCoverage,
  validateEventSemanticQualifierAuditResult,
} from "../src/evaluation/event-semantic-qualifier-audit.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
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
    posTag: input.dep === "ROOT" ? "VERB" : "X",
    finePosTag: input.dep === "ROOT" ? "VBD" : "X",
    dependencyRelation: input.dep,
    syntacticHeadTokenId: input.head,
  };
}

function trigger(value: SyntaxTokenEvidence, override: Partial<EventTriggerEvidence> = {}): EventTriggerEvidence {
  return {
    evidenceId: `event:${value.tokenId}`,
    surfaceText: value.surfaceText,
    lemma: value.lemma,
    startOffset: value.startOffset,
    endOffset: value.endOffset,
    structuralLocator: value.structuralLocator,
    sentenceId: value.sentenceId,
    tokenId: value.tokenId,
    dependencyRelation: value.dependencyRelation,
    syntacticHeadTokenId: value.syntacticHeadTokenId,
    ...override,
  };
}

function evidence(
  triggers: EventTriggerEvidence[],
  syntaxTokens: SyntaxTokenEvidence[] | undefined,
  inputFingerprint = fingerprint,
): LocalLiteraryEvidenceBundle {
  const provider = { name: "booknlp-small", model: "small", revision: "fixture" };
  return {
    provider,
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: { provider, normalizedInputFingerprint: inputFingerprint, mentions: [] },
    entities: [],
    quotes: [],
    eventTriggers: triggers,
    ...(syntaxTokens === undefined ? {} : { syntaxTokens }),
  };
}

function audit(triggers: EventTriggerEvidence[], syntaxTokens: SyntaxTokenEvidence[]) {
  return auditEventSemanticQualifierCoverage({
    normalizedInputFingerprint: fingerprint,
    literaryEvidence: evidence(triggers, syntaxTokens),
  });
}

test("audit classifies strict direct modal and conditional children as captured", () => {
  const text = "If Alice might leave.";
  const ifToken = token({ text, surface: "If", tokenId: 0, head: 3, dep: "mark", lemma: "if" });
  const alice = token({ text, surface: "Alice", tokenId: 1, head: 3, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 2, head: 3, dep: "aux" });
  const leave = token({ text, surface: "leave", tokenId: 3, head: 3, dep: "ROOT" });

  const result = audit([trigger(leave)], [ifToken, alice, might, leave]);
  assert.equal(result.candidateCueTokenCount, 2);
  assert.equal(result.cueTokenWithEventSentenceCount, 2);
  assert.equal(result.sameSentenceCueTriggerPairCount, 2);
  assert.deepEqual(result.associations.map((row) => [row.cueLemma, row.structuralCategory, row.capturedByCurrentPolicy]), [
    ["if", "captured_direct_trigger_child", true],
    ["might", "captured_direct_trigger_child", true],
  ]);
  validateEventSemanticQualifierAuditResult(result);
});

test("audit recognizes negation captured through a direct auxiliary child", () => {
  const text = "Alice could not leave.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 3, dep: "nsubj" });
  const could = token({ text, surface: "could", tokenId: 1, head: 3, dep: "aux" });
  const not = token({ text, surface: "not", tokenId: 2, head: 1, dep: "neg" });
  const leave = token({ text, surface: "leave", tokenId: 3, head: 3, dep: "ROOT" });

  const result = audit([trigger(leave)], [alice, could, not, leave]);
  const negation = result.associations.find((row) => row.cueLemma === "not")!;
  assert.equal(negation.dependencyDistance, 2);
  assert.equal(negation.structuralCategory, "captured_auxiliary_child");
  assert.equal(negation.capturedByCurrentPolicy, true);
});

test("audit separates direct lexical negatives rejected by the strict relation policy", () => {
  const text = "Alice never left.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 2, dep: "nsubj" });
  const never = token({ text, surface: "never", tokenId: 1, head: 2, dep: "advmod", lemma: "never" });
  const left = token({ text, surface: "left", tokenId: 2, head: 2, dep: "ROOT", lemma: "leave" });

  const result = audit([trigger(left)], [alice, never, left]);
  assert.equal(result.associations[0]!.structuralCategory, "direct_child_nonqualifying");
  assert.equal(result.associations[0]!.capturedByCurrentPolicy, false);
});

test("audit distinguishes deeper descendants, ancestors and siblings", () => {
  const text = "If Alice can leave and Bob might stay.";
  const ifToken = token({ text, surface: "If", tokenId: 0, head: 1, dep: "mark", lemma: "if" });
  const alice = token({ text, surface: "Alice", tokenId: 1, head: 3, dep: "nsubj" });
  const can = token({ text, surface: "can", tokenId: 2, head: 1, dep: "aux" });
  const leave = token({ text, surface: "leave", tokenId: 3, head: 3, dep: "ROOT" });
  const and = token({ text, surface: "and", tokenId: 4, head: 7, dep: "cc" });
  const bob = token({ text, surface: "Bob", tokenId: 5, head: 7, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 6, head: 3, dep: "aux" });
  const stay = token({ text, surface: "stay", tokenId: 7, head: 3, dep: "conj" });

  const result = audit([trigger(leave), trigger(stay)], [ifToken, alice, can, leave, and, bob, might, stay]);
  const ifRow = result.associations.find((row) => row.cueLemma === "if")!;
  const canRow = result.associations.find((row) => row.cueLemma === "can")!;
  const mightRow = result.associations.find((row) => row.cueLemma === "might")!;

  assert.equal(ifRow.structuralCategory, "descendant_depth_2_plus");
  assert.equal(canRow.structuralCategory, "descendant_depth_2_plus");
  assert.equal(mightRow.structuralCategory, "sibling_shared_head");
  assert.equal(result.sameSentenceCueTriggerPairCount, 6);
});

test("audit uses parent or ancestor category when the cue governs the event trigger", () => {
  const text = "Alice will leave.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const will = token({ text, surface: "will", tokenId: 1, head: 1, dep: "ROOT", lemma: "will" });
  const leave = token({ text, surface: "leave", tokenId: 2, head: 1, dep: "xcomp" });

  const result = audit([trigger(leave)], [alice, will, leave]);
  assert.equal(result.associations[0]!.structuralCategory, "parent_or_ancestor");
  assert.equal(result.associations[0]!.dependencyDistance, 1);
});

test("nearest-trigger association is deterministic under input order changes", () => {
  const text = "Alice left and Bob might stay.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const left = token({ text, surface: "left", tokenId: 1, head: 1, dep: "ROOT", lemma: "leave" });
  const and = token({ text, surface: "and", tokenId: 2, head: 5, dep: "cc" });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 5, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 4, head: 5, dep: "aux" });
  const stay = token({ text, surface: "stay", tokenId: 5, head: 1, dep: "conj" });
  const triggers = [trigger(left), trigger(stay)];
  const syntax = [alice, left, and, bob, might, stay];

  const first = audit(triggers, syntax);
  const second = audit([...triggers].reverse(), [...syntax].reverse());
  assert.equal(first.outputFingerprint, second.outputFingerprint);
  assert.equal(first.associations[0]!.triggerTokenId, 5);
  assert.equal(first.associations[0]!.capturedByCurrentPolicy, true);
});

test("audit counts cue tokens in sentences without event triggers separately", () => {
  const text = "Alice might leave. Bob stayed.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 2, dep: "nsubj", sentenceId: 0 });
  const might = token({ text, surface: "might", tokenId: 1, head: 2, dep: "aux", sentenceId: 0 });
  const leave = token({ text, surface: "leave", tokenId: 2, head: 2, dep: "ROOT", sentenceId: 0 });
  const bob = token({ text, surface: "Bob", tokenId: 3, head: 4, dep: "nsubj", sentenceId: 1, fromCodeUnit: text.indexOf("Bob") });
  const stayed = token({ text, surface: "stayed", tokenId: 4, head: 4, dep: "ROOT", sentenceId: 1, fromCodeUnit: text.indexOf("stayed") });

  const result = audit([trigger(stayed)], [alice, might, leave, bob, stayed]);
  assert.equal(result.candidateCueTokenCount, 1);
  assert.equal(result.cueTokenWithEventSentenceCount, 0);
  assert.equal(result.cueTokenWithoutEventSentenceCount, 1);
  assert.equal(result.sameSentenceCueTriggerPairCount, 0);
});

test("qualifier audit fails closed on missing syntax, fingerprint drift, malformed heads and trigger mismatch", () => {
  const text = "Alice might leave.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 2, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 1, head: 2, dep: "aux" });
  const leave = token({ text, surface: "leave", tokenId: 2, head: 2, dep: "ROOT" });

  assert.throws(
    () => auditEventSemanticQualifierCoverage({
      normalizedInputFingerprint: fingerprint,
      literaryEvidence: evidence([trigger(leave)], undefined),
    }),
    /event_qualifier_audit_syntax_evidence_missing/u,
  );
  assert.throws(
    () => auditEventSemanticQualifierCoverage({
      normalizedInputFingerprint: fingerprint,
      literaryEvidence: evidence([trigger(leave)], [alice, might, leave], "b".repeat(64)),
    }),
    /event_qualifier_audit_provider_input_fingerprint_mismatch/u,
  );
  assert.throws(
    () => audit([trigger(leave)], [{ ...alice, syntacticHeadTokenId: 99 }, might, leave]),
    /event_qualifier_audit_missing_syntax_head/u,
  );
  assert.throws(
    () => audit([trigger(leave)], [{ ...alice, sentenceId: 1 }, might, leave]),
    /event_qualifier_audit_cross_sentence_syntax_head/u,
  );
  assert.throws(
    () => audit([trigger(leave, { structuralLocator: "other:locator" })], [alice, might, leave]),
    /event_qualifier_audit_trigger_syntax_mismatch/u,
  );
});

test("qualifier audit validation detects semantic fingerprint tampering", () => {
  const text = "Alice might leave.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 2, dep: "nsubj" });
  const might = token({ text, surface: "might", tokenId: 1, head: 2, dep: "aux" });
  const leave = token({ text, surface: "leave", tokenId: 2, head: 2, dep: "ROOT" });
  const result = audit([trigger(leave)], [alice, might, leave]);

  const tampered = structuredClone(result);
  tampered.associations[0]!.capturedByCurrentPolicy = false;
  assert.throws(
    () => validateEventSemanticQualifierAuditResult(tampered),
    /event_qualifier_audit_capture_category_mismatch|event_qualifier_audit_output_fingerprint_mismatch/u,
  );
});
