import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "../..");
function read(relativePath) {
  return readFileSync(join(webRoot, relativePath), "utf8");
}

test("Phase 2C atomically hands successful ingestion to character identity work", () => {
  const migration = read("supabase/migrations/20260912030000_character_identity.sql");
  assert.match(migration, /saga_enqueue_character_identity_after_ingestion/);
  assert.match(migration, /new\.kind <> 'source_ingestion'/);
  assert.match(migration, /'character_identity'/);
  assert.match(migration, /ingestion_run\.output_fingerprint = v_job\.input_fingerprint/);
  assert.match(migration, /saga_service_commit_identity_success/);
  assert.match(migration, /saga_service_commit_identity_failure/);
  assert.match(migration, /resolver_key/);
  assert.match(migration, /provider_evidence_id/);
});

test("identity result reads stay behind the active account and ordinary RLS client", () => {
  const data = read("src/server/story/identity-data.ts");
  assert.match(data, /requireCurrentSagaAccount\s*\(\)/);
  assert.match(data, /createSupabaseServerClient\s*\(\)/);
  assert.match(data, /\.from\("saga_characters"\)/);
  assert.match(data, /\.from\("saga_character_aliases"\)/);
  assert.match(data, /\.from\("saga_character_mentions"\)/);
  assert.match(data, /\.eq\("owner_user_id", account\.userId\)/);
  assert.doesNotMatch(data, /createSupabasePrivilegedClient|service[_-]?role/i);
});

test("project workspace exposes inspectable identity evidence without model-control UI", () => {
  const page = read("src/app/(app)/projects/[projectId]/page.tsx");
  const evidence = read("src/features/characters/character-evidence-section.tsx");
  assert.match(page, /CharacterEvidenceSection/);
  assert.match(evidence, /Canonicals are admitted conservatively/);
  assert.match(evidence, /Unresolved evidence/);
  assert.match(evidence, /Quarantined evidence/);
  assert.match(evidence, /Run provenance/);
  assert.match(evidence, /Representative linked mentions/);
  assert.doesNotMatch(`${page}\n${evidence}`, /temperature|top[_ -]?p|system prompt|model selector/i);
});

test("Phase 2C database contract proves identity handoff, atomic persistence and owner isolation", () => {
  const contract = read("supabase/tests/character_identity.sql");
  assert.match(contract, /successful ingestion did not atomically enqueue exactly one identity job/);
  assert.match(contract, /identity success did not persist one atomic provenance\/result set/);
  assert.match(contract, /owner cannot read identity results/);
  assert.match(contract, /cross-user character read leaked/);
  assert.match(contract, /cross-user alias read leaked/);
  assert.match(contract, /cross-user mention read leaked/);
});
