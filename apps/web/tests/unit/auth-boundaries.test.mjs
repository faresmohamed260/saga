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
  assert.match(read("src/app/page.tsx"), /invitation-only/i);
});

test("Supabase secret-key capability remains inside server source", () => {
  const runtimeFiles = collectFiles(srcRoot).filter((path) => /\.(ts|tsx)$/.test(path));
  const secretKeyUsers = runtimeFiles
    .filter((path) => readFileSync(path, "utf8").includes("SUPABASE_SECRET_KEY"))
    .map((path) => path.replaceAll("\\", "/"));
  const legacyServiceRoleUsers = runtimeFiles
    .filter((path) => readFileSync(path, "utf8").includes("SUPABASE_SERVICE_ROLE_KEY"));

  assert.equal(secretKeyUsers.length, 1);
  assert.match(secretKeyUsers[0], /\/src\/server\/supabase\/config\.ts$/);
  assert.equal(legacyServiceRoleUsers.length, 0);
  assert.equal(read("src/lib/supabase/browser.ts").includes("SECRET_KEY"), false);
});

test("private application layout fails closed through server account state", () => {
  const layout = read("src/app/app/layout.tsx");
  assert.match(layout, /getCurrentSagaAccountState/);
  assert.match(layout, /state\.status !== "active"/);
  assert.match(layout, /redirect\("\/login"\)/);
});

test("admin routes require active SAGA admin authorization", () => {
  const invitationRoute = read("src/app/api/admin/invitations/route.ts");
  const invitationDeleteRoute = read("src/app/api/admin/invitations/[invitationId]/route.ts");
  const accountListRoute = read("src/app/api/admin/accounts/route.ts");
  const accountUpdateRoute = read("src/app/api/admin/accounts/[userId]/route.ts");
  for (const source of [invitationRoute, invitationDeleteRoute, accountListRoute, accountUpdateRoute]) {
    assert.match(source, /isActiveSagaAdmin/);
  }
  assert.match(invitationRoute, /SAGA_PUBLIC_APP_URL/);
  assert.doesNotMatch(invitationRoute, /request\.nextUrl\.origin/);
});

test("invitation confirmation claims access before password setup", () => {
  const confirmRoute = read("src/app/auth/confirm/route.ts");
  const passwordForm = read("src/features/account/set-password-form.tsx");
  assert.match(confirmRoute, /claimSagaInvitation/);
  assert.match(confirmRoute, /\/app\/welcome/);
  assert.match(passwordForm, /auth\.updateUser\(\{ password \}\)/);
  assert.doesNotMatch(passwordForm, /signUp/);
});

test("hosted invitation template contract is documented for SSR token-hash confirmation", () => {
  const supabaseReadme = read("supabase/README.md");
  assert.match(supabaseReadme, /\{\{ \.RedirectTo \}\}\?token_hash=\{\{ \.TokenHash \}\}&type=invite/);
  assert.match(supabaseReadme, /SUPABASE_SECRET_KEY/);
});

test("closed-demo migration denies browser access and protects admin mutations", () => {
  const migration = read("supabase/migrations/0001_closed_demo_access.sql");
  assert.match(migration, /enable row level security/);
  assert.match(migration, /revoke all on table public\.saga_account_access from anon, authenticated/);
  assert.match(migration, /revoke all on table public\.saga_invitations from anon, authenticated/);
  assert.match(migration, /grant execute on function public\.saga_claim_invitation\(uuid, text\) to service_role/);
  assert.match(migration, /saga_admin_self_lockout/);
  assert.match(migration, /saga_admin_last_active_admin/);
  assert.match(migration, /grant execute on function public\.saga_admin_set_account_access\(uuid, uuid, text, text\) to service_role/);
});
