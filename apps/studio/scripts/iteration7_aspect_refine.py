from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:1000]}")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        "function CompactPicker({ label, value, displayValue = value, title, options, onChoose, leading }) {",
        "function CompactPicker({ label, value, displayValue = value, title, options, onChoose, leading, menuClassName = '' }) {",
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''        <div className="saga-video-option-menu" role="menu" aria-label={label} aria-orientation="vertical">\n''',
        '''        <div className={`saga-video-option-menu ${menuClassName}`.trim()} role="menu" aria-label={label} aria-orientation="vertical">\n''',
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''    ? `Aspect · Auto ${aspectValue}${referenceInfo.fromReference ? ' · Ref' : ''}`\n''',
        '''    ? `Aspect · Auto ${aspectValue}${referenceInfo.fromReference ? ' · From reference' : ''}`\n''',
    )
    replace_once(
        "apps/studio/src/features/create/VideoGenerationControls.jsx",
        '''        options={aspectOptions}\n        onChoose={(value) => {\n''',
        '''        options={aspectOptions}\n        menuClassName="saga-video-aspect-menu"\n        onChoose={(value) => {\n''',
    )

    css_path = ROOT / "apps/studio/src/studio-polish.css"
    css = css_path.read_text()
    marker = '''.workspace .saga-video-option-menu {\n  top: calc(100% + 8px);\n  bottom: auto;\n  max-height: min(420px, calc(100vh - 24px));\n  overflow-y: auto;\n  overscroll-behavior: contain;\n  scrollbar-width: thin;\n}\n'''
    if marker not in css:
        raise RuntimeError("studio-polish.css: video option menu marker not found")
    css = css.replace(
        marker,
        marker + '''\n@media (min-width: 761px) {\n  .workspace .saga-video-option-menu.saga-video-aspect-menu {\n    max-height: min(456px, calc(100vh - 24px));\n  }\n}\n''',
        1,
    )
    css_path.write_text(css)

    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  await aspectMenu.waitFor({ state: 'visible' });\n  await page.screenshot({ path: path.join(outputDir, '05c-video-aspect-picker.png'), fullPage: true, animations: 'disabled' });\n''',
        '''  await aspectMenu.waitFor({ state: 'visible' });\n  const desktopMenuSize = await aspectMenu.evaluate((element) => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight }));\n  if (desktopMenuSize.scrollHeight > desktopMenuSize.clientHeight + 1) throw new Error(`Desktop Video Aspect menu should expose all options without scrolling: ${JSON.stringify(desktopMenuSize)}`);\n  await page.screenshot({ path: path.join(outputDir, '05c-video-aspect-picker.png'), fullPage: true, animations: 'disabled' });\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  if (!/Aspect\\s*·\\s*Auto\\s+4:3\\s*·\\s*Ref/.test(await aspect.innerText())) throw new Error(`Auto aspect did not inherit the 800x600 reference ratio: ${await aspect.innerText()}`);\n''',
        '''  if (!/Aspect\\s*·\\s*Auto\\s+4:3\\s*·\\s*From reference/.test(await aspect.innerText())) throw new Error(`Auto aspect did not visibly expose reference provenance: ${await aspect.innerText()}`);\n''',
    )
    replace_once(
        "apps/studio/scripts/capture-video-output-preview.mjs",
        '''  const mobileAspectBox = await mobileAspect.boundingBox();\n  if (!mobileAspectBox || mobileAspectBox.x < 0 || mobileAspectBox.x + mobileAspectBox.width > 390) throw new Error(`Mobile Aspect control is clipped: ${JSON.stringify(mobileAspectBox)}`);\n  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });\n''',
        '''  const mobileAspectBox = await mobileAspect.boundingBox();\n  if (!mobileAspectBox || mobileAspectBox.x < 0 || mobileAspectBox.x + mobileAspectBox.width > 390) throw new Error(`Mobile Aspect control is clipped: ${JSON.stringify(mobileAspectBox)}`);\n  await mobileAspect.click();\n  const mobileAspectMenu = mobile.getByRole('menu', { name: 'Video aspect' });\n  await mobileAspectMenu.waitFor({ state: 'visible' });\n  const mobileMenuBox = await mobileAspectMenu.boundingBox();\n  if (!mobileMenuBox || mobileMenuBox.y < 0 || mobileMenuBox.y + mobileMenuBox.height > 844) throw new Error(`Mobile Aspect menu leaves the viewport: ${JSON.stringify(mobileMenuBox)}`);\n  await mobile.keyboard.press('Escape');\n  await mobile.screenshot({ path: path.join(outputDir, '05g-video-output-controls-mobile.png'), fullPage: true, animations: 'disabled' });\n''',
    )

    print("Iteration 7 professional-review refinement applied")


if __name__ == "__main__":
    main()
