import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { processOneSourceIngestionJob, type IngestionDatabase } from "../src/processor.js";
import type { ClaimedIngestionJob, IngestionSource } from "../src/runtime/database.js";
import type { SourceObjectReader } from "../src/runtime/storage.js";

const bytes = new TextEncoder().encode("CHAPTER I\nAda arrived.");
const contentSha256 = sha256Hex(bytes);

const job: ClaimedIngestionJob = {
  jobId: "11111111-1111-4111-8111-111111111111",
  projectId: "22222222-2222-4222-8222-222222222222",
  sourceId: "33333333-3333-4333-8333-333333333333",
  ownerUserId: "44444444-4444-4444-8444-444444444444",
  inputFingerprint: contentSha256,
  attemptCount: 1,
  leaseToken: "55555555-5555-4555-8555-555555555555",
};

const source: IngestionSource = {
  id: job.sourceId,
  projectId: job.projectId,
  ownerUserId: job.ownerUserId,
  objectKey: `sources/${job.ownerUserId}/${job.projectId}/${job.sourceId}/${contentSha256}/original`,
  format: "txt",
  mediaType: "text/plain",
  byteSize: bytes.byteLength,
  contentSha256,
};

function databaseHarness(overrides: Partial<IngestionDatabase> = {}) {
  const calls: string[] = [];
  const database: IngestionDatabase = {
    async claimSourceIngestionJob() {
      calls.push("claim");
      return job;
    },
    async getSource() {
      calls.push("source");
      return source;
    },
    async renewLease() {
      calls.push("renew");
    },
    async markProcessing() {
      calls.push("processing");
    },
    async commitSuccess(_job, result) {
      calls.push(`success:${result.sections.length}`);
      return "66666666-6666-4666-8666-666666666666";
    },
    async commitTerminalFailure(_job, _engine, _config, code) {
      calls.push(`terminal:${code}`);
      return "77777777-7777-4777-8777-777777777777";
    },
    async requeueTransientFailure() {
      calls.push("requeue");
      return "queued";
    },
    ...overrides,
  };
  return { database, calls };
}

const goodStorage: SourceObjectReader = {
  async read(key, expectedBytes) {
    assert.equal(key, source.objectKey);
    assert.equal(expectedBytes, bytes.byteLength);
    return { bytes, contentType: "text/plain" };
  },
};

test("source worker claims, marks processing, renews around normalization, and commits success", async () => {
  const { database, calls } = databaseHarness();
  const result = await processOneSourceIngestionJob({
    database,
    storage: goodStorage,
    workerId: "fixture-worker",
    leaseSeconds: 600,
  });

  assert.deepEqual(result, {
    status: "succeeded",
    jobId: job.jobId,
    runId: "66666666-6666-4666-8666-666666666666",
  });
  assert.deepEqual(calls, ["claim", "source", "processing", "renew", "renew", "success:1"]);
});

test("byte fingerprint mismatch is terminal and never reaches success", async () => {
  const badSource = { ...source, contentSha256: "0".repeat(64) };
  const badJob = { ...job, inputFingerprint: badSource.contentSha256 };
  const { database, calls } = databaseHarness({
    async claimSourceIngestionJob() {
      calls.push("claim");
      return badJob;
    },
    async getSource() {
      calls.push("source");
      return badSource;
    },
  });

  const result = await processOneSourceIngestionJob({
    database,
    storage: goodStorage,
    workerId: "fixture-worker",
    leaseSeconds: 600,
  });

  assert.deepEqual(result, {
    status: "failed",
    jobId: job.jobId,
    failureCode: "content_sha_mismatch",
  });
  assert.ok(calls.includes("terminal:content_sha_mismatch"));
  assert.ok(!calls.some((call) => call.startsWith("success:")));
});

test("transient object-store errors requeue instead of creating a terminal run", async () => {
  const { database, calls } = databaseHarness();
  const storage: SourceObjectReader = {
    async read() {
      throw new Error("temporary object-store timeout");
    },
  };

  const result = await processOneSourceIngestionJob({
    database,
    storage,
    workerId: "fixture-worker",
    leaseSeconds: 600,
  });

  assert.deepEqual(result, { status: "requeued", jobId: job.jobId });
  assert.ok(calls.includes("requeue"));
  assert.ok(!calls.some((call) => call.startsWith("terminal:")));
});

test("no claimed job is a clean no-work iteration", async () => {
  const { database, calls } = databaseHarness({
    async claimSourceIngestionJob() {
      calls.push("claim");
      return null;
    },
  });

  const result = await processOneSourceIngestionJob({
    database,
    storage: goodStorage,
    workerId: "fixture-worker",
    leaseSeconds: 600,
  });

  assert.deepEqual(result, { status: "no_work" });
  assert.deepEqual(calls, ["claim"]);
});
