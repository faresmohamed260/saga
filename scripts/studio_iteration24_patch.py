from pathlib import Path

path = Path('apps/studio/scripts/capture-gallery-preview.mjs')
text = path.read_text()
needle = """  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');
  await page.locator('.gallery-grid').screenshot({ path: path.join(outputDir, '10c-gallery-video-posters.png'), animations: 'disabled' });
  diagnostics.screenshots.push('10c-gallery-video-posters.png');
"""
replacement = """  const compactDensity = page.getByRole('button', { name: 'Compact', exact: true });
  const comfortableDensity = page.getByRole('button', { name: 'Comfortable', exact: true });
  if (await compactDensity.getAttribute('aria-pressed') !== 'true') throw new Error('Gallery must default to Compact density');
  if (await page.locator('.gallery-grid').getAttribute('data-density') !== 'compact') throw new Error('Gallery grid did not expose Compact density');

  await page.screenshot({ path: path.join(outputDir, '10-gallery-grid.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10-gallery-grid.png');
  await page.locator('.gallery-grid').screenshot({ path: path.join(outputDir, '10c-gallery-video-posters.png'), animations: 'disabled' });
  diagnostics.screenshots.push('10c-gallery-video-posters.png');

  await comfortableDensity.click();
  if (await comfortableDensity.getAttribute('aria-pressed') !== 'true') throw new Error('Comfortable density did not become active');
  if (await page.locator('.gallery-grid').getAttribute('data-density') !== 'comfortable') throw new Error('Gallery grid did not expose Comfortable density');
  const comfortableBox = await cards.first().boundingBox();
  if (!comfortableBox || comfortableBox.width < 245) throw new Error(`Comfortable density card is too narrow: ${JSON.stringify(comfortableBox)}`);
  if (await page.evaluate(() => localStorage.getItem('saga.galleryDensity')) !== 'comfortable') throw new Error('Gallery density preference was not persisted');
  await page.screenshot({ path: path.join(outputDir, '10e-gallery-comfortable.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('10e-gallery-comfortable.png');
  await compactDensity.click();
"""
if needle not in text:
    raise SystemExit('Iteration 24 desktop density insertion point not found')
text = text.replace(needle, replacement, 1)
mobile_needle = """  await mobile.screenshot({ path: path.join(outputDir, '13-gallery-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13-gallery-mobile.png');
"""
mobile_replacement = """  await mobile.screenshot({ path: path.join(outputDir, '13-gallery-mobile.png'), fullPage: true, animations: 'disabled' });
  diagnostics.screenshots.push('13-gallery-mobile.png');
  await mobile.getByRole('button', { name: 'Comfortable', exact: true }).click();
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
if mobile_needle not in text:
    raise SystemExit('Iteration 24 mobile density insertion point not found')
text = text.replace(mobile_needle, mobile_replacement, 1)
path.write_text(text)
print('Patched Gallery visual harness for density modes.')
