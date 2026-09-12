import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { codePointLength, normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  aggregateDialogueReports,
  aggregateEventReports,
  evaluateLitBankComponentDocument,
} from "./litbank-component-benchmark.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";

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
    } else {
      throw new Error(`unknown argument: ${token}`);
    }
  }
  if (!litbankRoot || !booknlpRoot || !out) {
    throw new Error("usage: booknlp-component-cli --litbank-root <root> --booknlp-root <outputs> --out <report.json> [--limit N]");
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const corefDir = join(args.litbankRoot, "coref", "tsv");
  const documentIds = (await readdir(corefDir))
    .filter((name) => name.endsWith(".ann"))
    .map((name) => basename(name, ".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);
  if (documentIds.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const completed = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const documentId of documentIds) {
    try {
      const [corefAnnotation, textRaw, quotationAnnotation, quotationTextRaw, eventTsv, booknlp] = await Promise.all([
        readFile(join(corefDir, `${documentId}.ann`), "utf8"),
        readFile(join(corefDir, `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.ann`), "utf8"),
        readFile(join(args.litbankRoot, "quotations", "tsv", `${documentId}.txt`), "utf8"),
        readFile(join(args.litbankRoot, "events", "tsv", `${documentId}.tsv`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const text = normalizeNewlines(textRaw);
      const quotationText = normalizeNewlines(quotationTextRaw);
      if (quotationText !== text) throw new Error("litbank_component_quotation_source_mismatch");
      const fingerprint = sha256Hex(text);
      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint: fingerprint,
        normalizedText: text,
        sections: [{
          stable_key: `litbank:${documentId}`,
          ordinal: 0,
          section_kind: "document",
          title: null,
          source_locator: `litbank:${documentId}`,
          start_offset: 0,
          end_offset: codePointLength(text),
          normalized_text: text,
        }],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const evaluation = evaluateLitBankComponentDocument({
        documentId,
        text,
        corefAnnotation,
        quotationAnnotation,
        eventTsv,
        evidence,
      });
      completed.push({ documentId, ...evaluation });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({ documentId, code: message.split(":", 1)[0] || "unknown_error", message });
    }
  }

  const bookNlpDialogueReports = completed.map((row) => row.dialogue.bookNlp);
  const deterministicDialogueReports = completed.map((row) => row.dialogue.deterministicOracleIdentity);
  const bookNlpEventReports = completed.map((row) => row.events.bookNlp);
  const deterministicEventReports = completed.map((row) => row.events.deterministicLexicalOracleIdentity);
  const attributedMentionCount = completed.reduce((sum, row) => sum + row.dialogue.bookNlpSpeakerMapping.attributedMentionCount, 0);
  const goldMappedMentionCount = completed.reduce((sum, row) => sum + row.dialogue.bookNlpSpeakerMapping.goldMappedMentionCount, 0);

  const semantic = {
    schemaVersion: "saga-booknlp-litbank-component-benchmark-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      attemptedDocumentCount: documentIds.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    provider: BOOKNLP_SMALL_PROVIDER,
    isolationPolicy: {
      speakerAttribution: "BookNLP attributed mention span is mapped to LitBank gold coreference; BookNLP clustering quality is excluded from the speaker component score.",
      deterministicSpeakerBaseline: "S.A.G.A. deterministic attribution is supplied LitBank gold identity links to isolate attribution quality.",
      eventParticipants: "unscored; pinned LitBank event TSV supplies trigger labels, not S.A.G.A.-style grounded participants",
    },
    dialogue: {
      bookNlp: aggregateDialogueReports(bookNlpDialogueReports),
      deterministicOracleIdentity: aggregateDialogueReports(deterministicDialogueReports),
      bookNlpSpeakerMentionMapping: {
        attributedMentionCount,
        goldMappedMentionCount,
        coverage: attributedMentionCount === 0 ? 0 : goldMappedMentionCount / attributedMentionCount,
      },
    },
    events: {
      bookNlp: aggregateEventReports(bookNlpEventReports),
      deterministicLexicalOracleIdentity: aggregateEventReports(deterministicEventReports),
    },
    failures,
    perDocument: completed,
  };
  const output = {
    ...semantic,
    reportFingerprint: sha256Hex(canonicalJson(semantic)),
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    dataset: output.dataset,
    dialogue: output.dialogue,
    events: output.events,
    failures,
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
