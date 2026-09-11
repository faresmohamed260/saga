import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "../..");

function read(relativePath) {
  return readFileSync(join(webRoot, relativePath), "utf8");
}

function readTree(relativePath) {
  const root = join(webRoot, relativePath);
  const files = [];
  function visit(path) {
    for (const entry of readdirSync(path)) {
      const full = join(path, entry);
      if (statSync(full).isDirectory()) visit(full);
      else if (/\.(?:ts|tsx|mjs)$/.test(entry)) files.push(readFileSync(full, "utf8"));
    }
  }
  visit(root);
  return files.join("\n");
}

test("Phase 2B schema keeps normalized structure immutable and owner scoped", () => {
  const migration = read("supabase/migrations/20260912015000_source_ingestion.sql");
  const claimMigration = read("supabase/migrations/20260912020500_source_ingestion_claim.sql");

  assert.match(migration, /create table public\.saga_normalized_sources/);
  assert.match(migration, /create table public\.saga_normalized_sections/);
  assert.match(migration, /force row level security/);
  assert.match(migration, /saga_create_source_upload_intent/);
  assert.match(migration, /sources\/%s\/%s\/%s\/%s\/original/);
  assert.match(migration, /saga_service_finalize_source_upload/);
  assert.match(migration, /upload_metadata_mismatch/);
  assert.match(migration, /saga_service_commit_ingestion_success/);
  assert.match(migration, /saga_service_commit_ingestion_failure/);
  assert.match(migration, /grant select, insert on table public\.saga_normalized_sources to service_role/);
  assert.doesNotMatch(migration, /grant select, insert, update[^;]*saga_normalized_sources to service_role/i);
  assert.match(claimMigration, /saga_claim_analysis_job_kind/);
  assert.match(claimMigration, /job\.kind = p_kind/);
  assert.match(claimMigration, /for update skip locked/);
});

test("source upload is owner-bound, direct-to-storage, and server verified before enqueue", () => {
  const service = read("src/server/story/source-upload.ts");
  const actions = read("src/features/library/source-upload-actions.ts");
  const client = read("src/features/library/source-upload-form.tsx");
  const originalRoute = read("src/app/api/sources/[sourceId]/original/route.ts");

  assert.match(service, /requireCurrentSagaAccount\s*\(\)/);
  assert.match(service, /saga_create_source_upload_intent/);
  assert.match(service, /createUploadUrl/);
  assert.match(service, /saga-sha256/);
  assert.match(service, /saga-source-id/);
  const headIndex = service.indexOf("storage.head");
  const finalizeIndex = service.indexOf("saga_service_finalize_source_upload");
  assert.ok(headIndex >= 0 && finalizeIndex > headIndex, "object HEAD verification must precede trusted finalization");
  assert.match(service, /createSagaSourceReadUrl/);
  assert.match(service, /createReadUrl/);

  assert.match(actions, /^"use server";/);
  assert.match(actions, /startSourceUploadAction/);
  assert.match(actions, /completeSourceUploadAction/);
  assert.doesNotMatch(actions, /File|arrayBuffer|Blob/);

  assert.match(client, /crypto\.subtle\.digest\("SHA-256"/);
  assert.match(client, /fetch\(intent\.uploadUrl/);
  assert.match(client, /method: "PUT"/);
  assert.match(client, /completeSourceUploadAction/);
  assert.match(client, /type="file"/);

  assert.match(originalRoute, /createSagaSourceReadUrl/);
  assert.match(originalRoute, /NextResponse\.redirect/);
});

test("Backblaze adapter signs immutable upload metadata and exposes HEAD metadata through ObjectStorage", () => {
  const types = read("src/server/storage/types.ts");
  const b2 = read("src/server/storage/b2.ts");

  assert.match(types, /metadata\?: Record<string, string>/);
  assert.match(types, /metadata: Record<string, string>/);
  assert.match(b2, /Metadata: input\.metadata/);
  assert.match(b2, /metadata: response\.Metadata \?\? \{\}/);
});

test("full-book normalization remains outside the Next.js source tree", () => {
  const activeWebSource = readTree("src");

  assert.doesNotMatch(activeWebSource, /services\/analysis-worker/);
  assert.doesNotMatch(activeWebSource, /from ["']fflate["']/);
  assert.doesNotMatch(activeWebSource, /from ["']fast-xml-parser["']/);
  assert.doesNotMatch(activeWebSource, /normalizeEpubSource|normalizeTextSource|normalizeSource\s*\(/);
});

test("Phase 2B disposable database contract covers trusted completion, lease use, and owner isolation", () => {
  const contract = read("supabase/tests/source_ingestion.sql");

  assert.match(contract, /cross-user upload intent unexpectedly succeeded/);
  assert.match(contract, /mismatched upload metadata did not fail closed/);
  assert.match(contract, /mismatched upload enqueued ingestion work/);
  assert.match(contract, /verified upload did not enqueue ingestion/);
  assert.match(contract, /successful ingestion did not settle source\/job state/);
  assert.match(contract, /normalized structure was not persisted atomically/);
  assert.match(contract, /cross-user normalized source read leaked/);
  assert.match(contract, /cross-user normalized section read leaked/);
});
