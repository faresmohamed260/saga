import { appendFile, readFile, writeFile } from "node:fs/promises";
import process from "node:process";

const FIXTURE_TEXT = "Élodie smiled. 😀 Alice said, “Hello, Bob.” Bob waved.";
const DEFAULT_VERSION = "1.0.7";
const PROTOCOL_VERSION = "saga-booknlp-persistent-runner-v1";
const REQUEST_SCHEMA_VERSION = "saga-booknlp-persistent-request-v1";
const RESPONSE_SCHEMA_VERSION = "saga-booknlp-persistent-response-v1";

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

function valueAfter(flag) {
  const index = process.argv.indexOf(flag);
  return index < 0 ? null : process.argv[index + 1] ?? null;
}

const configurationFingerprint = valueAfter("--configuration-fingerprint");
const fixtureVersion = valueAfter("--fixture-version") ?? DEFAULT_VERSION;
const startupLog = valueAfter("--startup-log");
const responseConfigurationOverride = valueAfter("--response-configuration-fingerprint");
const crashOnceMarker = valueAfter("--crash-once-marker");
const structuredErrorFirstAnalyze = process.argv.includes("--structured-error-first-analyze");
const omitQuotes = process.argv.includes("--omit-quotes");

if (!configurationFingerprint) process.exit(2);
if (startupLog) await appendFile(startupLog, `${process.pid}\n`, "utf8");

let analyzeCount = 0;

function response(requestId, kind, fields = {}) {
  return {
    schemaVersion: RESPONSE_SCHEMA_VERSION,
    protocolVersion: PROTOCOL_VERSION,
    requestId,
    configurationFingerprint: responseConfigurationOverride ?? configurationFingerprint,
    kind,
    ...fields,
  };
}

function writeResponse(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function shouldCrashOnce() {
  if (!crashOnceMarker) return false;
  try {
    await readFile(crashOnceMarker, "utf8");
    return false;
  } catch {
    await writeFile(crashOnceMarker, "crashed\n", "utf8");
    return true;
  }
}

let buffered = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", async (chunk) => {
  buffered += chunk;
  while (true) {
    const newline = buffered.indexOf("\n");
    if (newline < 0) break;
    const line = buffered.slice(0, newline).trim();
    buffered = buffered.slice(newline + 1);

    let request;
    try {
      request = JSON.parse(line);
    } catch {
      writeResponse(response("invalid", "error", {
        error: { code: "fixture_invalid_json", retryable: false },
      }));
      continue;
    }

    const requestId = typeof request.requestId === "string" ? request.requestId : "invalid";
    if (
      request.schemaVersion !== REQUEST_SCHEMA_VERSION ||
      request.protocolVersion !== PROTOCOL_VERSION ||
      request.configurationFingerprint !== configurationFingerprint
    ) {
      writeResponse(response(requestId, "error", {
        error: { code: "fixture_protocol_mismatch", retryable: false },
      }));
      continue;
    }

    if (request.kind === "health") {
      writeResponse(response(requestId, "health", {
        status: "ok",
        booknlpVersion: fixtureVersion,
      }));
      continue;
    }

    if (request.kind === "shutdown") {
      writeResponse(response(requestId, "shutdown", {
        status: "ok",
        booknlpVersion: fixtureVersion,
      }));
      process.exit(0);
    }

    if (request.kind !== "analyze" || request.normalizedText !== FIXTURE_TEXT) {
      writeResponse(response(requestId, "error", {
        error: { code: "fixture_invalid_analyze", retryable: false },
      }));
      continue;
    }

    analyzeCount += 1;
    if (await shouldCrashOnce()) process.exit(17);
    if (structuredErrorFirstAnalyze && analyzeCount === 1) {
      writeResponse(response(requestId, "error", {
        error: { code: "fixture_transient", retryable: true },
      }));
      continue;
    }

    writeResponse(response(requestId, "analyze", {
      booknlpVersion: fixtureVersion,
      normalizedInputFingerprint: request.normalizedInputFingerprint,
      tokensTsv: `${tokensTsv}\n`,
      entitiesTsv: `${entitiesTsv}\n`,
      quotesTsv: omitQuotes ? null : `${quotesTsv}\n`,
    }));
  }
});
