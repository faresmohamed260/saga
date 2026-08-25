import subprocess
import sys
from pathlib import Path


def run(*args):
    subprocess.run(args, check=True)


patch = Path('scripts/studio_ui_ux_benchmark_patch.py')
if not patch.exists():
    raise SystemExit('Benchmark UX patch script is missing.')

run(sys.executable, str(patch))

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
