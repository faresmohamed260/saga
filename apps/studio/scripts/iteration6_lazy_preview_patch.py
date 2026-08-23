from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:800]}")
    path.write_text(text.replace(old, new, 1))


def mark_progress() -> None:
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '''**Iteration 5 — stored video poster thumbnails**\n\n- Status: `[x]` complete\n- Completed item: **05**\n- Next item: **06 — lazy-load Gallery hover video previews**\n- Rule: do not start Item 06 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.\n''',
        '''**Iteration 6 — lazy/deferred Gallery video previews**\n\n- Status: `[~]` in progress\n- Working item: **06**\n- Rule: defer poster-backed video sources until eligible hover/keyboard-preview intent while visible; keep reduced-motion and touch layouts static; validate with GitHub CI/visual preview and professional screenshot review before completion.\n''',
    )
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '- [ ] **06. Lazy-load Gallery hover video previews.** `preload="none"`/deferred `src`, attach/play on hover/focus/visibility, pause/detach appropriately, respect reduced motion and touch behavior.\n',
        '- [~] **06. Lazy-load Gallery hover video previews.** `preload="none"`/deferred `src`, attach/play on hover/focus/visibility, pause/detach appropriately, respect reduced motion and touch behavior. **Iteration 6 in progress.**\n',
    )
    print("Iteration 6 marked in progress")


