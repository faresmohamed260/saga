from pathlib import Path

path = Path('apps/studio/scripts/capture-gallery-preview.mjs')
text = path.read_text()

old = "for (const label of ['Favorite', 'Download ZIP', 'Delete'])"
new = "for (const label of ['Favorite', 'Download', 'Delete'])"
if old not in text:
    raise SystemExit('Bulk action label anchor not found')
text = text.replace(old, new, 1)

old = """  await mobile.getByRole('button', { name: 'Comfortable', exact: true }).click();
  const mobileComfortableGrid = mobile.locator('.gallery-grid');
  if (await mobileComfortableGrid.getAttribute('data-density') !== 'comfortable') throw new Error('Mobile Comfortable density did not activate');
  const mobileComfortableFirst = await mobileCards.first().boundingBox();
  const mobileComfortableSecond = await mobileCards.nth(1).boundingBox();
  if (!mobileComfortableFirst || !mobileComfortableSecond || Math.abs(mobileComfortableFirst.x - mobileComfortableSecond.x) > 3 || mobileComfortableSecond.y <= mobileComfortableFirst.y) {
    throw new Error(`Mobile Comfortable density is not a single-column detail layout: ${JSON.stringify({ mobileComfortableFirst, mobileComfortableSecond })}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '13c-gallery-mobile-comfortable.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13c-gallery-mobile-comfortable.png');
  await mobile.getByRole('button', { name: 'Compact', exact: true }).click();
"""
new = """  await mobile.getByRole('button', { name: 'Gallery layout: compact', exact: true }).click();
  const mobileComfortableGrid = mobile.locator('.gallery-grid');
  if (await mobileComfortableGrid.getAttribute('data-density') !== 'comfortable') throw new Error('Mobile Comfortable density did not activate');
  const mobileComfortableFirst = await mobileCards.first().boundingBox();
  const mobileComfortableSecond = await mobileCards.nth(1).boundingBox();
  if (!mobileComfortableFirst || !mobileComfortableSecond || Math.abs(mobileComfortableFirst.x - mobileComfortableSecond.x) > 3 || mobileComfortableSecond.y <= mobileComfortableFirst.y) {
    throw new Error(`Mobile Comfortable density is not a single-column detail layout: ${JSON.stringify({ mobileComfortableFirst, mobileComfortableSecond })}`);
  }
  await mobile.screenshot({ path: path.join(outputDir, '13c-gallery-mobile-comfortable.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13c-gallery-mobile-comfortable.png');
  await mobile.getByRole('button', { name: 'Gallery layout: comfortable', exact: true }).click();
"""
if old not in text:
    raise SystemExit('Mobile density interaction anchor not found')

path.write_text(text.replace(old, new, 1))
