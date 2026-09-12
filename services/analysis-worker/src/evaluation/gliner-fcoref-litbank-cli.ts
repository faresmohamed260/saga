import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { resolveCharacterIdentity } from "../identity/resolver.js";
import type {
  IdentityEvidenceMention,
  IdentityMentionKind,
  NormalizedIdentityEvidence,
} from "../identity/types.js";
import {
  aggregateIdentityBenchmarkReports,
  evaluateIdentityBenchmarkCase,
} from "./identity-benchmark.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";
import type { GoldIdentityMention, IdentityBenchmarkReport } from "./types.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const GLINER_CODE_COMMIT = "cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0";
const GLINER_MODEL_REVISION = "f23104c107e3c57f5c7aa36d53a9667c67b4b866";
const FCOREF_CODE_COMMIT = "8888e51d97d4818a25dd5f5d8b541d397fad9362";
const FCOREF_MODEL_REVISION = "d5a382c8bfe1105cee1a73007525ee08ab693d9a";
const GLINER_THRESHOLD = 0.5;
const GLINER_CHUNK_CHARS = 1400;
const GLINER_CHUNK_OVERLAP = 180;
const FCOREF_MAX_TOKENS_IN_BATCH = 3500;

const FCOREF_ORACLE_PROVIDER = {
  name: "fcoref-oracle-mentions",
  model: "biu-nlp/f-coref",
  revision: `fastcoref:${FCOREF_CODE_COMMIT}|model:${FCOREF_MODEL_REVISION}`,
} as const;

const GLINER_FCOREF_PROVIDER = {
  name: "gliner-small-v2.1+fcoref",
  model: "urchade/gliner_small-v2.1+biu-nlp/f-coref",
  revision: [
    `gliner:${GLINER_CODE_COMMIT}`,
    `gliner-model:${GLINER_MODEL_REVISION}`,
    `gliner-threshold:${GLINER_THRESHOLD}`,
    `gliner-chunk:${GLINER_CHUNK_CHARS}/${GLINER_CHUNK_OVERLAP}`,
    `fastcoref:${FCOREF_CODE_COMMIT}`,
    `fcoref-model:${FCOREF_MODEL_REVISION}`,
    `fcoref-batch:${FCOREF_MAX_TOKENS_IN_BATCH}`,
  ].join("|"),
} as const;

type RawEntity = {
  start: number;
  end: number;
  text: string;
  label: string;
  score: number;
};

type RawCorefMention = {
  start: number;
  end: number;
  text: string;
};

type RawProviderDocument = {
  schemaVersion: "saga-gliner-fcoref-raw-v1";
  documentId: string;
  textSha256: string;
  glinerEntities: RawEntity[];
  fcorefClusters: RawCorefMention[][];
};

type SpanCounts = {
  documentCount: number;
  goldPersonMentionCount: number;
  goldPersonProperNameCount: number;
  predictedPersonMentionCount: number;
  predictedPersonProperNameCount: number;
  correctPersonMentionCount: number;
  representedGoldPersonMentionCount: number;
  correctPersonProperNameCount: number;
  representedGoldPersonProperNameCount: number;
  goldTypedMentionCount: number;
  predictedTypedMentionCount: number;
  correctTypedMentionCount: number;
  representedGoldTypedMentionCount: number;
};

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let rawRoot: string | null = null;
  let outDir: string | null = null;
  let limit: number | null = null;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--raw-root") rawRoot = argv[++index] ?? null;
    else if (token === "--out-dir") outDir = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else throw new Error(`unknown argument: ${token}`);
  }

  if (!litbankRoot || !rawRoot || !outDir) {
    throw new Error(
      "usage: gliner-fcoref-litbank-cli --litbank-root <root> --raw-root <raw> --out-dir <dir> [--limit N]",
    );
  }
  return {
    litbankRoot: resolve(litbankRoot),
    rawRoot: resolve(rawRoot),
    outDir: resolve(outDir),
    limit,
  };
}

function spanKey(start: number, end: number) {
  return `${start}:${end}`;
}

function codePointSlice(text: string, start: number, end: number) {
  return Array.from(text).slice(start, end).join("");
}

