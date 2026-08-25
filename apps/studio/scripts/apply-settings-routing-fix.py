from pathlib import Path
import json
import subprocess

studio = Path.cwd()
repo = studio.parents[1]


def replace(path, old, new, count=1):
    p = repo / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'missing anchor in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')

# The global mobile topbar must make its settings action useful from every route.
replace(
    'apps/studio/src/app/App.jsx',
    '<MobileTopbar onOpenNavigation={() => setMobileNav(true)} onOpenSettings={() => setSettingsOpen(true)} />',
    '<MobileTopbar onOpenNavigation={() => setMobileNav(true)} onOpenSettings={() => { setSection(\'Create\'); setSettingsOpen(true); }} />',
)

# CreateWorkspace previously closed Advanced on its initial mount. That broke deliberate
# route -> Create -> Advanced actions. Close it only on subsequent mode transitions.
controls = repo / 'apps/studio/src/create-controls.jsx'
text = controls.read_text(encoding='utf-8')
old_ref = '  const settingsButtonRef = useRef(null);\n\n  const [resolutionOpen, setResolutionOpen] = useState(false);'
new_ref = '  const settingsButtonRef = useRef(null);\n  const modeEffectMountedRef = useRef(false);\n\n  const [resolutionOpen, setResolutionOpen] = useState(false);'
if old_ref not in text:
    raise SystemExit('missing settingsButtonRef anchor')
text = text.replace(old_ref, new_ref, 1)
old_effect = "  useEffect(() => {\n    setAspectOpen(false);\n    setResolutionOpen(false);\n    setVideoResolutionOpen(false);\n    setDurationOpen(false);\n    setSettingsOpen(false);\n  }, [mode]);"
new_effect = "  useEffect(() => {\n    setAspectOpen(false);\n    setResolutionOpen(false);\n    setVideoResolutionOpen(false);\n    setDurationOpen(false);\n    if (modeEffectMountedRef.current) setSettingsOpen(false);\n    else modeEffectMountedRef.current = true;\n  }, [mode]);"
if old_effect not in text:
    raise SystemExit('missing mode-close effect anchor')
controls.write_text(text.replace(old_effect, new_effect, 1), encoding='utf-8')

# Keep this regression explicit in source-level accessibility coverage too.
contract = repo / 'apps/studio/scripts/check-accessibility-polish-contract.mjs'
contract_text = contract.read_text(encoding='utf-8')
needle = "console.log('Typography, contrast, focus, and non-color state accessibility contract passed.');"
if needle in contract_text and "Open generation settings" not in contract_text:
    contract_text = contract_text.replace(
        needle,
        "expect(app.includes(\"setSection('Create'); setSettingsOpen(true)\"), 'Global generation-settings action must navigate to Create before opening Advanced');\n" + needle,
        1,
    )
    contract.write_text(contract_text, encoding='utf-8')

# Remove the temporary hook and script before committing.
pkg = studio / 'package.json'
payload = json.loads(pkg.read_text(encoding='utf-8'))
payload.get('scripts', {}).pop('postinstall', None)
pkg.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
Path(__file__).unlink()

subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=repo, check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=repo, check=True)
subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=repo).returncode != 0:
    subprocess.run(['git', 'commit', '-m', 'fix(studio): make generation settings route-safe'], cwd=repo, check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:studio/advanced-ui-audit'], cwd=repo, check=True)
