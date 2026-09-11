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

test("privileged Supabase config prefers the modern secret API key", () => {
  const config = read("src/server/supabase/config.ts");
  const modernIndex = config.indexOf('"SUPABASE_SECRET_KEY"');
  const legacyIndex = config.indexOf('"SUPABASE_SERVICE_ROLE_KEY"');

  assert.ok(modernIndex >= 0, "modern Supabase secret key variable is missing");
  assert.ok(legacyIndex >= 0, "legacy service-role fallback is missing");
  assert.ok(
    modernIndex < legacyIndex,
    "modern Supabase secret key must be preferred before the legacy fallback",
  );
});

test("environment template keeps the privileged key server-only by naming convention", () => {
  const envExample = read(".env.example");

  assert.match(envExample, /^SUPABASE_SECRET_KEY=$/m);
  assert.doesNotMatch(envExample, /NEXT_PUBLIC_SUPABASE_SECRET_KEY/);
  assert.doesNotMatch(envExample, /PUBLIC_SUPABASE_SECRET_KEY/);
});
