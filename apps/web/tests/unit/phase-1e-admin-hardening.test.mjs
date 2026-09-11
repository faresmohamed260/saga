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

test("Admin API route identifiers use canonical UUID-shape validation", () => {
  const validation = read("src/server/admin/validation.ts");
  const invitationRoute = read("src/app/api/admin/invitations/[invitationId]/route.ts");
  const accountRoute = read("src/app/api/admin/accounts/[userId]/route.ts");

  assert.match(validation, /\{8\}.*\{4\}.*\{4\}.*\{4\}.*\{12\}/s);
  assert.match(invitationRoute, /isCanonicalUuid\(invitationId\)/);
  assert.match(accountRoute, /isCanonicalUuid\(userId\)/);
  assert.match(invitationRoute, /invalid_request/);
  assert.match(accountRoute, /invalid_request/);
});

test("settled invitation revocation is explicitly non-mutating", () => {
  const hardeningMigration = read("supabase/migrations/20260911174500_admin_operation_hardening.sql");
  const databaseTest = read("supabase/tests/admin_operation_hardening.sql");

  assert.match(hardeningMigration, /v_invitation\.status <> 'pending'/);
  assert.match(databaseTest, /settled invitation unexpectedly returned a revoke result/);
  assert.match(databaseTest, /status = 'accepted'/);
});
