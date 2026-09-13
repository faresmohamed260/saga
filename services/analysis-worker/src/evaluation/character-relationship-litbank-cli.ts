import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
import {
  CHARACTER_RELATIONSHIP_PREDICATES,
  deriveCharacterRelationshipEvidence,
  type CharacterRelationshipEvidenceResult,
  type CharacterRelationshipPredicate,
} from "./character-relationship-evidence.js";
import {
  litBankDocumentSection,
  litBankGoldIdentityResult,
} from "./litbank-component-benchmark.js";
import { alignSingleSectionOracleIdentity } from "./litbank-oracle-section-alignment.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const SOURCE_RUN_ID = 34727310506;
const SOURCE_HEAD_SHA = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const SOURCE_ARTIFACT_NAME = `saga-phase3-booknlp-native-output-${SOURCE_HEAD_SHA}`;
const SOURCE_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";

const PREDICATE_SET = new Set<string>(CHARACTER_RELATIONSHIP_PREDICATES);

type CandidateShape = "active" | "passive" | "unsupported";

type RelationshipCoverageAudit = {
  candidatePredicateTokenCount: number;
  activeSupportedSyntaxCandidateCount: number;
  passiveSupportedSyntaxCandidateCount: number;
  supportedBinarySyntaxCandidateCount: number;
  unsupportedOrMixedSyntaxCandidateCount: number;
  relationshipObservationCount: number;
  activeObservationCount: number;
  passiveObservationCount: number;
  uniqueDirectedPairCount: number;
  uniqueDirectedPairPredicateCount: number;
  repeatedPairPredicateGroupCount: number;
  repeatedObservationCount: number;
  maxObservationSupportCount: number;
  qualifiedObservationCount: number;
  unqualifiedObservationCount: number;
  negatedObservationCount: number;
  modalizedObservationCount: number;
  conditionalObservationCount: number;
  qualifierCueCount: number;
  candidatePredicateCounts: Record<string, number>;
  observationPredicateCounts: Record<string, number>;
  supportCountHistogram: Record<string, number>;
};

function emptyAudit(): RelationshipCoverageAudit {
  return {
    candidatePredicateTokenCount: 0,
    activeSupportedSyntaxCandidateCount: 0,
    passiveSupportedSyntaxCandidateCount: 0,
    supportedBinarySyntaxCandidateCount: 0,
    unsupportedOrMixedSyntaxCandidateCount: 0,
    relationshipObservationCount: 0,
    activeObservationCount: 0,
    passiveObservationCount: 0,
    uniqueDirectedPairCount: 0,
    uniqueDirectedPairPredicateCount: 0,
    repeatedPairPredicateGroupCount: 0,
    repeatedObservationCount: 0,
    maxObservationSupportCount: 0,
    qualifiedObservationCount: 0,
    unqualifiedObservationCount: 0,
    negatedObservationCount: 0,
    modalizedObservationCount: 0,
    conditionalObservationCount: 0,
    qualifierCueCount: 0,
    candidatePredicateCounts: {},
    observationPredicateCounts: {},
    supportCountHistogram: {},
  };
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function addAudit(target: RelationshipCoverageAudit, source: RelationshipCoverageAudit) {
  target.candidatePredicateTokenCount += source.candidatePredicateTokenCount;
  target.activeSupportedSyntaxCandidateCount += source.activeSupportedSyntaxCandidateCount;
  target.passiveSupportedSyntaxCandidateCount += source.passiveSupportedSyntaxCandidateCount;
  target.supportedBinarySyntaxCandidateCount += source.supportedBinarySyntaxCandidateCount;
  target.unsupportedOrMixedSyntaxCandidateCount += source.unsupportedOrMixedSyntaxCandidateCount;
  target.relationshipObservationCount += source.relationshipObservationCount;
  target.activeObservationCount += source.activeObservationCount;
  target.passiveObservationCount += source.passiveObservationCount;
  target.uniqueDirectedPairCount += source.uniqueDirectedPairCount;
  target.uniqueDirectedPairPredicateCount += source.uniqueDirectedPairPredicateCount;
  target.repeatedPairPredicateGroupCount += source.repeatedPairPredicateGroupCount;
  target.repeatedObservationCount += source.repeatedObservationCount;
  target.maxObservationSupportCount = Math.max(target.maxObservationSupportCount, source.maxObservationSupportCount);
  target.qualifiedObservationCount += source.qualifiedObservationCount;
  target.unqualifiedObservationCount += source.unqualifiedObservationCount;
  target.negatedObservationCount += source.negatedObservationCount;
  target.modalizedObservationCount += source.modalizedObservationCount;
  target.conditionalObservationCount += source.conditionalObservationCount;
  target.qualifierCueCount += source.qualifierCueCount;
  for (const [predicate, count] of Object.entries(source.candidatePredicateCounts)) {
    increment(target.candidatePredicateCounts, predicate, count);
  }
  for (const [predicate, count] of Object.entries(source.observationPredicateCounts)) {
    increment(target.observationPredicateCounts, predicate, count);
  }
  for (const [supportCount, groupCount] of Object.entries(source.supportCountHistogram)) {
    increment(target.supportCountHistogram, supportCount, groupCount);
  }
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let booknlpRoot: string | null = null;
  let out: string | null = null;
  let limit: number | null = null;
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--booknlp-root") booknlpRoot = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else throw new Error(`unknown argument: ${token}`);
  }
  if (!litbankRoot || !booknlpRoot || !out) {
    throw new Error("usage: character-relationship-litbank-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
  }
  return { litbankRoot: resolve(litbankRoot), booknlpRoot: resolve(booknlpRoot), out: resolve(out), limit };
}

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/gu, "\n");
}

