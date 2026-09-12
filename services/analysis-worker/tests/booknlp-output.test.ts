import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { resolveCharacterIdentity } from "../src/identity/resolver.js";
import { codePointLength, codePointSlice, normalizeBookNlpOutput } from "../src/local-analysis/booknlp-output.js";

const text = "Élodie smiled. 😀 Alice said, “Hello, Bob.” Bob waved.";

const tokensTsv = [
  "paragraph_ID\tsentence_ID\ttoken_ID_within_sentence\ttoken_ID_within_document\tword\tlemma\tbyte_onset\tbyte_offset\tPOS_tag\tfine_POS_tag\tdependency_relation\tsyntactic_head_ID\tevent",
  "0\t0\t0\t0\tÉlodie\tÉlodie\t0\t6\tPROPN\tNNP\tnsubj\t1\tO",
  "0\t0\t1\t1\tsmiled\tsmile\t7\t13\tVERB\tVBD\tROOT\t1\tEVENT",
  "0\t0\t2\t2\t.\t.\t13\t14\tPUNCT\t.\tpunct\t1\tO",
  "0\t1\t0\t3\t😀\t😀\t15\t16\tSYM\tSYM\tdep\t5\tO",
  "0\t1\t1\t4\tAlice\tAlice\t17\t22\tPROPN\tNNP\tnsubj\t5\tO",
  "0\t1\t2\t5\tsaid\tsay\t23\t27\tVERB\tVBD\tROOT\t5\tEVENT",
  "0\t1\t3\t6\t,\t,\t27\t28\tPUNCT\t,\tpunct\t5\tO",
  "0\t1\t4\t7\t“\t“\t29\t30\tPUNCT\t``\tpunct\t5\tO",
  "0\t1\t5\t8\tHello\thello\t30\t35\tINTJ\tUH\tintj\t10\tO",
  "0\t1\t6\t9\t,\t,\t35\t36\tPUNCT\t,\tpunct\t10\tO",
  "0\t1\t7\t10\tBob\tBob\t37\t40\tPROPN\tNNP\tvocative\t8\tO",
  "0\t1\t8\t11\t.\t.\t40\t41\tPUNCT\t.\tpunct\t8\tO",
  "0\t1\t9\t12\t”\t”\t41\t42\tPUNCT\t''\tpunct\t5\tO",
  "0\t2\t0\t13\tBob\tBob\t43\t46\tPROPN\tNNP\tnsubj\t14\tO",
  "0\t2\t1\t14\twaved\twave\t47\t52\tVERB\tVBD\tROOT\t14\tEVENT",
  "0\t2\t2\t15\t.\t.\t52\t53\tPUNCT\t.\tpunct\t14\tO",
].join("\n");

const entitiesTsv = [
  "COREF\tstart_token\tend_token\tprop\tcat\ttext",
  "1\t0\t0\tPROP\tPER\tÉlodie",
  "2\t4\t4\tPROP\tPER\tAlice",
  "3\t10\t10\tPROP\tPER\tBob",
  "3\t13\t13\tPROP\tPER\tBob",
].join("\n");

const quotesTsv = [
  "quote_start\tquote_end\tmention_start\tmention_end\tmention_phrase\tchar_id\tquote",
  "7\t12\t4\t4\tAlice\t2\t“ Hello , Bob . ”",
].join("\n");

const sections = [
  {
    stable_key: "document:0",
    ordinal: 0,
    section_kind: "document" as const,
    title: null,
    source_locator: "fixture:unicode-booknlp",
    start_offset: 0,
    end_offset: codePointLength(text),
    normalized_text: text,
  },
];

const provider = {
  name: "booknlp_small",
  model: "booknlp-small",
  revision: "booknlp:1.0.7|fixture:v1",
};

test("code-point helpers preserve non-ASCII and astral characters", () => {
  assert.equal(codePointLength(text), 53);
  assert.equal(codePointSlice(text, 15, 16), "😀");
  assert.equal(codePointSlice(text, 17, 22), "Alice");
});

test("BookNLP output becomes source-anchored identity, quote, and event evidence", () => {
  const fingerprint = sha256Hex(text);
  const evidence = normalizeBookNlpOutput({
    normalizedInputFingerprint: fingerprint,
    normalizedText: text,
    sections,
    provider,
    tokensTsv,
    entitiesTsv,
    quotesTsv,
  });

  assert.equal(evidence.identityEvidence.mentions.length, 4);
  assert.equal(evidence.entities.length, 4);
  assert.equal(evidence.quotes.length, 1);
  assert.equal(evidence.eventTriggers.length, 3);

  const alice = evidence.identityEvidence.mentions.find((mention) => mention.surfaceText === "Alice");
  assert.ok(alice);
  assert.deepEqual(
    {
      startOffset: alice.startOffset,
      endOffset: alice.endOffset,
      mentionKind: alice.mentionKind,
      entityType: alice.entityType,
      personEvidence: alice.personEvidence,
      providerClusterId: alice.providerClusterId,
      boundaryQuality: alice.boundaryQuality,
    },
    {
      startOffset: 17,
      endOffset: 22,
      mentionKind: "proper_name",
      entityType: "person",
      personEvidence: "strong",
      providerClusterId: "booknlp:2",
      boundaryQuality: "clean",
    },
  );

  assert.deepEqual(
    {
      quoteText: evidence.quotes[0]!.quoteText,
      startOffset: evidence.quotes[0]!.startOffset,
      endOffset: evidence.quotes[0]!.endOffset,
      speakerSurfaceText: evidence.quotes[0]!.speakerSurfaceText,
      speakerProviderClusterId: evidence.quotes[0]!.speakerProviderClusterId,
    },
    {
      quoteText: "“Hello, Bob.”",
      startOffset: 29,
      endOffset: 42,
      speakerSurfaceText: "Alice",
      speakerProviderClusterId: "booknlp:2",
    },
  );

  assert.deepEqual(
    evidence.eventTriggers.map((event) => [event.surfaceText, event.lemma, event.startOffset, event.endOffset]),
    [
      ["smiled", "smile", 7, 13],
      ["said", "say", 23, 27],
      ["waved", "wave", 47, 52],
    ],
  );

  const result = resolveCharacterIdentity({ normalizedText: text, evidence: evidence.identityEvidence });
  assert.deepEqual(result.characters.map((character) => character.canonicalName).sort(), ["Alice", "Bob", "Élodie"]);
  assert.equal(result.mentions.filter((mention) => mention.characterKey !== null).length, 4);
});

test("BookNLP output fails closed on source/offset drift", () => {
  const badTokens = tokensTsv.replace("17\t22\tPROPN", "18\t23\tPROPN");
  const fingerprint = sha256Hex(text);

  assert.throws(
    () => normalizeBookNlpOutput({
      normalizedInputFingerprint: fingerprint,
      normalizedText: text,
      sections,
      provider,
      tokensTsv: badTokens,
      entitiesTsv,
      quotesTsv,
    }),
    /booknlp|span|source|identity/u,
  );
});
