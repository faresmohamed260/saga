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

test("Phase 1C auth surfaces use supported Auth operations without public signup", () => {
  const actions = read("src/features/auth/actions.ts");
  const confirm = read("src/app/(auth)/auth/confirm/route.ts");
  const combined = `${actions}\n${confirm}`;

  assert.match(actions, /auth\.signInWithPassword\s*\(/);
  assert.match(actions, /auth\.updateUser\s*\(\{ password \}\)/);
  assert.match(actions, /auth\.signOut\s*\(\)/);
  assert.match(confirm, /auth\.verifyOtp\s*\(/);
  assert.match(confirm, /type:\s*"invite"/);
  assert.match(confirm, /claimCurrentSagaInvitation\s*\(\)/);
  assert.doesNotMatch(combined, /auth\.signUp\s*\(/);
});

test("same-origin next-path helper rejects external and confirmation destinations", () => {
  const redirects = read("src/lib/auth/redirects.ts");

  assert.match(redirects, /candidateValue\.startsWith\("\/"\)/);
  assert.match(redirects, /candidateValue\.startsWith\("\/\/"\)/);
  assert.match(redirects, /candidateValue\.includes\("\\\\"\)/);
  assert.match(redirects, /candidate\.origin !== base\.origin/);
  assert.match(redirects, /candidate\.pathname === "\/auth\/confirm"/);
});

test("proxy refreshes SSR cookies but does not replace private authorization", () => {
  const proxy = read("src/server/supabase/proxy.ts");
  const rootProxy = read("src/proxy.ts");

  assert.match(proxy, /createServerClient/);
  assert.match(proxy, /request\.cookies\.getAll\(\)/);
  assert.match(proxy, /response\.cookies\.set/);
  assert.match(proxy, /auth\.getUser\(\)/);
  assert.doesNotMatch(proxy, /saga_account_access/);
  assert.match(rootProxy, /refreshSupabaseSession/);
});

test("private layout fails closed for every non-active account state", () => {
  const layout = read("src/app/(app)/layout.tsx");

  assert.match(layout, /resolveCurrentSagaAccount\s*\(\)/);
  assert.match(layout, /case "active"/);
  assert.match(layout, /case "unauthenticated"/);
  assert.match(layout, /case "not_admitted"/);
  assert.match(layout, /case "suspended"/);
  assert.match(layout, /case "unavailable"/);
  assert.match(layout, /redirect\("\/sign-in\?next=\/home"\)/);
  assert.match(layout, /redirect\("\/access\/not-admitted"\)/);
  assert.match(layout, /redirect\("\/access\/suspended"\)/);
  assert.match(layout, /redirect\("\/access\/unavailable"\)/);
});

test("account resolver converts provider/config failures into bounded unavailable state", () => {
  const accountAccess = read("src/server/account/account-access.ts");
  const unavailableReturns = accountAccess.match(/return \{ state: "unavailable" \};/g) ?? [];

  assert.ok(unavailableReturns.length >= 3);
  assert.match(accountAccess, /try \{\s*identity = await getFreshSagaIdentity\(\)/);
  assert.match(accountAccess, /try \{\s*const privileged = createSupabasePrivilegedClient\(\)/);
});
