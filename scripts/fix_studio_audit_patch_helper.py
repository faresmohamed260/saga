from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')
old = '''    write(path, text)
    commit("test(studio): cover repaired Advanced interactions", path)'''
new = '''    contract_path = "apps/studio/scripts/check-generate-action-contract.mjs"
    contract = read(contract_path)
    contract = replace_once(
        contract,
        '<span className="saga-submit-label">{isEdit ? \\\'Edit\\\' : \\\'Generate\\\'}</span>',
        '<span className="saga-submit-label">{isImageSetup ? \\\'Add image\\\' : isEdit ? \\\'Edit\\\' : \\\'Generate\\\'}</span>',
        "update primary action source contract",
    )
    contract = replace_once(
        contract,
        "Desktop primary action does not expose the Generate verb",
        "Image setup primary action must request a real reference image",
        "update primary action visual contract",
    )
    write(contract_path, contract)
    write(path, text)
    commit("test(studio): cover repaired Advanced interactions", path, contract_path)'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one preview commit block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