async function readBookNlpDocument(root: string, documentId: string) {
  const documentRoot = join(root, documentId);
  const [tokensTsv, entitiesTsv, quotesTsv] = await Promise.all([
    readFile(join(documentRoot, `${documentId}.tokens`), "utf8"),
    readFile(join(documentRoot, `${documentId}.entities`), "utf8"),
    readFile(join(documentRoot, `${documentId}.quotes`), "utf8"),
  ]);
  return { tokensTsv, entitiesTsv, quotesTsv };
}

function syntaxChildren(tokens: SyntaxTokenEvidence[]) {
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const group = children.get(token.syntacticHeadTokenId) ?? [];
    group.push(token);
    children.set(token.syntacticHeadTokenId, group);
  }
  for (const group of children.values()) group.sort((left, right) => left.tokenId - right.tokenId);
  return children;
}

function directChildren(
  children: Map<number, SyntaxTokenEvidence[]>,
  tokenId: number,
  relation: string,
) {
  return (children.get(tokenId) ?? []).filter((token) => token.dependencyRelation === relation);
}

function candidateShape(
  predicate: SyntaxTokenEvidence,
  children: Map<number, SyntaxTokenEvidence[]>,
): CandidateShape {
  const activeSubjects = directChildren(children, predicate.tokenId, "nsubj");
  const activeObjects = directChildren(children, predicate.tokenId, "dobj");
  const passiveSubjects = directChildren(children, predicate.tokenId, "nsubjpass");
  const agents = directChildren(children, predicate.tokenId, "agent");
  const agentObjects = agents.length === 1 ? directChildren(children, agents[0]!.tokenId, "pobj") : [];

  const activeShape = activeSubjects.length > 0 || activeObjects.length > 0;
  const passiveShape = passiveSubjects.length > 0 || agents.length > 0 || agentObjects.length > 0;
  if (!passiveShape && activeSubjects.length === 1 && activeObjects.length === 1) return "active";
  if (!activeShape && passiveSubjects.length === 1 && agents.length === 1 && agentObjects.length === 1) return "passive";
  return "unsupported";
}

