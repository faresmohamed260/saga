import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import type { LocalLiteraryAnalysisInput, LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";
import { validateLocalLiteraryEvidenceBundle } from "../src/local-analysis/validation.js";

const text = "Alice waved.";
const fingerprint = sha256Hex(text);
const provider = { name: "fixture", model: null, revision: "v1" };
const source: LocalLiteraryAnalysisInput = {
  normalizedInputFingerprint: fingerprint,
  normalizedText: text,
  sections: [{
    stable_key: "document:fixture",
    ordinal: 0,
    section_kind: "document",
    title: null,
    source_locator: "fixture",
    start_offset: 0,
    end_offset: 12,
    normalized_text: text,
  }],
};

function bundle(): LocalLiteraryEvidenceBundle {
  return {
    provider,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: {
      provider,
      normalizedInputFingerprint: fingerprint,
      mentions: [],
    },
    entities: [],
    quotes: [],
    eventTriggers: [{
      evidenceId: "event:1",
      surfaceText: "waved",
      lemma: "wave",
      startOffset: 6,
      endOffset: 11,
      structuralLocator: "document:fixture:fixture",
      sentenceId: 0,
      tokenId: 1,
      dependencyRelation: "ROOT",
      syntacticHeadTokenId: 1,
    }],
    syntaxTokens: [
      {
        evidenceId: "syntax:0",
        surfaceText: "Alice",
        lemma: "Alice",
        startOffset: 0,
        endOffset: 5,
        structuralLocator: "document:fixture:fixture",
        paragraphId: 0,
        sentenceId: 0,
        tokenIdWithinSentence: 0,
        tokenId: 0,
        posTag: "PROPN",
        finePosTag: "NNP",
        dependencyRelation: "nsubj",
        syntacticHeadTokenId: 1,
      },
      {
        evidenceId: "syntax:1",
        surfaceText: "waved",
        lemma: "wave",
        startOffset: 6,
        endOffset: 11,
        structuralLocator: "document:fixture:fixture",
        paragraphId: 0,
        sentenceId: 0,
        tokenIdWithinSentence: 1,
        tokenId: 1,
        posTag: "VERB",
        finePosTag: "VBD",
        dependencyRelation: "ROOT",
        syntacticHeadTokenId: 1,
      },
      {
        evidenceId: "syntax:2",
        surfaceText: ".",
        lemma: ".",
        startOffset: 11,
        endOffset: 12,
        structuralLocator: "document:fixture:fixture",
        paragraphId: 0,
        sentenceId: 0,
        tokenIdWithinSentence: 2,
        tokenId: 2,
        posTag: "PUNCT",
        finePosTag: ".",
        dependencyRelation: "punct",
        syntacticHeadTokenId: 1,
      },
    ],
  };
}

test("syntax evidence validates a source-anchored dependency graph and event-token consistency", () => {
  const validated = validateLocalLiteraryEvidenceBundle({ evidence: bundle(), source, expectedProvider: provider });
  assert.equal(validated.syntaxTokens?.length, 3);
  assert.equal(validated.syntaxTokens?.[0]!.dependencyRelation, "nsubj");
  assert.equal(validated.eventTriggers[0]!.tokenId, 1);
});

test("syntax evidence remains optional for providers without a dependency layer", () => {
  const evidence = bundle();
  delete evidence.syntaxTokens;
  const validated = validateLocalLiteraryEvidenceBundle({ evidence, source, expectedProvider: provider });
  assert.equal(validated.syntaxTokens, undefined);
});

test("syntax validation rejects missing and cross-sentence dependency heads", () => {
  const missingHead = bundle();
  missingHead.syntaxTokens![0]!.syntacticHeadTokenId = 99;
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence: missingHead, source, expectedProvider: provider }),
    /local_syntax_token_missing_head/u,
  );

  const crossSentence = bundle();
  crossSentence.syntaxTokens![0]!.sentenceId = 1;
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence: crossSentence, source, expectedProvider: provider }),
    /local_syntax_token_cross_sentence_head/u,
  );
});

test("syntax validation rejects duplicate token coordinates", () => {
  const duplicateDocumentToken = bundle();
  duplicateDocumentToken.syntaxTokens![2]!.tokenId = 1;
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence: duplicateDocumentToken, source, expectedProvider: provider }),
    /duplicate_local_syntax_token_id/u,
  );

  const duplicateSentenceToken = bundle();
  duplicateSentenceToken.syntaxTokens![2]!.tokenIdWithinSentence = 1;
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence: duplicateSentenceToken, source, expectedProvider: provider }),
    /duplicate_local_syntax_sentence_token_id/u,
  );
});

test("event triggers must agree with the corresponding syntax token when syntax is present", () => {
  const evidence = bundle();
  evidence.eventTriggers[0]!.lemma = "move";
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence, source, expectedProvider: provider }),
    /local_event_syntax_token_mismatch/u,
  );
});
