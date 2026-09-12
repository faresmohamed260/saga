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

test("Narrative Desk navigation exposes real destinations with accessible current state", () => {
  const navigation = read("src/components/shell/app-navigation.tsx");

  assert.match(navigation, /href: "\/home"/);
  assert.match(navigation, /href: "\/library"/);
  assert.match(navigation, /href: "\/projects"/);
  assert.match(navigation, /href: "\/settings"/);
  assert.match(navigation, /aria-current=\{current \? "page" : undefined\}/);
  assert.match(navigation, /<Dialog\.Title/);
  assert.match(navigation, /<Dialog\.Description/);
  assert.match(navigation, /saga-portal-theme/);
  assert.match(navigation, /saga-nav-sheet/);
  assert.match(navigation, /signOutAction/);
});

test("Home, Library, and Projects stay honest as Phase 2B activates bounded source ingestion", () => {
  const home = read("src/app/(app)/home/page.tsx");
  const library = read("src/app/(app)/library/page.tsx");
  const projects = read("src/app/(app)/projects/page.tsx");
  const projectWorkspace = read("src/app/(app)/projects/[projectId]/page.tsx");

  assert.match(home, /Add UTF-8 text or EPUB sources from a project workspace/);
  assert.match(home, /ingestion runs outside the web request/);
  assert.match(library, /listSagaSources/);
  assert.match(library, /No sources yet/);
  assert.match(library, /Upload completion is verified before ingestion work is queued/);
  assert.match(projects, /listSagaProjects/);
  assert.match(projects, /action=\{createProjectAction\}/);
  assert.match(projects, /No projects yet/);
  assert.match(projectWorkspace, /<SourceUploadForm projectId=\{workspace\.project\.id\}/);

  const combined = `${home}\n${library}\n${projects}\n${projectWorkspace}`;
  assert.doesNotMatch(combined, /model status|provider status|storage usage/i);
  assert.doesNotMatch(combined, /Phase 1D|Phase 1E/);
});

test("private-workspace styling themes portaled UI and defines reduced-motion behavior", () => {
  const css = read("src/app/globals.css");

  assert.match(css, /\.saga-app,\s*\n\.saga-portal-theme\s*\{/);
  assert.match(css, /--app-canvas:\s*#0b0c0e/);
  assert.match(css, /--app-rail:\s*#101215/);
  assert.match(css, /--app-accent:/);
  assert.match(css, /--font-narrative:/);
  assert.match(css, /\.saga-nav-sheet\[data-state="open"\]/);
  assert.match(css, /\.saga-nav-overlay\[data-state="open"\]/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.saga-portal-theme \*/);
});
