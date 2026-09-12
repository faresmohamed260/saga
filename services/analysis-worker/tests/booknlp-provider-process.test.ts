import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import {
  BOOKNLP_SMALL_PROVIDER,
  bookNlpRuntimeConfigurationFingerprint,
} from "../src/local-analysis/booknlp-provider.js";
import {
  LocalLiteraryProviderError,
  SubprocessLocalLiteraryEvidenceProvider,
} from "../src/local-analysis/subprocess-provider.js";

const providerProcessPath = fileURLToPath(
  new URL("../src/local-analysis/booknlp-provider-process.ts", import.meta.url),
);
const runnerFixturePath = fileURLToPath(
  new URL("./fixtures/booknlp-runner-fixture.mjs", import.meta.url),
);
const fixtureModelPath = fileURLToPath(new URL("./fixtures", import.meta.url));
const text = "Élodie smiled. 😀 Alice said, “Hello, Bob.” Bob waved.";

function codePointLength(value: string) {
  return Array.from(value).length;
}

function provider(runnerArgs: string[] = [runnerFixturePath], configurationOverride?: string) {
  const configurationFingerprint = configurationOverride ?? bookNlpRuntimeConfigurationFingerprint({
    runnerExecutable: process.execPath,
    runnerArgs,
    modelPath: fixtureModelPath,
  });
  return new SubprocessLocalLiteraryEvidenceProvider({
    executable: process.execPath,
    args: ["--import", "tsx", providerProcessPath],
    descriptor: BOOKNLP_SMALL_PROVIDER,
    configurationFingerprint,
    environment: {
      SAGA_BOOKNLP_RUNNER_EXECUTABLE: process.execPath,
      SAGA_BOOKNLP_RUNNER_ARGS_JSON: JSON.stringify(runnerArgs),
      SAGA_BOOKNLP_MODEL_DIR: fixtureModelPath,
    },
    timeoutMs: 10_000,
  });
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

async function expectProviderError(promise: Promise<unknown>, code: string, retryable: boolean) {
  await assert.rejects(promise, (error: unknown) => {
    assert.ok(error instanceof LocalLiteraryProviderError);
    assert.equal(error.code, code);
    assert.equal(error.retryable, retryable);
    return true;
  });
}

test("BookNLP provider process health verifies the pinned runner package version", async () => {
  assert.deepEqual(await provider().health(), {
    status: "ok",
    provider: BOOKNLP_SMALL_PROVIDER,
    protocolVersion: "saga-local-literary-subprocess-v1",
    configurationFingerprint: bookNlpRuntimeConfigurationFingerprint({
      runnerExecutable: process.execPath,
      runnerArgs: [runnerFixturePath],
      modelPath: fixtureModelPath,
    }),
  });
});

test("BookNLP provider process converts runner TSV outputs through the existing S.A.G.A. normalizer", async () => {
  const evidence = await provider().analyze(source);

  assert.deepEqual(evidence.provider, BOOKNLP_SMALL_PROVIDER);
  assert.equal(evidence.normalizedInputFingerprint, source.normalizedInputFingerprint);
  assert.equal(evidence.identityEvidence.mentions.length, 4);
  assert.equal(evidence.entities.length, 4);
  assert.equal(evidence.quotes.length, 1);
  assert.equal(evidence.eventTriggers.length, 3);

  assert.deepEqual(
    {
      quoteText: evidence.quotes[0]!.quoteText,
      speakerSurfaceText: evidence.quotes[0]!.speakerSurfaceText,
      speakerProviderClusterId: evidence.quotes[0]!.speakerProviderClusterId,
    },
    {
      quoteText: "“Hello, Bob.”",
      speakerSurfaceText: "Alice",
      speakerProviderClusterId: "booknlp:2",
    },
  );
  assert.deepEqual(
    evidence.eventTriggers.map((event) => [event.surfaceText, event.lemma]),
    [["smiled", "smile"], ["said", "say"], ["waved", "wave"]],
  );
});

test("BookNLP provider process rejects a runner with the wrong pinned package version", async () => {
  await expectProviderError(
    provider([runnerFixturePath, "--fixture-version", "9.9.9"]).health(),
    "local_provider_reported:booknlp_runner_version_mismatch",
    false,
  );
});

test("BookNLP provider process fails closed when required provider outputs are absent", async () => {
  await expectProviderError(
    provider([runnerFixturePath, "--omit-quotes"]).analyze(source),
    "local_provider_reported:booknlp_runner_missing_outputs",
    false,
  );
});

test("BookNLP provider process binds the outer protocol request to the exact runner and model-path fingerprint", async () => {
  await expectProviderError(
    provider([runnerFixturePath], "0".repeat(64)).health(),
    "local_provider_reported:booknlp_configuration_fingerprint_mismatch",
    false,
  );
});
