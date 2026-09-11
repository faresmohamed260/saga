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

test("Phase 1E admin APIs stay behind the fresh active-admin boundary", () => {
  const adminAuth = read("src/server/admin/admin-auth.ts");
  const operations = read("src/server/admin/admin-operations.ts");
  const invitationsApi = read("src/app/api/admin/invitations/route.ts");
  const accountsApi = read("src/app/api/admin/accounts/route.ts");

  assert.match(adminAuth, /requireCurrentSagaAccount\s*\(\)/);
  assert.match(adminAuth, /account\.role !== "admin"/);
  assert.match(operations, /requireCurrentSagaAdmin\s*\(\)/);
  assert.match(invitationsApi, /createOrRetrySagaInvitation/);
  assert.match(accountsApi, /listSagaAdminAccounts/);
  assert.doesNotMatch(operations, /auth\.admin\.listUsers/);
});

test("admin account directory begins with S.A.G.A.-owned access rows", () => {
  const operations = read("src/server/admin/admin-operations.ts");

  assert.match(operations, /\.from\("saga_account_access"\)/);
  assert.match(operations, /auth\.admin\.getUserById\(row\.user_id\)/);
  assert.doesNotMatch(operations, /listUsers/);
});

test("invitation delivery preserves product intent and returns bounded status", () => {
  const operations = read("src/server/admin/admin-operations.ts");

  const persistIndex = operations.indexOf("saga_admin_upsert_invitation_intent");
  const deliveryIndex = operations.indexOf("inviteUserByEmail");
  assert.ok(persistIndex >= 0 && deliveryIndex > persistIndex, "product invitation intent must persist before delivery is attempted");
  assert.match(operations, /delivery:\s*deliveryError \? "failed" : "sent"/);
});

test("Phase 1E migration protects admin mutations transactionally", () => {
  const migration = read("supabase/migrations/20260911173500_admin_operations.sql");

  assert.match(migration, /saga_assert_active_admin/);
  assert.match(migration, /saga_admin_upsert_invitation_intent/);
  assert.match(migration, /pg_advisory_xact_lock/);
  assert.match(migration, /saga_admin_self_lockout/);
  assert.match(migration, /saga_last_active_admin/);
  assert.match(migration, /revoke all on function public\.saga_admin_update_account[^;]+from public, anon, authenticated/si);
  assert.match(migration, /grant execute on function public\.saga_admin_update_account[^;]+to service_role/si);
});

test("Narrative Desk exposes Admin navigation only from server-derived role state", () => {
  const shell = read("src/components/shell/app-shell.tsx");
  const navigation = read("src/components/shell/app-navigation.tsx");

  assert.match(shell, /account\.role === "admin"/);
  assert.match(shell, /isAdmin=\{isAdmin\}/);
  assert.match(navigation, /href: "\/admin"/);
  assert.match(navigation, /isAdmin \? \[adminItem, settingsItem\] : \[settingsItem\]/);
});

test("Admin product surface stays bounded to invitations and admitted accounts", () => {
  const page = read("src/app/(app)/admin/page.tsx");
  const workspace = read("src/features/admin/admin-workspace.tsx");

  assert.match(page, /requireCurrentSagaAdmin/);
  assert.match(page, /listSagaAdminInvitations/);
  assert.match(page, /listSagaAdminAccounts/);
  assert.match(page, /<AdminWorkspace/);
  assert.match(workspace, /Self-demotion and self-suspension are blocked/);
  assert.match(workspace, /S\.A\.G\.A\.-owned invitations and admitted accounts/);
  assert.doesNotMatch(`${page}\n${workspace}`, /storage usage|model status|provider status|auth\.users/i);
});
