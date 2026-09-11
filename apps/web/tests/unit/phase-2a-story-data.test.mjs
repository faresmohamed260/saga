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

test("Phase 2A schema separates private product data, durable jobs, and immutable results", () => {
  const migration = read("supabase/migrations/20260912003000_story_intelligence_foundation.sql");

  for (const table of [
    "saga_projects",
    "saga_sources",
    "saga_analysis_jobs",
    "saga_analysis_runs",
    "saga_characters",
    "saga_character_aliases",
    "saga_character_mentions",
  ]) {
    assert.match(migration, new RegExp(`create table public\\.${table}`));
    assert.match(migration, new RegExp(`alter table public\\.${table} force row level security`));
  }

  assert.match(migration, /saga_current_user_has_active_access/);
  assert.match(migration, /owner_user_id = \(select auth\.uid\(\)\)/);
  assert.match(migration, /for update skip locked/);
  assert.match(migration, /lease_token/);
  assert.match(migration, /saga_finish_analysis_job/);
  assert.match(migration, /stale_lease/);
  assert.match(migration, /grant select on table public\.saga_sources to authenticated/);
  assert.doesNotMatch(migration, /grant select, insert[^;]*on table public\.saga_sources to authenticated/i);
  assert.match(migration, /grant select, insert on table public\.saga_analysis_runs to service_role/);
  assert.doesNotMatch(migration, /grant select, insert, update[^;]*saga_analysis_runs to service_role/i);
});

test("member story operations use the active account boundary plus session-scoped RLS", () => {
  const storyData = read("src/server/story/story-data.ts");

  assert.match(storyData, /requireCurrentSagaAccount\s*\(\)/);
  assert.match(storyData, /createSupabaseServerClient\s*\(\)/);
  assert.match(storyData, /\.from\("saga_projects"\)/);
  assert.match(storyData, /\.from\("saga_sources"\)/);
  assert.match(storyData, /\.from\("saga_analysis_jobs"\)/);
  assert.match(storyData, /\.from\("saga_characters"\)/);
  assert.match(storyData, /\.eq\("owner_user_id", account\.userId\)/);
  assert.doesNotMatch(storyData, /createSupabasePrivilegedClient/);
  assert.doesNotMatch(storyData, /service[_-]?role/i);
});

test("project creation is a server action with bounded validation and no upload shortcut", () => {
  const actions = read("src/features/projects/actions.ts");
  const projectsPage = read("src/app/(app)/projects/page.tsx");

  assert.match(actions, /^"use server";/);
  assert.match(actions, /createSagaProject/);
  assert.match(actions, /revalidatePath\("\/projects"\)/);
  assert.match(actions, /project_created/);
  assert.match(projectsPage, /action=\{createProjectAction\}/);
  assert.match(projectsPage, /maxLength=\{160\}/);
  assert.match(projectsPage, /Source upload and ingestion attach to this project in the next Phase 2 slice/);
  assert.doesNotMatch(projectsPage, /type="file"/);
});

test("Projects and Library render real private records while Phase 2B upload stays deferred", () => {
  const projectsPage = read("src/app/(app)/projects/page.tsx");
  const projectWorkspace = read("src/app/(app)/projects/[projectId]/page.tsx");
  const libraryPage = read("src/app/(app)/library/page.tsx");

  assert.match(projectsPage, /listSagaProjects/);
  assert.match(projectWorkspace, /getSagaProjectWorkspace/);
  assert.match(projectWorkspace, /Sources/);
  assert.match(projectWorkspace, /Analysis/);
  assert.match(projectWorkspace, /Characters/);
  assert.match(projectWorkspace, /Unresolved mentions will not be counted as canonicals/);
  assert.match(libraryPage, /listSagaSources/);
  assert.match(libraryPage, /Uploading new UTF-8 text or EPUB files begins in Phase 2B/);
  assert.doesNotMatch(`${projectWorkspace}\n${libraryPage}`, /createUploadUrl|<input[^>]+type="file"/i);
});

test("Phase 2A database contract exercises owner isolation and stale worker leases", () => {
  const contract = read("supabase/tests/story_intelligence_foundation.sql");

  assert.match(contract, /cross-user project read leaked/);
  assert.match(contract, /suspended user should not see project rows/);
  assert.match(contract, /duplicate active enqueue was not idempotent/);
  assert.match(contract, /active lease allowed a second worker claim/);
  assert.match(contract, /stale lease token could finish a newer attempt/);
  assert.match(contract, /cross-user character read leaked/);
  assert.match(contract, /ambiguous_pronoun_attachment/);
});