function normalizeRawDocument(raw: RawProviderDocument, documentId: string, text: string) {
  if (raw.schemaVersion !== "saga-gliner-fcoref-raw-v1") throw new Error("unsupported_gliner_fcoref_raw");
  if (raw.documentId !== documentId) throw new Error(`provider_document_id_mismatch:${documentId}`);
  if (raw.textSha256 !== sha256Hex(text)) throw new Error(`provider_text_fingerprint_mismatch:${documentId}`);

  const entities = raw.glinerEntities.map((entity, index) => {
    if (
      !Number.isSafeInteger(entity.start) ||
      !Number.isSafeInteger(entity.end) ||
      entity.start < 0 ||
      entity.end <= entity.start ||
      entity.end > Array.from(text).length ||
      !Number.isFinite(entity.score)
    ) {
      throw new Error(`invalid_gliner_entity:${documentId}:${index}`);
    }
    const observed = codePointSlice(text, entity.start, entity.end);
    if (observed !== entity.text) throw new Error(`gliner_surface_mismatch:${documentId}:${index}`);
    return { ...entity, label: entity.label.trim().toLowerCase() };
  });

  const clusters = raw.fcorefClusters.map((cluster, clusterIndex) =>
    cluster.map((mention, mentionIndex) => {
      if (
        !Number.isSafeInteger(mention.start) ||
        !Number.isSafeInteger(mention.end) ||
        mention.start < 0 ||
        mention.end <= mention.start ||
        mention.end > Array.from(text).length
      ) {
        throw new Error(`invalid_fcoref_mention:${documentId}:${clusterIndex}:${mentionIndex}`);
      }
      const observed = codePointSlice(text, mention.start, mention.end);
      if (observed !== mention.text) {
        throw new Error(`fcoref_surface_mismatch:${documentId}:${clusterIndex}:${mentionIndex}`);
      }
      return mention;
    }),
  );

  return { entities, clusters };
}

const pronouns = new Set([
  "he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them", "their", "theirs",
  "themselves", "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves", "you", "your",
  "yours", "yourself", "yourselves",
]);

const leadingDeterminers = new Set([
  "a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their", "its",
]);

