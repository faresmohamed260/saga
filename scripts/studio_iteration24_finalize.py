from pathlib import Path

path = Path('docs/studio-ui-polish-checklist.md')
text = path.read_text()
old = '- [ ] **24. Add optional Gallery density modes.** Compact default plus Comfortable/detail-oriented density where useful.'
new = '- [x] **24. Add optional Gallery density modes.** Gallery now defaults to persisted Compact density and offers a Comfortable detail-oriented mode. Desktop Comfortable uses larger cards and more generous copy spacing; 390px mobile Comfortable becomes a readable single-column layout while Compact remains two columns. The visual harness explicitly validates default Compact state, Comfortable activation, localStorage persistence, desktop card sizing, and mobile single-column behavior. Final artifact `9532564318` from Studio Visual Preview `32760586460` was manually inspected in desktop Compact/Comfortable and 390px mobile Compact/Comfortable states with no layout regression. Validated by Studio CI `32760586336`, Studio Visual Preview `32760586460`, Backend Architecture CI `32760586316`, Modal Worker Inventory `32760586340`, Worker Fleet Live Smoke `32760586381`, and Required Check Compatibility `32760586367`. **Iteration 24 complete.**'
if old not in text:
    raise SystemExit('Item 24 marker missing')
text = text.replace(old, new, 1)
text = text.replace('P2 polish is active; next planned scope begins at **Item 23**.', 'P2 polish is active; next planned scope begins at **Item 25**.')
path.write_text(text)
print('Completed Iteration 24 checklist bookkeeping.')
