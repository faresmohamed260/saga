import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { IdentityEvidenceProviderError } from "../src/identity/http-provider.js";
import { RecordedIdentityEvidenceProvider } from "../src/identity/recorded-provider.js";
import type { CharacterEvidenceProvider } from "../src/identity/types.js";
import { processOneCharacterIdentityJob, type IdentityDatabase } from "../src/identity-processor.js";
import type { ClaimedIdentityJob, IdentityInput } from "../src/runtime/database.js";

const text = "She ran. Ada Vale stopped.";
const normalizedInputFingerprint = sha256Hex(text);
const job: ClaimedIdentityJob = {
  jobId: "job-identity-1",
  projectId: "project-1",
  sourceId: "source-1",
  ownerUserId: "owner-1",
  inputFingerprint: "4".repeat(64),
  attemptCount: 1,
  leaseToken: "lease-1",
};
const identityInput: IdentityInput = {
  normalizedInputFingerprint,
  normalizedText: text,
  sections: [
    {
      stable_key: "section-0000",
      ordinal: 0,
      section_kind: "chapter",
      title: "Fixture",
      source_locator: "fixture:chapter-1",
      start_offset: 0,
      end_offset: [...text].length,
      normalized_text: text,
    },
  ],
};

function provider() {
  return new RecordedIdentityEvidenceProvider({
    mentions: [
      {
        evidenceId: "she",
        surfaceText: "She",
        startOffset: 0,
        endOffset: 3,
        structuralLocator: "fixture:chapter-1",
        mentionKind: "pronoun",
        entityType: "person",
        personEvidence: "supporting",
        boundaryQuality: "clean",
        providerClusterId: "ada",
      },
      {
        evidenceId: "ada",
        surfaceText: "Ada Vale",
        startOffset: 9,
        endOffset: 17,
        structuralLocator: "fixture:chapter-1",
        mentionKind: "proper_name",
        entityType: "person",
        personEvidence: "strong",
        boundaryQuality: "clean",
        providerClusterId: "ada",
      },
    ],
  });
}

function fakeDatabase(overrides: Partial<IdentityDatabase> = {}) {
  const calls: string[] = [];
  let committedResult: unknown = null;
  let committedFailure: unknown = null;
  const database: IdentityDatabase = {
    async claimCharacterIdentityJob() {
      calls.push("claim");
      return job;
    },
    async getIdentityInput() {
      calls.push("input");
      return identityInput;
    },
    async renewLease() {
      calls.push("renew");
    },
    async commitIdentitySuccess(_job, result) {
      calls.push("success");
      committedResult = result;
      return "run-identity-1";
    },
    async commitIdentityTerminalFailure(_job, input) {
      calls.push("terminal");
      committedFailure = input;
      return "run-failed-1";
    },
    async requeueTransientFailure() {
      calls.push("requeue");
      return "queued";
    },
    ...overrides,
  };
  return {
    database,
    calls,
    committedResult: () => committedResult,
    committedFailure: () => committedFailure,
  };
}

test("identity processor resolves recorded evidence and commits one immutable result", async () => {
  const fake = fakeDatabase();
  const result = await processOneCharacterIdentityJob({
    database: fake.database,
    provider: provider(),
    workerId: "identity-worker",
    leaseSeconds: 300,
  });

  assert.deepEqual(result, { status: "succeeded", jobId: job.jobId, runId: "run-identity-1" });
  assert.deepEqual(fake.calls, ["claim", "input", "renew", "renew", "success"]);
  const committed = fake.committedResult() as { characters: Array<{ canonicalName: string; admissionTier: string }> };
  assert.equal(committed.characters.length, 1);
  assert.equal(committed.characters[0]?.canonicalName, "Ada Vale");
  assert.equal(committed.characters[0]?.admissionTier, "stabilized");
});

test("provider evidence for the wrong normalized input fails terminally", async () => {
  const fake = fakeDatabase();
  const wrongProvider: CharacterEvidenceProvider = {
    descriptor: { name: "wrong-fixture", model: null, revision: "v1" },
    async collect() {
      return {
        provider: this.descriptor,
        normalizedInputFingerprint: "f".repeat(64),
        mentions: [],
      };
    },
  };

  const result = await processOneCharacterIdentityJob({
    database: fake.database,
    provider: wrongProvider,
    workerId: "identity-worker",
    leaseSeconds: 300,
  });

  assert.deepEqual(result, {
    status: "failed",
    jobId: job.jobId,
    failureCode: "provider_input_fingerprint_mismatch",
  });
  assert.ok(fake.calls.includes("terminal"));
  assert.ok(!fake.calls.includes("success"));
});

test("invalid provider payload failures are terminal, not retry loops", async () => {
  const fake = fakeDatabase();
  const invalidProvider: CharacterEvidenceProvider = {
    descriptor: { name: "invalid-fixture", model: null, revision: "v1" },
    async collect() {
      throw new IdentityEvidenceProviderError("identity_provider_invalid_payload", false);
    },
  };

  const result = await processOneCharacterIdentityJob({
    database: fake.database,
    provider: invalidProvider,
    workerId: "identity-worker",
    leaseSeconds: 300,
  });

  assert.equal(result.status, "failed");
  assert.equal(result.status === "failed" ? result.failureCode : null, "invalid_provider_evidence");
  assert.ok(fake.calls.includes("terminal"));
  assert.ok(!fake.calls.includes("requeue"));
});

test("transient provider failures preserve the durable job for retry", async () => {
  const fake = fakeDatabase();
  const transientProvider: CharacterEvidenceProvider = {
    descriptor: { name: "transient-fixture", model: null, revision: "v1" },
    async collect() {
      throw new IdentityEvidenceProviderError("identity_provider_http_503", true);
    },
  };

  const result = await processOneCharacterIdentityJob({
    database: fake.database,
    provider: transientProvider,
    workerId: "identity-worker",
    leaseSeconds: 300,
  });

  assert.deepEqual(result, { status: "requeued", jobId: job.jobId });
  assert.ok(fake.calls.includes("requeue"));
  assert.ok(!fake.calls.includes("terminal"));
});

test("identity processor leaves the provider untouched when no job is available", async () => {
  let providerCalls = 0;
  const fake = fakeDatabase({
    async claimCharacterIdentityJob() {
      return null;
    },
  });
  const noWorkProvider: CharacterEvidenceProvider = {
    descriptor: { name: "no-work", model: null, revision: "v1" },
    async collect() {
      providerCalls += 1;
      throw new Error("should not run");
    },
  };

  const result = await processOneCharacterIdentityJob({
    database: fake.database,
    provider: noWorkProvider,
    workerId: "identity-worker",
    leaseSeconds: 300,
  });

  assert.deepEqual(result, { status: "no_work" });
  assert.equal(providerCalls, 0);
});
