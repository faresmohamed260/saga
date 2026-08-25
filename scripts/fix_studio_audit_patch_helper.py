from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')
old = 'controls = replace_once(controls, "    setCfg(preset.cfg);\\n    setWorkflowId(preset.workflowId);", "    setCfg(preset.cfg);\\n    setNegativePrompt(preset.negativePrompt || \'\');\\n    setWorkflowId(preset.workflowId);", "reset negative prompt")'
new = 'controls = replace_once(controls, "                setCfg(preset.cfg);\\n                setWorkflowId(preset.workflowId);", "                setCfg(preset.cfg);\\n                setNegativePrompt(preset.negativePrompt || \'\');\\n                setWorkflowId(preset.workflowId);", "reset negative prompt")'
if text.count(old) != 1:
    raise SystemExit(f'Expected one reset patch target, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
