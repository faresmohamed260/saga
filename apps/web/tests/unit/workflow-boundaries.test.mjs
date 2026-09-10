import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../../..");

function readRepo(relativePath) {
  return readFileSync(resolve(repoRoot, relativePath), "utf8");
}

test("B2 bootstrap is manual-only after initial provisioning", () => {
  const workflow = readRepo(".github/workflows/v2-b2-bootstrap.yml");
  assert.match(workflow, /workflow_dispatch:/);
  assert.doesNotMatch(workflow, /^\s*push:/m);
  assert.doesNotMatch(workflow, /^\s*pull_request:/m);
});

test("B2 bootstrap consumes only the dedicated bootstrap master-secret names", () => {
  const workflow = readRepo(".github/workflows/v2-b2-bootstrap.yml");
  assert.match(workflow, /secrets\.SAGA_B2_KEY_ID/);
  assert.match(workflow, /secrets\.SAGA_B2_MASTER_APPLICATION_KEY/);
  assert.doesNotMatch(workflow, /secrets\.SAGA_B2_APPLICATION_KEY_ID/);
  assert.doesNotMatch(workflow, /secrets\.SAGA_B2_APPLICATION_KEY(?!_)/);
});

test("B2 bootstrap does not publish artifacts or source data", () => {
  const workflow = readRepo(".github/workflows/v2-b2-bootstrap.yml");
  assert.doesNotMatch(workflow, /actions\/upload-artifact/);
  assert.match(workflow, /_system\/bootstrap/);
  assert.match(workflow, /b2 rm/);
});

test("v2 web CI covers the complete deterministic quality gate", () => {
  const workflow = readRepo(".github/workflows/v2-web-ci.yml");
  for (const command of ["npm run lint", "npm run typecheck", "npm run test:unit", "npm run build"]) {
    assert.match(workflow, new RegExp(command.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});
