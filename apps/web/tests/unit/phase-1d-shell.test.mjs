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

test("Phase 1D private layout keeps access enforcement and renders the Narrative Desk shell", () => {
  const layout = read("src/app/(app)/layout.tsx");

  assert.match(layout, /resolveCurrentSagaAccount\s*\(\)/);
  assert.match(layout, /<AppShell account=\{access\.account\}>\{children\}<\/AppShell>/);
  assert.match(layout, /case "unauthenticated"/);
  assert.match(layout, /case "not_admitted"/);
  assert.match(layout, /case "suspended"/);
  assert.match(layout, /case "unavailable"/);
});

test("Narrative Desk navigation exposes real Phase 1D destinations with accessible current state", () => {
  const navigation = read("src/components/shell/app-navigation.tsx");

  assert.match(navigation, /href: "\/home"/);
  assert.match(navigation, /href: "\/library"/);
  assert.match(navigation, /href: "\/projects"/);
  assert.match(navigation, /href: "\/settings"/);
  assert.match(navigation, /aria-current=\{current \? "page" : undefined\}/);
  assert.match(navigation, /<Dialog\.Title/);
  assert.match(navigation, /<Dialog\.Description/);
  assert.match(navigation, /signOutAction/);
});

test("Home, Library, and Projects remain honest about unavailable domain data", () => {
  const home = read("src/app/(app)/home/page.tsx");
  const library = read("src/app/(app)/library/page.tsx");
  const projects = read("src/app/(app)/projects/page.tsx");

  assert.match(home, /Phase 1D establishes the product frame without inventing story data/);
  assert.match(library, /No sources yet/);
  assert.match(library, /Source ingestion is not part of Phase 1D/);
  assert.match(projects, /No projects yet/);
  assert.match(projects, /Project persistence and creation have not shipped yet/);

  const combined = `${home}\n${library}\n${projects}`;
  assert.doesNotMatch(combined, /\b\d+\s+(sources|projects|characters|jobs)\b/i);
  assert.doesNotMatch(combined, /model status|provider status|storage usage/i);
});

test("private-workspace styling defines dedicated Narrative Desk tokens and reduced-motion behavior", () => {
  const css = read("src/app/globals.css");

  assert.match(css, /\.saga-app\s*\{/);
  assert.match(css, /--app-canvas:\s*#0b0c0e/);
  assert.match(css, /--app-rail:\s*#101215/);
  assert.match(css, /--app-accent:/);
  assert.match(css, /--font-narrative:/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});
