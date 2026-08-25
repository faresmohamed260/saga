import subprocess
import sys
from pathlib import Path


def run(*args):
    subprocess.run(args, check=True)


patch = Path('scripts/studio_ui_ux_benchmark_patch.py')
if not patch.exists():
    raise SystemExit('Benchmark UX patch script is missing.')

run(sys.executable, str(patch))

# The bootstrap patch writes this generated source through a Python triple-quoted
# string. Keep the failure reporter syntax simple so newline escaping cannot turn
# into an invalid JavaScript string literal on the Actions runner.
contract = Path('apps/studio/scripts/check-ui-ux-benchmark-contract.mjs')
contract_text = contract.read_text(encoding='utf-8')
start = contract_text.index('const failures = ')
end = contract_text.index("console.log('UI/UX benchmark contract passed.');")
contract_text = contract_text[:start] + """const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error('UI/UX benchmark contract failed:', failures);
  process.exit(1);
}
""" + contract_text[end:]
contract.write_text(contract_text, encoding='utf-8')

# Persist the validated UX pass as one coherent commit. The temporary bootstrap
# workflow/script are removed so the branch keeps only product code, tests and docs.
run('git', 'add',
    'apps/studio/src/app/App.jsx',
    'apps/studio/src/features/library/GalleryView.jsx',
    'apps/studio/src/components/MediaCard.jsx',
    'apps/studio/src/components/MediaModal.jsx',
    'apps/studio/src/create-controls.jsx',
    'apps/studio/scripts/check-ui-ux-benchmark-contract.mjs',
    'apps/studio/package.json',
    'docs/studio-ui-ux-benchmark-audit.md',
)
if Path('.github/workflows/studio-ui-ux-benchmark-patch.yml').exists():
    run('git', 'rm', '.github/workflows/studio-ui-ux-benchmark-patch.yml')
if patch.exists():
    run('git', 'rm', str(patch))

run('git', 'commit', '-m', 'refactor(studio): remove misleading UI and improve real-user UX')
