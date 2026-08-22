import { readFile, writeFile } from 'node:fs/promises';
const path = 'scripts/capture-ui-preview.mjs';
let source = await readFile(path, 'utf8');
const before = `  const settingsButton = desktop.getByRole('button', { name: 'Advanced settings' });\n  await settingsButton.click();\n  const settingsPanel = desktop.locator('.advanced-settings-shell');`;
const after = `  const advancedSettingsButton = desktop.getByRole('button', { name: 'Advanced settings' });\n  await advancedSettingsButton.click();\n  const settingsPanel = desktop.locator('.advanced-settings-shell');`;
if (!source.includes(before)) throw new Error('Target advanced settings QA block not found');
source = source.replace(before, after);
await writeFile(path, source);
