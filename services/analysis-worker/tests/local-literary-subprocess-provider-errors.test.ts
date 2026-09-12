import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  LocalLiteraryProviderError,
  SubprocessLocalLiteraryEvidenceProvider,
} from "../src/local-analysis/subprocess-provider.js";

const fixturePath = fileURLToPath(new URL("./fixtures/local-literary-provider-fixture.mjs", import.meta.url));

test("malformed subprocess provider descriptors become explicit terminal provider errors", async () => {
  const provider = new SubprocessLocalLiteraryEvidenceProvider({
    executable: process.execPath,
    args: [fixturePath, "malformed-provider"],
    descriptor: { name: "fixture-local", model: null, revision: "v1" },
    configurationFingerprint: "c".repeat(64),
  });

  await assert.rejects(provider.health(), (error: unknown) => {
    assert.ok(error instanceof LocalLiteraryProviderError);
    assert.equal(error.code, "local_provider_invalid_descriptor");
    assert.equal(error.retryable, false);
    return true;
  });
});
