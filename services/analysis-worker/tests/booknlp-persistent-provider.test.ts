import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { PersistentBookNlpEvidenceProvider } from "../src/local-analysis/booknlp-persistent-provider.js";
import {
  BOOKNLP_SMALL_PROVIDER,
  bookNlpRuntimeConfigurationFingerprint,
} from "../src/local-analysis/booknlp-provider.js";
import {
  LocalLiteraryProviderError,
  SubprocessLocalLiteraryEvidenceProvider,
} from "../src/local-analysis/subprocess-provider.js";

const oneShotProviderProcessPath = fileURLToPath(
  new URL("../src/local-analysis/booknlp-provider-process.ts", import.meta.url),
);
const oneShotRunnerFixturePath = fileURLToPath(
  new URL("./fixtures/booknlp-runner-fixture.mjs", import.meta.url),
);
const persistentRunnerFixturePath = fileURLToPath(
  new URL("./fixtures/booknlp-persistent-runner-fixture.mjs", import.meta.url),
);
const fixtureModelPath = fileURLToPath(new URL("./fixtures", import.meta.url));
const text = "Élodie smiled. 😀 Alice said, “Hello, Bob.” Bob waved.";

function codePointLength(value: string) {
  return Array.from(value).length;
}

const source = {
  normalizedInputFingerprint: sha256Hex(text),
  normalizedText: text,
  sections: [
    {
      stable_key: "document:0",
      ordinal: 0,
      section_kind: "document" as const,
      title: null,
      source_locator: "fixture:booknlp-provider",
      start_offset: 0,
      end_offset: codePointLength(text),
      normalized_text: text,
    },
  ],
};

function oneShotProvider() {
  const configurationFingerprint = bookNlpRuntimeConfigurationFingerprint({
    runnerExecutable: process.execPath,
    runnerArgs: [oneShotRunnerFixturePath],
    modelPath: fixtureModelPath,
  });
  return new SubprocessLocalLiteraryEvidenceProvider({
    executable: process.execPath,
    args: ["--import", "tsx", oneShotProviderProcessPath],
    descriptor: BOOKNLP_SMALL_PROVIDER,
    configurationFingerprint,
    environment: {
      SAGA_BOOKNLP_RUNNER_EXECUTABLE: process.execPath,
      SAGA_BOOKNLP_RUNNER_ARGS_JSON: JSON.stringify([oneShotRunnerFixturePath]),
      SAGA_BOOKNLP_MODEL_DIR: fixtureModelPath,
    },
    timeoutMs: 10_000,
  });
}

function persistentProvider(extraArgs: string[] = [], timeoutMs = 10_000) {
  return new PersistentBookNlpEvidenceProvider({
    runnerExecutable: process.execPath,
    runnerArgs: [persistentRunnerFixturePath, ...extraArgs],
    modelPath: fixtureModelPath,
    timeoutMs,
  });
}

async function expectProviderError(promise: Promise<unknown>, code: string, retryable: boolean) {
  await assert.rejects(promise, (error: unknown) => {
    assert.ok(error instanceof LocalLiteraryProviderError);
    assert.equal(error.code, code);
    assert.equal(error.retryable, retryable);
    return true;
  });
}

async function startupPids(path: string) {
  const value = await readFile(path, "utf8");
  return value.trim().split(/\r?\n/u).filter(Boolean);
}

test("persistent BookNLP provider reuses one child and preserves one-shot semantic evidence", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "saga-booknlp-persistent-test-"));
  const startupLog = join(workspace, "startups.txt");
  const provider = persistentProvider(["--startup-log", startupLog]);
  try {
    const health = await provider.health();
    assert.equal(health.status, "ok");
    assert.equal(health.provider.name, BOOKNLP_SMALL_PROVIDER.name);
    assert.equal(health.protocolVersion, "saga-booknlp-persistent-runner-v1");

    const first = await provider.analyze(source);
    const second = await provider.analyze(source);
    const oneShot = await oneShotProvider().analyze(source);

    assert.deepEqual(first, second);
    assert.deepEqual(first, oneShot);
    assert.equal((await startupPids(startupLog)).length, 1);
  } finally {
    await provider.close();
    await rm(workspace, { recursive: true, force: true });
  }
});

test("persistent provider keeps the loaded process after a structured per-request error", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "saga-booknlp-persistent-error-"));
  const startupLog = join(workspace, "startups.txt");
  const provider = persistentProvider(["--startup-log", startupLog, "--structured-error-first-analyze"]);
  try {
    await expectProviderError(
      provider.analyze(source),
      "booknlp_persistent_reported:fixture_transient",
      true,
    );
    const evidence = await provider.analyze(source);
    assert.equal(evidence.eventTriggers.length, 3);
    assert.equal((await startupPids(startupLog)).length, 1);
  } finally {
    await provider.close();
    await rm(workspace, { recursive: true, force: true });
  }
});

test("persistent provider does not retry a crashed request but can restart for a later call", async () => {
  const workspace = await mkdtemp(join(tmpdir(), "saga-booknlp-persistent-crash-"));
  const startupLog = join(workspace, "startups.txt");
  const marker = join(workspace, "crashed.txt");
  const provider = persistentProvider([
    "--startup-log",
    startupLog,
    "--crash-once-marker",
    marker,
  ]);
  try {
    await expectProviderError(provider.analyze(source), "booknlp_persistent_exit:17", true);
    const evidence = await provider.analyze(source);
    assert.equal(evidence.identityEvidence.mentions.length, 4);
    assert.equal((await startupPids(startupLog)).length, 2);
  } finally {
    await provider.close();
    await rm(workspace, { recursive: true, force: true });
  }
});

test("persistent provider fails closed on package, response fingerprint, and output drift", async () => {
  const wrongVersion = persistentProvider(["--fixture-version", "9.9.9"]);
  try {
    await expectProviderError(
      wrongVersion.health(),
      "booknlp_persistent_invalid_health_response",
      false,
    );
  } finally {
    await wrongVersion.close().catch(() => undefined);
  }

  const wrongFingerprint = persistentProvider([
    "--response-configuration-fingerprint",
    "0".repeat(64),
  ]);
  try {
    await expectProviderError(
      wrongFingerprint.health(),
      "booknlp_persistent_protocol_mismatch",
      false,
    );
  } finally {
    await wrongFingerprint.close().catch(() => undefined);
  }

  const missingQuotes = persistentProvider(["--omit-quotes"]);
  try {
    await expectProviderError(
      missingQuotes.analyze(source),
      "booknlp_persistent_invalid_analyze_response",
      false,
    );
  } finally {
    await missingQuotes.close().catch(() => undefined);
  }
});

test("persistent provider strips ambient S.A.G.A. secrets from the child", async () => {
  const key = "SAGA_PERSISTENT_PROVIDER_SECRET_TEST";
  const previous = process.env[key];
  process.env[key] = "must-not-leak";
  const provider = persistentProvider(["--forbid-env", key]);
  try {
    assert.equal((await provider.health()).status, "ok");
  } finally {
    if (previous === undefined) delete process.env[key];
    else process.env[key] = previous;
    await provider.close();
  }
});

test("persistent provider times out explicitly and close is terminal", async () => {
  const provider = persistentProvider(["--delay-ms", "1500"], 1_000);
  await expectProviderError(provider.analyze(source), "booknlp_persistent_timeout", true);
  await new Promise((resolve) => setTimeout(resolve, 50));
  await provider.close();
  await expectProviderError(
    provider.health(),
    "booknlp_persistent_provider_closed",
    false,
  );
});
