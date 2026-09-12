import process from "node:process";

const mode = process.argv[2] ?? "success";
let input = "";
for await (const chunk of process.stdin) input += chunk;

if (mode === "exit") process.exit(7);
if (mode === "sleep") await new Promise((resolve) => setTimeout(resolve, 2500));
if (mode === "oversize") {
  process.stdout.write("x".repeat(4096));
  process.exit(0);
}
if (mode === "oversize-stderr") {
  process.stderr.write("x".repeat(4096));
  await new Promise((resolve) => setTimeout(resolve, 250));
  process.exit(0);
}
if (mode === "invalid-json") {
  process.stdout.write("not-json\n");
  process.exit(0);
}
if (mode === "fail-if-secret" && process.env.SAGA_SUPABASE_SERVICE_ROLE_KEY) process.exit(9);

const request = JSON.parse(input);
const provider = mode === "bad-provider"
  ? { name: "unexpected", model: null, revision: "v1" }
  : { name: "fixture-local", model: null, revision: "v1" };
const requestId = mode === "bad-request-id" ? "wrong-request" : request.requestId;
const protocolVersion = mode === "bad-protocol" ? "wrong-protocol" : request.protocolVersion;

const common = {
  schemaVersion: "saga-local-literary-response-v1",
  kind: request.kind,
  requestId,
  protocolVersion,
  configurationFingerprint: request.configurationFingerprint,
  provider,
};

if (mode === "reported-retryable" || mode === "reported-terminal") {
  process.stdout.write(`${JSON.stringify({
    ...common,
    kind: "error",
    error: {
      code: mode === "reported-retryable" ? "model_temporarily_unavailable" : "invalid_provider_configuration",
      retryable: mode === "reported-retryable",
    },
  })}\n`);
  process.exit(0);
}

if (request.kind === "health") {
  process.stdout.write(`${JSON.stringify({ ...common, status: "ok" })}\n`);
  process.exit(0);
}

const normalizedInputFingerprint = mode === "bad-fingerprint"
  ? "f".repeat(64)
  : request.normalizedInputFingerprint;
const evidence = {
  provider,
  normalizedInputFingerprint,
  identityEvidence: {
    provider,
    normalizedInputFingerprint,
    mentions: [],
  },
  entities: [],
  quotes: [],
  eventTriggers: [],
};

if (mode === "bad-surface") {
  evidence.entities.push({
    evidenceId: "fixture:entity:1",
    surfaceText: "Wrong",
    startOffset: 0,
    endOffset: 5,
    structuralLocator: request.sections[0]?.stable_key ?? null,
    mentionKind: "proper_name",
    category: "person",
    providerClusterId: null,
    boundaryQuality: "clean",
  });
}

process.stdout.write(`${JSON.stringify({
  ...common,
  normalizedInputFingerprint,
  evidence,
})}\n`);
