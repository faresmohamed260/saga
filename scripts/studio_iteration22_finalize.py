from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'docs/studio-ui-polish-checklist.md'
base = subprocess.check_output([
    'git', 'show', '483333a0b218fc848503b3a5f134d328715784b9:docs/studio-ui-polish-checklist.md'
], text=True)
old = '- [ ] **22. Replace technical checkpoint/model strings with user-facing names.** Keep exact checkpoint/quantization/workflow metadata in a Details surface.'
new = '- [x] **22. Replace technical checkpoint/model strings with user-facing names.** Gallery filters and media summaries use friendly names (`FLUX.2 Klein 9B`, `LTX Video 2.5`), while exact stored model/checkpoint/quantization strings remain unchanged and appear only under `Implementation` in expandable Details. The Models catalog also uses product-facing names. Final artifact `9531600899` from Studio Visual Preview `32757916111` was manually inspected across desktop Gallery, 390px mobile Gallery, and expanded media Details: friendly labels are clear, technical metadata is contained in Details, and no layout regression is present. The visual harness explicitly rejects DarkBeast/Sulphur2/INT8/ConvRot/REDGraft strings in the Gallery filter and verifies the exact raw implementation string remains available in Details. Validated by Studio CI `32757915877`, Studio Visual Preview `32757916111`, Backend Architecture CI `32757915849`, Modal Worker Inventory `32757915865`, Worker Fleet Live Smoke `32757915871`, and Required Check Compatibility `32757915835`. **Iteration 22 complete.**'
if old not in base:
    raise SystemExit('Item 22 marker missing from intact checklist revision')
base = base.replace(old, new)
base = base.replace('Next planned polish scope begins at **Item 21** in P2.', 'P2 polish is active; next planned scope begins at **Item 23**.')
path.write_text(base)
print('Restored intact checklist history and completed Iteration 22.')