function auditDocument(
  evidence: LocalLiteraryEvidenceBundle,
  relationships: CharacterRelationshipEvidenceResult,
): RelationshipCoverageAudit {
  if (!evidence.syntaxTokens) throw new Error("relationship_diagnostic_missing_syntax");
  const audit = emptyAudit();
  const children = syntaxChildren(evidence.syntaxTokens);

  for (const token of evidence.syntaxTokens) {
    const lemma = normalizeLemma(token.lemma);
    if (!PREDICATE_SET.has(lemma)) continue;
    audit.candidatePredicateTokenCount += 1;
    increment(audit.candidatePredicateCounts, lemma);
    const shape = candidateShape(token, children);
    if (shape === "active") audit.activeSupportedSyntaxCandidateCount += 1;
    else if (shape === "passive") audit.passiveSupportedSyntaxCandidateCount += 1;
    else audit.unsupportedOrMixedSyntaxCandidateCount += 1;
  }
  audit.supportedBinarySyntaxCandidateCount =
    audit.activeSupportedSyntaxCandidateCount + audit.passiveSupportedSyntaxCandidateCount;

  audit.relationshipObservationCount = relationships.observations.length;
  const directedPairs = new Set<string>();
  for (const observation of relationships.observations) {
    if (observation.voice === "active") audit.activeObservationCount += 1;
    else audit.passiveObservationCount += 1;
    increment(audit.observationPredicateCounts, observation.predicate);
    directedPairs.add(`${observation.subjectCharacterKey}\u0000${observation.objectCharacterKey}`);
    const qualified = observation.qualifierCues.length > 0;
    if (qualified) audit.qualifiedObservationCount += 1;
    else audit.unqualifiedObservationCount += 1;
    if (observation.polarity === "negated") audit.negatedObservationCount += 1;
    if (observation.modality === "modalized") audit.modalizedObservationCount += 1;
    if (observation.conditionality === "conditional_cued") audit.conditionalObservationCount += 1;
    audit.qualifierCueCount += observation.qualifierCues.length;
  }
  audit.uniqueDirectedPairCount = directedPairs.size;
  audit.uniqueDirectedPairPredicateCount = relationships.sourceOrderLedger.length;

  for (const entry of relationships.sourceOrderLedger) {
    increment(audit.supportCountHistogram, String(entry.observationCount));
    audit.maxObservationSupportCount = Math.max(audit.maxObservationSupportCount, entry.observationCount);
    if (entry.observationCount > 1) {
      audit.repeatedPairPredicateGroupCount += 1;
      audit.repeatedObservationCount += entry.observationCount;
    }
  }
  return audit;
}

