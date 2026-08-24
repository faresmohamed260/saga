from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text()
old = '- [~] **25. Simplify persistent sidebar/product status information.** Implementation in validation: the ambiguous `More` destination is now consistently user-facing as `Tools` / `Creation tools` / `Additional tools`, and the persistent footer no longer claims `FLUX.2 online`; it directs users to Jobs & Models for operational status instead of mixing provider state into account/navigation chrome.'
new = '- [x] **25. Simplify persistent sidebar/product status information.** The ambiguous `More` destination is consistently user-facing as `Tools` / `Creation tools` / `Additional tools`; the persistent footer no longer claims `FLUX.2 online` and instead directs operational status to Jobs & Models. The visual contract rejects provider-status leakage in the sidebar and rejects ambiguous `More tools` terminology on the Tools destination. Final artifact `9533301055` from Studio Visual Preview `32762690020` was manually inspected: sidebar hierarchy, Tools destination, and neutral workspace footer are clear and contained with no visual regression. Validated by Studio CI `32762689935`, Studio Visual Preview `32762690020`, Backend Architecture CI `32762689969`, Modal Worker Inventory `32762690023`, Worker Fleet Live Smoke `32762689991`, and Required Check Compatibility `32762689972`. **Iteration 25 complete.**'
if old not in text:
    raise SystemExit('Item 25 in-progress marker missing')
text = text.replace(old, new, 1)
text = text.replace('P2 polish is active; next planned scope begins at **Item 25**.', 'P2 polish is active; next planned scope begins at **Item 26**.')
path.write_text(text)
print('Completed Iteration 25 checklist bookkeeping.')
