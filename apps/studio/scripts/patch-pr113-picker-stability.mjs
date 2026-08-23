import { readFile, writeFile } from 'node:fs/promises';

// One-shot remote patch for picker opening stability and reset icon alignment.
function replaceOnce(source, from, to, label) {
  if (source.includes(to)) return source;
  if (!source.includes(from)) throw new Error(`Missing ${label}`);
  return source.replace(from, to);
}

const cssPath = 'src/create-workspace-v2.css';
let css = await readFile(cssPath, 'utf8');
css = replaceOnce(
  css,
  `.workspace .saga-picker,\n.workspace .saga-advanced-panel{\n  z-index:1600;`,
  `.workspace .saga-picker,\n.workspace .saga-advanced-panel{\n  position:fixed;\n  z-index:1600;`,
  'picker fixed positioning',
);
css = replaceOnce(
  css,
  `.workspace .saga-reset{width:100%;height:40px;margin-top:10px;border:1px solid #403760;border-radius:11px;background:#171427;color:#beb6e3;font-size:10px;font-weight:700;cursor:pointer}\n.workspace .saga-reset:hover{background:#211c37;color:#fff}`,
  `.workspace .saga-reset{width:100%;height:40px;margin-top:10px;display:flex;align-items:center;justify-content:center;gap:7px;line-height:1;border:1px solid #403760;border-radius:11px;background:#171427;color:#beb6e3;font-size:10px;font-weight:700;cursor:pointer}\n.workspace .saga-reset svg{display:block;flex:none}\n.workspace .saga-reset:hover{background:#211c37;color:#fff}`,
  'reset button alignment',
);
await writeFile(cssPath, css);

const qaPath = 'scripts/capture-ui-preview.mjs';
let qa = await readFile(qaPath, 'utf8');
qa = replaceOnce(
  qa,
  `  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });\n  await aspectTrigger.click();\n  const aspectPicker = desktop.locator('.saga-aspect-picker');`,
  `  const aspectTrigger = desktop.locator('.saga-control-pill').filter({ has: desktop.locator('.saga-aspect-icon') });\n  await desktop.evaluate(() => {\n    const wall = document.querySelector('.saga-output-wall');\n    const baseline = wall?.getBoundingClientRect().top ?? null;\n    window.__sagaPickerBirth = null;\n    const observer = new MutationObserver(() => {\n      const picker = document.querySelector('.saga-picker');\n      if (!picker) return;\n      const nextTop = wall?.getBoundingClientRect().top ?? null;\n      window.__sagaPickerBirth = {\n        position: getComputedStyle(picker).position,\n        delta: baseline == null || nextTop == null ? 0 : Math.abs(nextTop - baseline),\n      };\n      observer.disconnect();\n    });\n    observer.observe(document.body, { childList: true, subtree: true });\n  });\n  await aspectTrigger.click();\n  const aspectPicker = desktop.locator('.saga-aspect-picker');`,
  'picker birth instrumentation',
);
qa = replaceOnce(
  qa,
  `  await aspectPicker.waitFor({ state: 'visible' });\n  await shot(desktop, '02-image-aspect-picker.png');`,
  `  await aspectPicker.waitFor({ state: 'visible' });\n  const pickerBirth = await desktop.evaluate(() => window.__sagaPickerBirth);\n  if (!pickerBirth || pickerBirth.position !== 'fixed' || pickerBirth.delta > 1) throw new Error(\`Picker caused opening reflow: \${JSON.stringify(pickerBirth)}\`);\n  await shot(desktop, '02-image-aspect-picker.png');`,
  'picker no-reflow assertion',
);
qa = replaceOnce(
  qa,
  `  await shot(desktop, '03-advanced-custom-dropdown.png');`,
  `  const resetButton = advanced.locator('.saga-reset');\n  const resetLayout = await resetButton.evaluate((button) => {\n    const icon = button.querySelector('svg');\n    if (!icon) return null;\n    const b = button.getBoundingClientRect();\n    const i = icon.getBoundingClientRect();\n    return { buttonCenter: b.top + b.height / 2, iconCenter: i.top + i.height / 2 };\n  });\n  if (!resetLayout || Math.abs(resetLayout.buttonCenter - resetLayout.iconCenter) > 1.5) throw new Error(\`Reset icon is vertically misaligned: \${JSON.stringify(resetLayout)}\`);\n  await shot(desktop, '03-advanced-custom-dropdown.png');`,
  'reset icon alignment assertion',
);
await writeFile(qaPath, qa);
