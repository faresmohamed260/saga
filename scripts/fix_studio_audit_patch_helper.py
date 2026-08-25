from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')
old = '''    contract = replace_once(
        contract,
        '<span className="saga-submit-label">{isEdit ? \\'Edit\\' : \\'Generate\\'}</span>',
        '<span className="saga-submit-label">{isImageSetup ? \\'Add image\\' : isEdit ? \\'Edit\\' : \\'Generate\\'}</span>',
        "update primary action source contract",
    )'''
new = '''    old_primary = "{isEdit ? \\\\'Edit\\\\' : \\\\'Generate\\\\'}"
    new_primary = "{isImageSetup ? \\\\'Add image\\\\' : isEdit ? \\\\'Edit\\\\' : \\\\'Generate\\\\'}"
    if contract.count(old_primary) != 1:
        raise RuntimeError(f"update primary action source contract: expected one escaped markup match, found {contract.count(old_primary)}")
    contract = contract.replace(old_primary, new_primary, 1)'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one escaped Generate contract block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
