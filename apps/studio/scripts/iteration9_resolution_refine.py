import iteration9_resolution_patch as base


def apply_refinement() -> None:
    base.apply_product()
    path = 'apps/studio/scripts/capture-ui-preview.mjs'
    base.replace_once(
        path,
        "  if (!/4K/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last resolution option');",
        "  if (!/3840 px/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('End did not focus the last resolution option');",
    )
    base.replace_once(
        path,
        "  if (!/SD/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first resolution option');",
        "  if (!/480 px/.test(await desktop.evaluate(() => document.activeElement?.innerText || ''))) throw new Error('Home did not focus the first resolution option');",
    )
    base.validate_source()
    print('Iteration 9 keyboard terminology refinement applied')


if __name__ == '__main__':
    apply_refinement()
