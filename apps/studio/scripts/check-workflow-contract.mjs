import fs from 'node:fs';

const clientPath = new URL('../src/generation-client.js', import.meta.url);
const registryPath = new URL('../api/_workflows.js', import.meta.url);

const clientSource = fs.readFileSync(clientPath, 'utf8');
const registrySource = fs.readFileSync(registryPath, 'utf8');

const submittedIds = new Set(
  [...clientSource.matchAll(/workflowId:\s*['"]([^'"]+)['"]/g)].map((match) => match[1]),
);
const registeredIds = new Set(
  [...registrySource.matchAll(/^  '([^']+)':\s*\{/gm)].map((match) => match[1]),
);

const missing = [...submittedIds].filter((id) => !registeredIds.has(id));
if (missing.length) {
  throw new Error(`Studio submits unregistered generation workflow id(s): ${missing.join(', ')}`);
}

if (!submittedIds.has('ltx25-redgraft-video') || !registeredIds.has('ltx25-redgraft-video')) {
  throw new Error('REDGraft LTX 2.5 workflow contract is incomplete.');
}

console.log(`Workflow contract OK: ${[...submittedIds].join(', ')}`);
