from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def patch(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: expected one match, got {text.count(old)}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

patch(
    'apps/studio/src/app/App.jsx',
    "        setMode('Edit');\n",
    "        setCreateMode('Edit');\n",
)
patch(
    'apps/studio/src/app/App.jsx',
    "        onModeChange={setMode}\n",
    "        onModeChange={setCreateMode}\n",
)
patch(
    'apps/studio/src/hooks/useMediaActions.js',
    "    if (item.kind === 'video') setMode('Video');\n",
    "    if (item.kind === 'video') { setMode('Video'); setSteps(11); setCfg(1); setWorkflowId('ltx25-redgraft-video'); setModelId('ltx25-redgraft'); }\n",
)
patch(
    'apps/studio/src/hooks/useMediaActions.js',
    "      if (section === 'Favorites') loadFavorites();\n",
    "      if (section === 'Favorites' || section === 'Create') loadFavorites();\n",
)

contract = ROOT / 'apps/studio/scripts/check-create-advanced-contract.mjs'
text = contract.read_text(encoding='utf-8')
needle = "expect(app.includes('favoriteItems.filter'), 'Create output wall must draw from Favorites');\n"
addition = needle + "expect(app.includes(\"setCreateMode('Edit')\"), 'Uploading a reference must apply the FLUX preset when entering Edit');\n"
if text.count(needle) != 1:
    raise RuntimeError('advanced contract App marker missing')
text = text.replace(needle, addition, 1)
needle = "expect(library.includes(\"['Create', 'Gallery', 'Favorites', 'Collections']\"), 'Favorites must refresh while Create is visible');\n"
addition = needle + "expect(/item\.kind === 'video'[\\s\\S]*?setSteps\(11\)[\\s\\S]*?setCfg\(1\)[\\s\\S]*?ltx25-redgraft-video/.test(await readFile(new URL('src/hooks/useMediaActions.js', root), 'utf8')), 'Reusing a video must restore the LTX production preset');\n"
if text.count(needle) != 1:
    raise RuntimeError('advanced contract library marker missing')
text = text.replace(needle, addition, 1)
contract.write_text(text, encoding='utf-8')
print('Preset entrypoints patched.')
