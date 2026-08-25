from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')

replacements = [
    (
        'controls = replace_once(controls, "  seed, setSeed, steps, setSteps, cfg, setCfg, workflowId, setWorkflowId, modelId, setModelId,", "  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt, workflowId, setWorkflowId, modelId, setModelId,", "AdvancedSettings negative prompt props")',
        'controls = replace_once(controls, "  cfg, setCfg, workflowId, setWorkflowId, modelId, setModelId,", "  cfg, setCfg, negativePrompt, setNegativePrompt, workflowId, setWorkflowId, modelId, setModelId,", "AdvancedSettings negative prompt props")',
    ),
    (
        '''    seed_anchor = \'\'\'          <div className="saga-seed-row">\n            <div><strong>Seed</strong><small>Reuse a seed to reproduce a result.</small></div>\n            <div className="saga-seed-input"><input value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9]/g, ''))} inputMode="numeric" aria-label="Seed value" /><button type="button" aria-label="Randomize seed" onClick={() => setSeed(String(Math.floor(Math.random() * 999999)))}><Dices size={15} /></button></div>\n          </div>\'\'\'\n    negative_block = seed_anchor + \'\'\'\n          <label className="saga-negative-prompt">\n            <span><strong>Negative prompt</strong><small>Tell the active workflow what to avoid.</small></span>\n            <textarea\n              value={negativePrompt}\n              onChange={(event) => setNegativePrompt(event.target.value)}\n              maxLength={2000}\n              rows={3}\n              placeholder="Optional exclusions…"\n              aria-label="Negative prompt"\n            />\n          </label>\'\'\'\n    controls = replace_once(controls, seed_anchor, negative_block, "render backend negative prompt control")''',
        '''    negative_block = \'\'\'\n              <label className="saga-negative-prompt">\n                <span><strong>Negative prompt</strong><small>Tell the active workflow what to avoid.</small></span>\n                <textarea\n                  value={negativePrompt}\n                  onChange={(event) => setNegativePrompt(event.target.value)}\n                  maxLength={2000}\n                  rows={3}\n                  placeholder="Optional exclusions…"\n                  aria-label="Negative prompt"\n                />\n              </label>\'\'\'\n    controls = sub_once(\n        controls,\n        r'(              <div className="saga-seed-row">.*?\n              </div>)',\n        lambda match: match.group(1) + negative_block,\n        "render backend negative prompt control",\n    )''',
    ),
    (
        'controls = replace_once(controls, "  const isEdit = mode === \'Edit\';\\n  const isVideo = mode === \'Video\';", "  const isEdit = mode === \'Edit\';\\n  const isVideo = mode === \'Video\';\\n  const isImageSetup = mode === \'Image\';", "Image setup state")',
        'controls = replace_once(controls, "  const isVideo = mode === \'Video\';\\n  const referenceInputRef", "  const isVideo = mode === \'Video\';\\n  const isImageSetup = mode === \'Image\';\\n  const referenceInputRef", "Image setup state")',
    ),
    (
        '''    controls = replace_once(\n        controls,\n        "<button className={visualMode === 'Image' ? 'selected' : ''} onClick={() => setMode('Image')} title=\\"Image\\"><ImageIcon size={15}/><span>Image</span></button>",\n        "<button className={visualMode === 'Image' ? 'selected' : ''} onClick={() => { if (visualMode !== 'Image') setMode('Image'); }} title=\\"Image\\"><ImageIcon size={15}/><span>Image</span></button>",\n        "prevent selected Image toggle from dropping Edit mode",\n    )''',
        '''    controls = replace_once(\n        controls,\n        "onClick={() => setMode('Image')}",\n        "onClick={() => { if (visualMode !== 'Image') setMode('Image'); }}",\n        "prevent selected Image toggle from dropping Edit mode",\n    )''',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected one patch-helper target, found {count}: {old[:100]!r}')
    text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
