from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} replacement count was {count}")
    target.write_text(text.replace(old, new, 1))


replace_once(
    "src/create-controls.jsx",
    """              >
                <ArrowUp size={21} />
              </button>
""",
    """              >
                <span className=\"saga-submit-label\">{isEdit ? 'Edit' : 'Generate'}</span>
                <ArrowUp size={18} aria-hidden=\"true\" />
              </button>
""",
    "Generate button markup",
)

replace_once(
    "src/create-workspace-v2.css",
    """.workspace .saga-round-button,
.workspace .saga-settings-button,
.workspace .saga-submit{
  width:36px;height:36px;flex:0 0 36px;display:grid;place-items:center;border:1px solid #272c35;border-radius:50%;background:#171b21;color:#b7beca;cursor:pointer;transition:.18s ease;
}
.workspace .saga-round-button:hover,.workspace .saga-settings-button:hover{background:#20252d;color:#fff;border-color:#363d49}
.workspace .saga-settings-button.active{color:#ddd7ff;background:#242039;border-color:#5d4db0}
.workspace .saga-submit{background:#f1f1ef;color:#101216;border-color:#f1f1ef}
.workspace .saga-submit:hover:not(:disabled){transform:translateY(-1px);background:#fff}
.workspace .saga-submit:disabled{opacity:.28;cursor:not-allowed}
""",
    """.workspace .saga-round-button,
.workspace .saga-settings-button{
  width:36px;height:36px;flex:0 0 36px;display:grid;place-items:center;border:1px solid #272c35;border-radius:50%;background:#171b21;color:#b7beca;cursor:pointer;transition:.18s ease;
}
.workspace .saga-round-button:hover,.workspace .saga-settings-button:hover{background:#20252d;color:#fff;border-color:#363d49}
.workspace .saga-settings-button.active{color:#ddd7ff;background:#242039;border-color:#5d4db0}
.workspace .saga-submit{
  min-width:112px;height:38px;flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:0 15px;border:1px solid #f1f1ef;border-radius:12px;background:#f1f1ef;color:#101216;font-size:11px;font-weight:800;letter-spacing:-.01em;cursor:pointer;box-shadow:0 8px 20px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.55);transition:transform .18s ease,background .18s ease,box-shadow .18s ease,opacity .18s ease;
}
.workspace .saga-submit-label{display:block;line-height:1}
.workspace .saga-submit svg{flex:0 0 auto;stroke-width:2.4}
.workspace .saga-submit:hover:not(:disabled){transform:translateY(-1px);background:#fff;box-shadow:0 10px 24px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.7)}
.workspace .saga-submit:active:not(:disabled){transform:translateY(0)}
.workspace .saga-submit:focus-visible{outline:2px solid #9f8cff;outline-offset:2px}
.workspace .saga-submit:disabled{opacity:.32;cursor:not-allowed;box-shadow:none}
""",
    "Generate desktop CSS",
)

replace_once(
    "src/create-workspace-v2.css",
    """  .workspace .saga-toolbar-left{gap:5px}
  .workspace .saga-toolbar-right{gap:5px}
  .workspace .saga-prompt-count{display:none}
""",
    """  .workspace .saga-toolbar-left{gap:5px}
  .workspace .saga-toolbar-right{gap:5px}
  .workspace .saga-submit{width:36px;height:36px;min-width:36px;flex-basis:36px;padding:0;border-radius:50%;box-shadow:none}
  .workspace .saga-submit-label{display:none}
  .workspace .saga-submit svg{width:21px;height:21px}
  .workspace .saga-prompt-count{display:none}
""",
    "Generate mobile CSS",
)

