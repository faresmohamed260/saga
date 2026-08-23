from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:800]}")
    path.write_text(text.replace(old, new, 1))


replace_once(
    "apps/studio/src/components/MediaCard.jsx",
    '''      setPreviewMotionAllowed(!reducedMotion.matches);\n      setPreviewHoverCapable(hoverFine.matches && window.innerWidth > 640);\n    };\n    updateCapabilities();\n    reducedMotion.addEventListener?.('change', updateCapabilities);\n    hoverFine.addEventListener?.('change', updateCapabilities);\n    window.addEventListener('resize', updateCapabilities);\n    return () => {\n      reducedMotion.removeEventListener?.('change', updateCapabilities);\n      hoverFine.removeEventListener?.('change', updateCapabilities);\n      window.removeEventListener('resize', updateCapabilities);\n    };\n''',
    '''      setPreviewMotionAllowed(!reducedMotion.matches);\n      setPreviewHoverCapable(hoverFine.matches);\n    };\n    updateCapabilities();\n    reducedMotion.addEventListener?.('change', updateCapabilities);\n    hoverFine.addEventListener?.('change', updateCapabilities);\n    return () => {\n      reducedMotion.removeEventListener?.('change', updateCapabilities);\n      hoverFine.removeEventListener?.('change', updateCapabilities);\n    };\n''',
)

replace_once(
    "apps/studio/scripts/capture-gallery-preview.mjs",
    "  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });\n",
    "  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark', hasTouch: true, isMobile: true });\n",
)
replace_once(
    "apps/studio/scripts/capture-gallery-preview.mjs",
    '''  const mobileVideo = mobileCards.first().locator('video');\n  if (await mobileVideo.getAttribute('src')) throw new Error('Mobile Gallery eagerly attached a poster-backed MP4 source');\n  await mobileCards.first().locator('.media-frame').hover();\n  await mobile.waitForTimeout(120);\n  if (await mobileVideo.getAttribute('src')) throw new Error('Narrow/touch-oriented Gallery hover should not attach a video source');\n  if (await mobileVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Mobile Gallery should keep video previews poster-only');\n''',
    '''  const mobileVideo = mobileCards.first().locator('video');\n  if (await mobileVideo.getAttribute('src')) throw new Error('Mobile Gallery eagerly attached a poster-backed MP4 source');\n  const mobileFineHover = await mobile.evaluate(() => window.matchMedia('(hover: hover) and (pointer: fine)').matches);\n  if (mobileFineHover) throw new Error('Touch-emulated Gallery unexpectedly reports fine-hover input capability');\n  await mobileCards.first().locator('.media-frame').dispatchEvent('mouseenter');\n  await mobile.waitForTimeout(120);\n  if (await mobileVideo.getAttribute('src')) throw new Error('Touch Gallery synthetic hover attached a video source');\n  if (await mobileVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Touch Gallery should keep video previews poster-only');\n''',
)

replace_once(
    "apps/studio/scripts/check-video-poster-contract.mjs",
    '''assert.match(cardSource, /data-preview-state=\\{previewActive \\? 'active'/);\nassert.match(cardSource, /preload=\\{history \\? \\(item\\.thumbnailUrl \\? 'none'/);\n''',
    '''assert.match(cardSource, /data-preview-state=\\{previewActive \\? 'active'/);\nassert.match(cardSource, /preload=\\{history \\? \\(item\\.thumbnailUrl \\? 'none'/);\nassert.match(cardSource, /setPreviewHoverCapable\\(hoverFine\\.matches\\)/);\nassert.doesNotMatch(cardSource, /innerWidth > 640/);\n''',
)

print("Iteration 6 input-modality refinement applied")