function lexicalMentionKind(surface: string): IdentityMentionKind {
  const normalized = surface.trim().toLocaleLowerCase("en-US");
  if (pronouns.has(normalized)) return "pronoun";
  const words = surface.match(/\p{L}[\p{L}\p{M}'’.-]*/gu) ?? [];
  if (words.length === 0) return "nominal";
  if (leadingDeterminers.has(words[0]!.toLocaleLowerCase("en-US"))) return "nominal";
  const allCapitalized = words.every((word) => {
    const firstLetter = [...word].find((character) => /\p{L}/u.test(character));
    return Boolean(
      firstLetter &&
      firstLetter === firstLetter.toLocaleUpperCase("en-US") &&
      firstLetter !== firstLetter.toLocaleLowerCase("en-US"),
    );
  });
  return allCapitalized ? "proper_name" : "nominal";
}

function compatibleSpan(a: { start: number; end: number }, b: { start: number; end: number }) {
  return (
    (a.start <= b.start && a.end >= b.end) ||
    (b.start <= a.start && b.end >= a.end)
  );
}

function clusterIdsForSpan(
  span: { start: number; end: number },
  clusters: RawCorefMention[][],
) {
  const exact: string[] = [];
  const compatible: string[] = [];
  for (let clusterIndex = 0; clusterIndex < clusters.length; clusterIndex += 1) {
    const clusterId = `fcoref:${clusterIndex}`;
    for (const mention of clusters[clusterIndex] ?? []) {
      if (mention.start === span.start && mention.end === span.end) exact.push(clusterId);
      else if (compatibleSpan(span, mention)) compatible.push(clusterId);
    }
  }
  const uniqueExact = [...new Set(exact)];
  if (uniqueExact.length === 1) return uniqueExact;
  if (uniqueExact.length > 1) return [];
  const uniqueCompatible = [...new Set(compatible)];
  return uniqueCompatible.length === 1 ? uniqueCompatible : [];
}

function buildFcorefOracleEvidence(
  documentId: string,
  oracle: NormalizedIdentityEvidence,
  clusters: RawCorefMention[][],
): NormalizedIdentityEvidence {
  return {
    provider: FCOREF_ORACLE_PROVIDER,
    normalizedInputFingerprint: oracle.normalizedInputFingerprint,
    mentions: oracle.mentions.map((mention) => ({
      ...mention,
      evidenceId: `${documentId}:fcoref-oracle:${mention.startOffset}:${mention.endOffset}:${mention.mentionKind}`,
      providerClusterId: clusterIdsForSpan(
        { start: mention.startOffset, end: mention.endOffset },
        clusters,
      )[0] ?? null,
    })),
  };
}

function buildCombinedEvidence(input: {
  documentId: string;
  text: string;
  normalizedInputFingerprint: string;
  entities: RawEntity[];
  clusters: RawCorefMention[][];
}): NormalizedIdentityEvidence {
  const { documentId, text, normalizedInputFingerprint, entities, clusters } = input;
  const evidence = new Map<string, IdentityEvidenceMention>();
  const personEntities = entities.filter((entity) => entity.label === "person");
  const anchoredClusters = new Set<string>();

  for (const entity of personEntities) {
    for (const clusterId of clusterIdsForSpan(entity, clusters)) anchoredClusters.add(clusterId);
  }

  for (const entity of entities) {
    const entityType = entity.label === "person" ? "person" : "non_person";
    const kind = lexicalMentionKind(entity.text);
    const key = spanKey(entity.start, entity.end);
    evidence.set(key, {
      evidenceId: `${documentId}:gliner:${entity.start}:${entity.end}:${entity.label}`,
      surfaceText: entity.text,
      startOffset: entity.start,
      endOffset: entity.end,
      structuralLocator: `litbank:${documentId}`,
      mentionKind: kind,
      entityType,
      personEvidence: entityType === "person" ? (kind === "proper_name" ? "strong" : "supporting") : "none",
      boundaryQuality: "clean",
      providerClusterId: clusterIdsForSpan(entity, clusters)[0] ?? null,
    });
  }

  for (let clusterIndex = 0; clusterIndex < clusters.length; clusterIndex += 1) {
    const clusterId = `fcoref:${clusterIndex}`;
    if (!anchoredClusters.has(clusterId)) continue;
    for (const mention of clusters[clusterIndex] ?? []) {
      const key = spanKey(mention.start, mention.end);
      if (evidence.has(key)) continue;
      const kind = lexicalMentionKind(mention.text);
      evidence.set(key, {
        evidenceId: `${documentId}:fcoref-attachment:${clusterIndex}:${mention.start}:${mention.end}`,
        surfaceText: codePointSlice(text, mention.start, mention.end),
        startOffset: mention.start,
        endOffset: mention.end,
        structuralLocator: `litbank:${documentId}`,
        mentionKind: kind,
        entityType: "person",
        // F-Coref can attach to a GLiNER-anchored person cluster but cannot mint canon on its own.
        personEvidence: "supporting",
        boundaryQuality: "clean",
        providerClusterId: clusterId,
      });
    }
  }

  return {
    provider: GLINER_FCOREF_PROVIDER,
    normalizedInputFingerprint,
    mentions: [...evidence.values()].sort(
      (a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.evidenceId.localeCompare(b.evidenceId),
    ),
  };
}

function goldBySpan(mentions: GoldIdentityMention[]) {
  const index = new Map<string, GoldIdentityMention[]>();
  for (const mention of mentions) {
    const key = spanKey(mention.startOffset, mention.endOffset);
    const rows = index.get(key) ?? [];
    rows.push(mention);
    index.set(key, rows);
  }
  return index;
}

function evaluateGlinerSpans(entities: RawEntity[], goldMentions: GoldIdentityMention[]) {
  const index = goldBySpan(goldMentions);
  const goldPerson = goldMentions.filter((mention) => mention.entityType === "person");
  const goldProper = goldPerson.filter((mention) => mention.mentionKind === "proper_name");
  const predictedPerson = entities.filter((entity) => entity.label === "person");
  const predictedProper = predictedPerson.filter((entity) => lexicalMentionKind(entity.text) === "proper_name");
  const correctPerson = predictedPerson.filter((entity) =>
    (index.get(spanKey(entity.start, entity.end)) ?? []).some((mention) => mention.entityType === "person"),
  );
  const correctProper = predictedProper.filter((entity) =>
    (index.get(spanKey(entity.start, entity.end)) ?? []).some(
      (mention) => mention.entityType === "person" && mention.mentionKind === "proper_name",
    ),
  );
  const representedPerson = new Set(correctPerson.map((entity) => spanKey(entity.start, entity.end)));
  const representedProper = new Set(correctProper.map((entity) => spanKey(entity.start, entity.end)));
  const correctTyped = entities.filter((entity) => {
    const predictedType = entity.label === "person" ? "person" : "non_person";
    return (index.get(spanKey(entity.start, entity.end)) ?? []).some((mention) => mention.entityType === predictedType);
  });
  const representedTyped = new Set(correctTyped.map((entity) => spanKey(entity.start, entity.end)));

  const counts: SpanCounts = {
    documentCount: 1,
    goldPersonMentionCount: goldPerson.length,
    goldPersonProperNameCount: goldProper.length,
    predictedPersonMentionCount: predictedPerson.length,
    predictedPersonProperNameCount: predictedProper.length,
    correctPersonMentionCount: correctPerson.length,
    representedGoldPersonMentionCount: representedPerson.size,
    correctPersonProperNameCount: correctProper.length,
    representedGoldPersonProperNameCount: representedProper.size,
    goldTypedMentionCount: goldMentions.length,
    predictedTypedMentionCount: entities.length,
    correctTypedMentionCount: correctTyped.length,
    representedGoldTypedMentionCount: representedTyped.size,
  };
  return {
    counts,
    metrics: {
      personSpanPrecision: ratio(counts.correctPersonMentionCount, counts.predictedPersonMentionCount),
      personSpanRecall: ratio(counts.representedGoldPersonMentionCount, counts.goldPersonMentionCount),
      properPersonSpanPrecision: ratio(counts.correctPersonProperNameCount, counts.predictedPersonProperNameCount),
      properPersonSpanRecall: ratio(counts.representedGoldPersonProperNameCount, counts.goldPersonProperNameCount),
      typedSpanPrecision: ratio(counts.correctTypedMentionCount, counts.predictedTypedMentionCount),
      typedSpanRecall: ratio(counts.representedGoldTypedMentionCount, counts.goldTypedMentionCount),
    },
  };
}

function aggregateSpanReports(reports: ReturnType<typeof evaluateGlinerSpans>[]) {
  const counts: SpanCounts = {
    documentCount: 0,
    goldPersonMentionCount: 0,
    goldPersonProperNameCount: 0,
    predictedPersonMentionCount: 0,
    predictedPersonProperNameCount: 0,
    correctPersonMentionCount: 0,
    representedGoldPersonMentionCount: 0,
    correctPersonProperNameCount: 0,
    representedGoldPersonProperNameCount: 0,
    goldTypedMentionCount: 0,
    predictedTypedMentionCount: 0,
    correctTypedMentionCount: 0,
    representedGoldTypedMentionCount: 0,
  };
  for (const report of reports) {
    for (const key of Object.keys(counts) as Array<keyof SpanCounts>) counts[key] += report.counts[key];
  }
  return {
    counts,
    metrics: {
      personSpanPrecision: ratio(counts.correctPersonMentionCount, counts.predictedPersonMentionCount),
      personSpanRecall: ratio(counts.representedGoldPersonMentionCount, counts.goldPersonMentionCount),
      properPersonSpanPrecision: ratio(counts.correctPersonProperNameCount, counts.predictedPersonProperNameCount),
      properPersonSpanRecall: ratio(counts.representedGoldPersonProperNameCount, counts.goldPersonProperNameCount),
      typedSpanPrecision: ratio(counts.correctTypedMentionCount, counts.predictedTypedMentionCount),
      typedSpanRecall: ratio(counts.representedGoldTypedMentionCount, counts.goldTypedMentionCount),
    },
  };
}

function identityAggregateFingerprint(
  documents: Array<{ documentId: string; outputFingerprint: string }>,
) {
  return sha256Hex(canonicalJson(
    documents.map((document) => ({
      documentId: document.documentId,
      outputFingerprint: document.outputFingerprint,
    })),
  ));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const annotationDir = join(args.litbankRoot, "coref", "tsv");
  const names = (await readdir(annotationDir))
    .filter((name) => name.endsWith(".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (names.length === 0) throw new Error("no LitBank annotations found");

  const spanDocuments = [];
  const fcorefDocuments: Array<{ documentId: string; outputFingerprint: string; counts: IdentityBenchmarkReport["counts"]; metrics: IdentityBenchmarkReport["metrics"] }> = [];
  const combinedDocuments: typeof fcorefDocuments = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const annotationName of names) {
    const documentId = basename(annotationName, ".ann");
    try {
      const [annotation, source, rawText] = await Promise.all([
        readFile(join(annotationDir, annotationName), "utf8"),
        readFile(join(annotationDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.rawRoot, `${documentId}.json`), "utf8"),
      ]);
      const converted = convertLitBankTsvDocument({ documentId, annotation, text: source });
      const raw = normalizeRawDocument(JSON.parse(rawText) as RawProviderDocument, documentId, converted.gold.text);

      spanDocuments.push({
        documentId,
        ...evaluateGlinerSpans(raw.entities, converted.gold.mentions),
      });

      const fcorefEvidence = buildFcorefOracleEvidence(documentId, converted.evidence, raw.clusters);
      const fcorefResult = resolveCharacterIdentity({ normalizedText: converted.gold.text, evidence: fcorefEvidence });
      const fcorefReport = evaluateIdentityBenchmarkCase({ gold: converted.gold, evidence: fcorefEvidence, result: fcorefResult });
      fcorefDocuments.push({
        documentId,
        outputFingerprint: fcorefResult.outputFingerprint,
        counts: fcorefReport.counts,
        metrics: fcorefReport.metrics,
      });

      const combinedEvidence = buildCombinedEvidence({
        documentId,
        text: converted.gold.text,
        normalizedInputFingerprint: converted.evidence.normalizedInputFingerprint,
        entities: raw.entities,
        clusters: raw.clusters,
      });
      const combinedResult = resolveCharacterIdentity({ normalizedText: converted.gold.text, evidence: combinedEvidence });
      const combinedReport = evaluateIdentityBenchmarkCase({ gold: converted.gold, evidence: combinedEvidence, result: combinedResult });
      combinedDocuments.push({
        documentId,
        outputFingerprint: combinedResult.outputFingerprint,
        counts: combinedReport.counts,
        metrics: combinedReport.metrics,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  await mkdir(args.outDir, { recursive: true });
  const commonDataset = {
    repository: "dbamman/litbank",
    commit: LITBANK_COMMIT,
    license: "CC BY 4.0",
    annotationLayer: "coref/tsv",
    attemptedDocumentCount: names.length,
    completedDocumentCount: combinedDocuments.length,
    failedDocumentCount: failures.length,
  };

  const spanOutput = {
    schemaVersion: "saga-gliner-litbank-span-benchmark-v1",
    benchmark: "GLiNER small v2.1 typed spans against LitBank entity/coref mentions",
    dataset: commonDataset,
    provider: {
      name: "gliner-small-v2.1",
      model: "urchade/gliner_small-v2.1",
      revision: `gliner:${GLINER_CODE_COMMIT}|model:${GLINER_MODEL_REVISION}|threshold:${GLINER_THRESHOLD}`,
    },
    aggregate: aggregateSpanReports(spanDocuments.map((document) => ({ counts: document.counts, metrics: document.metrics }))),
    failures,
    perDocument: spanDocuments,
  };

  const fcorefOutput = {
    schemaVersion: "saga-fcoref-oracle-mentions-litbank-v1",
    benchmark: "F-Coref clusters with LitBank oracle mention typing -> S.A.G.A. identity policy",
    benchmarkPurpose: "Isolate F-Coref cluster/attachment quality from mention detection and person typing.",
    dataset: commonDataset,
    provider: FCOREF_ORACLE_PROVIDER,
    providerCodeLicense: "MIT",
    providerModelLicense: "MIT",
    aggregateOutputFingerprint: identityAggregateFingerprint(fcorefDocuments),
    aggregate: aggregateIdentityBenchmarkReports(fcorefDocuments.map((document) => ({ counts: document.counts, metrics: document.metrics }))),
    failures,
    perDocument: fcorefDocuments,
  };

  const combinedOutput = {
    schemaVersion: "saga-gliner-fcoref-litbank-benchmark-v1",
    benchmark: "GLiNER small v2.1 + F-Coref -> S.A.G.A. identity policy",
    benchmarkPurpose: "Measure a fully local permissively-licensed typed-span + coreference candidate without allowing coreference-only mentions to mint canon.",
    dataset: commonDataset,
    provider: GLINER_FCOREF_PROVIDER,
    licenses: { glinerCodeAndModel: "Apache-2.0", fastcorefCodeAndModel: "MIT" },
    aggregateOutputFingerprint: identityAggregateFingerprint(combinedDocuments),
    aggregate: aggregateIdentityBenchmarkReports(combinedDocuments.map((document) => ({ counts: document.counts, metrics: document.metrics }))),
    failures,
    perDocument: combinedDocuments,
  };

  await Promise.all([
    writeFile(join(args.outDir, "gliner-span.json"), `${JSON.stringify(spanOutput, null, 2)}\n`, "utf8"),
    writeFile(join(args.outDir, "fcoref-oracle-mentions.json"), `${JSON.stringify(fcorefOutput, null, 2)}\n`, "utf8"),
    writeFile(join(args.outDir, "gliner-fcoref-combined.json"), `${JSON.stringify(combinedOutput, null, 2)}\n`, "utf8"),
  ]);

  process.stdout.write(`${JSON.stringify({
    dataset: commonDataset,
    gliner: spanOutput.aggregate,
    fcorefOracleMentions: fcorefOutput.aggregate,
    combined: combinedOutput.aggregate,
  }, null, 2)}\n`);
  if (combinedDocuments.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
