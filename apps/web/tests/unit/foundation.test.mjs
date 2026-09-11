import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
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

test("web runtime never consumes the B2 master bootstrap secret", () => {
  const runtimeSource = collectFiles(srcRoot)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");

  assert.equal(runtimeSource.includes("SAGA_B2_MASTER_APPLICATION_KEY"), false);
  assert.equal(runtimeSource.includes("SAGA_B2_KEY_ID"), false);
  assert.match(runtimeSource, /SAGA_B2_APPLICATION_KEY_ID/);
  assert.match(runtimeSource, /SAGA_B2_APPLICATION_KEY/);
});

test("storage SDK construction stays inside the storage infrastructure boundary", () => {
  const sdkUsers = collectFiles(srcRoot)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .filter((path) => readFileSync(path, "utf8").includes("@aws-sdk/"))
    .map((path) => path.replaceAll("\\", "/"));

  assert.equal(sdkUsers.length, 1);
  assert.match(sdkUsers[0], /\/src\/server\/storage\/b2\.ts$/);
});

test("health route reports v2 integration readiness and non-secret release identity without contacting providers", () => {
  const healthRoute = read("src/app/api/health/route.ts");
  assert.match(healthRoute, /architecture: "v2"/);
  assert.match(healthRoute, /VERCEL_GIT_COMMIT_SHA/);
  assert.match(healthRoute, /VERCEL_ENV/);
  assert.doesNotMatch(healthRoute, /SUPABASE_SECRET_KEY/);
  assert.doesNotMatch(healthRoute, /createObjectStorage\(/);
  assert.doesNotMatch(healthRoute, /createSupabaseServerClient\(/);
});

test("web package exposes the deterministic v2 quality gate", () => {
  const pkg = JSON.parse(read("package.json"));
  for (const script of ["lint", "typecheck", "test:unit", "build"]) {
    assert.equal(typeof pkg.scripts[script], "string", `missing ${script} script`);
  }
});
