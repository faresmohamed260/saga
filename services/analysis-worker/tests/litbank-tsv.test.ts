import assert from "node:assert/strict";
import test from "node:test";

import { evaluateIdentityBenchmarkCase } from "../src/evaluation/identity-benchmark.js";
import { convertLitBankTsvDocument } from "../src/evaluation/litbank-tsv.js";
import { resolveCharacterIdentity } from "../src/identity/resolver.js";

// Derived from dbamman/litbank @ 3e50db0ffc033d7ccbb94f4d88f6b99210328ed8,
// coref/tsv/113_the_secret_garden_brat.{txt,ann}; LitBank is CC BY 4.0.
const text =
  "CHAPTER I THERE IS NO ONE LEFT When Mary Lennox was sent to Misselthwaite Manor to live with her uncle everybody said she was the most disagreeable-looking child ever seen .";

const annotation = [
  "MENTION\tT3\t0\t8\t0\t9\tMary Lennox\tPER\tPROP",
  "MENTION\tT2\t0\t13\t0\t14\tMisselthwaite Manor\tFAC\tPROP",
  "MENTION\tT83\t0\t18\t0\t19\ther uncle\tPER\tNOM",
  "MENTION\tT161\t0\t18\t0\t18\ther\tPER\tPRON",
  "MENTION\tT84\t0\t20\t0\t20\teverybody\tPER\tNOM",
  "MENTION\tT162\t0\t22\t0\t22\tshe\tPER\tPRON",
  "COREF\tT3\tMARY_LENNOX-0",
  "COREF\tT2\tMisselthwaite_Manor-1",
  "COREF\tT83\ther_uncle-2",
  "COREF\tT161\tMARY_LENNOX-0",
  "COREF\tT84\teverybody-3",
  "COREF\tT162\tMARY_LENNOX-0",
].join("\n");

test("LitBank TSV conversion preserves literary mention typing, clusters, and source spans", () => {
  const converted = convertLitBankTsvDocument({
    documentId: "113_the_secret_garden_brat",
    text,
    annotation,
  });

  assert.equal(converted.gold.mentions.length, 6);
  const mary = converted.gold.mentions.find((mention) => mention.mentionId.endsWith(":T3"))!;
  assert.equal(mary.surfaceText, "Mary Lennox");
  assert.equal(mary.entityType, "person");
  assert.equal(mary.mentionKind, "proper_name");
  assert.equal(mary.goldCharacterId, "MARY_LENNOX-0");

  const manor = converted.evidence.mentions.find((mention) => mention.evidenceId.endsWith(":T2"))!;
  assert.equal(manor.entityType, "non_person");
  assert.equal(manor.mentionKind, "proper_name");

  const nestedPronoun = converted.evidence.mentions.find((mention) => mention.evidenceId.endsWith(":T161"))!;
  assert.equal(nestedPronoun.surfaceText, "her");
  assert.equal(nestedPronoun.providerClusterId, "MARY_LENNOX-0");
});

test("LitBank oracle evidence isolates resolver policy from provider/model recall", () => {
  const converted = convertLitBankTsvDocument({
    documentId: "113_the_secret_garden_brat",
    text,
    annotation,
  });
  const result = resolveCharacterIdentity({
    normalizedText: converted.gold.text,
    evidence: converted.evidence,
  });
  const report = evaluateIdentityBenchmarkCase({
    gold: converted.gold,
    evidence: converted.evidence,
    result,
  });

  assert.deepEqual(result.characters.map((character) => character.canonicalName), ["Mary Lennox"]);
  assert.equal(report.counts.goldSeedEligibleCharacterCount, 1);
  assert.equal(report.counts.falseCanonicalCount, 0);
  assert.equal(report.counts.incorrectMergeCount, 0);
  assert.equal(report.metrics.canonicalPrecision, 1);
  assert.equal(report.metrics.canonicalRecall, 1);
  assert.equal(report.metrics.linkedMentionPrecision, 1);
  assert.equal(report.metrics.linkedMentionRecall, 1);
  assert.equal(report.metrics.nonPersonQuarantineRate, 1);
});
