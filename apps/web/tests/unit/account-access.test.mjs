import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "../..");
const srcRoot = join(webRoot, "src");
const migrationPath = join(
  webRoot,
  "supabase/migrations/20260911142000_closed_demo_account_access.sql",
);

function collectFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? collectFiles(path) : [path];
  });
}

function read(relativePath) {
  return readFileSync(join(webRoot, relativePath), "utf8");
}

const sourceFiles = collectFiles(srcRoot).filter((path) => /\.(ts|tsx)$/.test(path));

test("v2 account and invitation migration is isolated from the historical root lineage", () => {
  const readme = read("supabase/README.md");
  assert.match(readme, /active v2 database lineage/i);
  assert.match(readme, /do not apply those root migrations/i);
  assert.equal(migrationPath.includes("apps/web/supabase/migrations"), true);
  assert.equal(readFileSync(migrationPath, "utf8").length > 0, true);
});

test("closed-demo schema owns access and invitation state behind RLS", () => {
  const sql = readFileSync(migrationPath, "utf8");

  assert.match(sql, /create table public\.saga_account_access/i);
  assert.match(sql, /create table public\.saga_invitations/i);
  assert.match(sql, /role in \('member', 'admin'\)/i);
  assert.match(sql, /status in \('active', 'suspended'\)/i);
  assert.match(sql, /status in \('pending', 'accepted', 'revoked', 'expired'\)/i);
  assert.match(sql, /enable row level security/i);
  assert.match(sql, /force row level security/i);
  assert.match(sql, /revoke all on table public\.saga_account_access from public, anon, authenticated/i);
  assert.match(sql, /revoke all on table public\.saga_invitations from public, anon, authenticated/i);
  assert.doesNotMatch(sql, /grant\s+(?:all|select|insert|update|delete)[^;]*\s+to\s+(?:anon|authenticated)/i);
});

test("invitation records cannot become a parallel token or credential store", () => {
  const sql = readFileSync(migrationPath, "utf8");
  const invitationTable = sql.match(
    /create table public\.saga_invitations \(([\s\S]*?)\n\);/i,
  );

  assert.ok(invitationTable, "saga_invitations table definition was not found");
  assert.doesNotMatch(invitationTable[1], /\b(token|secret|otp|password|credential)\b/i);
  assert.match(sql, /saga_invitations_one_pending_email_idx/i);
  assert.match(sql, /where status = 'pending'/i);
});

test("invitation claim independently verifies the Auth email and serializes the claim", () => {
  const sql = readFileSync(migrationPath, "utf8");

  assert.match(sql, /create or replace function public\.saga_claim_invitation\(p_user_id uuid\)/i);
  assert.match(sql, /security definer/i);
  assert.match(sql, /set search_path = ''/i);
  assert.match(sql, /from auth\.users as u/i);
  assert.match(sql, /public\.saga_normalize_email\(v_email\)/i);
  assert.match(sql, /for update/i);
  assert.match(sql, /set status = 'accepted'/i);
  assert.match(sql, /grant execute on function public\.saga_claim_invitation\(uuid\) to service_role/i);
  assert.match(sql, /revoke all on function public\.saga_claim_invitation\(uuid\) from public, anon, authenticated/i);
});

test("private identity uses a fresh Auth server lookup and never browser metadata roles", () => {
  const identity = read("src/server/account/identity.ts");
  const accountAccess = read("src/server/account/account-access.ts");
  const adminAuth = read("src/server/admin/admin-auth.ts");

  assert.match(identity, /auth\.getUser\(\)/);
  assert.doesNotMatch(identity, /user_metadata/);
  assert.doesNotMatch(accountAccess, /user_metadata/);
  assert.match(accountAccess, /\.from\("saga_account_access"\)/);
  assert.match(adminAuth, /account\.role !== "admin"/);
});

test("service-role configuration stays inside the server Supabase boundary", () => {
  const secretUsers = sourceFiles
    .filter((path) => readFileSync(path, "utf8").includes("SUPABASE_SERVICE_ROLE_KEY"))
    .map((path) => path.replaceAll("\\", "/"));

  assert.equal(secretUsers.length, 1);
  assert.match(secretUsers[0], /\/src\/server\/supabase\/config\.ts$/);

  for (const path of sourceFiles) {
    const source = readFileSync(path, "utf8");
    if (/^["']use client["'];/m.test(source)) {
      assert.doesNotMatch(source, /SUPABASE_SERVICE_ROLE_KEY/);
      assert.doesNotMatch(source, /@\/server\/supabase\/privileged/);
      assert.doesNotMatch(source, /@\/server\/account\/account-access/);
      assert.doesNotMatch(source, /@\/server\/admin\/admin-auth/);
    }
  }
});

test("the active web source exposes no public Supabase sign-up call", () => {
  const runtimeSource = sourceFiles.map((path) => readFileSync(path, "utf8")).join("\n");
  assert.doesNotMatch(runtimeSource, /\.auth\.signUp\s*\(/);
  assert.doesNotMatch(runtimeSource, /create account/i);
});