function assertDocumentAccounting(audit: RelationshipCoverageAudit) {
  if (
    audit.candidatePredicateTokenCount
    !== audit.supportedBinarySyntaxCandidateCount + audit.unsupportedOrMixedSyntaxCandidateCount
  ) throw new Error("relationship_diagnostic_candidate_accounting_mismatch");
  if (audit.relationshipObservationCount > audit.supportedBinarySyntaxCandidateCount) {
    throw new Error("relationship_diagnostic_observation_exceeds_supported_candidates");
  }
  if (audit.uniqueDirectedPairPredicateCount > audit.relationshipObservationCount) {
    throw new Error("relationship_diagnostic_ledger_exceeds_observations");
  }
  if (audit.qualifiedObservationCount + audit.unqualifiedObservationCount !== audit.relationshipObservationCount) {
    throw new Error("relationship_diagnostic_qualifier_accounting_mismatch");
  }
  if (audit.activeObservationCount + audit.passiveObservationCount !== audit.relationshipObservationCount) {
    throw new Error("relationship_diagnostic_voice_accounting_mismatch");
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const annotationNames = (await readdir(corefDir))
    .filter((name) => name.endsWith(".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (annotationNames.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const completed: Array<{
    documentId: string;
    relationshipOutputFingerprint: string;
    candidatePredicateTokenCount: number;
    supportedBinarySyntaxCandidateCount: number;
    relationshipObservationCount: number;
    uniqueDirectedPairPredicateCount: number;
    qualifiedObservationCount: number;
    audit: RelationshipCoverageAudit;
  }> = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const annotationName of annotationNames) {
    const documentId = basename(annotationName, ".ann");
    try {
      const [textRaw, corefAnnotation, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(corefDir, annotationName), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      const normalizedInputFingerprint = sha256Hex(text);
      const section = litBankDocumentSection(documentId, text);
      const literaryEvidence = normalizeBookNlpOutput({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [section],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const gold = convertLitBankTsvDocument({ documentId, text, annotation: corefAnnotation }).gold;
      const identity = alignSingleSectionOracleIdentity({
        identity: litBankGoldIdentityResult(gold),
        section,
      });
      const relationships = deriveCharacterRelationshipEvidence({
        normalizedInputFingerprint,
        identity,
        literaryEvidence,
      });
      const audit = auditDocument(literaryEvidence, relationships);
      assertDocumentAccounting(audit);
      completed.push({
        documentId,
        relationshipOutputFingerprint: relationships.outputFingerprint,
        candidatePredicateTokenCount: audit.candidatePredicateTokenCount,
        supportedBinarySyntaxCandidateCount: audit.supportedBinarySyntaxCandidateCount,
        relationshipObservationCount: audit.relationshipObservationCount,
        uniqueDirectedPairPredicateCount: audit.uniqueDirectedPairPredicateCount,
        qualifiedObservationCount: audit.qualifiedObservationCount,
        audit,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const audit = emptyAudit();
  for (const row of completed) addAudit(audit, row.audit);
  assertDocumentAccounting(audit);

  const semantic = {
    schemaVersion: "saga-character-relationship-litbank-diagnostic-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      attemptedDocumentCount: annotationNames.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    sourceEvidence: {
      sourceRunId: SOURCE_RUN_ID,
      sourceHeadSha: SOURCE_HEAD_SHA,
      nativeArtifactName: SOURCE_ARTIFACT_NAME,
      nativeArtifactSha256: SOURCE_ARTIFACT_SHA256,
      inferenceReused: true,
    },
    policy: {
      predicates: [...CHARACTER_RELATIONSHIP_PREDICATES] as CharacterRelationshipPredicate[],
      activeShape: "exactly one direct nsubj + exactly one direct dobj; no passive role shape",
      passiveShape: "exactly one direct nsubjpass + exactly one direct agent with exactly one pobj; no active role shape",
      identityGrounding: "benchmark-only aligned LitBank oracle identity through exact structural locator",
      selfRelationsObserved: false,
      reciprocalInference: false,
      conjunctionInheritance: false,
      cooccurrenceRelationshipInference: false,
      eventCoparticipationRelationshipInference: false,
      persistenceClaimed: false,
      storyTimeInferred: false,
    },
    scope: {
      newModelInference: false,
      correctnessScored: false,
      relationshipAccuracyClaimed: false,
      productionAdoptionClaimed: false,
      rawSourceTextEmitted: false,
      sourceOrderLedgerOnly: true,
    },
    audit: {
      ...audit,
      supportedBinarySyntaxRate: ratio(audit.supportedBinarySyntaxCandidateCount, audit.candidatePredicateTokenCount),
      twoCharacterGroundingYield: ratio(audit.relationshipObservationCount, audit.supportedBinarySyntaxCandidateCount),
      observationRatePerPredicateHit: ratio(audit.relationshipObservationCount, audit.candidatePredicateTokenCount),
      repeatedPairPredicateGroupRate: ratio(audit.repeatedPairPredicateGroupCount, audit.uniqueDirectedPairPredicateCount),
      qualifiedObservationRate: ratio(audit.qualifiedObservationCount, audit.relationshipObservationCount),
      negatedObservationRate: ratio(audit.negatedObservationCount, audit.relationshipObservationCount),
      modalizedObservationRate: ratio(audit.modalizedObservationCount, audit.relationshipObservationCount),
      conditionalObservationRate: ratio(audit.conditionalObservationCount, audit.relationshipObservationCount),
    },
    caveat: "LitBank provides character/coreference gold used here only as benchmark oracle identity; it does not provide S.A.G.A.-style interpersonal relationship/state gold. Counts are structural coverage diagnostics, not relationship precision, recall, accuracy, persistence, or narrative-time truth.",
    failures,
    perDocument: completed.map((row) => ({
      documentId: row.documentId,
      relationshipOutputFingerprint: row.relationshipOutputFingerprint,
      candidatePredicateTokenCount: row.candidatePredicateTokenCount,
      supportedBinarySyntaxCandidateCount: row.supportedBinarySyntaxCandidateCount,
      relationshipObservationCount: row.relationshipObservationCount,
      uniqueDirectedPairPredicateCount: row.uniqueDirectedPairPredicateCount,
      qualifiedObservationCount: row.qualifiedObservationCount,
    })),
  };
  const output = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };
  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    sourceEvidence: output.sourceEvidence,
    policy: output.policy,
    scope: output.scope,
    audit: output.audit,
    caveat: output.caveat,
    failures: output.failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
