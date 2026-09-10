import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "../..");
const srcRoot = join(webRoot, "src");

function collectFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? collectFiles(path) : [path];
  });
}

function read(relativePath) {
  return readFileSync(join(webRoot, relativePath), "utf8");
}

test("closed demo exposes no public sign-up operation", () => {
  const runtimeSource = collectFiles(srcRoot)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");

  assert.equal(runtimeSource.includes(".auth.signUp("), false);
  assert.equal(runtimeSource.includes('href="/signup"'), false);
  assert.match(read("src/features/account/login-form.tsx"), /invitation only/i);
});

test("service-role capability remains inside server source", () => {
  const serviceRoleUsers = collectFiles(srcRoot)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .filter((path) => readFileSync(path, "utf8").includes("SUPABASE_SERVICE_ROLE_KEY"))
    .map((path) => path.replaceAll("\\", "/"));

  assert.equal(serviceRoleUsers.length, 1);
  assert.match(serviceRoleUsers[0], /\/src\/server\/supabase\/config\.ts$/);
  assert.equal(read("src/lib/supabase/browser.ts").includes("SERVICE_ROLE"), false);
});

test("private application layout fails closed through server account state", () => {
  const layout = read("src/app/app/layout.tsx");
  assert.match(layout, /getCurrentSagaAccountState/);
  assert.match(layout, /state\.status !== "active"/);
  assert.match(layout, /redirect\("\/login"\)/);
});

test("admin invitation routes require active SAGA admin authorization", () => {
  const createRoute = read("src/app/api/admin/invitations/route.ts");
  const revokeRoute = read("src/app/api/admin/invitations/[invitationId]/route.ts");
  assert.match(createRoute, /isActiveSagaAdmin/);
  assert.match(revokeRoute, /isActiveSagaAdmin/);
  assert.match(createRoute, /SAGA_PUBLIC_APP_URL/);
});

test("closed-demo migration denies direct browser table access", () => {
  const migration = read("supabase/migrations/0001_closed_demo_access.sql");
  assert.match(migration, /enable row level security/);
  assert.match(migration, /revoke all on table public\.saga_account_access from anon, authenticated/);
  assert.match(migration, /revoke all on table public\.saga_invitations from anon, authenticated/);
  assert.match(migration, /grant execute on function public\.saga_claim_invitation\(uuid, text\) to service_role/);
});