def apply_product() -> None:
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''  const videoRef = useRef(null);\n  const moreRef = useRef(null);\n  const [moreOpen, setMoreOpen] = useState(false);\n''',
        '''  const frameRef = useRef(null);\n  const videoRef = useRef(null);\n  const moreRef = useRef(null);\n  const [moreOpen, setMoreOpen] = useState(false);\n  const [previewIntent, setPreviewIntent] = useState(false);\n  const [previewVisible, setPreviewVisible] = useState(!history);\n  const [previewMotionAllowed, setPreviewMotionAllowed] = useState(false);\n  const [previewHoverCapable, setPreviewHoverCapable] = useState(false);\n''',
    )
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''  const videoSource = item.originalUrl || item.url || '';\n  const itemLabel = item.title || 'media';\n  const openOrSelect = () => selectable ? onSelect?.(item) : onOpen(item);\n''',
        '''  const videoSource = item.originalUrl || item.url || '';\n  const itemLabel = item.title || 'media';\n  const isGalleryVideo = history && item.kind === 'video' && Boolean(videoSource);\n  const previewActive = isGalleryVideo\n    && !selectable\n    && previewVisible\n    && previewIntent\n    && previewMotionAllowed\n    && previewHoverCapable;\n  const legacyFrameAttached = isGalleryVideo && !item.thumbnailUrl && previewVisible;\n  const attachedVideoSource = history\n    ? ((previewActive || legacyFrameAttached) ? videoSource : '')\n    : videoSource;\n  const openOrSelect = () => selectable ? onSelect?.(item) : onOpen(item);\n''',
    )
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''  useEffect(() => {\n    if (!moreOpen) return undefined;\n''',
        '''  useEffect(() => {\n    if (!isGalleryVideo) return undefined;\n    const node = frameRef.current;\n    if (!node) return undefined;\n    if (typeof IntersectionObserver === 'undefined') {\n      setPreviewVisible(true);\n      return undefined;\n    }\n\n    const observer = new IntersectionObserver(([entry]) => {\n      setPreviewVisible(Boolean(entry?.isIntersecting));\n    }, { rootMargin: '120px 0px' });\n    observer.observe(node);\n    return () => observer.disconnect();\n  }, [isGalleryVideo]);\n\n  useEffect(() => {\n    if (!isGalleryVideo) return undefined;\n    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');\n    const hoverFine = window.matchMedia('(hover: hover) and (pointer: fine)');\n    const updateCapabilities = () => {\n      setPreviewMotionAllowed(!reducedMotion.matches);\n      setPreviewHoverCapable(hoverFine.matches && window.innerWidth > 640);\n    };\n    updateCapabilities();\n    reducedMotion.addEventListener?.('change', updateCapabilities);\n    hoverFine.addEventListener?.('change', updateCapabilities);\n    window.addEventListener('resize', updateCapabilities);\n    return () => {\n      reducedMotion.removeEventListener?.('change', updateCapabilities);\n      hoverFine.removeEventListener?.('change', updateCapabilities);\n      window.removeEventListener('resize', updateCapabilities);\n    };\n  }, [isGalleryVideo]);\n\n  useEffect(() => {\n    const video = videoRef.current;\n    if (!isGalleryVideo || !video) return;\n    if (previewActive) {\n      video.play().catch(() => {});\n      return;\n    }\n    video.pause();\n    if (item.thumbnailUrl && video.currentSrc) video.load();\n  }, [isGalleryVideo, previewActive, item.thumbnailUrl]);\n\n  useEffect(() => {\n    if (!moreOpen) return undefined;\n''',
    )
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''  useEffect(() => {\n    if (selectable && moreOpen) setMoreOpen(false);\n  }, [selectable, moreOpen]);\n''',
        '''  useEffect(() => {\n    if (selectable && moreOpen) setMoreOpen(false);\n    if (selectable && previewIntent) setPreviewIntent(false);\n  }, [selectable, moreOpen, previewIntent]);\n''',
    )
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''      <div\n        className={`media-frame ${!item.url && !videoSource ? 'media-frame-empty' : ''}`}\n        style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined}\n        onMouseEnter={() => {\n          if (history && !selectable && videoRef.current) videoRef.current.play().catch(() => {});\n        }}\n        onMouseLeave={() => {\n          if (videoRef.current) videoRef.current.pause();\n        }}\n      >\n''',
        '''      <div\n        ref={frameRef}\n        className={`media-frame ${!item.url && !videoSource ? 'media-frame-empty' : ''}`}\n        style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined}\n        onMouseEnter={() => {\n          if (isGalleryVideo && !selectable) setPreviewIntent(true);\n        }}\n        onMouseLeave={() => {\n          if (isGalleryVideo) setPreviewIntent(false);\n        }}\n        onFocusCapture={() => {\n          if (isGalleryVideo && !selectable) setPreviewIntent(true);\n        }}\n        onBlurCapture={(event) => {\n          if (isGalleryVideo && !event.currentTarget.contains(event.relatedTarget)) setPreviewIntent(false);\n        }}\n      >\n''',
    )
    replace_once(
        "apps/studio/src/components/MediaCard.jsx",
        '''            src={videoSource}\n            poster={item.thumbnailUrl || undefined}\n            muted\n            playsInline\n            loop\n            preload={item.thumbnailUrl ? 'none' : 'metadata'}\n            onLoadedMetadata={(event) => {\n''',
        '''            src={attachedVideoSource || undefined}\n            poster={item.thumbnailUrl || undefined}\n            muted\n            playsInline\n            loop\n            preload={history ? (item.thumbnailUrl ? 'none' : (previewVisible ? 'metadata' : 'none')) : 'metadata'}\n            data-preview-state={previewActive ? 'active' : attachedVideoSource ? 'fallback' : 'deferred'}\n            onCanPlay={(event) => {\n              if (previewActive) event.currentTarget.play().catch(() => {});\n            }}\n            onLoadedMetadata={(event) => {\n''',
    )

    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  for (let index = 0; index < 3; index += 1) {\n    const preview = videoPreviews.nth(index);\n    if (!(await preview.getAttribute('poster'))) throw new Error(`Video card ${index} is missing its stored poster URL`);\n    if (await preview.getAttribute('preload') !== 'none') throw new Error(`Poster-backed video card ${index} should use preload=none`);\n  }\n''',
        '''  for (let index = 0; index < 3; index += 1) {\n    const preview = videoPreviews.nth(index);\n    if (!(await preview.getAttribute('poster'))) throw new Error(`Video card ${index} is missing its stored poster URL`);\n    if (await preview.getAttribute('preload') !== 'none') throw new Error(`Poster-backed video card ${index} should use preload=none`);\n    if (await preview.getAttribute('src')) throw new Error(`Poster-backed video card ${index} eagerly attached its MP4 source`);\n    if (await preview.getAttribute('data-preview-state') !== 'deferred') throw new Error(`Video card ${index} should start in deferred preview state`);\n  }\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  await page.keyboard.press('Tab');\n  await primaryButtons.first().focus();\n  if (!(await primaryButtons.first().evaluate((element) => element.matches(':focus-visible')))) throw new Error('Primary media action does not receive :focus-visible treatment');\n''',
        '''  await page.keyboard.press('Tab');\n  await primaryButtons.first().focus();\n  const focusedVideo = cards.first().locator('video');\n  await page.waitForFunction((element) => element?.getAttribute('data-preview-state') === 'active', await focusedVideo.elementHandle());\n  if (!(await focusedVideo.getAttribute('src'))) throw new Error('Keyboard focus did not attach the deferred video source');\n  if (!(await primaryButtons.first().evaluate((element) => element.matches(':focus-visible')))) throw new Error('Primary media action does not receive :focus-visible treatment');\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  await page.locator('body').click({ position: { x: 2, y: 2 } });\n  await page.waitForTimeout(220);\n  const resetOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));\n''',
        '''  await page.locator('body').click({ position: { x: 2, y: 2 } });\n  await page.waitForTimeout(220);\n  const resetOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));\n  if (await focusedVideo.getAttribute('src')) throw new Error('Video source stayed attached after keyboard focus left the card');\n  if (await focusedVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Video preview did not return to deferred state after focus left');\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  await cards.first().locator('.media-frame').hover();\n  await page.waitForTimeout(180);\n  const afterOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));\n  if (afterOpacity < 0.9) throw new Error(`Gallery actions did not appear over media on hover, opacity=${afterOpacity}`);\n\n  const desktopPrimary = overlay.locator('.media-action-primary:visible');\n''',
        '''  await cards.first().locator('.media-frame').hover();\n  await page.waitForTimeout(180);\n  const afterOpacity = Number(await overlay.evaluate((element) => getComputedStyle(element).opacity));\n  if (afterOpacity < 0.9) throw new Error(`Gallery actions did not appear over media on hover, opacity=${afterOpacity}`);\n  if (!(await focusedVideo.getAttribute('src'))) throw new Error('Desktop hover did not attach the deferred MP4 source');\n  if (await focusedVideo.getAttribute('data-preview-state') !== 'active') throw new Error('Desktop hover did not activate video preview state');\n  await page.screenshot({ path: path.join(outputDir, '11c-gallery-video-preview-hover.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('11c-gallery-video-preview-hover.png');\n\n  const desktopPrimary = overlay.locator('.media-action-primary:visible');\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  await page.screenshot({ path: path.join(outputDir, '12-gallery-manager.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('12-gallery-manager.png');\n\n  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });\n''',
        '''  await page.screenshot({ path: path.join(outputDir, '12-gallery-manager.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('12-gallery-manager.png');\n\n  const reduced = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: 'dark' });\n  reduced.on('pageerror', (error) => diagnostics.pageErrors.push({ label: 'reduced-motion', text: error?.stack || error?.message || String(error) }));\n  await reduced.emulateMedia({ reducedMotion: 'reduce' });\n  await mockHistory(reduced);\n  await reduced.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });\n  await reduced.getByRole('heading', { name: 'Gallery', exact: true }).waitFor({ state: 'visible', timeout: 20_000 });\n  const reducedCard = reduced.locator('.gallery-grid .history-card').first();\n  const reducedVideo = reducedCard.locator('video');\n  await reducedCard.locator('.media-frame').hover();\n  await reduced.waitForTimeout(180);\n  if (await reducedVideo.getAttribute('src')) throw new Error('Reduced-motion mode attached a hover video source');\n  if (await reducedVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Reduced-motion mode should keep poster-backed video deferred');\n  await reduced.screenshot({ path: path.join(outputDir, '10d-gallery-reduced-motion.png'), fullPage: true, animations: 'disabled' });\n  diagnostics.screenshots.push('10d-gallery-reduced-motion.png');\n  await reduced.close();\n\n  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, colorScheme: 'dark' });\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-gallery-preview.mjs",
        '''  const mobileOverlay = mobileCards.first().locator('.media-actions-overlay');\n  const mobileOpacity = Number(await mobileOverlay.evaluate((element) => getComputedStyle(element).opacity));\n''',
        '''  const mobileVideo = mobileCards.first().locator('video');\n  if (await mobileVideo.getAttribute('src')) throw new Error('Mobile Gallery eagerly attached a poster-backed MP4 source');\n  await mobileCards.first().locator('.media-frame').hover();\n  await mobile.waitForTimeout(120);\n  if (await mobileVideo.getAttribute('src')) throw new Error('Narrow/touch-oriented Gallery hover should not attach a video source');\n  if (await mobileVideo.getAttribute('data-preview-state') !== 'deferred') throw new Error('Mobile Gallery should keep video previews poster-only');\n\n  const mobileOverlay = mobileCards.first().locator('.media-actions-overlay');\n  const mobileOpacity = Number(await mobileOverlay.evaluate((element) => getComputedStyle(element).opacity));\n''',
    )
    print("Iteration 6 lazy preview product patch applied")


parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["progress", "product"])
args = parser.parse_args()
if args.mode == "progress":
    mark_progress()
else:
    apply_product()
