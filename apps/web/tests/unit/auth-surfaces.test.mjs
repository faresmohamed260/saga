import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import test from "node:test";

const webRoot = resolve(import.meta.dirname, "../..");
const read = (path) => readFileSync(join(webRoot, path), "utf8");

test("Phase 1C exposes sign-in without public signup", () => {
  const page = read("src/app/sign-in/page.tsx");
  const actions = read("src/server/auth/actions.ts");

  assert.match(page, /action=\{signInAction\}/);
  assert.match(actions, /auth\.signInWithPassword/);
  assert.doesNotMatch(page, /create account|sign up/i);
  assert.doesNotMatch(actions, /auth\.signUp/);
});

test("invitation confirmation verifies an Auth invite before S.A.G.A. claim", () => {
  const route = read("src/app/auth/confirm/route.ts");

  assert.match(route, /type !== "invite"/);
  assert.match(route, /auth\.verifyOtp/);
  assert.match(route, /type: "invite"/);
  assert.match(route, /claimCurrentSagaInvitation/);
  assert.doesNotMatch(route, /service[_-]?role|SUPABASE_SERVICE_ROLE_KEY/i);
});

test("private layout resolves fresh S.A.G.A. account state and fails closed", () => {
  const layout = read("src/app/(app)/layout.tsx");
  const accountAccess = read("src/server/account/account-access.ts");

  assert.match(layout, /resolveCurrentSagaAccount/);
  assert.match(layout, /case "unauthenticated"/);
  assert.match(layout, /case "not_admitted"/);
  assert.match(layout, /case "suspended"/);
  assert.match(layout, /case "unavailable"/);
  assert.match(accountAccess, /catch \{/);
  assert.match(accountAccess, /state: "unavailable"/);
});

test("SSR proxy refreshes Supabase cookies but does not authorize product access", () => {
  const proxy = read("src/proxy.ts");

  assert.match(proxy, /createServerClient/);
  assert.match(proxy, /auth\.getUser\(\)/);
  assert.match(proxy, /response\.cookies\.set/);
  assert.doesNotMatch(proxy, /saga_account_access|role === "admin"|status === "active"/);
});

test("password mutation is session-bound and sign-out is supported", () => {
  const actions = read("src/server/auth/actions.ts");
  const passwordPage = read("src/app/set-password/page.tsx");

  assert.match(passwordPage, /getFreshSagaIdentity/);
  assert.match(actions, /auth\.updateUser\(\{ password \}\)/);
  assert.match(actions, /auth\.signOut\(\)/);
});

test("same-origin next paths are normalized before redirects", () => {
  const redirectHelper = read("src/lib/auth/redirect.ts");
  const actions = read("src/server/auth/actions.ts");
  const confirmation = read("src/app/auth/confirm/route.ts");

  assert.match(redirectHelper, /candidate\.startsWith\("\/"\)/);
  assert.match(redirectHelper, /candidate\.startsWith\("\/\/"\)/);
  assert.match(redirectHelper, /parsed\.origin !== SAFE_ORIGIN/);
  assert.match(actions, /safeNextPath/);
  assert.match(confirmation, /safeNextPath/);
});