replace_once(
    "scripts/capture-ui-preview.mjs",
    """  if (Math.abs(composerCenter - workspaceCenter) > 70) throw new Error(`Composer is not centered: ${composerCenter} vs ${workspaceCenter}`);
  await shot(desktop, '01-create-image-centered.png');

  // Image picker keyboard, morphing and outside dismissal.
""",
    """  if (Math.abs(composerCenter - workspaceCenter) > 70) throw new Error(`Composer is not centered: ${composerCenter} vs ${workspaceCenter}`);
  const primarySubmit = desktop.locator('.saga-submit');
  await primarySubmit.waitFor({ state: 'visible' });
  if ((await primarySubmit.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Desktop primary action does not expose the Generate verb');
  if (await primarySubmit.getAttribute('aria-label') !== 'Generate image') throw new Error('Desktop primary action lost its mode-specific accessible name');
  const primarySubmitBox = await primarySubmit.boundingBox();
  if (!primarySubmitBox || primarySubmitBox.width < 100 || primarySubmitBox.width < primarySubmitBox.height * 2.4) throw new Error(`Desktop Generate action is not visually promoted as a primary verb: ${JSON.stringify(primarySubmitBox)}`);
  const primarySubmitStyle = await primarySubmit.evaluate((element) => {
    const style = getComputedStyle(element);
    return { display: style.display, fontWeight: Number(style.fontWeight), borderRadius: style.borderRadius };
  });
  if (!primarySubmitStyle.display.includes('flex') || primarySubmitStyle.fontWeight < 700) throw new Error(`Desktop Generate action styling is not sufficiently primary: ${JSON.stringify(primarySubmitStyle)}`);
  await shot(desktop, '01-create-image-centered.png');
  await shot(desktop, '01b-generate-primary.png');
  await primarySubmit.focus();
  await expectStrongFocus(primarySubmit, 'Generate primary action');

  // Image picker keyboard, morphing and outside dismissal.
""",
    "Desktop Generate visual contract",
)

replace_once(
    "scripts/capture-ui-preview.mjs",
    """  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });
  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');
""",
    """  await desktop.locator('.saga-media-toggle button').filter({ hasText: 'Video' }).click();
  await desktop.locator('.saga-composer.is-video').waitFor({ state: 'visible' });
  if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Generate') throw new Error('Video mode primary action does not retain the Generate verb');
  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Generate video') throw new Error('Video Generate action lost its mode-specific accessible name');
  const videoControls = desktop.locator('.saga-toolbar-left .saga-control-pill');
""",
    "Video Generate visual contract",
)

replace_once(
    "scripts/capture-ui-preview.mjs",
    """  const refChips = desktop.locator('.saga-reference-chip');
  await refChips.nth(1).waitFor({ state: 'visible', timeout: 5000 });
  const richPrompt = desktop.locator('.saga-rich-prompt');
""",
    """  const refChips = desktop.locator('.saga-reference-chip');
  await refChips.nth(1).waitFor({ state: 'visible', timeout: 5000 });
  if ((await desktop.locator('.saga-submit-label').innerText()).trim() !== 'Edit') throw new Error('Edit mode primary action does not expose its principal Edit verb');
  if (await desktop.locator('.saga-submit').getAttribute('aria-label') !== 'Edit image') throw new Error('Edit primary action lost its accessible name');
  const richPrompt = desktop.locator('.saga-rich-prompt');
""",
    "Edit primary-action visual contract",
)

replace_once(
    "scripts/capture-ui-preview.mjs",
    """  await waitForStudio(mobile);
  await shot(mobile, '09-mobile-create.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
""",
    """  await waitForStudio(mobile);
  const mobileSubmit = mobile.locator('.saga-submit');
  await mobileSubmit.waitFor({ state: 'visible' });
  if (await mobileSubmit.locator('.saga-submit-label').isVisible()) throw new Error('Mobile Generate action should collapse its text label');
  if (await mobileSubmit.getAttribute('aria-label') !== 'Generate image') throw new Error('Compact mobile Generate action lost its accessible name');
  const mobileSubmitBox = await mobileSubmit.boundingBox();
  if (!mobileSubmitBox || mobileSubmitBox.width > 40 || mobileSubmitBox.height > 40 || Math.abs(mobileSubmitBox.width - mobileSubmitBox.height) > 1) throw new Error(`Mobile Generate action is not compact/circular: ${JSON.stringify(mobileSubmitBox)}`);
  await shot(mobile, '09-mobile-create.png');

  if (diagnostics.pageErrors.length) throw new Error(`Page errors: ${diagnostics.pageErrors.map((entry) => entry.text).join(' | ')}`);
""",
    "Mobile Generate visual contract",
)

print("Iteration 10 product and visual-contract patch applied.")
